"""Matching sums over half-hours, one value per scenario. Arrays are (S, T); G is generation,
C the capped book, d a (capped) prospect. Multiply by ν̄ for money."""

from __future__ import annotations

import numpy as np


def matched(g: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Σ_t min(G, C)."""
    return np.minimum(g, c).sum(axis=-1)


def increment(g: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Exact matched increment of a prospect: Σ_t min(d, (G − C)⁺)."""
    return np.minimum(d, np.maximum(g - c, 0.0)).sum(axis=-1)


def dual_increment(g: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """First-order (dual) increment: Σ_t 1{G > C}·d."""
    return np.where(g > c, d, 0.0).sum(axis=-1)


def dual_error(g: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Σ_t 1{G > C}·(d − (G − C))⁺: the closed form of dual − exact."""
    return np.where(g > c, np.maximum(d - (g - c), 0.0), 0.0).sum(axis=-1)


def point_share(g_mean: np.ndarray, c_mean: np.ndarray, d_mean: np.ndarray) -> float:
    """A prospect's matched share on mean shapes: Σ min(d̄, (Ḡ − C̄)⁺) / Σ d̄."""
    return float(np.minimum(d_mean, np.maximum(g_mean - c_mean, 0.0)).sum() / d_mean.sum())


def jensen_terms(g: np.ndarray, c: np.ndarray) -> tuple[float, float]:
    """(Σ_t min(Ḡ_t, C̄_t), M̄) with in-sample means over scenarios (axis 0). The overstatement is
    (point − M̄)/M̄. x02 and its analytic checker both call this."""
    point = float(np.minimum(g.mean(axis=0), c.mean(axis=0)).sum())
    m_bar = float(np.minimum(g, c).sum(axis=-1).mean())
    return point, m_bar


def resampled_overstatement(g_b: np.ndarray, c_b: np.ndarray, weights: np.ndarray, m_s: np.ndarray
                            ) -> np.ndarray:
    """O in each bootstrap resample. `weights` is (B, S) counts; g_b and c_b are the resampled mean
    shapes, weights @ x / S, so each resample recomputes its own mean shapes, as registered."""
    point = np.minimum(g_b, c_b).sum(axis=1)
    m_b = weights @ m_s / weights.shape[1]
    return (point - m_b) / m_b
