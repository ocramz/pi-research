"""Run machinery, in a throwaway git repository."""

import json
import subprocess
from pathlib import Path

import pytest

from epmlib.runlib import RefusedRun, RunArgs, git_state, open_run, parallel_map, utc_run_id

PREREG = """# x99-demo — pre-registration
<!-- registered config: config.toml -->
```toml
[experiment]
name = "x99-demo"
seed = 1

[run]
workers = 2
```
"""
CONFIG = '[experiment]\nname = "x99-demo"\nseed = 1\n\n[run]\nworkers = 2\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    exp = root / "experiments" / "x99-demo"
    exp.mkdir(parents=True)
    (exp / "PREREG.md").write_text(PREREG)
    (exp / "config.toml").write_text(CONFIG)
    (root / "experiments" / "uv.lock").write_text("lock\n")
    (root / ".gitignore").write_text("results/\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return exp


def _args(exp: Path, out: Path, **kw) -> RunArgs:
    base = dict(config=exp / "config.toml", out=out, resume=None, workers=None, allow_dirty=False)
    base.update(kw)
    return RunArgs(**base)


def test_registered_run_writes_manifest_and_config_copy(repo):
    ctx = open_run("x99-demo", repo, _args(repo, repo / "results"))
    m = json.loads((ctx.run_dir / "manifest.json").read_text())
    assert m["git_dirty"] is False and m["smoke"] is False and m["workers"] == 2
    assert len(m["git_commit"]) == 40 and m["uv_lock_sha256"] and m["config_sha256"]
    assert (ctx.run_dir / "config.toml").read_bytes() == (repo / "config.toml").read_bytes()
    ctx.append_record({"key": "b", "v": 2})
    ctx.append_record({"key": "a", "v": 1})
    assert [r["key"] for r in ctx.read_records()] == ["a", "b"]
    ctx.finish({"class": "x"})
    m = json.loads((ctx.run_dir / "manifest.json").read_text())
    assert m["status"] == "complete" and m["wall_seconds"] >= 0 and "git_dirty_end" in m


def test_dirty_tree_is_refused_unless_smoke_outside_repo(repo, tmp_path):
    (repo / "stray.txt").write_text("x")
    with pytest.raises(RefusedRun, match="uncommitted"):
        open_run("x99-demo", repo, _args(repo, repo / "results"))
    with pytest.raises(RefusedRun, match="outside the repository"):
        open_run("x99-demo", repo, _args(repo, repo / "results", allow_dirty=True))
    ctx = open_run("x99-demo", repo, _args(repo, tmp_path / "smoke", allow_dirty=True))
    assert ctx.smoke and json.loads((ctx.run_dir / "manifest.json").read_text())["git_dirty"] is True


def test_config_drift_is_refused(repo, tmp_path):
    other = tmp_path / "other.toml"
    other.write_text(CONFIG.replace("workers = 2", "workers = 3"))
    with pytest.raises(RefusedRun, match="differs from the config registered"):
        open_run("x99-demo", repo, _args(repo, repo / "results", config=other))
    smoke = tmp_path / "smoke.toml"
    smoke.write_text(CONFIG.replace('seed = 1', 'seed = 1\nsmoke = true'))
    ctx = open_run("x99-demo", repo, _args(repo, tmp_path / "s", config=smoke))
    assert ctx.smoke


def test_resume_keeps_records_and_checks_config(repo, tmp_path):
    ctx = open_run("x99-demo", repo, _args(repo, repo / "results"))
    ctx.append_record({"key": "u1"})
    ctx.save_checkpoint("state", {"n": 1})
    again = open_run("x99-demo", repo, _args(repo, repo / "results", resume=ctx.run_id))
    assert again.run_dir == ctx.run_dir and again.done_keys() == {"u1"}
    assert again.load_checkpoint("state") == {"n": 1}
    assert len(again.manifest["resumes"]) == 1


def test_git_state_sees_worktree(repo, tmp_path):
    root = repo.parents[1]
    wt = tmp_path / "wt"
    _git(root, "worktree", "add", "-q", "--detach", str(wt))
    s = git_state(wt)
    assert s.is_worktree and s.main_root.resolve() == root.resolve() and not s.dirty


def test_run_id_format():
    assert len(utc_run_id()) == 16 and utc_run_id().endswith("Z")


def _square(x: int) -> int:
    return x * x


def test_parallel_map_does_not_depend_on_workers():
    one = dict(parallel_map(_square, range(8), workers=1))
    two = dict(parallel_map(_square, range(8), workers=2))
    assert one == two == {i: i * i for i in range(8)}
