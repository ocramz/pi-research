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
