"""What a PREREG registers verbatim: fenced blocks marked `<!-- registered config: NAME -->` or
`<!-- registered file: NAME -->`, and the order of the classes in its outcome table."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_BLOCK = re.compile(r"<!-- registered (config|file): (\S+) -->\n```[A-Za-z]*\n(.*?)\n```", re.S)
_CLASS_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def registered_blocks(prereg: str) -> dict[str, tuple[str, str]]:
    """{name: (kind, content)}. A name registered twice is an error."""
    out: dict[str, tuple[str, str]] = {}
    for kind, name, content in _BLOCK.findall(prereg):
        if name in out:
            raise ValueError(f"{name} is registered twice")
        out[name] = (kind, content + "\n")
    return out


def registered_config(exp_dir: Path) -> dict:
    blocks = registered_blocks((exp_dir / "PREREG.md").read_text(encoding="utf-8"))
    kind, content = blocks["config.toml"]
    if kind != "config":
        raise ValueError("config.toml must be registered as a config")
    return tomllib.loads(content)


def outcome_classes(prereg: str) -> list[str]:
    """Class names, in order, from the first table after `## Outcome classes`."""
    lines = prereg.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Outcome classes")
    except StopIteration:
        raise ValueError("no `## Outcome classes` section") from None
    classes: list[str] = []
    in_table = False
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            in_table = True
            m = _CLASS_ROW.match(line)
            if m:
                classes.append(m.group(1))
        elif in_table:
            break
    return classes
