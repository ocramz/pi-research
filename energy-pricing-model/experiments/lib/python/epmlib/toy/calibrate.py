"""Calibration (toy v1 §2–3): η for solar and μ_w for wind, by 64-point Gauss–Hermite quadrature
and brentq, and the analytic expected shapes they imply."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit

from .shapes import clear_sky, time_grid
from .spec import DAYS, GH_NODES, HH_HOURS, SOLAR_MWH_PER_MW, WIND_CF, ToyParams, winter


@lru_cache(maxsize=1)
def _gh() -> tuple[np.ndarray, np.ndarray]:
    """Nodes and weights for E f(Z), Z ~ N(0,1): Σ w_j f(z_j)."""
    x, w = np.polynomial.hermite.hermgauss(GH_NODES)
    return np.sqrt(2.0) * x, w / np.sqrt(np.pi)


@lru_cache(maxsize=16)
def _clear_sky_ro(kind: str) -> np.ndarray:
    c = clear_sky(kind)
    c.setflags(write=False)
    return c


def expected_solar_per_mw(eta: float, s_c: float, kind: str) -> np.ndarray:
    """E[min(1, η·c_t·k)]·0.5 MWh per half-hour per MW, with k = σ(s_c·Z)."""
    z, w = _gh()
    k = expit(s_c * z)  # (nodes,)
    c = _clear_sky_ro(kind)
    return HH_HOURS * (np.minimum(1.0, eta * c[:, None] * k[None, :]) @ w)


@lru_cache(maxsize=64)
def solar_eta(s_c: float, kind: str) -> float:
    def excess(eta: float) -> float:
        return float(expected_solar_per_mw(eta, s_c, kind).sum()) - SOLAR_MWH_PER_MW
    return float(brentq(excess, 1e-3, 50.0, xtol=1e-14, rtol=1e-14, maxiter=500))


def expected_wind_cf_by_day(mu: float, a_w: float, s_w: float) -> np.ndarray:
    z, w = _gh()
    d = np.arange(DAYS)
    return expit(mu + a_w * winter(d)[:, None] + s_w * z[None, :]) @ w


@lru_cache(maxsize=64)
def wind_mu(a_w: float, s_w: float) -> float:
    def excess(mu: float) -> float:
        return float(expected_wind_cf_by_day(mu, a_w, s_w).mean()) - WIND_CF
    return float(brentq(excess, -20.0, 20.0, xtol=1e-14, rtol=1e-14, maxiter=500))


def expected_wind_per_mw(p: ToyParams) -> np.ndarray:
    day, _, _, _ = time_grid()
    by_day = expected_wind_cf_by_day(wind_mu(p.a_w, p.s_w), p.a_w, p.s_w)
    return HH_HOURS * by_day[day]


def expected_solar(p: ToyParams) -> np.ndarray:
    return expected_solar_per_mw(solar_eta(p.s_c, p.clear_sky), p.s_c, p.clear_sky)
