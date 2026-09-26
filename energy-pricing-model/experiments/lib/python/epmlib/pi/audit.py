"""x06 controls C1 (extension set, per session) and C2 (isolation, per run)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .events import extension_errors, search_count, tool_calls
from .paths import sha256_file

STDERR_EXT_ERROR = re.compile(r"(?i)extension.{0,80}(error|failed)|(error|failed).{0,80}extension")


def check_c1(*, get_commands: dict, get_state: dict, events: list[dict], stderr_text: str, workdir: Path,
             expected_commands: list[str], notebook_commands: list[str], notebook_ext: Path, provider: str,
             model: str, thinking: str, pi_version_ok: bool, allowed_tools: list[str]) -> dict[str, Any]:
    cmds = (get_commands.get("data") or {}).get("commands") or []
    names = sorted(c.get("name") for c in cmds)
    base_dirs = {c.get("name"): (c.get("sourceInfo") or {}).get("baseDir") for c in cmds}
    nb_paths_ok = all(base_dirs.get(n) and Path(base_dirs[n]).resolve() == notebook_ext.resolve()
                      for n in notebook_commands)
    state = get_state.get("data") or {}
    m = state.get("model") or {}
    calls = tool_calls(events)
    used = sorted({c["name"] for c in calls if c.get("name")})
    detail = {
        "commands_exact": names == sorted(expected_commands),
        "commands": names,
        "notebook_base_dir": nb_paths_ok,
        "model": m.get("provider") == provider and m.get("id") == model,
        "thinking": state.get("thinkingLevel") == thinking,
        "pi_version": pi_version_ok,
        "no_extension_error_events": not extension_errors(events),
        "no_extension_error_stderr": not STDERR_EXT_ERROR.search(stderr_text or ""),
        "allowed_tools_only": all(t in allowed_tools for t in used),
        "tools_used": used,
        "no_stories_db": not (workdir / ".pi" / "stories.db").exists(),
        "searches": search_count(events),
    }
    detail["vacuous_web_search"] = detail["searches"] == 0
    detail["ok"] = all(detail[k] for k in ("commands_exact", "notebook_base_dir", "model", "thinking", "pi_version",
                                           "no_extension_error_events", "no_extension_error_stderr",
                                           "allowed_tools_only", "no_stories_db"))
    return detail


def _status(path: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"],
                         capture_output=True, text=True, check=True).stdout
    return sorted(line for line in out.splitlines() if line)


def isolation_snapshot(main_root: Path, code_root: Path, submodule: Path, settings: Path) -> dict[str, Any]:
    head = subprocess.run(["git", "-C", str(submodule), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    return {"main_status": _status(main_root),
            "code_status": _status(code_root) if code_root.resolve() != main_root.resolve() else None,
            "submodule_head": head, "submodule_status": _status(submodule),
            "settings_sha256": sha256_file(settings)}


def check_c2(before: dict[str, Any], after: dict[str, Any], run_dir_rel: str, tool_args: list[str],
             forbidden: list[str]) -> dict[str, Any]:
    new_main = sorted(set(after["main_status"]) - set(before["main_status"]))
    outside = [line for line in new_main if run_dir_rel not in line]
    detail = {
        "main_tree_only_run_dir_added": not outside and set(before["main_status"]) <= set(after["main_status"]),
        "unexpected_main_changes": outside[:20],
        "code_tree_clean": before["code_status"] in (None, []) and after["code_status"] in (None, []),
        "submodule_unchanged": before["submodule_head"] == after["submodule_head"] and not after["submodule_status"],
        "settings_unchanged": before["settings_sha256"] == after["settings_sha256"],
        "no_repo_paths_in_tool_args": not any(f in a for a in tool_args for f in forbidden),
    }
    detail["ok"] = all(v for k, v in detail.items() if k != "unexpected_main_changes")
    return detail


def tool_arg_texts(events: list[dict]) -> list[str]:
    return [json.dumps(c.get("args"), ensure_ascii=False) for c in tool_calls(events)]
