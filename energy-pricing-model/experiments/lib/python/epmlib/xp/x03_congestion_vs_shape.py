"""x03-congestion-vs-shape: does book size (congestion) dominate load shape in a prospect's marginal
matched share?

Registered in PREREG.md (19852ef); toy v1 from plans/toy_v1_spec.md (26abb27)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..config import build, section
from ..lpcheck import max_matched_value
from ..outcomes import Rule, first_match, otherwise
from ..rng import generator
from ..runlib import RunStatus, open_run, parallel_map, parse_args
from ..toy import ARCHETYPES, BASE, KAPPA, LAM, NU_BAR, PREMIUM, Pool, ToyEngine, ToyParams, calibration, calibration_ok
from ..toy.matching import increment, matched
from ..toy.scenarios import pool_capacities
from ..toy.spec import INVARIANCE_CELLS, SITE_MWH, invariance_configs, lhs_configs, oat_configs

EXPERIMENT = "x03-congestion-vs-shape"
INVARIANCE = tuple(name for name, _ in INVARIANCE_CELLS)
NOTE_KEYS = {"office": "office", "24/7": "always_on", "evening": "evening"}


@dataclass(frozen=True)
class Toy:
    spec: str
    scenarios: int
    books: tuple[int, ...]
    core_books: tuple[int, ...]


@dataclass(frozen=True)
class Analysis:
    dominance_threshold: float
    bootstrap: int
    shape_books: tuple[int, ...]
    gap_book: int
    markup_floor_gbp: float
    standalone_book: int
    theta_fit: tuple[float, ...]
    value_books: tuple[int, ...]
    note_values_gbp: tuple[float, ...]
    invariance_se: float


@dataclass(frozen=True)
class NoteTable:
    books: tuple[int, ...]
    office: tuple[float, ...]
    always_on: tuple[float, ...]
    evening: tuple[float, ...]


@dataclass(frozen=True)
class Checker:
    highs_halfhours: int
    highs_scenarios: int


@dataclass(frozen=True)
class RunCfg:
    workers: int
    config_cap_s: float
    wall_cap_s: float


@dataclass(frozen=True)
class Config:
    seed: int
    toy: Toy
    analysis: Analysis
    table_7_1: NoteTable
    table_7_2: NoteTable
    checker: Checker
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    note = section(data, "note")
    return Config(seed=int(section(data, "experiment")["seed"]),
                  toy=build(Toy, section(data, "toy"), where="toy"),
                  analysis=build(Analysis, section(data, "analysis"), where="analysis"),
                  table_7_1=build(NoteTable, section(note, "table_7_1"), where="note.table_7_1"),
                  table_7_2=build(NoteTable, section(note, "table_7_2"), where="note.table_7_2"),
                  checker=build(Checker, section(data, "checker"), where="checker"),
                  run=build(RunCfg, section(data, "run"), where="run"))


def all_configs(cfg: Config) -> dict[str, ToyParams]:
    out: dict[str, ToyParams] = {"base": BASE}
    for t in cfg.analysis.theta_fit:
        if t != BASE.theta_s:
            out[f"fit-theta_s={t}"] = BASE.with_(theta_s=t)
    for name, p in oat_configs() + lhs_configs() + invariance_configs():
        out[name] = p
    return out


def _check_points(cfg: Config, scenarios: int, t_len: int) -> np.ndarray:
    rng = generator(cfg.seed, 304)
    s = np.sort(rng.choice(scenarios, size=cfg.checker.highs_scenarios, replace=False))
    t = np.sort(rng.choice(t_len, size=cfg.checker.highs_halfhours, replace=False))
    return (s[:, None] * t_len + t[None, :]).ravel()


def pool_unit(cfg: Config, eng: ToyEngine, pool: Pool, *, keep_scenarios: bool, checks: bool) -> dict[str, Any]:
    g = eng.generation(pool)
    solar_mw, wind_mw = pool_capacities(pool, eng.p)
    prospects = {a: np.minimum(eng.prospect_demand(a), KAPPA) for a in ARCHETYPES}
    dsum = {a: prospects[a].sum(axis=1) for a in ARCHETYPES}
    points = _check_points(cfg, eng.S, g.shape[1]) if checks else None
    rows: list[dict[str, Any]] = []
    prev_inc: dict[Any, np.ndarray] = {}
    prev_c = None
    c1 = c2 = c4 = True
    c3 = {"checked": 0, "failures": 0, "censored": 0, "max_abs_err": 0.0}
    for n, c, sites in eng.books(cfg.toy.books, keep_sites_at=points):
        v0 = _book_values(g, sites, points, solar_mw, wind_mw, eng) if checks else None
        for a in ARCHETYPES:
            inc = increment(g, c, prospects[a])
            if a in prev_inc:
                c1 &= bool((inc <= prev_inc[a] * (1 + 1e-12) + 1e-12).all())
            prev_inc[a] = inc
            share = float(inc.sum() / dsum[a].sum())
            row: dict[str, Any] = {"pool": pool.value, "N": n, "archetype": a.value, "share": share}
            if keep_scenarios:
                row["inc_s"] = inc.tolist()
                row["dsum_s"] = dsum[a].tolist()
            rows.append(row)
            if checks:
                zero = increment(np.zeros_like(g), c, prospects[a]).sum() / dsum[a].sum()
                full = increment(np.full_like(g, 1e9), c, prospects[a]).sum() / dsum[a].sum()
                c4 &= zero == 0.0 and full == 1.0
                c3 = _highs_check(c3, g, c, prospects[a], sites, points, solar_mw, wind_mw, eng, v0)
        if prev_c is not None:
            lhs = matched(g, c) - matched(g, prev_c)
            rhs = increment(g, prev_c, c - prev_c)
            c2 &= bool((np.abs(lhs - rhs) <= 1e-9 * np.maximum(1.0, np.abs(lhs))).all())
        prev_c = c
    out: dict[str, Any] = {"rows": rows, "c1": c1, "c2": c2}
    if checks:
        out.update({"c3": c3, "c4": c4})
    return out


def _gens(points: np.ndarray, solar_mw: float, wind_mw: float, eng: ToyEngine) -> tuple[np.ndarray, np.ndarray]:
    solar = (solar_mw * eng.solar_per_mw).ravel()[points]
    wind = (wind_mw * eng.wind_per_mw).ravel()[points] if wind_mw > 0 else np.zeros(len(points))
    return solar, wind


def _book_values(g: np.ndarray, sites: np.ndarray, points: np.ndarray, solar_mw: float, wind_mw: float,
                 eng: ToyEngine) -> list[float | None]:
    """HiGHS value of the book without the prospect at each check point (None if not optimal)."""
    solar, wind = _gens(points, solar_mw, wind_mw, eng)
    out: list[float | None] = []
    for j in range(len(points)):
        if sites.shape[0] == 0:
            out.append(0.0)
            continue
        r0 = max_matched_value(LAM, PREMIUM, sites[:, j], np.array([solar[j], wind[j]]))
        out.append(r0.value if r0.optimal else None)
    return out


def _highs_check(acc: dict, g: np.ndarray, c: np.ndarray, d: np.ndarray, sites: np.ndarray, points: np.ndarray,
                 solar_mw: float, wind_mw: float, eng: ToyEngine, v0: list[float | None]) -> dict:
    solar, wind = _gens(points, solar_mw, wind_mw, eng)
    gf, cf, df = g.ravel()[points], c.ravel()[points], d.ravel()[points]
    for j in range(len(points)):
        r1 = max_matched_value(LAM, PREMIUM, np.append(sites[:, j], df[j]), np.array([solar[j], wind[j]]))
        acc["checked"] += 1
        if v0[j] is None or not r1.optimal:
            acc["censored"] += 1
            continue
        expected = NU_BAR * min(df[j], max(gf[j] - cf[j], 0.0))
        err = abs((r1.value - v0[j]) - expected)
        acc["max_abs_err"] = max(acc["max_abs_err"], err)
        if err > 1e-7 * max(1.0, abs(r1.value)):
            acc["failures"] += 1
    return acc


def config_unit(job: tuple[Config, str]) -> dict[str, Any]:
    cfg, name = job
    started, cpu0 = time.monotonic(), time.process_time()
    eng = ToyEngine(all_configs(cfg)[name], cfg.toy.scenarios)
    base = name == "base"
    keep = base or name in INVARIANCE
    out: dict[str, Any] = {"config": name}
    p71 = pool_unit(cfg, eng, Pool.P71, keep_scenarios=keep, checks=base)
    rows = p71["rows"]
    out.update({"c1": p71["c1"], "c2": p71["c2"]})
    if base:
        p72 = pool_unit(cfg, eng, Pool.P72, keep_scenarios=True, checks=True)
        rows += p72["rows"]
        out["c1"] &= p72["c1"]
        out["c2"] &= p72["c2"]
        out["c3"] = {k: p71["c3"][k] + p72["c3"][k] if k != "max_abs_err" else max(p71["c3"][k], p72["c3"][k])
                     for k in p71["c3"]}
        out["c4"] = p71["c4"] and p72["c4"]
    cal = calibration(eng)
    out.update({"rows": rows, "calibration": cal, "c6": calibration_ok(cal),
                "seconds": round(time.monotonic() - started, 3), "cpu_seconds": round(time.process_time() - cpu0, 3)})
    return out


# --- summary ---------------------------------------------------------------------------------------------


def shares_table(rows: list[dict[str, Any]], pool: str) -> dict[tuple[int, str], float]:
    return {(r["N"], r["archetype"]): r["share"] for r in rows if r["pool"] == pool}


def dominance(s: dict[tuple[int, str], float], core: tuple[int, ...]) -> float:
    arch = [a.value for a in ARCHETYPES]
    ranges = [max(s[(n, a)] for n in core) - min(s[(n, a)] for n in core) for a in arch]
    spreads = [max(s[(n, a)] for a in arch) - min(s[(n, a)] for a in arch) for n in core]
    return min(ranges) / max(spreads)


def boot_shares(cfg: Config, rows: list[dict[str, Any]], pool: str, weights: np.ndarray) -> dict[tuple[int, str], np.ndarray]:
    """s^(b) for every (N, archetype) of one pool."""
    return {(r["N"], r["archetype"]): (weights @ np.array(r["inc_s"])) / (weights @ np.array(r["dsum_s"]))
            for r in rows if r["pool"] == pool}


def boot_dominance(sb: dict[tuple[int, str], np.ndarray], core: tuple[int, ...]) -> np.ndarray:
    arch = [a.value for a in ARCHETYPES]
    ranges = np.stack([np.max([sb[(n, a)] for n in core], axis=0) - np.min([sb[(n, a)] for n in core], axis=0)
                       for a in arch])
    spreads = np.stack([np.max([sb[(n, a)] for a in arch], axis=0) - np.min([sb[(n, a)] for a in arch], axis=0)
                        for n in core])
    return ranges.min(axis=0) / spreads.max(axis=0)


def _ci(x: np.ndarray) -> list[float]:
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [float(lo), float(hi)]


def verdict(ci: list[float], threshold: float) -> str:
    if ci[0] >= threshold:
        return "holds"
    if ci[1] < threshold:
        return "fails"
    return "inconclusive"


def summarise(cfg: Config, units: dict[str, dict[str, Any]], wall_seconds: float) -> dict[str, Any]:
    an, core = cfg.analysis, cfg.toy.core_books
    s_count = cfg.toy.scenarios
    rng = generator(cfg.seed, 302)
    w = np.stack([np.bincount(rng.integers(0, s_count, s_count), minlength=s_count) for _ in range(an.bootstrap)]
                 ).astype(float)
    base = units["base"]
    s71, s72 = shares_table(base["rows"], "P71"), shares_table(base["rows"], "P72")
    b71, b72 = boot_shares(cfg, base["rows"], "P71", w), boot_shares(cfg, base["rows"], "P72", w)
    r_point, r_ci = dominance(s71, core), _ci(boot_dominance(b71, core))
    # Secondary: shape in the solar-only pool.
    gaps = []
    for n in an.shape_books:
        for hi_a, lo_a in (("office", "24/7"), ("24/7", "evening")):
            diff_b = b72[(n, hi_a)] - b72[(n, lo_a)]
            gaps.append({"N": n, "gap": f"{hi_a} - {lo_a}", "value": s72[(n, hi_a)] - s72[(n, lo_a)], "ci": _ci(diff_b)})
    if all(x["ci"][0] > 0 for x in gaps):
        rank = "holds"
    elif any(x["ci"][1] < 0 for x in gaps):
        rank = "fails"
    else:
        rank = "inconclusive"
    n = an.gap_book
    gap_gbp_b = NU_BAR * (b72[(n, "office")] - b72[(n, "evening")])
    gap_gbp = NU_BAR * (s72[(n, "office")] - s72[(n, "evening")])
    gap_ci = _ci(gap_gbp_b)
    # Controls.
    c5 = {}
    for name in INVARIANCE:
        inv = units[name]
        ib = boot_shares(cfg, inv["rows"], "P71", w)
        si = shares_table(inv["rows"], "P71")
        worst = 0.0
        ok = True
        for nn in core:
            for a in ARCHETYPES:
                key = (nn, a.value)
                se = float((ib[key] - b71[key]).std(ddof=1))
                z = abs(si[key] - s71[key]) / se if se > 0 else (0.0 if si[key] == s71[key] else math.inf)
                worst = max(worst, z)
                ok &= z < an.invariance_se
        c5[name] = {"max_abs_z": worst, "ok": ok}
    config_units = list(units.values())
    caps_ok = all(u["seconds"] <= cfg.run.config_cap_s for u in config_units) and wall_seconds <= cfg.run.wall_cap_s
    controls = {"C1": all(u["c1"] for u in config_units), "C2": all(u["c2"] for u in config_units),
                "C3": base["c3"]["failures"] == 0, "C4": base["c4"], "C5": all(v["ok"] for v in c5.values()),
                "C6": all(u["c6"] for u in config_units)}
    censored = base["c3"]["censored"]
    # Descriptive.
    arch = [a.value for a in ARCHETYPES]
    reversal = next((nn for nn in cfg.toy.books if nn > 0 and s71[(nn, "24/7")] > s71[(nn, "office")]), None)

    def rmse(table: NoteTable, s: dict) -> tuple[float, list[dict]]:
        cells = []
        for i, nn in enumerate(table.books):
            for a in arch:
                note = getattr(table, NOTE_KEYS[a])[i]
                cells.append({"N": nn, "archetype": a, "model": 100 * s[(nn, a)], "note": note,
                              "diff": 100 * s[(nn, a)] - note})
        return float(np.sqrt(np.mean([c["diff"] ** 2 for c in cells]))), cells

    rmse71, cells71 = rmse(cfg.table_7_1, s71)
    rmse72, cells72 = rmse(cfg.table_7_2, s72)
    fit = {}
    for t in an.theta_fit:
        name = "base" if t == BASE.theta_s else f"fit-theta_s={t}"
        if name in units:
            fit[str(t)] = rmse(cfg.table_7_1, shares_table(units[name]["rows"], "P71"))[0]
    oat = {nm: dominance(shares_table(units[nm]["rows"], "P71"), core) for nm, _ in oat_configs() if nm in units}
    lhs = {nm: dominance(shares_table(units[nm]["rows"], "P71"), core) for nm in units if nm.startswith("lhs-")}
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "controls": controls,
        "controls_pass": all(controls.values()) and caps_ok and censored == 0,
        "caps_ok": caps_ok,
        "R": r_point,
        "R_ci": r_ci,
        "dominance_threshold": an.dominance_threshold,
        "shares_P71": [{"N": nn, **{a: s71[(nn, a)] for a in arch}} for nn in cfg.toy.books],
        "shares_P72": [{"N": nn, **{a: s72[(nn, a)] for a in arch}} for nn in cfg.toy.books],
        "shape_rank_solar": {"verdict": rank, "gaps": gaps},
        "shape_gap_vs_markup": {"verdict": verdict(gap_ci, an.markup_floor_gbp), "gap_gbp_per_mwh": gap_gbp,
                                "ci": gap_ci, "floor": an.markup_floor_gbp},
        "rank_reversal_71": reversal,
        "solar_R": dominance(s72, core),
        "solar_R_ci": _ci(boot_dominance(b72, core)),
        "standalone_vs_marginal": {a: s71[(0, a)] / s71[(an.standalone_book, a)] for a in arch},
        "note_tables": {"rmse_7_1_pp": rmse71, "rmse_7_2_pp": rmse72, "cells_7_1": cells71, "cells_7_2": cells72,
                        "theta_fit_rmse": fit, "best_theta": min(fit, key=fit.get) if fit else None},
        "thin_vs_saturated_value": {"model_gbp": [SITE_MWH * NU_BAR * s71[(nn, "office")] for nn in an.value_books],
                                    "note_gbp": list(an.note_values_gbp), "books": list(an.value_books)},
        "robustness": {"oat_R": oat, "lhs_R": lhs,
                       "lhs_share_dominant": float(np.mean([v >= an.dominance_threshold for v in lhs.values()]))},
        "c3": base["c3"],
        "c5": c5,
        "calibration_base": base["calibration"],
        "unit_seconds": {k: v["seconds"] for k, v in units.items()},
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


RULES: list[Rule[dict]] = [
    Rule("invalid", "any control fails", "debug, record a deviation, re-run", lambda s: not s["controls_pass"]),
    Rule("congestion-dominant", "CI lower(R) ≥ 2", "run x04; carry the result to G1",
         lambda s: s["R_ci"][0] >= s["dominance_threshold"]),
    Rule("congestion-larger", "CI lower(R) ≥ 1",
         "run x04; G1 records congestion as larger than shape, but not dominant", lambda s: s["R_ci"][0] >= 1.0),
    Rule("shape-comparable", "CI upper(R) < 1", "run x04; G1 records shape as at least comparable to congestion",
         lambda s: s["R_ci"][1] < 1.0),
    Rule("inconclusive", "otherwise", "run x04; G1", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started = time.monotonic()
    names = list(all_configs(cfg))
    done = ctx.done_keys()
    pending = [n for n in names if f"unit|{n}" not in done]
    for (_, name), result in parallel_map(config_unit, [(cfg, n) for n in pending], workers=ctx.workers):
        for r in result["rows"]:
            ctx.append_record({"key": f"row|{name}|{r['pool']}|N{r['N']:03d}|{r['archetype']}", "config": name, **r})
        ctx.append_record({"key": f"unit|{name}", **{k: v for k, v in result.items() if k != "rows"}})
        ctx.save_checkpoint("units", {"done": sorted(k.removeprefix("unit|") for k in ctx.done_keys()
                                                      if k.startswith("unit|"))})
    records = ctx.read_records()
    units: dict[str, dict[str, Any]] = {}
    for r in records:
        if r["key"].startswith("unit|"):
            name = r["key"].removeprefix("unit|")
            units[name] = {**r, "rows": [x for x in records if x["key"].startswith(f"row|{name}|")]}
    summary = summarise(cfg, units, time.monotonic() - started)
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=sum(u.get("cpu_seconds", 0.0) for u in units.values()))
    print(f"{EXPERIMENT}: {summary['class']} (R = {summary['R']:.3f}, CI {summary['R_ci']}); shape-rank-solar: "
          f"{summary['shape_rank_solar']['verdict']}; shape-gap-vs-markup: {summary['shape_gap_vs_markup']['verdict']}; "
          f"run {ctx.run_dir}")
    return 0
