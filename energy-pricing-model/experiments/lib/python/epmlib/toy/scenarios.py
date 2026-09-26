"""The scenario engine of toy v1 (§2–7): S weather-years, each stream keyed
`SeedSequence([20260926, s, entity])`, so every config and experiment sees common random numbers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from functools import cached_property

import numpy as np
from scipy.signal import lfilter
from scipy.special import expit

from ..rng import generator
from .calibrate import expected_solar, expected_wind_per_mw, solar_eta, wind_mu
from .shapes import archetype_shape, clear_sky, time_grid
from .spec import (ARCHETYPES, HH_HOURS, HOURS_PER_YEAR, KAPPA, P71_MWH, P72_SOLAR_MW, SEED, SOLAR_MWH_PER_MW,
                   T, WIND_CF, Archetype, Entity, Pool, ToyParams, winter)


def ar1(eps: np.ndarray, phi: float) -> np.ndarray:
    """Stationary AR(1) with unit variance along the last axis: y_0 = ε_0 and
    y_t = φ·y_{t−1} + √(1 − φ²)·ε_t."""
    if not 0.0 <= phi < 1.0:
        raise ValueError(f"phi must be in [0, 1), not {phi}")
    b0 = np.sqrt(1.0 - phi * phi)
    e = eps.copy()
    e[..., 0] = eps[..., 0] / b0
    return lfilter([b0], [1.0, -phi], e, axis=-1)


def pool_capacities(pool: Pool, p: ToyParams) -> tuple[float, float]:
    """(solar MW, wind MW)."""
    if pool is Pool.P71:
        return p.theta_s * P71_MWH / SOLAR_MWH_PER_MW, (1.0 - p.theta_s) * P71_MWH / (WIND_CF * HOURS_PER_YEAR)
    if pool is Pool.P72:
        return P72_SOLAR_MW, 0.0
    raise ValueError(pool)


class ToyEngine:
    """One config's scenarios. Arrays are (S, T) in MWh per half-hour."""

    def __init__(self, params: ToyParams, scenarios: int):
        self.p = params
        self.S = scenarios
        self.eta = solar_eta(params.s_c, params.clear_sky)
        self.mu_w = wind_mu(params.a_w, params.s_w)
        self._shapes = {a: archetype_shape(a, params) for a in ARCHETYPES}

    def normals(self, entity: int) -> np.ndarray:
        return np.stack([generator(SEED, s, entity).standard_normal(T) for s in range(self.S)])

    @cached_property
    def cloud_latent(self) -> np.ndarray:
        return ar1(self.normals(Entity.CLOUD), self.p.phi_c)

    @cached_property
    def solar_per_mw(self) -> np.ndarray:
        if self.p.generation == "mean":
            return np.broadcast_to(expected_solar(self.p), (self.S, T)).copy()
        c = clear_sky(self.p.clear_sky)
        k = expit(self.p.s_c * self.cloud_latent)
        return HH_HOURS * np.minimum(1.0, self.eta * c[None, :] * k)

    @cached_property
    def wind_per_mw(self) -> np.ndarray:
        if self.p.generation == "mean":
            return np.broadcast_to(expected_wind_per_mw(self.p), (self.S, T)).copy()
        day, _, _, _ = time_grid()
        w = ar1(self.normals(Entity.WIND), self.p.phi_w)
        return HH_HOURS * expit(self.mu_w + self.p.a_w * winter(day)[None, :] + self.p.s_w * w)

    def generation(self, pool: Pool) -> np.ndarray:
        solar_mw, wind_mw = pool_capacities(pool, self.p)
        g = solar_mw * self.solar_per_mw
        if wind_mw > 0.0:
            g = g + wind_mw * self.wind_per_mw
        return g

    def expected_generation(self, pool: Pool) -> np.ndarray:
        solar_mw, wind_mw = pool_capacities(pool, self.p)
        return solar_mw * expected_solar(self.p) + wind_mw * expected_wind_per_mw(self.p)

    @cached_property
    def common_factor(self) -> np.ndarray:
        s, rho = self.p.s_cm, self.p.rho_dg
        c = rho * self.cloud_latent + np.sqrt(1.0 - rho * rho) * ar1(self.normals(Entity.COMMON), self.p.phi_cm)
        return np.exp(s * c - 0.5 * s * s)

    def _noise(self, entity: int) -> np.ndarray:
        s = self.p.s_i
        return np.exp(s * ar1(self.normals(entity), self.p.phi_i) - 0.5 * s * s)

    def site_archetype(self, i: int) -> Archetype:
        if self.p.book_order == "round_robin":
            return ARCHETYPES[i % 3]
        if self.p.book_order == "shuffled":
            perm = generator(SEED, Entity.SHUFFLE, i // 3).permutation(3)
            return ARCHETYPES[int(perm[i % 3])]
        raise ValueError(self.p.book_order)

    def shape(self, a: Archetype) -> np.ndarray:
        return self._shapes[a]

    def site_demand(self, i: int) -> np.ndarray:
        """Uncapped D_i."""
        return self.shape(self.site_archetype(i))[None, :] * self._noise(Entity.SITE + i) * self.common_factor

    def prospect_demand(self, a: Archetype) -> np.ndarray:
        """Uncapped demand of a fresh 250 MWh site of archetype a."""
        return self.shape(a)[None, :] * self._noise(Entity.PROSPECT + a.index) * self.common_factor

    def books(self, sizes: Sequence[int], *, keep_sites_at: np.ndarray | None = None
              ) -> Iterator[tuple[int, np.ndarray, np.ndarray | None]]:
        """Yield (N, C_N, site values) for each requested N, ascending: C_N = Σ_{i<N} min(D_i, κ).
        `keep_sites_at` is an index array into the flattened (S, T) grid; the yielded site values
        are the capped demands of sites 0..N−1 there, shape (N, len(points))."""
        wanted = sorted(set(sizes))
        c = np.zeros((self.S, T))
        kept: list[np.ndarray] = []
        i = 0
        for n in wanted:
            while i < n:
                d = np.minimum(self.site_demand(i), KAPPA)
                c += d
                if keep_sites_at is not None:
                    kept.append(d.ravel()[keep_sites_at])
                i += 1
            sites = np.array(kept).reshape(len(kept), -1) if keep_sites_at is not None else None
            yield n, c.copy(), sites

    def expected_book(self, n: int) -> np.ndarray:
        """Σ_{i<N} f_{a(i)}: the analytic expected book shape (the cap is inert)."""
        out = np.zeros(T)
        for i in range(n):
            out += self.shape(self.site_archetype(i))
        return out


def calibration(engine: ToyEngine, sites: int = 30) -> dict[str, dict[str, float]]:
    """Toy v1 §8's calibration control: mean and standard error over scenarios."""
    def stat(per_scenario: np.ndarray, target: float) -> dict[str, float]:
        mean = float(per_scenario.mean())
        se = float(per_scenario.std(ddof=1) / np.sqrt(len(per_scenario)))
        return {"mean": mean, "se": se, "target": target, "z": (mean - target) / se if se > 0 else 0.0}

    solar_cf = engine.solar_per_mw.sum(axis=1) / HOURS_PER_YEAR
    wind_cf = engine.wind_per_mw.sum(axis=1) / HOURS_PER_YEAR
    volumes = np.stack([engine.site_demand(i).sum(axis=1) for i in range(sites)]).mean(axis=0)
    p71 = engine.generation(Pool.P71).sum(axis=1)
    return {"solar_cf": stat(solar_cf, 0.117), "wind_cf": stat(wind_cf, 0.30),
            "site_mwh": stat(volumes, 250.0), "p71_mwh": stat(p71, P71_MWH)}


def calibration_ok(cal: dict[str, dict[str, float]], z: float = 4.0) -> bool:
    return all(abs(v["z"]) <= z for v in cal.values())
