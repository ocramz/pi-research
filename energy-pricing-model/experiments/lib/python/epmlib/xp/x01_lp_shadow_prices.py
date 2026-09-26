"""x01-lp-shadow-prices: the note's §3 dual statements (Part A) and its 2% re-solve rule (Part B).

Registered in PREREG.md (9b75f38); toy v1 from plans/toy_v1_spec.md (26abb27)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from .. import jsonio
from ..allocation import HHInstance, Regime, certify, greedy, note_regime, regime, table_duals
from ..config import build, section
from ..lpcheck import max_matched_value, solve_hh_lp
from ..outcomes import Rule, first_match, otherwise
from ..rng import generator
from ..runlib import RunStatus, open_run, parallel_map, parse_args
from ..toy import ARCHETYPES, KAPPA, LAM, NU_BAR, PREMIUM, Pool, ToyEngine, calibration, calibration_ok, named_config
from ..toy.matching import dual_error, dual_increment, increment
from ..toy.scenarios import pool_capacities

EXPERIMENT = "x01-lp-shadow-prices"
DEGENERATE_KINDS = ("gplus_eq_c", "merit_sum_eq_c", "duplicate_premium", "premium_eq_lambda")
CHUNK = 250


@dataclass(frozen=True)
class PartA:
    instances: int
    degenerate_per_kind: int
    customer_counts: tuple[int, ...]
    asset_counts: tuple[int, ...]
    demand_lognormal_sigma: float
    gen_ratio_range: tuple[float, float]
    premium_range: tuple[float, float]
    lam: float
    kappa: float
    lp_time_limit_s: float
    dual_tol: float
    objective_rtol: float


@dataclass(frozen=True)
class PartB:
    toy_spec: str
    scenarios: int
    books: tuple[int, ...]
    q_percent: tuple[float, ...]
    rule_q_percent: float
    tolerance: float
    bootstrap: int
    lhs_cells: int
    highs_check_halfhours: int
    highs_check_scenarios: int
    highs_check_q_percent: tuple[float, ...]


@dataclass(frozen=True)
class RunCfg:
    workers: int
    config_cap_s: float
    wall_cap_s: float
    max_censored_fraction: float


@dataclass(frozen=True)
class Config:
    seed: int
    a: PartA
    b: PartB
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    exp = section(data, "experiment")
    return Config(seed=int(exp["seed"]), a=build(PartA, section(data, "part_a"), where="part_a"),
                  b=build(PartB, section(data, "part_b"), where="part_b"),
                  run=build(RunCfg, section(data, "run"), where="run"))


# --- Part A: instances ------------------------------------------------------------------------------


def random_instance(cfg: Config, k: int) -> HHInstance:
    a = cfg.a
    rng = generator(cfg.seed, 101, k)
    n_c = int(rng.choice(a.customer_counts))
    n_a = int(rng.choice(a.asset_counts))
    c = np.minimum(rng.lognormal(0.0, a.demand_lognormal_sigma, n_c), a.kappa)
    lo, hi = a.gen_ratio_range
    g = math.exp(rng.uniform(math.log(lo), math.log(hi)))
    gen = g * c.sum() * rng.dirichlet(np.ones(n_a))
    prem = rng.uniform(a.premium_range[0], a.premium_range[1], n_a)
    return HHInstance(float(a.lam), tuple(map(float, c)), tuple(map(float, gen)), tuple(map(float, prem)))


def _composition(rng: np.random.Generator, total: int, parts: int) -> list[int]:
    """A random split of a positive integer into `parts` positive integers."""
    cuts = sorted(rng.choice(np.arange(1, total), size=parts - 1, replace=False).tolist()) if parts > 1 else []
    edges = [0, *cuts, total]
    return [edges[i + 1] - edges[i] for i in range(parts)]


def degenerate_instance(cfg: Config, j: int) -> tuple[str, HHInstance]:
    """Exact ties, built from multiples of 1/8 so that they are exact in floating point."""
    kind = DEGENERATE_KINDS[j // cfg.a.degenerate_per_kind]
    rng = generator(cfg.seed, 103, j)
    lam = cfg.a.lam
    n_c = int(rng.choice([1, 2, 3, 5]))
    n_a = int(rng.choice([2, 3, 5]))
    eighths = rng.integers(1, 21, n_c)  # c_i ∈ {1/8, …, 20/8 = κ}
    c = tuple(float(k) / 8 for k in eighths)
    c8 = int(eighths.sum())
    if kind == "gplus_eq_c":
        prem = tuple(float(x) for x in rng.integers(0, 45, n_a))
        c8 = max(c8, n_a)
        if c8 != int(eighths.sum()):  # make C large enough to split into n_a positive parts
            eighths[0] += c8 - int(eighths.sum())
            c = tuple(float(k) / 8 for k in eighths)
        gen = tuple(float(x) / 8 for x in _composition(rng, c8, n_a))
    elif kind == "merit_sum_eq_c":
        prem = tuple(float(x) for x in rng.choice(np.arange(0, 45), size=n_a, replace=False))
        order = sorted(range(n_a), key=lambda a: prem[a])
        m = int(rng.integers(1, n_a))  # the cheapest m assets exactly exhaust C
        c8 = max(c8, m)
        if c8 != int(eighths.sum()):
            eighths[0] += c8 - int(eighths.sum())
            c = tuple(float(k) / 8 for k in eighths)
        head = _composition(rng, c8, m)
        gen_list = [0.0] * n_a
        for pos, a in enumerate(order):
            gen_list[a] = float(head[pos]) / 8 if pos < m else float(rng.integers(1, 21)) / 8
        gen = tuple(gen_list)
    elif kind == "duplicate_premium":
        base = rng.integers(0, 45, n_a - 1).tolist()
        base.append(base[int(rng.integers(0, n_a - 1))])
        prem = tuple(float(x) for x in rng.permutation(base))
        gen = tuple(float(x) / 8 for x in rng.integers(1, 21, n_a))
    else:  # premium_eq_lambda
        vals = [float(x) for x in rng.integers(0, 45, n_a - 1)] + [float(lam)]
        prem = tuple(float(x) for x in rng.permutation(vals))
        gen = tuple(float(x) / 8 for x in rng.integers(1, 21, n_a))
    return kind, HHInstance(float(lam), c, gen, prem)


def is_degenerate(inst: HHInstance) -> bool:
    c = sum(inst.cap_demand)
    tol = 1e-9 * max(1.0, c)
    order = sorted((a for a in range(inst.n_assets) if inst.premium[a] < inst.lam),
                   key=lambda a: (inst.premium[a], a))
    g_plus = sum(inst.gen[a] for a in order)
    if abs(g_plus - c) <= tol:
        return True
    cum = 0.0
    for a in order:
        cum += inst.gen[a]
        if abs(cum - c) <= tol:
            return True
    if len(set(inst.premium)) < len(inst.premium) or any(p == inst.lam for p in inst.premium):
        return True
    return any(x <= 0 for x in inst.cap_demand) or any(x <= 0 for x in inst.gen)


def _frac(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def evaluate_instance(cfg: Config, key: str, kind: str, inst: HHInstance) -> tuple[dict, list[dict]]:
    a = cfg.a
    ex = inst.exact()
    sol = greedy(ex)
    c1 = certify(ex, sol.m, sol.nu, sol.mu).ok
    planted = (sol.nu[0] + 1, *sol.nu[1:])
    c3 = not certify(ex, sol.m, planted, sol.mu).ok
    res = solve_hh_lp(inst, time_limit=a.lp_time_limit_s)
    degenerate = is_degenerate(inst)
    value = float(sol.value)
    rec: dict[str, Any] = {"key": key, "part": "A", "kind": kind, "n_customers": inst.n_customers,
                           "n_assets": inst.n_assets, "degenerate": degenerate, "regime": sol.regime.value,
                           "value": value, "c1": c1, "c3": c3, "highs_optimal": res.optimal}
    witnesses: list[dict] = []
    if not res.optimal:
        rec.update({"c2": None, "censored": True})
        return rec, witnesses
    scale = max(1.0, abs(value))
    c2_obj = abs(res.value - value) <= a.objective_rtol * scale
    nu_t = np.array([float(x) for x in sol.nu])
    mu_t = np.array([float(x) for x in sol.mu])
    if degenerate:
        feasible = bool((res.nu >= -1e-9).all() and (res.mu >= -1e-9).all())
        prof = np.array([inst.lam - p for p in inst.premium])
        feasible &= bool((res.nu[:, None] + res.mu[None, :] >= prof[None, :] - 1e-9 * scale).all())
        dual_value = float(np.dot(inst.cap_demand, res.nu) + np.dot(inst.gen, res.mu))
        c2_dual = feasible and abs(dual_value - value) <= a.objective_rtol * scale
        dual_diff = None
    else:
        dual_diff = float(max(np.abs(res.nu - nu_t).max(initial=0.0), np.abs(res.mu - mu_t).max(initial=0.0)))
        c2_dual = dual_diff <= a.dual_tol
    rec.update({"c2": bool(c2_obj and c2_dual), "c2_objective": bool(c2_obj), "c2_duals": bool(c2_dual),
                "dual_max_diff": dual_diff, "censored": False})

    # The note's statements, on nondegenerate instances only.
    s1_elig = s2_elig = False
    s1_holds = s2_holds = None
    s3_mis = None
    certified = c1 and rec["c2"]
    if not degenerate:
        k = sol.marginal
        if sol.regime is Regime.DEMAND_SCARCE and k is not None:
            used = [sum(sol.m[i][x] for i in range(ex.n_customers)) for x in range(ex.n_assets)]
            infra = [x for x in range(ex.n_assets) if ex.premium[x] < ex.premium[k] and used[x] == ex.gen[x]]
            if infra:
                s1_elig = True
                s1_holds = all(abs(res.mu[x]) <= a.dual_tol for x in infra)
                if not s1_holds and certified:
                    for x in infra:
                        witnesses.append({"statement": "S1", "key": key, "asset": x, "note_mu": "0",
                                          "certified_mu": _frac(sol.mu[x]), "highs_mu": float(res.mu[x]),
                                          "instance": _exact_instance(ex), "marginal": k})
        if sol.regime is Regime.GENERATION_SCARCE:
            above = [x for x in range(ex.n_assets) if ex.premium[x] > ex.lam]
            if above:
                s2_elig = True
                s2_holds = all(abs(res.mu[x] - (inst.lam - inst.premium[x])) <= a.dual_tol for x in above)
                if not s2_holds and certified:
                    for x in above:
                        witnesses.append({"statement": "S2", "key": key, "asset": x,
                                          "note_mu": _frac(ex.lam - ex.premium[x]),
                                          "certified_mu": _frac(sol.mu[x]), "highs_mu": float(res.mu[x]),
                                          "instance": _exact_instance(ex)})
        true_r, note_r = regime(ex), note_regime(ex)
        s3_mis = true_r != note_r
        if s3_mis and certified:
            witnesses.append({"statement": "S3", "key": key, "note_regime": note_r.value,
                              "true_regime": true_r.value, "sum_g": _frac(sum(ex.gen)),
                              "g_plus": _frac(sum(ex.gen[x] for x in range(ex.n_assets) if ex.premium[x] < ex.lam)),
                              "c": _frac(sum(ex.cap_demand)), "instance": _exact_instance(ex)})
    rec.update({"s1_eligible": s1_elig, "s1_holds": s1_holds, "s2_eligible": s2_elig, "s2_holds": s2_holds,
                "s3_misclassified": s3_mis})
    return rec, witnesses


def _exact_instance(ex: HHInstance) -> dict[str, Any]:
    return {"lam": _frac(ex.lam), "c": [_frac(x) for x in ex.cap_demand], "gen": [_frac(x) for x in ex.gen],
            "premium": [_frac(x) for x in ex.premium]}


# --- Part B: the toy book ------------------------------------------------------------------------------


def _check_points(cfg: Config, scenarios: int, t_len: int) -> np.ndarray:
    rng = generator(cfg.seed, 104)
    s = np.sort(rng.choice(scenarios, size=cfg.b.highs_check_scenarios, replace=False))
    t = np.sort(rng.choice(t_len, size=cfg.b.highs_check_halfhours, replace=False))
    return (s[:, None] * t_len + t[None, :]).ravel()


def part_b_unit(cfg: Config, config_name: str) -> dict[str, Any]:
    started = time.monotonic()
    b = cfg.b
    base = config_name == "base"
    eng = ToyEngine(named_config(config_name), b.scenarios)
    g = eng.generation(Pool.P71)
    solar_mw, wind_mw = pool_capacities(Pool.P71, eng.p)
    prospects = {a: eng.prospect_demand(a) for a in ARCHETYPES}
    points = _check_points(cfg, b.scenarios, g.shape[1]) if base else None
    cells: list[dict[str, Any]] = []
    c5 = c6 = True
    c4 = {"checked": 0, "failures": 0, "censored": 0, "max_abs_err": 0.0}
    for n, c, sites in eng.books(b.books, keep_sites_at=points):
        base_values: dict[int, float] = {}
        for a in ARCHETYPES:
            for q in b.q_percent:
                d = np.minimum((q / 100.0) * n * prospects[a], KAPPA)
                dual = NU_BAR * dual_increment(g, c, d)
                exact = NU_BAR * increment(g, c, d)
                closed = NU_BAR * dual_error(g, c, d)
                scale = np.maximum(1.0, np.abs(dual))
                c5 &= bool((dual - exact >= -1e-12 * scale).all())
                c6 &= bool((np.abs((dual - exact) - closed) <= 1e-9 * scale).all())
                vol = float(d.sum())
                rec: dict[str, Any] = {
                    "key": f"B|{config_name}|N{n:03d}|{a.value}|q{q:05.2f}", "part": "B", "config": config_name,
                    "N": n, "archetype": a.value, "q_percent": q, "dual_sum": float(dual.sum()),
                    "exact_sum": float(exact.sum()), "volume_mwh": vol,
                    "rel_err": float((dual.sum() - exact.sum()) / exact.sum()) if exact.sum() > 0 else None,
                    "err_gbp_per_mwh": float((dual.sum() - exact.sum()) / vol) if vol > 0 else None,
                }
                if base:
                    rec["dual_s"] = dual.tolist()
                    rec["exact_s"] = exact.tolist()
                cells.append(rec)
                if base and q in b.highs_check_q_percent:
                    c4 = _highs_check(c4, n, g, c, d, sites, points, solar_mw, wind_mw, eng, base_values)
    out: dict[str, Any] = {"config": config_name, "cells": cells, "c5": c5, "c6": c6,
                           "seconds": round(time.monotonic() - started, 3)}
    if base:
        cal = calibration(eng)
        out.update({"c4": c4, "calibration": cal, "c7": calibration_ok(cal)})
    return out


def _highs_check(acc: dict, n: int, g: np.ndarray, c: np.ndarray, d: np.ndarray, sites: np.ndarray,
                 points: np.ndarray, solar_mw: float, wind_mw: float, eng: ToyEngine,
                 base_values: dict[int, float]) -> dict:
    solar = (solar_mw * eng.solar_per_mw).ravel()[points]
    wind = (wind_mw * eng.wind_per_mw).ravel()[points]
    gf, cf, df = g.ravel()[points], c.ravel()[points], d.ravel()[points]
    for j in range(len(points)):
        gens = np.array([solar[j], wind[j]])
        if j not in base_values:
            r0 = max_matched_value(LAM, PREMIUM, sites[:, j], gens)
            if not r0.optimal:
                acc["censored"] += 1
                base_values[j] = float("nan")
                continue
            base_values[j] = r0.value
        r1 = max_matched_value(LAM, PREMIUM, np.append(sites[:, j], df[j]), gens)
        acc["checked"] += 1
        if not r1.optimal or math.isnan(base_values[j]):
            acc["censored"] += 1
            continue
        expected = NU_BAR * min(df[j], max(gf[j] - cf[j], 0.0))
        err = abs((r1.value - base_values[j]) - expected)
        acc["max_abs_err"] = max(acc["max_abs_err"], err)
        if err > 1e-7 * max(1.0, abs(r1.value)):
            acc["failures"] += 1
    return acc


# --- units, summary, rules -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    name: str
    kind: str  # "A" or "B"
    start: int = 0
    stop: int = 0
    degenerate: bool = False


def units(cfg: Config) -> list[Unit]:
    out = [Unit(f"A-random-{i:02d}", "A", s, min(s + CHUNK, cfg.a.instances))
           for i, s in enumerate(range(0, cfg.a.instances, CHUNK))]
    n_deg = cfg.a.degenerate_per_kind * len(DEGENERATE_KINDS)
    out += [Unit(f"A-degenerate-{i:02d}", "A", s, min(s + CHUNK, n_deg), True)
            for i, s in enumerate(range(0, n_deg, CHUNK))]
    out.append(Unit("B-base", "B"))
    out += [Unit(f"B-lhs-{j:02d}", "B") for j in range(cfg.b.lhs_cells)]
    return out


def run_unit(job: tuple[Config, Unit]) -> dict[str, Any]:
    cpu0 = time.process_time()
    out = _run_unit(job)
    out["cpu_seconds"] = round(time.process_time() - cpu0, 3)
    return out


def _run_unit(job: tuple[Config, Unit]) -> dict[str, Any]:
    cfg, unit = job
    started = time.monotonic()
    if unit.kind == "A":
        records, witnesses = [], []
        for idx in range(unit.start, unit.stop):
            if unit.degenerate:
                kind, inst = degenerate_instance(cfg, idx)
                key = f"A|deg|{idx:05d}"
            else:
                kind, inst = "random", random_instance(cfg, idx)
                key = f"A|rnd|{idx:05d}"
            rec, wit = evaluate_instance(cfg, key, kind, inst)
            records.append(rec)
            witnesses += wit
        return {"unit": unit.name, "records": records, "witnesses": witnesses,
                "seconds": round(time.monotonic() - started, 3)}
    name = "base" if unit.name == "B-base" else unit.name.removeprefix("B-")
    return {"unit": unit.name, **part_b_unit(cfg, name)}


def bootstrap_cells(cfg: Config, base_cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Percentile CIs of rel_err at every base cell and q, and of e* at the rule's q."""
    s = cfg.b.scenarios
    rng = generator(cfg.seed, 102)
    weights = np.stack([np.bincount(rng.integers(0, s, s), minlength=s) for _ in range(cfg.b.bootstrap)])
    diff = np.array([np.subtract(r["dual_s"], r["exact_s"]) for r in base_cells]).T  # (S, cells)
    exact = np.array([r["exact_s"] for r in base_cells]).T
    rel = (weights @ diff) / (weights @ exact)  # (B, cells)
    ci = np.percentile(rel, [2.5, 97.5], axis=0)
    rule = [j for j, r in enumerate(base_cells) if r["q_percent"] == cfg.b.rule_q_percent]
    e_star_b = rel[:, rule].max(axis=1)
    return {"cell_ci": {base_cells[j]["key"]: [float(ci[0, j]), float(ci[1, j])] for j in range(len(base_cells))},
            "e_star_ci": [float(x) for x in np.percentile(e_star_b, [2.5, 97.5])]}


