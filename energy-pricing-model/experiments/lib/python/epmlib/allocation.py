"""The half-hour allocation LP of design note §3, solved by merit order, with the corrected dual
table of `plans/theory-rosso-claims.md` §2.1 and an exact primal-dual certificate.

    max Σ_{i,a} (λ − π_a)·m_ia   s.t.   Σ_a m_ia ≤ c_i  [ν_i],   Σ_i m_ia ≤ G_a  [μ_a],   m ≥ 0

Everything here is generic over the number type: pass `fractions.Fraction`s for exact arithmetic,
floats otherwise."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Any

Num = Any  # float or Fraction


class Regime(StrEnum):
    GENERATION_SCARCE = "generation-scarce"
    DEMAND_SCARCE = "demand-scarce"
    BALANCED = "balanced"


@dataclass(frozen=True)
class HHInstance:
    lam: Num
    cap_demand: tuple[Num, ...]  # c_i = min(D_i, κ)
    gen: tuple[Num, ...]  # G_a
    premium: tuple[Num, ...]  # π_a

    @property
    def n_customers(self) -> int:
        return len(self.cap_demand)

    @property
    def n_assets(self) -> int:
        return len(self.gen)

    def exact(self) -> HHInstance:
        """The same instance in exact rationals. Fraction(float) is exact."""
        f = Fraction
        return HHInstance(f(self.lam), tuple(map(f, self.cap_demand)), tuple(map(f, self.gen)),
                          tuple(map(f, self.premium)))


def merit_order(inst: HHInstance) -> list[int]:
    """Assets with π_a < λ, by ascending π; ties by index."""
    return sorted((a for a in range(inst.n_assets) if inst.premium[a] < inst.lam),
                  key=lambda a: (inst.premium[a], a))


def profitable_generation(inst: HHInstance) -> Num:
    return sum((inst.gen[a] for a in merit_order(inst)), inst.lam * 0)


def regime(inst: HHInstance) -> Regime:
    g_plus, c = profitable_generation(inst), sum(inst.cap_demand, inst.lam * 0)
    if g_plus < c:
        return Regime.GENERATION_SCARCE
    if g_plus > c:
        return Regime.DEMAND_SCARCE
    return Regime.BALANCED


def note_regime(inst: HHInstance) -> Regime:
    """The note's rule: all generation ΣG against C (S3)."""
    g, c = sum(inst.gen, inst.lam * 0), sum(inst.cap_demand, inst.lam * 0)
    if g < c:
        return Regime.GENERATION_SCARCE
    if g > c:
        return Regime.DEMAND_SCARCE
    return Regime.BALANCED


@dataclass(frozen=True)
class Solution:
    m: tuple[tuple[Num, ...], ...]  # customers × assets
    value: Num
    nu: tuple[Num, ...]
    mu: tuple[Num, ...]
    regime: Regime
    marginal: int | None  # k in the demand-scarce regime


def table_duals(inst: HHInstance) -> tuple[tuple[Num, ...], tuple[Num, ...], int | None]:
    """If G⁺ ≤ C: ν = 0 and μ_a = (λ − π_a)⁺. Otherwise k is the first asset in merit order at which
    cumulative profitable generation reaches C, ν_i = λ − π_k and μ_a = (π_k − π_a)⁺."""
    zero = inst.lam * 0
    c = sum(inst.cap_demand, zero)
    order = merit_order(inst)
    if profitable_generation(inst) <= c:
        mu = tuple(max(inst.lam - p, zero) for p in inst.premium)
        return tuple(zero for _ in inst.cap_demand), mu, None
    cum = zero
    for k in order:
        cum += inst.gen[k]
        if cum >= c:
            nu_k = inst.lam - inst.premium[k]
            mu = tuple(max(inst.premium[k] - p, zero) for p in inst.premium)
            return tuple(nu_k for _ in inst.cap_demand), mu, k
    raise AssertionError("unreachable: G⁺ > C implies some cumulative sum reaches C")


def greedy(inst: HHInstance) -> Solution:
    """Fill min(G⁺, C) from cheapest profitable assets upward, customers in index order."""
    zero = inst.lam * 0
    remaining_cap = list(inst.cap_demand)
    m = [[zero] * inst.n_assets for _ in range(inst.n_customers)]
    value = zero
    i = 0
    for a in merit_order(inst):
        left = inst.gen[a]
        while left > zero and i < inst.n_customers:
            take = min(left, remaining_cap[i])
            if take > zero:
                m[i][a] += take
                remaining_cap[i] -= take
                left -= take
                value += (inst.lam - inst.premium[a]) * take
            if remaining_cap[i] <= zero:
                i += 1
    nu, mu, k = table_duals(inst)
    return Solution(tuple(tuple(row) for row in m), value, nu, mu, regime(inst), k)


@dataclass(frozen=True)
class Certificate:
    primal_feasible: bool
    dual_feasible: bool
    primal_value: Num
    dual_value: Num

    @property
    def ok(self) -> bool:
        return self.primal_feasible and self.dual_feasible and self.primal_value == self.dual_value


def certify(inst: HHInstance, m: tuple[tuple[Num, ...], ...], nu: tuple[Num, ...], mu: tuple[Num, ...]
            ) -> Certificate:
    """Primal and dual feasibility and equal objectives. Exact when every input is a Fraction."""
    zero = inst.lam * 0
    primal = all(x >= zero for row in m for x in row)
    primal &= all(sum(m[i], zero) <= inst.cap_demand[i] for i in range(inst.n_customers))
    primal &= all(sum((m[i][a] for i in range(inst.n_customers)), zero) <= inst.gen[a]
                  for a in range(inst.n_assets))
    dual = all(v >= zero for v in nu) and all(v >= zero for v in mu)
    dual &= all(nu[i] + mu[a] >= inst.lam - inst.premium[a]
                for i in range(inst.n_customers) for a in range(inst.n_assets))
    pv = sum(((inst.lam - inst.premium[a]) * m[i][a] for i in range(inst.n_customers)
              for a in range(inst.n_assets)), zero)
    dv = sum((inst.cap_demand[i] * nu[i] for i in range(inst.n_customers)), zero) + \
        sum((inst.gen[a] * mu[a] for a in range(inst.n_assets)), zero)
    return Certificate(primal, dual, pv, dv)
