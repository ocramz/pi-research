"""Deterministic shapes of toy v1: the time grid, clear sky (§2) and the demand archetypes (§5)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .spec import DAYS, PER_DAY, SITE_MWH, T, Archetype, ToyParams, seasonal, winter


@lru_cache(maxsize=1)
def time_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(day, half-hour, τ = midpoint in hours, weekday with 0 = Monday), each of length T."""
    t = np.arange(T)
    day = t // PER_DAY
    hh = t % PER_DAY
    tau = (hh + 0.5) / 2.0
    for a in (day, hh, tau):
        a.setflags(write=False)
    weekday = day % 7
    weekday.setflags(write=False)
    return day, hh, tau, weekday


def clear_sky(kind: str) -> np.ndarray:
    day, _, tau, _ = time_grid()
    s = seasonal(day)
    if kind == "halfsine":
        length = 12.2 + 4.3 * s
        rise = 12.0 - length / 2.0
        amp = 1.0 + 0.6 * s
        phase = (tau - rise) / length
        c = np.where((phase > 0.0) & (phase < 1.0), amp * np.sin(np.pi * np.clip(phase, 0.0, 1.0)), 0.0)
    elif kind == "astro":
        lat = np.deg2rad(52.0)
        dec = np.deg2rad(23.44) * s
        hour_angle = np.deg2rad(15.0 * (tau - 12.0))
        sin_e = np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.cos(hour_angle)
        c = np.maximum(0.0, sin_e)
    else:
        raise ValueError(f"unknown clear-sky model {kind!r}")
    return c


def _ramp(tau: np.ndarray, t0: float, t1: float, v0: float, v1: float) -> np.ndarray:
    return v0 + (v1 - v0) * (tau - t0) / (t1 - t0)


def archetype_shape(a: Archetype, p: ToyParams) -> np.ndarray:
    """f_a(t), scaled so that Σ_t f_a = 250 MWh/yr."""
    day, _, tau, weekday = time_grid()
    w = winter(day)
    if a is Archetype.OFFICE:
        b = p.b_o
        weekday_shape = np.select(
            [tau < 7, tau < 9, tau < 17, tau < 19],
            [np.full_like(tau, b), _ramp(tau, 7, 9, b, 1.0), np.ones_like(tau), _ramp(tau, 17, 19, 1.0, b)],
            default=b)
        f = np.where(weekday < 5, weekday_shape, b) * (1.0 + 0.10 * w)
    elif a is Archetype.ALWAYS_ON:
        f = (1.0 + p.a_f * np.cos(2 * np.pi * (tau - 14.0) / 24.0)) * (1.0 + 0.05 * w)
    elif a is Archetype.EVENING:
        e = p.e_m
        base = np.select(
            [tau < 1, tau < 10, tau < 12, tau < 17, tau < 18, tau < 23],
            [np.full_like(tau, 0.6), np.full_like(tau, 0.15), _ramp(tau, 10, 12, 0.15, e),
             np.full_like(tau, e), _ramp(tau, 17, 18, e, 1.0), np.ones_like(tau)],
            default=0.8)
        fri_sat = ((weekday == 4) | (weekday == 5)) & (tau >= 17)
        f = base * np.where(fri_sat, 1.2, 1.0) * (1.0 + 0.05 * w)
    else:
        raise ValueError(a)
    return f * (SITE_MWH / f.sum())


assert DAYS * PER_DAY == T