def _q_star(qs: list[float], errs: list[float], tol: float) -> dict[str, Any]:
    if all(e <= tol for e in errs):
        return {"q_star": None, "censored": f">= {qs[-1]}"}
    j = next(i for i, e in enumerate(errs) if e > tol)
    if j == 0:
        return {"q_star": None, "censored": f"< {qs[0]}"}
    x0, x1 = math.log(qs[j - 1]), math.log(qs[j])
    y0, y1 = errs[j - 1], errs[j]
    return {"q_star": math.exp(x0 + (tol - y0) * (x1 - x0) / (y1 - y0)), "censored": None}


def summarise(cfg: Config, a_records: list[dict], b_units: list[dict], witnesses: list[dict],
              wall_seconds: float) -> dict[str, Any]:
    tol, rq = cfg.b.tolerance, cfg.b.rule_q_percent
    # Part A controls and statements.
    n_a = len(a_records)
    censored = sum(1 for r in a_records if r["censored"])
    optimal = [r for r in a_records if not r["censored"]]
    c1 = all(r["c1"] for r in a_records)
    c2 = all(r["c2"] for r in optimal)
    c3 = all(r["c3"] for r in a_records)
    nondeg = [r for r in optimal if not r["degenerate"]]
    s1 = [r for r in nondeg if r["s1_eligible"]]
    s2 = [r for r in nondeg if r["s2_eligible"]]
    statements = {
        "S1": {"eligible": len(s1), "counterexamples": sum(1 for r in s1 if not r["s1_holds"])},
        "S2": {"eligible": len(s2), "counterexamples": sum(1 for r in s2 if not r["s2_holds"])},
        "S3": {"eligible": len(nondeg), "counterexamples": sum(1 for r in nondeg if r["s3_misclassified"])},
    }
    # Witnesses are recorded only for instances that pass C1 and C2, so each one is certified.
    certified = {st: sum(1 for w in witnesses if w["statement"] == st) for st in ("S1", "S2", "S3")}
    note_dual_statements = "fails" if any(certified.values()) else "holds"
    # Part B.
    base = next(u for u in b_units if u["config"] == "base")
    base_cells = sorted(base["cells"], key=lambda r: r["key"])
    boot = bootstrap_cells(cfg, base_cells)
    c4 = base["c4"]
    lp_total = n_a + c4["checked"] + len(cfg.b.books) * cfg.b.highs_check_halfhours * cfg.b.highs_check_scenarios
    lp_censored = censored + c4["censored"]
    c5 = all(u["c5"] for u in b_units)
    c6 = all(u["c6"] for u in b_units)
    cap_ok = all(u["seconds"] <= cfg.run.config_cap_s for u in b_units) and wall_seconds <= cfg.run.wall_cap_s
    controls = {"C1": c1, "C2": c2, "C3": c3, "C4": c4["failures"] == 0, "C5": c5, "C6": c6, "C7": base["c7"]}
    censored_fraction = lp_censored / lp_total if lp_total else 0.0
    by_cell = {}
    for r in base_cells:
        by_cell.setdefault((r["N"], r["archetype"]), {})[r["q_percent"]] = r
    rule_cells = []
    for (n, arch), per_q in sorted(by_cell.items()):
        r = per_q[rq]
        lo, hi = boot["cell_ci"][r["key"]]
        qs = sorted(per_q)
        rule_cells.append({"N": n, "archetype": arch, "rel_err": r["rel_err"], "ci": [lo, hi],
                           "err_gbp_per_mwh": r["err_gbp_per_mwh"],
                           "linearity_8_over_2": per_q[8.0]["rel_err"] / r["rel_err"] if 8.0 in per_q and r["rel_err"] else None,
                           "q_star_5": _q_star(qs, [per_q[q]["rel_err"] for q in qs], tol)})
    e_star = max(c["rel_err"] for c in rule_cells)
    lhs_units = [u for u in b_units if u["config"] != "base"]
    lhs_hold = [all(r["rel_err"] <= tol for r in u["cells"] if r["q_percent"] == rq) for u in lhs_units]
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "controls": controls,
        "controls_pass": all(controls.values()) and censored_fraction <= cfg.run.max_censored_fraction and cap_ok,
        "censored": {"lp_total": lp_total, "lp_censored": lp_censored, "fraction": censored_fraction},
        "caps_ok": cap_ok,
        "tolerance": tol,
        "e_star": e_star,
        "e_star_ci": boot["e_star_ci"],
        "rule_cells": rule_cells,
        "note_dual_statements": note_dual_statements,
        "statements": statements,
        "certified_witnesses": certified,
        "part_a": {"instances": n_a, "censored": censored,
                   "regimes": {rg.value: sum(1 for r in a_records if r["regime"] == rg.value) for rg in Regime}},
        "c4": c4,
        "calibration": base["calibration"],
        "lhs": {"cells": len(lhs_units), "hold": int(sum(lhs_hold)),
                "share": float(np.mean(lhs_hold)) if lhs_hold else None},
        "unit_seconds": {u["config"]: u["seconds"] for u in b_units},
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


