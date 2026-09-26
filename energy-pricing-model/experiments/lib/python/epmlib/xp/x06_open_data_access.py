"""x06-open-data-access: can the pi agent (pi-notebook-py and pi-web-search only) fetch keyless
samples of the companion note's Tier-1 datasets? Verdicts come only from saved evidence.

Registered in PREREG.md (f787c4a). Run it with the API keys exported (`set -a; . ./.env; set +a`)."""

from __future__ import annotations

import datetime as dt
import json
import os
import string
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import jsonio
from ..config import build, section
from ..outcomes import Rule, first_match, otherwise
from ..runlib import RunStatus, open_run, parse_args
from ..pi.audit import check_c1, check_c2, isolation_snapshot, tool_arg_texts
from ..pi.control_server import ControlServer
from ..pi.events import curl_writeouts, events_cost, iter_events, tool_calls
from ..pi.evidence import DatasetSpec, agent_outcomes, judge_dataset
from ..pi.paths import PiPaths, sha256_file
from ..pi.secrets import scan_tree
from ..pi.session import SessionSpec, run_session

EXPERIMENT = "x06-open-data-access"
SOURCE_IDS = ("elexon", "neso-demand", "feed-a", "neso-ews", "pvlive", "feed-b", "om-era5", "om-hfc")


@dataclass(frozen=True)
class PiCfg:
    pi_version: str
    thinking: str
    expected_commands: tuple[str, ...]
    notebook_commands: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    workdir_root: str


@dataclass(frozen=True)
class Sessions:
    count: int
    concurrent: int
    stagger_s: float
    max_seconds: float
    budget_usd: float
    search_limit_prompt: int
    search_hard_cap: int
    attempts_per_source: int
    max_followups: int
    min_valid_sessions: int
    refutation_sessions: int
    send_prompt: bool = True  # smoke only: false starts pi and runs the pre-check without a prompt
    prompt_file: str = "prompt.txt"  # smoke only


@dataclass(frozen=True)
class Controls:
    feed_rows: int
    feed_date: str


@dataclass(frozen=True)
class RunCfg:
    workers: int
    wall_cap_s: float


@dataclass(frozen=True)
class Config:
    seed: int
    pi: PiCfg
    sessions: Sessions
    controls: Controls
    datasets: tuple[DatasetSpec, ...]
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    return Config(seed=int(section(data, "experiment")["seed"]), pi=build(PiCfg, section(data, "pi"), where="pi"),
                  sessions=build(Sessions, section(data, "sessions"), where="sessions"),
                  controls=build(Controls, section(data, "controls"), where="controls"),
                  datasets=tuple(build(DatasetSpec, d, where="datasets") for d in data["datasets"]),
                  run=build(RunCfg, section(data, "run"), where="run"))


def feed_specs(cfg: Config) -> dict[str, DatasetSpec]:
    return {f: DatasetSpec(f, "127.0.0.1", "none", 30, cfg.controls.feed_date, cfg.controls.feed_rows - 2)
            for f in ("feed-a", "feed-b")}


