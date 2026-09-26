"""The x05 quote market: population response, oracle, desk, a logit fit by IRLS, and IPS.

Wins follow σ(β(base(x) + u − p)) with u ~ N(0, τ_u²) unlogged. The population response
P_x(p) = E_u[σ(β(base(x) + u − p))] is computed by Gauss–Hermite quadrature."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit, log_expit

from .pricing import WinModel, optimal_price, optimal_price_vec

CENTER = 160.0  # prices enter the logit as p − 160, for conditioning; slopes are unaffected


@dataclass(frozen=True)
class Market:
    bases: tuple[float, ...]
    beta: float
    tau_u: float
    tau_zeta: float
    c_hat: float
    nodes: int

    @cached_property
    def _gh(self) -> tuple[np.ndarray, np.ndarray]:
        x, w = np.polynomial.hermite.hermgauss(self.nodes)
        return np.sqrt(2.0) * x, w / np.sqrt(np.pi)

    @property
    def n_segments(self) -> int:
        return len(self.bases)

    def pop_prob(self, x: np.ndarray, p: np.ndarray) -> np.ndarray:
        """P_x(p), elementwise over arrays x (segment index) and p."""
        z, w = self._gh
        base = np.asarray(self.bases)[np.asarray(x)]
        arg = self.beta * (base[..., None] + self.tau_u * z - np.asarray(p, dtype=float)[..., None])
        return expit(arg) @ w

    def value(self, x: np.ndarray, p: np.ndarray) -> np.ndarray:
        """V_x(p) = (p − ĉ)·P_x(p), per MWh quoted."""
        return (np.asarray(p, dtype=float) - self.c_hat) * self.pop_prob(x, p)

    @cached_property
    def oracle_prices(self) -> np.ndarray:
        out = []
        for x in range(self.n_segments):
            res = minimize_scalar(lambda p: -float(self.value(np.array(x), np.array(p))),
                                  bounds=(self.c_hat, self.c_hat + 60.0), method="bounded",
                                  options={"xatol": 1e-10, "maxiter": 500})
            out.append(float(res.x))
        return np.array(out)

    @cached_property
    def oracle_value(self) -> float:
        return float(np.mean(self.value(np.arange(self.n_segments), self.oracle_prices)))

    def plug_prices(self, belief_ref: np.ndarray) -> np.ndarray:
        """The desk's plug-in price for its estimate of p_ref (base + ρ²s), with the true individual β."""
        return optimal_price_vec(self.c_hat, self.beta, belief_ref)

    def win_prob(self, x: np.ndarray, u: np.ndarray, p: np.ndarray) -> np.ndarray:
        return expit(self.beta * (np.asarray(self.bases)[x] + u - p))


@dataclass(frozen=True)
class LogitFit:
    alpha: np.ndarray  # per segment, on the price scale: logit P = α_x − b·p
    b: float
    se_b: float
    converged: bool
    iterations: int


def logit_irls(x: np.ndarray, p: np.ndarray, y: np.ndarray, n_segments: int, *, weights: np.ndarray | None = None,
               max_iter: int = 50, tol: float = 1e-10) -> LogitFit:
    """Maximum likelihood for logit P(win) = θ_x + θ_p·(p − 160), by Newton–Raphson with step halving.
    y may be fractional (expected responses) with case weights. Returns b = −θ_p."""
    n = len(y)
    xm = np.zeros((n, n_segments + 1))
    xm[np.arange(n), x] = 1.0
    xm[:, -1] = p - CENTER
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)

    def loglik(theta: np.ndarray) -> float:
        eta = xm @ theta
        return float(np.sum(w * (y * log_expit(eta) + (1 - y) * log_expit(-eta))))

    theta = np.zeros(n_segments + 1)
    ll = loglik(theta)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        mu = expit(xm @ theta)
        grad = xm.T @ (w * (y - mu))
        hess = xm.T @ (xm * (w * mu * (1 - mu))[:, None])
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        new = theta + step
        ll_new = loglik(new)
        halvings = 0
        while ll_new < ll - 1e-12 * (1 + abs(ll)) and halvings < 30:
            step /= 2
            new = theta + step
            ll_new = loglik(new)
            halvings += 1
        theta = new
        done = abs(ll_new - ll) <= tol * (1 + abs(ll_new)) and np.max(np.abs(step)) < 1e-7
        ll = ll_new
        if done:
            converged = True
            break
    mu = expit(xm @ theta)
    hess = xm.T @ (xm * (w * mu * (1 - mu))[:, None])
    try:
        se_b = float(np.sqrt(np.linalg.inv(hess)[-1, -1]))
    except np.linalg.LinAlgError:
        se_b, converged = float("nan"), False
    if not np.all(np.isfinite(theta)):
        converged = False
    b = -theta[-1]
    alpha = theta[:-1] + CENTER * b
    return LogitFit(alpha, float(b), se_b, converged, it)


def deployed_prices(fit: LogitFit, market: Market, *, mirage_min_slope: float, mirage_markup: float) -> np.ndarray:
    """argmax_p (p − ĉ)·σ(α̂_x − b̂·p) per segment; the mirage rule when b̂ ≤ the floor."""
    if fit.b <= mirage_min_slope:
        return np.full(market.n_segments, market.c_hat + mirage_markup)
    return np.array([optimal_price(market.c_hat, WinModel(fit.b, a / fit.b), span=max(100.0, 40.0 / fit.b))
                     for a in fit.alpha])


def ips_segment_values(x: np.ndarray, offset_idx: np.ndarray, wins: np.ndarray, prices: np.ndarray, c_hat: float,
                       n_segments: int, n_offsets: int) -> np.ndarray:
    """IPS value of each (segment, offset) under a uniform logging policy: (n_segments, n_offsets)."""
    reward = wins * (prices - c_hat)
    out = np.zeros((n_segments, n_offsets))
    for s in range(n_segments):
        m = x == s
        n_s = m.sum()
        for j in range(n_offsets):
            out[s, j] = n_offsets * float(np.sum(reward[m & (offset_idx == j)])) / max(n_s, 1)
    return out


def plim_slope(market: Market, seg: np.ndarray, prices: np.ndarray, weights: np.ndarray) -> LogitFit:
    """The probability limit of the logit on a price design, given as quadrature points (segment,
    price, weight): the logit fitted to the expected responses P_x(p)."""
    return logit_irls(seg, prices, market.pop_prob(seg, prices), market.n_segments, weights=weights,
                      max_iter=200, tol=1e-14)
