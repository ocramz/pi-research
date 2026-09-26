"""JSON helpers: deterministic dumps (sorted keys, no NaN), JSONL append and read, atomic writes."""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


def _default(o: object) -> Any:
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Fraction):
        return f"{o.numerator}/{o.denominator}"  # exact rationals, as "p/q"
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def dumps(obj: object, *, indent: int | None = None) -> str:
    """Sorted keys and no NaN or infinity: a value that may be undefined must be written as None."""
    return json.dumps(obj, sort_keys=True, allow_nan=False, default=_default, indent=indent,
                      ensure_ascii=False)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, obj: object) -> None:
    atomic_write(path, dumps(obj, indent=2) + "\n")


def append_jsonl(path: Path, obj: object) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(dumps(obj) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
