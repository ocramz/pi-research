"""Recompute every x06 verdict from a committed run directory: evidence files, gzipped event logs,
fetch.sh, the RPC captures and control_server.jsonl. No network. Prints whether each dataset verdict
and each session's C1/C3/C4 agree with summary.json.

    uv run python x06-open-data-access/recheck.py RUN_DIR"""

import json
import sys
from pathlib import Path

from epmlib.config import load_toml
from epmlib.jsonio import read_jsonl
from epmlib.pi.paths import PiPaths
from epmlib.xp import x06_open_data_access as x06


def main() -> int:
    run = Path(sys.argv[1]).resolve()
    cfg = x06.load(load_toml(run / "config.toml")[0])
    env = json.loads((run / "environment.json").read_text())
    summary = json.loads((run / "summary.json").read_text())
    records = {r["session"]: r for r in read_jsonl(run / "records.jsonl") if r["key"].startswith("session|")}
    server_log = read_jsonl(run / "control_server.jsonl")
    paths = PiPaths.discover(Path(__file__).resolve().parent)
    pins = {"DEFAULT_PI_PROVIDER": env["pins"]["DEFAULT_PI_PROVIDER"], "DEFAULT_PI_MODEL": env["pins"]["DEFAULT_PI_MODEL"]}
    feeds = {k: tuple(v) for k, v in env["feeds"].items()}
    checks = {s: x06.check_session(cfg, run / "sessions" / s, rec, paths, pins, env["pi_version"] == cfg.pi.pi_version,
                                   env["fetch_sh_sha256"], feeds, server_log) for s, rec in records.items()}
    verdicts = x06.dataset_verdicts(cfg, checks)
    ok = True
    for d, v in verdicts.items():
        same = v["verdict"] == summary["datasets"][d]["verdict"]
        ok &= same
        print(f"{d:12s} recheck {v['verdict']:15s} summary {summary['datasets'][d]['verdict']:15s} {'ok' if same else 'DIFFERS'}")
    for s, c in checks.items():
        got = (c["c1"]["ok"], c["c3"]["ok"], c["c4"]["ok"])
        want = (summary["sessions"][s]["C1"], summary["sessions"][s]["C3"], summary["sessions"][s]["C4"])
        ok &= got == want
        print(f"{s}: C1/C3/C4 recheck {got} summary {want} {'ok' if got == want else 'DIFFERS'}")
    print("recheck:", "all verdicts reproduce" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