def _failing(s: dict) -> list[dict]:
    return [c for c in s["rule_cells"] if c["ci"][0] > s["tolerance"]]


RULES: list[Rule[dict]] = [
    Rule("invalid", "any control fails, or more than 0.1% of solves are censored",
         "debug, record a deviation, re-run", lambda s: not s["controls_pass"]),
    Rule("rule-holds", "CI upper(e*) ≤ 5%", "run x02; carry the result to G1",
         lambda s: s["e_star_ci"][1] <= s["tolerance"]),
    Rule("rule-fails-saturated",
         "CI lower(e*) > 5%, every failing cell has N ≥ 60, and every cell with N ≤ 40 has CI upper ≤ 5%",
         "run x02; the G1 report drafts x01a (a surplus-scaled re-solve rule), unregistered",
         lambda s: s["e_star_ci"][0] > s["tolerance"] and all(c["N"] >= 60 for c in _failing(s))
         and all(c["ci"][1] <= s["tolerance"] for c in s["rule_cells"] if c["N"] <= 40)),
    Rule("rule-fails-broadly", "CI lower(e*) > 5%, and some failing cell has N ≤ 40",
         "run x02; G1 flags the rule as unsafe",
         lambda s: s["e_star_ci"][0] > s["tolerance"] and any(c["N"] <= 40 for c in _failing(s))),
    Rule("inconclusive", "otherwise", "run x02; G1 decides whether to register a larger S", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started = time.monotonic()
    done = ctx.done_keys()
    pending = [u for u in units(cfg) if f"unit|{u.name}" not in done]
    for unit, result in parallel_map(run_unit, [(cfg, u) for u in pending], workers=ctx.workers):
        u = unit[1]
        if u.kind == "A":
            for rec in result["records"]:
                ctx.append_record(rec)
            for w in result["witnesses"]:
                jsonio.append_jsonl(ctx.run_dir / "witnesses.jsonl", w)
            ctx.append_record({"key": f"unit|{u.name}", "seconds": result["seconds"], "cpu_seconds": result["cpu_seconds"]})
        else:
            for rec in result["cells"]:
                ctx.append_record(rec)
            meta = {k: v for k, v in result.items() if k not in ("cells", "unit")}
            ctx.append_record({"key": f"unit|{u.name}", **meta})
        ctx.save_checkpoint("units", {"done": sorted(k.removeprefix("unit|") for k in ctx.done_keys()
                                                        if k.startswith("unit|"))})
    records = ctx.read_records()
    a_records = [r for r in records if r.get("part") == "A"]
    b_meta = {r["key"].removeprefix("unit|B-"): r for r in records if r["key"].startswith("unit|B-")}
    b_units = []
    for name, meta in b_meta.items():
        cfg_name = "base" if name == "base" else name
        cells = [r for r in records if r.get("part") == "B" and r["config"] == cfg_name]
        b_units.append({**meta, "config": cfg_name, "cells": cells})
    witnesses = jsonio.read_jsonl(ctx.run_dir / "witnesses.jsonl")
    summary = summarise(cfg, a_records, b_units, witnesses, time.monotonic() - started)
    unit_cpu = sum(r.get("cpu_seconds", 0.0) for r in records if r["key"].startswith("unit|"))
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=unit_cpu)
    print(f"{EXPERIMENT}: {summary['class']} (e* = {summary['e_star']:.4f}, CI {summary['e_star_ci']}); "
          f"note-dual-statements: {summary['note_dual_statements']}; run {ctx.run_dir}")
    return 0