def pi_version(env: dict[str, str]) -> str:
    binary = env.get("PI_BIN", "pi")
    r = subprocess.run([binary, "--version"], capture_output=True, text=True, env=env, timeout=60)
    return (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else ""


def check_session(cfg: Config, sdir: Path, rec: dict[str, Any], paths: PiPaths, pins: dict[str, str], version_ok: bool,
                  fetch_sha: str, feeds: dict[str, Any], server_log: list[dict]) -> dict[str, Any]:
    """Every check for one session, from its committed files (and the server log)."""
    ev_path = sdir / "drive" / "events.jsonl.gz"
    events = list(iter_events(ev_path)) if ev_path.exists() else []
    calls = tool_calls(events)
    writeouts = curl_writeouts(calls)
    fetch_ok = sha256_file(sdir / "fetch.sh") == fetch_sha
    rpc = {k: json.loads((sdir / "rpc" / f"{k}.json").read_text()) for k in ("get_commands", "get_state")
           if (sdir / "rpc" / f"{k}.json").exists()}
    stderr = (sdir / "drive" / "stderr.log").read_text(errors="replace") if (sdir / "drive" / "stderr.log").exists() else ""
    c1 = check_c1(get_commands=rpc.get("get_commands", {}), get_state=rpc.get("get_state", {}), events=events,
                  stderr_text=stderr, workdir=sdir, expected_commands=list(cfg.pi.expected_commands),
                  notebook_commands=list(cfg.pi.notebook_commands), notebook_ext=paths.notebook_ext,
                  provider=pins["DEFAULT_PI_PROVIDER"], model=pins["DEFAULT_PI_MODEL"], thinking=cfg.pi.thinking,
                  pi_version_ok=version_ok, allowed_tools=list(cfg.pi.allowed_tools))
    c1["no_stories_db"] = c1["no_stories_db"] and not rec.get("stories_db", False)
    c1["ok"] = c1["ok"] and c1["no_stories_db"]
    specs = {d.id: d for d in cfg.datasets} | feed_specs(cfg)
    judged = {sid: judge_dataset(sdir, spec, writeouts, fetch_ok) for sid, spec in specs.items()}
    ev_json = sdir / "evidence.json"
    outcomes = agent_outcomes(json.loads(ev_json.read_text())) if ev_json.exists() else {}
    name = rec["session"]
    a, b = feeds.get(name, (None, None))
    log_a = [e for e in server_log if e["session"] == name and e["feed"] == "a"]
    log_b = [e for e in server_log if e["session"] == name and e["feed"] == "b"]
    a_witness = any(x["verdict"] == "witness" and x["body_sha256"] == (a or {}).get("sha256")
                    and x["best_series"]["distinct"] == cfg.controls.feed_rows for x in judged["feed-a"]["attempts"])
    c3 = {"server_200": any(e["status"] == 200 for e in log_a), "witness_sha": a_witness,
          "agent_retrieved": outcomes.get("feed-a") == "retrieved"}
    c3["ok"] = all(c3.values())
    c4 = {"server_401": any(e["status"] == 401 for e in log_b),
          "no_authorization": not any(e["authorization"] for e in log_b),
          "agent_not_retrieved": outcomes.get("feed-b") != "retrieved",
          "no_witness": not judged["feed-b"]["witness"]}
    c4["ok"] = all(c4.values())
    accuracy = {sid: {"agent": outcomes.get(sid), "witness": judged[sid]["witness"], "refuted": judged[sid]["refuted"]}
                for sid in SOURCE_IDS}
    return {"c1": c1, "c3": c3, "c4": c4, "datasets": judged, "accuracy": accuracy, "cost_usd": events_cost(events),
            "tool_args": tool_arg_texts(events), "writeouts": len(writeouts), "fetch_sh_unchanged": fetch_ok}


def dataset_verdicts(cfg: Config, checks: dict[str, dict]) -> dict[str, dict[str, Any]]:
    valid = [s for s, c in checks.items() if c["c3"]["ok"] and c["c4"]["ok"]]
    out = {}
    for d in cfg.datasets:
        witnesses = [s for s, c in checks.items() if c["datasets"][d.id]["witness"]]
        refuting = [s for s in valid if checks[s]["datasets"][d.id]["refuted"]]
        if witnesses:
            verdict = "accessible"
        elif len(refuting) >= cfg.sessions.refutation_sessions:
            verdict = "not_as_claimed"
        else:
            verdict = "inconclusive"
        out[d.id] = {"verdict": verdict, "witness_sessions": witnesses, "refuting_sessions": refuting}
    return out


def summarise(cfg: Config, records: list[dict], checks: dict[str, dict], c2: dict, version: str,
              secret_hits: list[str]) -> dict[str, Any]:
    verdicts = dataset_verdicts(cfg, checks)
    c1_all = all(c["c1"]["ok"] for c in checks.values()) and len(checks) == cfg.sessions.count
    feed_b_witness = any(c["datasets"]["feed-b"]["witness"] for c in checks.values())
    c3c4 = sum(1 for c in checks.values() if c["c3"]["ok"] and c["c4"]["ok"])
    valid = c1_all and c2["ok"] and not feed_b_witness and c3c4 >= cfg.sessions.min_valid_sessions
    n_acc = sum(1 for v in verdicts.values() if v["verdict"] == "accessible")
    n_ref = sum(1 for v in verdicts.values() if v["verdict"] == "not_as_claimed")
    costs = [c["cost_usd"] for c in checks.values()]  # deviation 1: from the event log
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "valid": valid,
        "validity": {"C1_all_sessions": c1_all, "C2": c2["ok"], "feed_b_witness": feed_b_witness,
                     "sessions_passing_C3_C4": c3c4},
        "secrets_left_after_redaction": secret_hits,
        "pi_version": version,
        "datasets": verdicts,
        "n_accessible": n_acc,
        "n_refuted": n_ref,
        "sessions": {s: {"C1": c["c1"]["ok"], "C3": c["c3"]["ok"], "C4": c["c4"]["ok"],
                         "vacuous_web_search": c["c1"]["vacuous_web_search"], "searches": c["c1"]["searches"],
                         "tools_used": c["c1"]["tools_used"], "c1_detail": c["c1"], "c3": c["c3"], "c4": c["c4"],
                         "accuracy": c["accuracy"]} for s, c in checks.items()},
        "c2": c2,
        "cost": {"per_session": costs, "total": sum(costs), "median": sorted(costs)[len(costs) // 2] if costs else None},
        "sessions_run": len(records),
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


RULES: list[Rule[dict]] = [
    Rule("invalid", "the run fails the validity rule above", "debug, record a deviation, re-run",
         lambda s: not s["valid"]),
    Rule("access-claims-refuted", "at least 1 dataset is not as claimed", "G1: a corrected access table for the notes",
         lambda s: s["n_refuted"] >= 1),
    Rule("access-claims-confirmed", "all 6 datasets are accessible as claimed", "G1", lambda s: s["n_accessible"] == 6),
    Rule("access-claims-mostly-confirmed", "at least 4 are accessible, and none is refuted",
         "G1: options for the inconclusive datasets", lambda s: s["n_accessible"] >= 4 and s["n_refuted"] == 0),
    Rule("inconclusive", "otherwise", "G1: the limit is the instrument, pi at this budget", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started = time.monotonic()
    paths = PiPaths.discover(exp_dir)
    pins = paths.versions_env()
    secrets = {k: os.environ.get(k, "") for k in ("OPENROUTER_API_KEY", "TAVILY_API_KEY")}
    if not all(secrets.values()) and "PI_BIN" not in os.environ:
        raise SystemExit("export OPENROUTER_API_KEY and TAVILY_API_KEY first (set -a; . ./.env; set +a)")
    base_env = dict(os.environ)
    settings = Path.home() / ".pi" / "agent" / "settings.json"
    submodule = paths.main_root / "pi-agent-experiments"
    before = isolation_snapshot(paths.main_root, paths.code_root, submodule, settings)
    version = pi_version({**{k: v for k, v in base_env.items() if k in ("HOME", "PATH", "PI_BIN")}})
    version_ok = version == cfg.pi.pi_version
    fetch_bytes = (exp_dir / "fetch.sh").read_bytes()
    fetch_sha = sha256_file(exp_dir / "fetch.sh")
    prompt_t = (exp_dir / cfg.sessions.prompt_file).read_text()
    followup_t = (exp_dir / "followup.txt").read_text()
    cap_followup_t = (exp_dir / "cap_followup.txt").read_text().rstrip("\n")
    work_root = Path(os.path.expanduser(cfg.pi.workdir_root)) / ctx.run_id
    stop_flag = threading.Event()
    feeds: dict[str, Any] = {}
    records: list[dict] = []

    def precheck(rpc: dict) -> dict:
        cmds = (rpc.get("get_commands", {}).get("data") or {}).get("commands") or []
        names = sorted(c.get("name") for c in cmds)
        state = rpc.get("get_state", {}).get("data") or {}
        m = state.get("model") or {}
        base_dirs = {c.get("name"): (c.get("sourceInfo") or {}).get("baseDir") for c in cmds}
        detail = {"commands_exact": names == sorted(cfg.pi.expected_commands),
                  "notebook_base_dir": all(base_dirs.get(n) and Path(base_dirs[n]).resolve() == paths.notebook_ext
                                           for n in cfg.pi.notebook_commands),
                  "model": m.get("provider") == pins["DEFAULT_PI_PROVIDER"] and m.get("id") == pins["DEFAULT_PI_MODEL"],
                  "thinking": state.get("thinkingLevel") == cfg.pi.thinking, "pi_version": version_ok}
        detail["ok"] = all(detail.values())
        if not detail["ok"]:
            stop_flag.set()
        return detail

    with ControlServer(cfg.controls.feed_date, cfg.controls.feed_rows, cfg.seed) as server:
        specs = []
        for i in range(cfg.sessions.count):
            name = f"s{i + 1:02d}"
            a, b = server.add_session(i, name)
            feeds[name] = ({"token": a.token, "sha256": a.sha256}, {"token": b.token})
            prompt = string.Template(prompt_t).safe_substitute(port=server.port, token_a=a.token, token_b=b.token)
            specs.append(SessionSpec(i, name, work_root / name, ctx.run_dir / "sessions" / name, prompt.rstrip("\n"),
                                     followup_t, fetch_bytes, SOURCE_IDS, cfg.sessions.max_seconds,
                                     cfg.sessions.budget_usd, cfg.sessions.search_hard_cap, cfg.sessions.max_followups,
                                     cfg.pi.thinking, cap_followup_t, cfg.sessions.send_prompt))

        def launch(spec: SessionSpec) -> dict | None:
            if stop_flag.is_set():
                return None
            return run_session(spec, paths, base_env, secrets, on_precheck=precheck)

        with ThreadPoolExecutor(max_workers=cfg.sessions.concurrent) as pool:
            futures = []
            for k, spec in enumerate(specs):
                if k:
                    time.sleep(cfg.sessions.stagger_s)
                if stop_flag.is_set():
                    break
                futures.append(pool.submit(launch, spec))
            for f in futures:
                rec = f.result()
                if rec is not None:
                    records.append(rec)
                    ctx.append_record(rec)
        server_log = list(server.log)
    after = isolation_snapshot(paths.main_root, paths.code_root, submodule, settings)
    for entry in server_log:
        jsonio.append_jsonl(ctx.run_dir / "control_server.jsonl", entry)
    env_info = {"pi_version": version, "pins": {k: pins.get(k) for k in ("DEFAULT_PI_PROVIDER", "DEFAULT_PI_MODEL",
                                                                          "DEFAULT_PI_VERSION")},
                "submodule_commit": paths.submodule_commit, "settings_sha256": sha256_file(settings),
                "models_store_sha256": sha256_file(Path.home() / ".pi" / "agent" / "models-store.json"),
                "fetch_sh_sha256": fetch_sha, "feeds": feeds, "utc": dt.datetime.now(dt.UTC).isoformat()}
    jsonio.write_json(ctx.run_dir / "environment.json", env_info)
    checks = {}
    for rec in records:
        checks[rec["session"]] = check_session(cfg, ctx.run_dir / "sessions" / rec["session"], rec, paths, pins,
                                               version_ok, fetch_sha, feeds, server_log)
    run_rel = str(ctx.run_dir.relative_to(paths.main_root)) if ctx.run_dir.is_relative_to(paths.main_root) else "@@"
    c2 = check_c2(before, after, run_rel, [a for c in checks.values() for a in c["tool_args"]],
                  [str(paths.main_root), str(paths.code_root)])
    jsonio.write_json(ctx.run_dir / "checks.json", {s: {k: v for k, v in c.items() if k != "tool_args"}
                                                     for s, c in checks.items()})
    secret_hits = scan_tree(ctx.run_dir, secrets) if all(secrets.values()) else []
    summary = summarise(cfg, records, checks, c2, version, secret_hits)
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=None)
    print(f"{EXPERIMENT}: {summary['class']}; datasets: "
          f"{ {k: v['verdict'] for k, v in summary['datasets'].items()} }; valid={summary['valid']}; "
          f"cost ${summary['cost']['total']:.3f}; wall {time.monotonic() - started:.0f}s; run {ctx.run_dir}")
    return 0
