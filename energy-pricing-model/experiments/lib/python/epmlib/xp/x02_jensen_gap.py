"""x02-jensen-gap: where the mean-shape overstatement of matched volume peaks, and whether point
forecasts underprice a prospect.

Registered in PREREG.md (bcd483e); toy v1 from plans/toy_v1_spec.md (26abb27)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

from ..config import build, section
from ..outcomes import Rule, first_match, otherwise
from ..rng import generator
from ..runlib import RunStatus, open_run, parallel_map, parse_args
from ..toy import ARCHETYPES, BASE, KAPPA, NU_BAR, Pool, ToyEngine, ToyParams, calibration, calibration_ok
from ..toy.matching import increment, jensen_terms, point_share, resampled_overstatement
from ..toy.spec import INVARIANCE_CELLS, P71_MWH, SITE_MWH, invariance_configs, lhs_configs, oat_configs

EXPERIMENT = "x02-jensen-gap"


@dataclass(frozen=True)
class Toy:
    spec: str
    scenarios: int
    books: tuple[int, ...]


@dataclass(frozen=True)
class Analysis:
    balance_band: tuple[float, float]
    class_probability: float
    local_peak_fraction: float
    bootstrap: int
    secondary_books: tuple[int, ...]
    magnitude_books: tuple[int, ...]
    note_magnitudes_percent: tuple[float, ...]
    note_range_percent: tuple[float, float]
    theta_sweep: tuple[float, ...]
    phantom_book: int
    note_phantom_gbp: float
    finite_s_books: tuple[int, ...]
    finite_s_abs_pp: float
    finite_s_rel: float
    invariance_se: float


@dataclass(frozen=True)
class Checker:
    gaussian_mu_over_d: tuple[float, ...]
    gaussian_sd_over_d: float
    gaussian_scenarios: int
    gaussian_halfhours: int
    replications: int
    se_multiple: float


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
    checker: Checker
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    return Config(seed=int(section(data, "experiment")["seed"]),
                  toy=build(Toy, section(data, "toy"), where="toy"),
                  analysis=build(Analysis, section(data, "analysis"), where="analysis"),
                  checker=build(Checker, section(data, "checker"), where="checker"),
                  run=build(RunCfg, section(data, "run"), where="run"))


INVARIANCE = tuple(name for name, _ in INVARIANCE_CELLS)
SPECIAL = {
    "base": BASE,
    "theta_s=0": BASE.with_(theta_s=0.0),
    "theta_s=1": BASE.with_(theta_s=1.0),
    "gen-noise-only": BASE.with_(s_i=0.0, s_cm=0.0),
    "demand-noise-only": BASE.with_(generation="mean"),
    "zero-noise": BASE.with_(s_c=0.0, s_w=0.0, s_i=0.0, s_cm=0.0),
}


def all_configs() -> dict[str, ToyParams]:
    out = dict(SPECIAL)
    for name, p in oat_configs() + lhs_configs() + invariance_configs():
        out[name] = p
    return out


def ratio(n: int) -> float:
    return P71_MWH / (SITE_MWH * n)


def bootstrap_weights(cfg: Config) -> np.ndarray:
    s = cfg.toy.scenarios
    rng = generator(cfg.seed, 202)
    return np.stack([np.bincount(rng.integers(0, s, s), minlength=s) for _ in range(cfg.analysis.bootstrap)]
                    ).astype(float)


def config_unit(cfg: Config, name: str) -> dict[str, Any]:
    started, cpu0 = time.monotonic(), time.process_time()
    params = all_configs()[name]
    s_count = cfg.toy.scenarios
    eng = ToyEngine(params, s_count)
    g = eng.generation(Pool.P71)
    eg = eng.expected_generation(Pool.P71)
    g_mean = g.mean(axis=0)
    boot = name == "base" or name in INVARIANCE
    secondary = name == "base"
    w = bootstrap_weights(cfg) if boot else None
    g_b = w @ g / s_count if boot else None
    prospects = {a: np.minimum(eng.prospect_demand(a), KAPPA) for a in ARCHETYPES} if secondary else {}
    rows, boot_o, sec = [], [], []
    c1 = True
    for n, c, _ in eng.books(cfg.toy.books):
        c_mean = c.mean(axis=0)
        per_hh = np.minimum(g, c)
        c1 &= bool((np.minimum(g_mean, c_mean) >= per_hh.mean(axis=0) - 1e-12).all())
        m_s = per_hh.sum(axis=1)
        point, m_bar = jensen_terms(g, c)
        o = (point - m_bar) / m_bar
        o_an = (float(np.minimum(eg, eng.expected_book(n)).sum()) - m_bar) / m_bar
        rows.append({"N": n, "r": ratio(n), "O": o, "O_an": o_an, "point_mwh": point, "matched_mwh": m_bar})
        if boot:
            c_b = w @ c / s_count
            boot_o.append(resampled_overstatement(g_b, c_b, w, m_s))
            if secondary and n in cfg.analysis.secondary_books:
                for a in ARCHETYPES:
                    d = prospects[a]
                    inc_s, dsum_s = increment(g, c, d), d.sum(axis=1)
                    s_true = float(inc_s.sum() / dsum_s.sum())
                    s_pt = point_share(g_mean, c_mean, d.mean(axis=0))
                    d_b = w @ d / s_count
                    s_pt_b = np.minimum(d_b, np.maximum(g_b - c_b, 0.0)).sum(axis=1) / d_b.sum(axis=1)
                    diff_b = s_pt_b - (w @ inc_s) / (w @ dsum_s)
                    lo, hi = np.percentile(diff_b, [2.5, 97.5])
                    sec.append({"N": n, "archetype": a.value, "s_point": s_pt, "s_true": s_true,
                                "diff": s_pt - s_true, "ci": [float(lo), float(hi)]})
    cal = calibration(eng)
    out: dict[str, Any] = {"config": name, "rows": rows, "c1": c1, "calibration": cal, "c6": calibration_ok(cal),
                           "secondary": sec,
                           "boot_O": np.array(boot_o).T.tolist() if boot else None,  # (B, books)
                           "seconds": round(time.monotonic() - started, 3),
                           "cpu_seconds": round(time.process_time() - cpu0, 3)}
    return out


def expected_min(mu: float, sd: float, d: float) -> float:
    """E min(X, d) for X ~ N(mu, sd²)."""
    a = (mu - d) / sd
    return mu - sd * norm.pdf(a) - (mu - d) * norm.cdf(a)


def _z(diff: float, se: float) -> float:
    """diff/se. When every replication gives the same value (se = 0, e.g. the resampled mean
    shape never crosses D), "within k standard errors" means equal up to float rounding."""
    if se > 0:
        return diff / se
    return 0.0 if abs(diff) <= 1e-12 else math.inf


def checker_unit(cfg: Config) -> dict[str, Any]:
    """C3: the estimator on Gaussian G and constant D against the closed form."""
    started, cpu0 = time.monotonic(), time.process_time()
    ch = cfg.checker
    results = []
    for j, mu in enumerate(ch.gaussian_mu_over_d):
        sd, d = ch.gaussian_sd_over_d, 1.0
        points, means = [], []
        for r in range(ch.replications):
            rng = generator(cfg.seed, 203, j, r)
            g = mu + sd * rng.standard_normal((ch.gaussian_scenarios, ch.gaussian_halfhours))
            point, m_bar = jensen_terms(g, np.full_like(g, d))
            points.append(point / ch.gaussian_halfhours)
            means.append(m_bar / ch.gaussian_halfhours)
        points, means = np.array(points), np.array(means)
        want_point = expected_min(mu, sd / math.sqrt(ch.gaussian_scenarios), d)
        want_mean = expected_min(mu, sd, d)
        se_p = points.std(ddof=1) / math.sqrt(len(points))
        se_m = means.std(ddof=1) / math.sqrt(len(means))
        z_p = _z(points.mean() - want_point, se_p)
        z_m = _z(means.mean() - want_mean, se_m)
        results.append({"mu_over_d": mu, "point": float(points.mean()), "point_closed_form": want_point,
                        "z_point": float(z_p), "matched": float(means.mean()), "matched_closed_form": want_mean,
                        "z_matched": float(z_m),
                        "ok": abs(z_p) <= ch.se_multiple and abs(z_m) <= ch.se_multiple})
    return {"config": "checker", "results": results, "c3": all(r["ok"] for r in results),
            "seconds": round(time.monotonic() - started, 3), "cpu_seconds": round(time.process_time() - cpu0, 3)}


def run_unit(job: tuple[Config, str]) -> dict[str, Any]:
    cfg, name = job
    return checker_unit(cfg) if name == "checker" else config_unit(cfg, name)


def peaks(rs: list[float], os_: list[float], fraction: float) -> dict[str, Any]:
    j = int(np.argmax(os_))
    top = os_[j]
    local = [rs[i] for i in range(1, len(os_) - 1)
             if os_[i] > os_[i - 1] and os_[i] > os_[i + 1] and os_[i] >= fraction * top]
    return {"r_peak": rs[j], "O_max": top, "edge": j in (0, len(os_) - 1), "local_peaks": local}


def summarise(cfg: Config, units: dict[str, dict[str, Any]], wall_seconds: float) -> dict[str, Any]:
    an = cfg.analysis
    lo_b, hi_b = an.balance_band
    base = units["base"]
    rows = sorted(base["rows"], key=lambda r: r["N"])
    rs, os_ = [r["r"] for r in rows], [r["O"] for r in rows]
    pk = peaks(rs, os_, an.local_peak_fraction)
    boot = np.array(base["boot_O"])  # (B, books), columns in ascending N
    r_arr = np.array(rs)
    r_peak_b = r_arr[np.argmax(boot, axis=1)]
    p_b = {"balance": float(np.mean((r_peak_b >= lo_b) & (r_peak_b <= hi_b))),
           "above": float(np.mean(r_peak_b > hi_b)), "below": float(np.mean(r_peak_b < lo_b))}
    # Controls.
    zero = units["zero-noise"]
    c2 = all(abs(r["O"]) <= 1e-12 for r in zero["rows"])
    c4_detail = {}
    for name in INVARIANCE:
        inv = units[name]
        inv_rows = sorted(inv["rows"], key=lambda r: r["N"])
        diff_b = np.array(inv["boot_O"]) - boot
        se = diff_b.std(axis=0, ddof=1)
        diffs = np.array([a["O"] - b["O"] for a, b in zip(inv_rows, rows)])
        c4_detail[name] = {"max_abs_z": float(np.max(np.abs(diffs) / se)),
                           "ok": bool((np.abs(diffs) < an.invariance_se * se).all())}
    c5_detail = []
    for r in rows:
        if r["N"] in an.finite_s_books:
            limit = max(an.finite_s_abs_pp / 100.0, an.finite_s_rel * r["O"])
            c5_detail.append({"N": r["N"], "O": r["O"], "O_an": r["O_an"], "ok": abs(r["O"] - r["O_an"]) <= limit})
    config_units = {k: v for k, v in units.items() if k != "checker"}
    caps_ok = all(u["seconds"] <= cfg.run.config_cap_s for u in units.values()) and wall_seconds <= cfg.run.wall_cap_s
    controls = {"C1": all(u["c1"] for u in config_units.values()), "C2": c2, "C3": units["checker"]["c3"],
                "C4": all(d["ok"] for d in c4_detail.values()), "C5": all(d["ok"] for d in c5_detail),
                "C6": all(u["c6"] for u in config_units.values())}
    # Secondary.
    sec = base["secondary"]
    if all(x["ci"][0] >= 0 for x in sec):
        secondary = "holds"
    elif any(x["ci"][1] < 0 for x in sec):
        secondary = "fails"
    else:
        secondary = "inconclusive"
    # Descriptive.
    def peak_of(name: str) -> dict[str, Any]:
        rr = sorted(units[name]["rows"], key=lambda r: r["N"])
        return peaks([r["r"] for r in rr], [r["O"] for r in rr], an.local_peak_fraction)
    mix_names = {0.0: "theta_s=0", 0.25: "theta_s=0.25", 0.5: "base", 0.75: "theta_s=0.75", 1.0: "theta_s=1"}
    by_n = {r["N"]: r for r in rows}
    in_range = [r["O"] for r in rows if 0.5 <= r["r"] <= 1.6]
    lhs_names = [n for n in units if n.startswith("lhs-")]
    lhs_peaks = {n: peak_of(n)["r_peak"] for n in lhs_names}
    oat_names = [n for n, _ in oat_configs() if n in units]
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "controls": controls,
        "controls_pass": all(controls.values()) and caps_ok,
        "caps_ok": caps_ok,
        "balance_band": [lo_b, hi_b],
        "class_probability": an.class_probability,
        "curve": [{"N": r["N"], "r": r["r"], "O": r["O"], "O_an": r["O_an"]} for r in rows],
        **pk,
        "P_B": p_b,
        "secondary": {"verdict": secondary, "cells": sec},
        "peak_vs_mix": {str(t): peak_of(n) for t, n in mix_names.items() if n in units},
        "magnitude": [{"N": n, "r": ratio(n), "O": by_n[n]["O"], "note_percent": v}
                      for n, v in zip(an.magnitude_books, an.note_magnitudes_percent)],
        "range_r_0.5_1.6": [min(in_range), max(in_range)] if in_range else None,
        "note_range_percent": list(an.note_range_percent),
        "balance_ratio_N30": by_n[30]["O"] / pk["O_max"] if 30 in by_n else None,
        "noise_source": {n: {str(r["N"]): r["O"] for r in units[n]["rows"]}
                         for n in ("gen-noise-only", "demand-noise-only")},
        "phantom_margin_gbp": NU_BAR * (by_n[an.phantom_book]["point_mwh"] - by_n[an.phantom_book]["matched_mwh"]),
        "note_phantom_gbp": an.note_phantom_gbp,
        "robustness": {"oat": {n: peak_of(n)["r_peak"] for n in oat_names},
                       "lhs": lhs_peaks,
                       "lhs_share_in_band": float(np.mean([lo_b <= v <= hi_b for v in lhs_peaks.values()]))},
        "c3": units["checker"]["results"],
        "c4": c4_detail,
        "c5": c5_detail,
        "calibration_base": base["calibration"],
        "unit_seconds": {k: v["seconds"] for k, v in units.items()},
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


def _band(s: dict) -> tuple[float, float]:
    return s["balance_band"][0], s["balance_band"][1]


RULES: list[Rule[dict]] = [
    Rule("invalid", "any control fails", "debug, record a deviation, re-run", lambda s: not s["controls_pass"]),
    Rule("peak-at-balance", "r_peak ∈ B and P_B(B) ≥ 0.8", "run x03; carry the result to G1",
         lambda s: _band(s)[0] <= s["r_peak"] <= _band(s)[1] and s["P_B"]["balance"] >= s["class_probability"]),
    Rule("peak-above-balance", "r_peak > 1.33 and P_B(r > 1.33) ≥ 0.8",
         "run x03; G1 records the note's \"peaks at balance\" as refuted in toy v1",
         lambda s: s["r_peak"] > _band(s)[1] and s["P_B"]["above"] >= s["class_probability"]),
    Rule("peak-below-balance", "r_peak < 0.75 and P_B(r < 0.75) ≥ 0.8",
         "run x03; G1 records the note's \"peaks at balance\" as refuted in toy v1",
         lambda s: s["r_peak"] < _band(s)[0] and s["P_B"]["below"] >= s["class_probability"]),
    Rule("multimodal", "local peaks lie both above 1.33 and below 0.75", "run x03; G1",
         lambda s: any(r > _band(s)[1] for r in s["local_peaks"]) and any(r < _band(s)[0] for r in s["local_peaks"])),
    Rule("inconclusive", "otherwise", "run x03; G1 decides whether to register a larger S", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started = time.monotonic()
    names = ["base", *[n for n in all_configs() if n != "base"], "checker"]
    done = ctx.done_keys()
    pending = [n for n in names if f"unit|{n}" not in done]
    for (_, name), result in parallel_map(run_unit, [(cfg, n) for n in pending], workers=ctx.workers):
        if name != "checker":
            for r in result["rows"]:
                ctx.append_record({"key": f"row|{name}|N{r['N']:03d}", "config": name, **r})
        if result.get("boot_O") is not None:
            ctx.save_checkpoint(f"bootstrap_{name}", {"books": list(cfg.toy.books), "O": result["boot_O"]})
        meta = {k: v for k, v in result.items() if k not in ("rows", "boot_O")}
        ctx.append_record({"key": f"unit|{name}", **meta})
        ctx.save_checkpoint("units", {"done": sorted(k.removeprefix("unit|") for k in ctx.done_keys()
                                                      if k.startswith("unit|"))})
    records = ctx.read_records()
    units: dict[str, dict[str, Any]] = {}
    for r in records:
        if r["key"].startswith("unit|"):
            name = r["key"].removeprefix("unit|")
            units[name] = dict(r)
            if name != "checker":
                units[name]["rows"] = [x for x in records if x["key"].startswith(f"row|{name}|")]
                cp = ctx.load_checkpoint(f"bootstrap_{name}")
                units[name]["boot_O"] = cp["O"] if cp else None
    summary = summarise(cfg, units, time.monotonic() - started)
    unit_cpu = sum(u.get("cpu_seconds", 0.0) for u in units.values())
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=unit_cpu)
    print(f"{EXPERIMENT}: {summary['class']} (r_peak = {summary['r_peak']:.3f}, O_max = {summary['O_max']:.4f}, "
          f"P_B = {summary['P_B']}); pointforecast-underprices: {summary['secondary']['verdict']}; run {ctx.run_dir}")
    return 0
