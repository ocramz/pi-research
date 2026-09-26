"""One x06 session, run by the registered procedure (PREREG, Method): fetch.sh and the prompt, `serve`,
the C1 pre-check, the prompt with a search monitor, at most one follow-up, stop, then copy, redact,
gzip and check."""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import signal
import string
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import iter_events, search_count
from .evidence import validate_evidence
from .paths import PiPaths
from .secrets import redact_tree

DIALOG = re.compile(r"dialog open: pidrive\.py ui \S+ (\S+)")
DRIVE_FILES = ("events.jsonl", "transcript.log", "stderr.log", "cmds.jsonl", "exit_code", "serve.out", "turn.json")


@dataclass(frozen=True)
class SessionSpec:
    index: int
    name: str
    work_root: Path  # ~/pi-work/energy-pricing-model/x06/<run-id>/sNN
    out_dir: Path  # results/<run-id>/sessions/sNN
    prompt: str
    followup_template: str
    fetch_sh: bytes
    source_ids: tuple[str, ...]  # the 8 sources in evidence.json
    max_seconds: float
    budget_usd: float
    search_hard_cap: int
    max_followups: int
    thinking: str
    cap_followup: str = ""  # deviation 1: the one follow-up when the search cap was reached
    send_prompt: bool = True


def pi_env(paths: PiPaths, spec: SessionSpec, base: dict[str, str]) -> dict[str, str]:
    """The registered allowlist; nothing else from the parent's environment reaches pi."""
    home = base["HOME"]
    env = {
        "HOME": home, "USER": base.get("USER", ""), "LOGNAME": base.get("LOGNAME", base.get("USER", "")),
        "SHELL": "/bin/bash", "LANG": "C.UTF-8", "TZ": "UTC", "TMPDIR": str(spec.work_root / "tmp"),
        "PATH": f"{paths.shim_dir}:{home}/.local/bin:/usr/local/bin:/usr/bin:/bin",
        "OPENROUTER_API_KEY": base.get("OPENROUTER_API_KEY", ""), "TAVILY_API_KEY": base.get("TAVILY_API_KEY", ""),
        "PI_NOTEBOOK_HOME": str(spec.work_root / "nbhome"), "PI_SKIP_VERSION_CHECK": "1",
    }
    if "PI_BIN" in base:  # tests and smoke checks with a stand-in pi only
        env["PI_BIN"] = base["PI_BIN"]
    for k in ("FAKE_PI_MODE", "FAKE_PI_NB_DIR"):
        if k in base:
            env[k] = base[k]
    return env


def pi_args(paths: PiPaths, spec: SessionSpec, drive: Path) -> list[str]:
    return ["--no-extensions", "-e", str(paths.notebook_ext), "-e", str(paths.websearch_ext), "--no-skills",
            "--no-prompt-templates", "--no-context-files", "--thinking", spec.thinking,
            "--session-dir", str(drive / "sessions")]


class Driver:
    def __init__(self, paths: PiPaths, drive: Path, env: dict[str, str]):
        self.paths, self.drive, self.env = paths, drive, env

    def run(self, *args: str, timeout: float) -> subprocess.CompletedProcess:
        return subprocess.run(["python3", str(self.paths.pidrive), *args], env=self.env, capture_output=True,
                              text=True, timeout=timeout)

    def cmd(self, obj: dict, timeout: float = 60) -> dict | None:
        r = self.run("cmd", str(self.drive), json.dumps(obj), "--timeout", str(timeout), timeout=timeout + 30)
        try:
            return json.loads(r.stdout)
        except ValueError:
            return None

    def alive(self) -> bool:
        return not (self.drive / "exit_code").exists()


def _turn(driver: Driver, first: list[str], deadline: float) -> dict[str, Any]:
    """Run send/ui/wait until pi settles, goes, or the deadline passes. Dialogs are cancelled."""
    log = []
    args = first
    while True:
        remaining = max(5.0, deadline - time.monotonic())
        try:
            r = driver.run(*args, "--timeout", f"{remaining:.0f}", timeout=remaining + 60)
            code, out = r.returncode, r.stdout
        except subprocess.TimeoutExpired:
            code, out = 124, ""
        log.append({"args": args[0], "exit": code})
        if code == 2:
            m = DIALOG.search(out)
            if m:
                args = ["ui", str(driver.drive), m.group(1), "--cancel"]
                continue
        if code == 124 and driver.alive() and time.monotonic() < deadline:
            args = ["wait", str(driver.drive)]
            continue
        return {"exit": code, "steps": log}


def _monitor(driver: Driver, cap: int, stop: threading.Event, fired: dict) -> None:
    """Deviation 1: at the cap, abort the current turn only (pi stays alive); abort again whenever a
    later search appears. Never stops pi."""
    events = driver.drive / "events.jsonl"
    aborted_at = 0
    fired.setdefault("aborts", 0)
    while not stop.is_set():
        if events.exists():
            try:
                n = search_count(list(iter_events(events)))
            except OSError:
                n = 0
            if n >= cap and n > aborted_at:
                aborted_at = n
                fired["done"] = True
                fired["searches"] = n
                fired["aborts"] += 1
                driver.cmd({"type": "abort"}, timeout=20)
        stop.wait(0.5)


