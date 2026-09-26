"""The independent checker for the allocation LP: HiGHS dual simplex through `scipy.optimize.linprog`.
It shares no code with `allocation.py` beyond the instance type."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .allocation import HHInstance


@dataclass(frozen=True)
class LPResult:
    optimal: bool
    status: int
    message: str
    value: float
    m: np.ndarray  # customers × assets
    nu: np.ndarray
    mu: np.ndarray


def solve_hh_lp(inst: HHInstance, *, time_limit: float = 10.0) -> LPResult:
    n_c, n_a = inst.n_customers, inst.n_assets
    profit = np.array([float(inst.lam) - float(p) for p in inst.premium])
    c = -np.tile(profit, n_c)  # variable (i, a) at index i·n_a + a; minimise −profit
    a_ub = np.zeros((n_c + n_a, n_c * n_a))
    for i in range(n_c):
        a_ub[i, i * n_a:(i + 1) * n_a] = 1.0
    for a in range(n_a):
        a_ub[n_c + a, a::n_a] = 1.0
    b_ub = np.array([float(x) for x in inst.cap_demand] + [float(x) for x in inst.gen])
    res = linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=(0, None), method="highs-ds",
                  options={"time_limit": time_limit})
    if res.status != 0:
        nan = np.full(n_c + n_a, np.nan)
        return LPResult(False, int(res.status), str(res.message), float("nan"),
                        np.full((n_c, n_a), np.nan), nan[:n_c], nan[n_c:])
    duals = -np.asarray(res.ineqlin.marginals)
    return LPResult(True, 0, str(res.message), float(-res.fun), np.asarray(res.x).reshape(n_c, n_a),
                    duals[:n_c], duals[n_c:])


def max_matched_value(lam: float, premium: float, cap_demands: np.ndarray, gens: np.ndarray, *,
                      time_limit: float = 10.0) -> LPResult:
    """The per-site LP of toy v1 at one half-hour: customers are the sites (and any prospect), and the
    assets are the pool's parts, all at one premium."""
    inst = HHInstance(lam, tuple(float(x) for x in cap_demands), tuple(float(x) for x in gens),
                      tuple(premium for _ in gens))
    return solve_hh_lp(inst, time_limit=time_limit)
