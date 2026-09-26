"""Registered outcome tables. Each experiment lists its classes in PREREG order, `invalid` first;
the first rule whose test holds decides the class."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

S = TypeVar("S")


@dataclass(frozen=True)
class Rule(Generic[S]):
    cls: str
    condition: str  # the PREREG's wording, verbatim
    action: str
    test: Callable[[S], bool]


def first_match(rules: Sequence[Rule[S]], summary: S) -> Rule[S]:
    if not rules or rules[0].cls != "invalid":
        raise ValueError("an outcome table starts with `invalid`")
    for rule in rules:
        if rule.test(summary):
            return rule
    raise ValueError("no rule matched; the last rule of a registered table must be a catch-all")


def otherwise(_: object) -> bool:
    return True
