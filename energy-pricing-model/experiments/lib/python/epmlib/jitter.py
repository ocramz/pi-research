"""Expected margin lost to price jitter: L(p₀, σ) = 1 − E[Π(p₀ + ε)]/Π(p₀).

Designs: SYMMETRIC, ε ~ N(0, σ²); CAP_RESPECTING, ε = −σ|Z| (half-normal, never above p₀).
Three independent integrators: adaptive quadrature (primary), Gauss–Hermite (symmetric only) and
Monte Carlo (the checker)."""

from __future__ import annotations

import math
from enum import StrEnum

import numpy as np
from scipy import integrate
from scipy.special import expit

from .pricing import WinModel, profit


class Design(StrEnum):
    SYMMETRIC = "symmetric"
    CAP_RESPECTING = "cap-respecting"


def _profit_vec(p: np.ndarray, c_hat: float, win: WinModel, q: float) -> np.ndarray:
    return q * expit(win.beta * (win.p_ref - p)) * (p - c_hat)


def loss_quad(p0: float, c_hat: float, win: WinModel, q: float, sigma: float, design: Design) -> float:
    base = profit(p0, c_hat, win, q)
    if sigma == 0.0:
        return 0.0
    phi = lambda z: math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)  # noqa: E731
    if design is Design.SYMMETRIC:
        val, _ = integrate.quad(lambda z: profit(p0 + sigma * z, c_hat, win, q) * phi(z), -np.inf, np.inf,
                                epsabs=1e-12, epsrel=1e-12, limit=500)
    else:
        val, _ = integrate.quad(lambda z: 2.0 * profit(p0 - sigma * z, c_hat, win, q) * phi(z), 0.0, np.inf,
                                epsabs=1e-12, epsrel=1e-12, limit=500)
    return 1.0 - val / base


def loss_gauss_hermite(p0: float, c_hat: float, win: WinModel, q: float, sigma: float, nodes: int) -> float:
    """Symmetric design only."""
    x, w = np.polynomial.hermite.hermgauss(nodes)
    val = float(_profit_vec(p0 + sigma * math.sqrt(2.0) * x, c_hat, win, q) @ w / math.sqrt(math.pi))
    return 1.0 - val / profit(p0, c_hat, win, q)


def loss_monte_carlo(p0: float, c_hat: float, win: WinModel, q: float, sigma: float, design: Design,
                     z: np.ndarray) -> tuple[float, float]:
    """(loss, standard error) from standard normals z. Symmetric: antithetic pairs (z, −z)."""
    base = profit(p0, c_hat, win, q)
    if design is Design.SYMMETRIC:
        pairs = 0.5 * (_profit_vec(p0 + sigma * z, c_hat, win, q) + _profit_vec(p0 - sigma * z, c_hat, win, q))
    else:
        pairs = _profit_vec(p0 - sigma * np.abs(z), c_hat, win, q)
    mean = float(pairs.mean())
    se = float(pairs.std(ddof=1) / math.sqrt(len(pairs)))
    return 1.0 - mean / base, se / base