def run_session(spec: SessionSpec, paths: PiPaths, base_env: dict[str, str], secrets: dict[str, str],
                on_precheck: Any = None) -> dict[str, Any]:
    t0 = time.monotonic()
    work, drive = spec.work_root / "work", spec.work_root / "drive"
    for d in (work, spec.work_root / "nbhome", spec.work_root / "tmp"):
        d.mkdir(parents=True, exist_ok=True)
    fetch = work / "fetch.sh"
    fetch.write_bytes(spec.fetch_sh)
    fetch.chmod(0o755)
    env = pi_env(paths, spec, base_env)
    driver = Driver(paths, drive, env)
    drive.mkdir(parents=True, exist_ok=True)
    serve_out = open(drive / "serve.out", "wb")
    serve = subprocess.Popen([str(paths.with_versions), "python3", str(paths.pidrive), "serve", str(drive), "--cwd",
                              str(work), "--max-seconds", str(spec.max_seconds), "--budget-usd", str(spec.budget_usd),
                              "--", *pi_args(paths, spec, drive)], env=env, stdout=serve_out,
                             stderr=subprocess.STDOUT, start_new_session=True)
    rec: dict[str, Any] = {"key": f"session|{spec.name}", "session": spec.name, "index": spec.index}
    rpc: dict[str, Any] = {}
    for kind in ("get_commands", "get_state", "get_available_thinking_levels"):
        rpc[kind] = driver.cmd({"type": kind}) or {}
    precheck = on_precheck(rpc) if on_precheck else {"ok": True}
    rec["precheck"] = precheck
    followups = 0
    followup_errors: list[list[str]] = []
    followup_kinds: list[str] = []
    turns = []
    monitor_state: dict[str, Any] = {}
    if precheck["ok"] and spec.send_prompt:
        stop_monitor = threading.Event()
        mon = threading.Thread(target=_monitor, args=(driver, spec.search_hard_cap, stop_monitor, monitor_state),
                               daemon=True)
        mon.start()
        deadline = t0 + spec.max_seconds + 30
        turns.append(_turn(driver, ["send", str(drive), spec.prompt], deadline))
        ev_path = work / "evidence.json"
        while followups < spec.max_followups and driver.alive():
            try:
                errors = validate_evidence(json.loads(ev_path.read_text()), list(spec.source_ids), work)
            except (OSError, ValueError):
                errors = ["evidence.json is missing or is not valid JSON"]
            if not errors:
                break
            events_now = drive / "events.jsonl"
            cap_hit = events_now.exists() and search_count(list(iter_events(events_now))) >= spec.search_hard_cap
            followup_errors.append(errors[:10])
            if cap_hit and spec.cap_followup:
                text = spec.cap_followup
            else:
                text = string.Template(spec.followup_template).safe_substitute(errors="; ".join(errors[:10]))
            followups += 1
            followup_kinds.append("cap" if cap_hit and spec.cap_followup else "registered")
            turns.append(_turn(driver, ["send", str(drive), text.rstrip("\n")], deadline))
        stop_monitor.set()
    rpc["get_session_stats"] = (driver.cmd({"type": "get_session_stats"}) or {}) if driver.alive() else {}
    if driver.alive():
        driver.run("stop", str(drive), timeout=90)
    try:
        os.killpg(serve.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        serve.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(serve.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        serve.wait()
    serve_out.close()
    rec.update({"turns": turns, "followups": followups, "followup_errors": followup_errors,
                "followup_kinds": followup_kinds, "search_monitor": monitor_state,
                "wall_seconds": round(time.monotonic() - t0, 1)})
    _copy(spec, work, drive, rpc)
    rec["redactions"] = redact_tree(spec.out_dir, secrets)
    _gzip(spec.out_dir / "drive")
    stats = (rpc.get("get_session_stats") or {}).get("data") or {}
    rec.update({"cost_usd": stats.get("cost"), "tokens": (stats.get("tokens") or {}).get("total"),
                "tool_calls": stats.get("toolCalls")})
    rec["stories_db"] = (work / ".pi" / "stories.db").exists()
    shutil.rmtree(spec.work_root / "nbhome", ignore_errors=True)
    return rec


def _copy(spec: SessionSpec, work: Path, drive: Path, rpc: dict[str, Any]) -> None:
    out = spec.out_dir
    out.mkdir(parents=True, exist_ok=True)
    if (work / "evidence.json").exists():
        shutil.copy2(work / "evidence.json", out / "evidence.json")
    if (work / "evidence").exists():
        shutil.copytree(work / "evidence", out / "evidence", dirs_exist_ok=True)
    shutil.copy2(work / "fetch.sh", out / "fetch.sh")
    nb = work / ".pi" / "notebooks"
    if nb.exists():
        shutil.copytree(nb, out / "notebooks", dirs_exist_ok=True)
    (out / "drive").mkdir(exist_ok=True)
    for name in DRIVE_FILES:
        if (drive / name).exists():
            shutil.copy2(drive / name, out / "drive" / name)
    if (drive / "sessions").exists():
        shutil.copytree(drive / "sessions", out / "drive" / "sessions", dirs_exist_ok=True)
    (out / "rpc").mkdir(exist_ok=True)
    for kind, resp in rpc.items():
        (out / "rpc" / f"{kind}.json").write_text(json.dumps(resp, indent=2, sort_keys=True) + "\n")
    lock = []
    for py in sorted((spec.work_root / "nbhome").rglob("bin/python")):
        r = subprocess.run(["uv", "pip", "freeze", "--python", str(py)], capture_output=True, text=True)
        lock.append(f"# {py.relative_to(spec.work_root)}\n{r.stdout}")
    (out / "nb_env_lock.txt").write_text("".join(lock) if lock else "# no notebook venv was built\n")


def _gzip(drive: Path) -> None:
    for path in [drive / "events.jsonl", *sorted((drive / "sessions").rglob("*.jsonl"))]:
        if path.exists():
            data = path.read_bytes()
            with open(str(path) + ".gz", "wb") as f:
                with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as g:
                    g.write(data)
            path.unlink()
