"""Run machinery shared by every experiment: CLI, run directory, manifest, records, checkpoints,
resume and workers.

A run writes `<out>/<UTC run-id>/`: `manifest.json`, `config.toml` (a byte copy), `records.jsonl`
(one record per unit, keyed), `summary.json` and `checkpoints/`.

Registered runs need a clean tree and the PREREG's registered config. Smoke runs (a config with
`smoke = true`, or `--allow-dirty`) must write outside the repository, so an unregistered result can
never land in `results/`."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import multiprocessing
import os
import platform
import resource
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

from . import jsonio
from .config import load_toml
from .registered import registered_config

T = TypeVar("T")
R = TypeVar("R")

BLAS_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class RefusedRun(RuntimeError):
    """The run would not be a registered run, or not an honest smoke run."""


@dataclass(frozen=True)
class RunArgs:
    config: Path
    out: Path
    resume: str | None
    workers: int | None
    allow_dirty: bool


def parse_args(argv: list[str] | None, *, exp_dir: Path, description: str) -> RunArgs:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--config", type=Path, default=exp_dir / "config.toml")
    p.add_argument("--out", type=Path, default=exp_dir / "results")
    p.add_argument("--resume", metavar="RUN_ID", help="continue this run's directory")
    p.add_argument("--workers", type=int, help="default: the config's [run] workers")
    p.add_argument("--allow-dirty", action="store_true",
                   help="smoke only: allow uncommitted changes; --out must be outside the repository")
    a = p.parse_args(argv)
    return RunArgs(a.config.resolve(), a.out.resolve(), a.resume, a.workers, a.allow_dirty)


@dataclass(frozen=True)
class GitState:
    commit: str
    dirty: bool
    porcelain: tuple[str, ...]
    toplevel: Path
    main_root: Path
    is_worktree: bool


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def git_state(path: Path) -> GitState:
    top = Path(_git(path, "rev-parse", "--show-toplevel"))
    porcelain = tuple(line for line in _git(top, "status", "--porcelain=v1", "--untracked-files=all")
                      .splitlines() if line)
    main_root = Path(_git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    return GitState(commit=_git(top, "rev-parse", "HEAD"), dirty=bool(porcelain), porcelain=porcelain,
                    toplevel=top, main_root=main_root, is_worktree=top.resolve() != main_root.resolve())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _meminfo_total() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return None


def _cpu_description() -> dict[str, Any]:
    info: dict[str, Any] = {"count": os.cpu_count(), "processor": platform.processor() or None}
    try:
        fields: dict[str, str] = {}
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if ":" in line:
                k, v = (s.strip() for s in line.split(":", 1))
                fields.setdefault(k, v)
        for k in ("model name", "CPU implementer", "CPU part", "Features"):
            if k in fields:
                info[k.replace(" ", "_").lower()] = fields[k]
    except OSError:
        pass
    return info


def platform_info() -> dict[str, Any]:
    import numpy
    import scipy
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "cpu": _cpu_description(),
        "memory_bytes": _meminfo_total(),
    }


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_run_id(now: dt.datetime | None = None) -> str:
    return (now or dt.datetime.now(dt.UTC)).strftime("%Y%m%dT%H%M%SZ")


def _cpu_seconds() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + kids.ru_utime + kids.ru_stime


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class RunContext:
    def __init__(self, run_dir: Path, manifest: dict[str, Any], config: dict[str, Any], workers: int):
        self.run_dir = run_dir
        self.run_id = run_dir.name
        self.manifest = manifest
        self.config = config
        self.workers = workers
        self.smoke: bool = manifest["smoke"]
        self._records = run_dir / "records.jsonl"
        self._started = time.monotonic()

    def append_record(self, record: dict[str, Any]) -> None:
        if "key" not in record:
            raise ValueError("a record needs a unique 'key'")
        jsonio.append_jsonl(self._records, record)

    def done_keys(self) -> frozenset[str]:
        return frozenset(r["key"] for r in jsonio.read_jsonl(self._records))

    def read_records(self) -> list[dict[str, Any]]:
        rows = jsonio.read_jsonl(self._records)
        keys = [r["key"] for r in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate record keys in records.jsonl")
        return sorted(rows, key=lambda r: r["key"])

    def save_checkpoint(self, name: str, state: object) -> None:
        jsonio.write_json(self.run_dir / "checkpoints" / f"{name}.json", state)

    def load_checkpoint(self, name: str) -> Any:
        path = self.run_dir / "checkpoints" / f"{name}.json"
        if not path.exists():
            return None
        import json
        return json.loads(path.read_text(encoding="utf-8"))

    def write_artifact(self, name: str, obj: object) -> None:
        jsonio.write_json(self.run_dir / name, obj)

    def finish(self, summary: dict[str, Any], status: RunStatus = RunStatus.COMPLETE, *,
               unit_cpu_seconds: float | None = None) -> None:
        """`cpu_seconds` is this process's (and its waited children's); forkserver workers are not its
        children, so experiments also report `unit_cpu_seconds`, measured inside each unit."""
        jsonio.write_json(self.run_dir / "summary.json", summary)
        state = git_state(Path(self.manifest["code_root"]))
        self.manifest.update({
            "status": status.value,
            "finished_utc": utc_now(),
            "wall_seconds": round(self.manifest.get("wall_seconds_before", 0.0)
                                  + time.monotonic() - self._started, 3),
            "cpu_seconds": round(_cpu_seconds(), 3),
            "unit_cpu_seconds": None if unit_cpu_seconds is None else round(unit_cpu_seconds, 3),
            "git_dirty_end": state.dirty,
            "git_commit_end": state.commit,
        })
        self.manifest.pop("wall_seconds_before", None)
        jsonio.write_json(self.run_dir / "manifest.json", self.manifest)


def open_run(experiment: str, exp_dir: Path, args: RunArgs, *,
             extra: dict[str, Any] | None = None, state: GitState | None = None) -> RunContext:
    """Check that this is an honest run, then create (or reopen, with --resume) its directory."""
    config, raw = load_toml(args.config)
    state = state or git_state(exp_dir)
    smoke_config = bool(config.get("experiment", {}).get("smoke", False))
    smoke = smoke_config or args.allow_dirty
    if smoke:
        if _inside(args.out, state.toplevel) or _inside(args.out, state.main_root):
            raise RefusedRun("a smoke run must write outside the repository (use the scratchpad)")
    else:
        if state.dirty:
            raise RefusedRun("uncommitted changes: run from a clean worktree of the implementation "
                             "commit, or pass --allow-dirty for a smoke run outside the repository:\n  "
                             + "\n  ".join(state.porcelain[:20]))
        if config != registered_config(exp_dir):
            raise RefusedRun(f"{args.config} differs from the config registered in PREREG.md; "
                             "a change needs a deviation")
    if config.get("experiment", {}).get("name") != experiment:
        raise RefusedRun(f"config names {config.get('experiment', {}).get('name')!r}, not {experiment!r}")
    workers = args.workers or int(config.get("run", {}).get("workers", 1))
    seed = config.get("experiment", {}).get("seed")
    uv_lock = exp_dir.parent / "uv.lock"

    if args.resume:
        run_dir = args.out / args.resume
        manifest = jsonio_load(run_dir / "manifest.json")
        if manifest["config_sha256"] != hashlib.sha256(raw).hexdigest():
            raise RefusedRun("--resume: the config differs from the run's")
        if manifest["git_commit"] != state.commit:
            raise RefusedRun("--resume: HEAD differs from the run's commit")
        manifest.setdefault("resumes", []).append({"started_utc": utc_now(), "argv": sys.argv,
                                                   "workers": workers})
        manifest["wall_seconds_before"] = manifest.get("wall_seconds", 0.0)
        manifest["status"] = RunStatus.RUNNING.value
        jsonio.write_json(run_dir / "manifest.json", manifest)
        return RunContext(run_dir, manifest, config, workers)

    args.out.mkdir(parents=True, exist_ok=True)
    while True:
        run_dir = args.out / utc_run_id()
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            time.sleep(1.0)
    (run_dir / "config.toml").write_bytes(raw)
    manifest = {
        "experiment": experiment,
        "run_id": run_dir.name,
        "status": RunStatus.RUNNING.value,
        "smoke": smoke,
        "git_commit": state.commit,
        "git_dirty": state.dirty,
        "porcelain": list(state.porcelain),
        "code_root": str(state.toplevel),
        "main_root": str(state.main_root),
        "worktree": state.is_worktree,
        "uv_lock_sha256": sha256_file(uv_lock) if uv_lock.exists() else None,
        "config_path": str(args.config),
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "argv": sys.argv,
        "workers": workers,
        "seed": seed,
        "blas_threads": {v: os.environ.get(v) for v in BLAS_VARS},
        "started_utc": utc_now(),
        "resumes": [],
        **platform_info(),
        "extra": extra or {},
    }
    jsonio.write_json(run_dir / "manifest.json", manifest)
    return RunContext(run_dir, manifest, config, workers)


def jsonio_load(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def pin_blas_threads() -> None:
    """One BLAS thread per process: results must not depend on --workers."""
    for v in BLAS_VARS:
        os.environ[v] = "1"


def parallel_map(fn: Callable[[T], R], items: Iterable[T], *, workers: int) -> Iterator[tuple[T, R]]:
    """Yield (item, fn(item)) as each finishes. Workers start from a forkserver, so they inherit no
    threads, with BLAS pinned to one thread."""
    items = list(items)
    if workers <= 1 or len(items) <= 1:
        for item in items:
            yield item, fn(item)
        return
    pin_blas_threads()
    ctx = multiprocessing.get_context("forkserver")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        futures = {ex.submit(fn, item): item for item in items}
        for fut in as_completed(futures):
            yield futures[fut], fut.result()
