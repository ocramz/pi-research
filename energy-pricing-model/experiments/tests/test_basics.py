"""jsonio, rng, config and outcomes."""

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import pytest

from epmlib import jsonio
from epmlib.config import build
from epmlib.outcomes import Rule, first_match, otherwise
from epmlib.rng import generator


def test_dumps_is_sorted_and_refuses_nan():
    assert jsonio.dumps({"b": 1, "a": np.int64(2), "c": np.float32(0.5), "d": Fraction(1, 3)}) == \
        '{"a": 2, "b": 1, "c": 0.5, "d": "1/3"}'
    with pytest.raises(ValueError):
        jsonio.dumps({"x": math.nan})
    with pytest.raises(TypeError):
        jsonio.dumps({"x": object()})


def test_jsonl_roundtrip_and_atomic_write(tmp_path):
    p = tmp_path / "r.jsonl"
    jsonio.append_jsonl(p, {"key": "a", "v": 1})
    jsonio.append_jsonl(p, {"key": "b", "v": [1, 2]})
    assert jsonio.read_jsonl(p) == [{"key": "a", "v": 1}, {"key": "b", "v": [1, 2]}]
    jsonio.write_json(tmp_path / "x" / "s.json", {"z": 1})
    assert (tmp_path / "x" / "s.json").read_text() == '{\n  "z": 1\n}\n'
    assert not [f for f in (tmp_path / "x").iterdir() if f.name.startswith(".")]


def test_streams_are_keyed_not_ordered():
    a1 = generator(20260926, 3, 1000).standard_normal(5)
    generator(20260926, 3, 1001).standard_normal(5)  # another stream in between changes nothing
    a2 = generator(20260926, 3, 1000).standard_normal(5)
    assert np.array_equal(a1, a2)
    assert not np.array_equal(a1, generator(20260926, 3, 1001).standard_normal(5))


@dataclass(frozen=True)
class _Cfg:
    a: int
    b: tuple[float, ...]
    c: str = "x"


def test_build_is_strict():
    assert build(_Cfg, {"a": 1, "b": [1.0, 2.0]}, where="t") == _Cfg(1, (1.0, 2.0), "x")
    with pytest.raises(ValueError, match="unknown"):
        build(_Cfg, {"a": 1, "b": [], "typo": 2}, where="t")
    with pytest.raises(ValueError, match="missing"):
        build(_Cfg, {"b": []}, where="t")


def test_first_match_order_and_invalid_first():
    rules = [Rule("invalid", "c0", "a0", lambda s: s["bad"]),
             Rule("high", "c1", "a1", lambda s: s["x"] > 1),
             Rule("inconclusive", "otherwise", "a2", otherwise)]
    assert first_match(rules, {"bad": True, "x": 5}).cls == "invalid"
    assert first_match(rules, {"bad": False, "x": 5}).cls == "high"
    assert first_match(rules, {"bad": False, "x": 0}).cls == "inconclusive"
    with pytest.raises(ValueError):
        first_match(rules[1:], {"bad": False, "x": 5})
