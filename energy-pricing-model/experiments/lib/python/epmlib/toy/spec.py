"""Toy model v1: constants, parameters and the named configs of `plans/toy_v1_spec.md` (26abb27)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

SEED = 20260926
DAYS = 365
PER_DAY = 48
T = DAYS * PER_DAY
HOURS_PER_YEAR = 8760.0
HH_HOURS = 0.5

SOLAR_CF = 0.117
WIND_CF = 0.30
SOLAR_MWH_PER_MW = SOLAR_CF * HOURS_PER_YEAR  # 1,024.92
SITE_MWH = 250.0
P71_MWH = 7800.0
P72_SOLAR_MW = 6.0

KAPPA = 2.5
LAM = 45.0
PREMIUM = 10.0
NU_BAR = LAM - PREMIUM

GH_NODES = 64


class Entity:
    """Stream keys: `SeedSequence([SEED, s, entity])` for scenario s."""
    CLOUD = 1
    WIND = 2
    COMMON = 3
    SITE = 1000  # site i uses 1000 + i
    PROSPECT = 900000  # the prospect of archetype a uses 900000 + index(a)
    SHUFFLE = 7  # book order "shuffled": SeedSequence([SEED, 7, block])


class Archetype(StrEnum):
    OFFICE = "office"
    ALWAYS_ON = "24/7"
    EVENING = "evening"

    @property
    def index(self) -> int:
        return ARCHETYPES.index(self)


ARCHETYPES = (Archetype.OFFICE, Archetype.ALWAYS_ON, Archetype.EVENING)


class Pool(StrEnum):
    P71 = "P71"  # 7,800 MWh/yr, solar share theta_s by energy
    P72 = "P72"  # 6 MW solar only


@dataclass(frozen=True)
class ToyParams:
    theta_s: float = 0.5
    s_c: float = 1.5
    s_w: float = 1.2
    a_w: float = 0.0
    b_o: float = 0.35
    a_f: float = 0.10
    e_m: float = 0.45
    s_i: float = 0.15
    s_cm: float = 0.05
    rho_dg: float = 0.0
    clear_sky: str = "halfsine"  # or "astro"
    book_order: str = "round_robin"  # or "shuffled"
    phi_c: float = 0.95
    phi_w: float = 0.99
    phi_i: float = 0.9
    phi_cm: float = 0.99
    generation: str = "stochastic"  # or "mean": G fixed at its expected shape (x02 only)

    def with_(self, **changes: object) -> ToyParams:
        return dataclasses.replace(self, **changes)


BASE = ToyParams()

OAT_CELLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("theta_s=0.25", {"theta_s": 0.25}), ("theta_s=0.75", {"theta_s": 0.75}),
    ("s_c=1.0", {"s_c": 1.0}), ("s_c=2.0", {"s_c": 2.0}),
    ("s_w=0.8", {"s_w": 0.8}), ("s_w=1.6", {"s_w": 1.6}),
    ("a_w=0.4", {"a_w": 0.4}),
    ("b_o=0.2", {"b_o": 0.2}), ("b_o=0.5", {"b_o": 0.5}),
    ("a_f=0", {"a_f": 0.0}), ("a_f=0.25", {"a_f": 0.25}),
    ("e_m=0.25", {"e_m": 0.25}), ("e_m=0.65", {"e_m": 0.65}),
    ("s_i=0.05", {"s_i": 0.05}), ("s_i=0.30", {"s_i": 0.30}),
    ("s_cm=0", {"s_cm": 0.0}), ("s_cm=0.10", {"s_cm": 0.10}),
    ("rho_dg=-0.3", {"rho_dg": -0.3}), ("rho_dg=0.3", {"rho_dg": 0.3}),
    ("clear_sky=astro", {"clear_sky": "astro"}),
    ("book_order=shuffled", {"book_order": "shuffled"}),
)

INVARIANCE_CELLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("phi_c=0.5", {"phi_c": 0.5}), ("phi_w=0.9", {"phi_w": 0.9}), ("phi_i=0.5", {"phi_i": 0.5}),
)

LHS_RANGES: tuple[tuple[str, float, float], ...] = (
    ("theta_s", 0.2, 0.8), ("s_c", 1.0, 2.0), ("s_w", 0.8, 1.6), ("a_w", 0.0, 0.4),
    ("b_o", 0.2, 0.5), ("a_f", 0.0, 0.25), ("e_m", 0.25, 0.65), ("s_i", 0.05, 0.3),
    ("s_cm", 0.0, 0.1), ("rho_dg", -0.3, 0.3),
)
LHS_N = 40


def oat_configs() -> list[tuple[str, ToyParams]]:
    return [(name, BASE.with_(**kw)) for name, kw in OAT_CELLS]


def invariance_configs() -> list[tuple[str, ToyParams]]:
    return [(name, BASE.with_(**kw)) for name, kw in INVARIANCE_CELLS]


def lhs_configs() -> list[tuple[str, ToyParams]]:
    """`LatinHypercube(d=10, seed=20260926).random(40)`, as registered. In scipy 1.18 `seed=` and
    `rng=` give different designs; the spec names `seed=`."""
    from scipy.stats import qmc
    u = qmc.LatinHypercube(d=len(LHS_RANGES), seed=SEED).random(LHS_N)
    out = []
    for j, row in enumerate(u):
        kw = {name: float(lo + x * (hi - lo)) for (name, lo, hi), x in zip(LHS_RANGES, row)}
        out.append((f"lhs-{j:02d}", BASE.with_(**kw)))
    return out


def named_config(name: str) -> ToyParams:
    if name == "base":
        return BASE
    for cells in (oat_configs(), invariance_configs(), lhs_configs()):
        for n, p in cells:
            if n == name:
                return p
    raise KeyError(name)


def seasonal(d: np.ndarray) -> np.ndarray:
    """S(d) = sin(2π(d − 79)/365)."""
    return np.sin(2 * np.pi * (d - 79) / 365)


def winter(d: np.ndarray) -> np.ndarray:
    """W(d) = cos(2π(d − 15)/365)."""
    return np.cos(2 * np.pi * (d - 15) / 365)
