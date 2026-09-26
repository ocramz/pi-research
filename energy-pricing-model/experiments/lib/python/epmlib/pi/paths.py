"""Where pi's pieces live. A worktree has no submodule, `.cache` or `.env`, so the harness takes them
from the main tree, after checking that the submodule there is clean and at the run commit's gitlink.
`tools/pidrive.py` comes from the code root: the committed copy."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUBMODULE = "pi-agent-experiments"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@dataclass(frozen=True)
class PiPaths:
    code_root: Path
    main_root: Path
    pidrive: Path
    with_versions: Path
    notebook_ext: Path
    websearch_ext: Path
    shim_dir: Path
    submodule_commit: str

    @classmethod
    def discover(cls, code_root: Path) -> PiPaths:
        top = Path(_git(code_root, "rev-parse", "--show-toplevel"))
        main_root = Path(_git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
        gitlink = _git(top, "ls-tree", "HEAD", SUBMODULE).split()[2]
        sub = main_root / SUBMODULE
        head = _git(sub, "rev-parse", "HEAD")
        if head != gitlink:
            raise RuntimeError(f"{sub} is at {head}, not the run commit's gitlink {gitlink}")
        if _git(sub, "status", "--porcelain"):
            raise RuntimeError(f"{sub} has uncommitted changes")
        return cls(code_root=top, main_root=main_root, pidrive=top / "tools" / "pidrive.py",
                   with_versions=sub / "shared" / "with-versions.sh", notebook_ext=(sub / "pi-notebook-py").resolve(),
                   websearch_ext=(sub / "pi-web-search").resolve(), shim_dir=main_root / ".cache" / "python-shim",
                   submodule_commit=head)

    def versions_env(self) -> dict[str, str]:
        out = {}
        for line in (self.with_versions.parent / "versions.env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
        return out


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
