"""The note's §5 pricing layer: a logistic win model, expected profit and the optimal markup.

    P(p) = σ(β(p_ref − p)),   Π(p) = Q·P(p)·(p − ĉ),   p* solves p − ĉ = 1/(β(1 − P(p)))"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.special import expit


@dataclass(frozen=True)
class WinModel:
    beta: float
    p_ref: float

    def prob(self, p: float) -> float:
        return float(expit(self.beta * (self.p_ref - p)))

    def prob_lose(self, p: float) -> float:
        """1 − P(p), computed directly: no cancellation when P(p) rounds to 1."""
        return float(expit(self.beta * (p - self.p_ref)))


def profit(p: float, c_hat: float, win: WinModel, q: float) -> float:
    return q * win.prob(p) * (p - c_hat)


def profit_slope(p: float, c_hat: float, win: WinModel, q: float) -> float:
    """Π'(p) = Q·[P'(p)(p − ĉ) + P(p)], with P' = −βP(1 − P)."""
    pr = win.prob(p)
    return q * (-win.beta * pr * (1 - pr) * (p - c_hat) + pr)


def foc(p: float, c_hat: float, win: WinModel) -> float:
    """g(p) = p − ĉ − 1/(β(1 − P(p))): strictly increasing, with its root at p*."""
    return p - c_hat - 1.0 / (win.beta * win.prob_lose(p))


def optimal_price(c_hat: float, win: WinModel, *, tol: float = 1e-12, span: float = 100.0) -> float:
    """Bisection on g over [ĉ, ĉ + span]: g(ĉ) < 0 and g increases."""
    lo, hi = c_hat, c_hat + span
    if not (foc(lo, c_hat, win) < 0 < foc(hi, c_hat, win)):
        raise ValueError("the optimum is not bracketed")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if foc(mid, c_hat, win) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@dataclass(frozen=True)
class CostStack:
    """§7.4's illustrative stack, in £/MWh."""
    commodity: float
    network: float
    levies: float
    nu_bar: float
    matched_share: float
    phi: float
    sigma_cost: float

    @property
    def gross(self) -> float:
        return self.commodity + self.network + self.levies

    @property
    def credit(self) -> float:
        return self.nu_bar * self.matched_share

    @property
    def loading(self) -> float:
        return self.phi * self.sigma_cost

    def c_hat(self, *, with_match: bool) -> float:
        return self.gross - (self.credit if with_match else 0.0) + self.loading

    def pass_through_cap(self, gamma: float) -> float:
        """p ≤ F + n + ℓ + φσ − γ·ν̄·s̄."""
        return self.gross + self.loading - gamma * self.credit


def markup_sign_rule(c_hat: float, win: WinModel) -> float:
    """β·P*·(p_ref − p*) − 1: its sign is the sign of ∂m*/∂β (theory note §2.5)."""
    p = optimal_price(c_hat, win)
    return win.beta * win.prob(p) * (win.p_ref - p) - 1.0


def second_order_loss_at_optimum(c_hat: float, win: WinModel) -> float:
    """½β²(1 − P*): relative loss per σ² from mean-zero jitter at p* (theory note §2.4)."""
    p = optimal_price(c_hat, win)
    return 0.5 * win.beta ** 2 * win.prob_lose(p)


assert math.isclose(expit(0.0), 0.5)
