"""Configs: TOML in, frozen dataclasses out. Unknown or missing keys are errors, so a typo in a
config can never silently fall back to a default."""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def load_toml(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = Path(path).read_bytes()
    return tomllib.loads(raw.decode("utf-8")), raw


def build(cls: type[T], data: dict[str, Any], *, where: str) -> T:
    """`cls(**data)`, refusing keys the dataclass lacks and required fields the data lacks.
    Lists become tuples so the result stays hashable and frozen."""
    fields = {f.name: f for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    unknown = sorted(set(data) - set(fields))
    if unknown:
        raise ValueError(f"{where}: unknown keys {unknown}")
    missing = sorted(name for name, f in fields.items()
                     if name not in data and f.default is dataclasses.MISSING
                     and f.default_factory is dataclasses.MISSING)
    if missing:
        raise ValueError(f"{where}: missing keys {missing}")
    return cls(**{k: _freeze(v) for k, v in data.items()})


def _freeze(v: Any) -> Any:
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)
    return v


def section(data: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in data or not isinstance(data[name], dict):
        raise ValueError(f"config: missing table [{name}]")
    return data[name]
