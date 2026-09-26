"""x05-confounded-elasticity: is the naive logit on historical quotes biased toward inelasticity, and
does randomised pricing pay?

Registered in PREREG.md (222aa9e)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from ..config import build, section
from ..elasticity import Market, deployed_prices, ips_segment_values, logit_irls, plim_slope
from ..outcomes import Rule, first_match, otherwise
from ..rng import generator
from ..runlib import RunStatus, open_run, parallel_map, parse_args

EXPERIMENT = "x05-confounded-elasticity"
CHUNK = 100


@dataclass(frozen=True)
class MarketCfg:
    segment_bases: tuple[float, ...]
    beta: float
    tau_u: float
    tau_zeta: float
    c_hat: float
    quadrature_nodes: int


@dataclass(frozen=True)
class Pipelines:
    historical_quotes: int
    logging_quotes: int
    exploit_quotes: int
    jitter_sigmas: tuple[float, ...]
    primary_sigma: float
    grid_offsets: tuple[float, ...]
    mirage_min_slope: float
    mirage_markup: float
    irls_max_iter: int
    irls_tol: float


@dataclass(frozen=True)
class Grid:
    rhos: tuple[float, ...]
    replications: int
    oat_rhos: tuple[float, ...]
    oat_tau_u: tuple[float, ...]
    oat_tau_zeta: tuple[float, ...]
    oat_logging_quotes: tuple[int, ...]


@dataclass(frozen=True)
class Checker:
    ips_logs: int
    ips_offsets: tuple[float, ...]
    positive_control_quotes: int
    positive_control_halfwidth: float
    simulator_quotes: int
    simulator_offsets: tuple[float, ...]
    oracle_grid_step: float
    se_multiple_c1: float
    se_multiple_c4: float


@dataclass(frozen=True)
class RunCfg:
    workers: int
    max_censored_fraction: float
    wall_cap_s: float


@dataclass(frozen=True)
class Config:
    seed: int
    market: MarketCfg
    pipelines: Pipelines
    grid: Grid
    checker: Checker
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    return Config(seed=int(section(data, "experiment")["seed"]),
                  market=build(MarketCfg, section(data, "market"), where="market"),
                  pipelines=build(Pipelines, section(data, "pipelines"), where="pipelines"),
                  grid=build(Grid, section(data, "grid"), where="grid"),
                  checker=build(Checker, section(data, "checker"), where="checker"),
                  run=build(RunCfg, section(data, "run"), where="run"))


@dataclass(frozen=True)
class Variant:
    name: str
    market: MarketCfg
    logging_quotes: int
    rhos: tuple[float, ...]
    sigmas: tuple[float, ...]
    with_rg: bool


def variants(cfg: Config) -> list[Variant]:
    main = Variant("main", cfg.market, cfg.pipelines.logging_quotes, cfg.grid.rhos, cfg.pipelines.jitter_sigmas, True)
    out = [main]
    prim = (cfg.pipelines.primary_sigma,)
    for t in cfg.grid.oat_tau_u:
        out.append(Variant(f"tau_u={t}", replace(cfg.market, tau_u=t), cfg.pipelines.logging_quotes, cfg.grid.oat_rhos, prim, False))
    for t in cfg.grid.oat_tau_zeta:
        out.append(Variant(f"tau_zeta={t}", replace(cfg.market, tau_zeta=t), cfg.pipelines.logging_quotes, cfg.grid.oat_rhos, prim, False))
    for n in cfg.grid.oat_logging_quotes:
        out.append(Variant(f"n_log={n}", cfg.market, n, cfg.grid.oat_rhos, prim, False))
    return out


def market_of(m: MarketCfg) -> Market:
    return Market(tuple(m.segment_bases), m.beta, m.tau_u, m.tau_zeta, m.c_hat, m.quadrature_nodes)


def beta_marg(market: Market) -> float:
    """The naive slope's probability limit at ρ = 0: the logit fitted to P_x(p) over the desk's
    ζ-spread around its plug-in price at p_ref = base(x)."""
    z, w = np.polynomial.hermite.hermgauss(market.nodes)
    seg, prices, weights = [], [], []
    for x, base in enumerate(market.bases):
        p0 = float(market.plug_prices(np.array([base]))[0])
        seg += [x] * len(z)
        prices += list(p0 + market.tau_zeta * math.sqrt(2.0) * z)
        weights += list(w / math.sqrt(math.pi) / market.n_segments)
    fit = plim_slope(market, np.array(seg), np.array(prices), np.array(weights))
    return fit.b


# --- one replication -----------------------------------------------------------------------------------


def replicate(cfg: Config, var: Variant, rho_idx: int, r: int, market: Market, v_oracle: float) -> dict[str, Any]:
    pl, m = cfg.pipelines, market
    rho = cfg.grid.rhos[rho_idx]
    rng = generator(cfg.seed, 105, rho_idx, r)
    n_h, n_l, n_e = pl.historical_quotes, var.logging_quotes, pl.exploit_quotes
    bases = np.asarray(m.bases)
    # History from the desk.
    xh = rng.integers(0, m.n_segments, n_h)
    uh = rng.normal(0.0, m.tau_u, n_h)
    eta = rng.standard_normal(n_h)
    zeta = rng.normal(0.0, m.tau_zeta, n_h)
    uw_h = rng.random(n_h)
    belief = rho ** 2 * (uh + m.tau_u * math.sqrt(1.0 / rho ** 2 - 1.0) * eta) if rho > 0 else np.zeros(n_h)
    p_hist = m.plug_prices(bases[xh] + belief) + zeta
    win_h = (uw_h < m.win_prob(xh, uh, p_hist)).astype(float)
    # The horizon, shared by every pipeline.
    n_t = n_l + n_e
    xt = rng.integers(0, m.n_segments, n_t)
    ut = rng.normal(0.0, m.tau_u, n_t)
    uw_t = rng.random(n_t)
    eps = generator(cfg.seed, 106, rho_idx, r).standard_normal(n_l)
    offs_idx = generator(cfg.seed, 107, rho_idx, r).integers(0, len(pl.grid_offsets), n_l)
    xl, ul, uwl = xt[:n_l], ut[:n_l], uw_t[:n_l]
    xe = xt[n_l:]

    rec: dict[str, Any] = {"key": f"rep|{var.name}|rho{rho_idx}|r{r:04d}", "variant": var.name, "rho": rho, "r": r}
    fit_nv = logit_irls(xh, p_hist, win_h, m.n_segments, max_iter=pl.irls_max_iter, tol=pl.irls_tol)
    rec["nv_converged"] = fit_nv.converged
    if not fit_nv.converged:
        return rec
    p_nv = deployed_prices(fit_nv, m, mirage_min_slope=pl.mirage_min_slope, mirage_markup=pl.mirage_markup)
    v_nv_log = m.value(xl, p_nv[xl])
    h_nv = float(np.sum(m.value(xt, p_nv[xt]))) / (n_t * v_oracle)
    rec.update({"b_nv": fit_nv.b, "p_nv": p_nv.tolist(), "h_nv": h_nv,
                "loss_nv": 1.0 - float(np.mean(m.value(np.arange(m.n_segments), p_nv))) / v_oracle,
                "mirage_nv": fit_nv.b <= pl.mirage_min_slope})
    for sj in var.sigmas:
        pl_prices = p_nv[xl] + sj * eps
        win_l = (uwl < m.win_prob(xl, ul, pl_prices)).astype(float)
        fit = logit_irls(xl, pl_prices, win_l, m.n_segments, max_iter=pl.irls_max_iter, tol=pl.irls_tol)
        tag = f"rl{sj:g}"
        rec[f"{tag}_converged"] = fit.converged
        if not fit.converged:
            continue
        p_rl = deployed_prices(fit, m, mirage_min_slope=pl.mirage_min_slope, mirage_markup=pl.mirage_markup)
        v_log = m.value(xl, pl_prices)
        h = (float(np.sum(v_log)) + float(np.sum(m.value(xe, p_rl[xe])))) / (n_t * v_oracle)
        rec.update({f"{tag}_b": fit.b, f"{tag}_delta": 100.0 * (h - h_nv),
                    f"{tag}_jitter_loss": 1.0 - float(np.mean(v_log)) / float(np.mean(v_nv_log))})
    if var.with_rg:
        offsets = np.asarray(pl.grid_offsets)
        pg = p_nv[xl] + offsets[offs_idx]
        win_g = (uwl < m.win_prob(xl, ul, pg)).astype(float)
        ips = ips_segment_values(xl, offs_idx, win_g, pg, m.c_hat, m.n_segments, len(offsets))
        p_rg = p_nv + offsets[np.argmax(ips, axis=1)]
        h = (float(np.sum(m.value(xl, pg))) + float(np.sum(m.value(xe, p_rg[xe])))) / (n_t * v_oracle)
        rec["rg_delta"] = 100.0 * (h - h_nv)
    return rec


def rep_unit(job: tuple[Config, str, int, int, int]) -> dict[str, Any]:
    cfg, var_name, rho_idx, start, stop = job
    cpu0 = time.process_time()
    var = next(v for v in variants(cfg) if v.name == var_name)
    market = market_of(var.market)
    v_o = market.oracle_value
    recs = [replicate(cfg, var, rho_idx, r, market, v_o) for r in range(start, stop)]
    return {"unit": f"{var_name}|rho{rho_idx}|{start:04d}", "records": recs, "cpu_seconds": time.process_time() - cpu0}


# --- controls ------------------------------------------------------------------------------------------------


def control_unit(job: tuple[Config, str]) -> dict[str, Any]:
    cfg, which = job
    cpu0 = time.process_time()
    m = market_of(cfg.market)
    ch = cfg.checker
    offsets = np.asarray(cfg.pipelines.grid_offsets)
    out: dict[str, Any] = {"unit": f"control|{which}"}
    if which == "C1":
        base = m.oracle_prices
        results = []
        estimates = {t: [] for t in ch.ips_offsets}
        for i in range(ch.ips_logs):
            rng = generator(cfg.seed, 108, i)
            n = cfg.pipelines.logging_quotes
            x = rng.integers(0, m.n_segments, n)
            u = rng.normal(0.0, m.tau_u, n)
            idx = rng.integers(0, len(offsets), n)
            p = base[x] + offsets[idx]
            win = (rng.random(n) < m.win_prob(x, u, p)).astype(float)
            reward = win * (p - m.c_hat)
            for t in ch.ips_offsets:
                j = int(np.flatnonzero(offsets == t)[0])
                estimates[t].append(len(offsets) * float(np.mean(reward * (idx == j))))
        for t in ch.ips_offsets:
            est = np.array(estimates[t])
            truth = float(np.mean(m.value(np.arange(m.n_segments), base + t)))
            se = float(est.std(ddof=1) / math.sqrt(len(est)))
            z = (est.mean() - truth) / se
            results.append({"offset": t, "mean": float(est.mean()), "truth": truth, "z": float(z),
                            "ok": abs(z) <= ch.se_multiple_c1})
        out.update({"results": results, "ok": all(r["ok"] for r in results)})
    elif which == "C2":
        res = []
        for label, market in (("tau_u=3", m), ("tau_u=0", replace(m, tau_u=0.0))):
            rng = generator(cfg.seed, 109, 0 if label == "tau_u=3" else 1)
            n, hw = ch.positive_control_quotes, ch.positive_control_halfwidth
            base = market.oracle_prices
            x = rng.integers(0, m.n_segments, n)
            p = base[x] + rng.uniform(-hw, hw, n)
            u = rng.normal(0.0, market.tau_u, n) if market.tau_u > 0 else np.zeros(n)
            win = (rng.random(n) < market.win_prob(x, u, p)).astype(float)
            fit = logit_irls(x, p, win, m.n_segments, max_iter=200, tol=1e-12)
            gl_x, gl_w = np.polynomial.legendre.leggauss(64)
            seg = np.repeat(np.arange(m.n_segments), len(gl_x))
            prices = np.concatenate([b + hw * gl_x for b in base])
            weights = np.tile(gl_w / 2.0, m.n_segments) / m.n_segments
            target = plim_slope(market, seg, prices, weights).b if market.tau_u > 0 else market.beta
            z = (fit.b - target) / fit.se_b
            res.append({"case": label, "b_hat": fit.b, "se": fit.se_b, "target": target, "z": float(z),
                        "ok": fit.converged and abs(z) <= 3.0})
        out.update({"results": res, "ok": all(r["ok"] for r in res)})
    elif which == "C4":
        rng = generator(cfg.seed, 110)
        n = ch.simulator_quotes
        base = m.oracle_prices
        x = rng.integers(0, m.n_segments, n)
        k = rng.integers(0, len(ch.simulator_offsets), n)
        p = base[x] + np.asarray(ch.simulator_offsets)[k]
        u = rng.normal(0.0, m.tau_u, n)
        win = rng.random(n) < m.win_prob(x, u, p)
        cells = []
        for s in range(m.n_segments):
            for j, off in enumerate(ch.simulator_offsets):
                sel = (x == s) & (k == j)
                rate = float(win[sel].mean())
                want = float(m.pop_prob(np.array(s), np.array(base[s] + off)))
                se = math.sqrt(want * (1 - want) / sel.sum())
                cells.append({"segment": s, "offset": off, "rate": rate, "want": want, "z": (rate - want) / se,
                              "ok": abs(rate - want) <= ch.se_multiple_c4 * se})
        out.update({"results": cells, "ok": all(c["ok"] for c in cells)})
    elif which == "C5":
        res = []
        for s in range(m.n_segments):
            grid = np.arange(m.c_hat, m.c_hat + 40.0, ch.oracle_grid_step)
            vals = m.value(np.full(len(grid), s), grid)
            p_grid = float(grid[int(np.argmax(vals))])
            res.append({"segment": s, "oracle": float(m.oracle_prices[s]), "grid": p_grid,
                        "ok": abs(p_grid - m.oracle_prices[s]) <= 2 * ch.oracle_grid_step})
        out.update({"results": res, "ok": all(r["ok"] for r in res)})
    out["cpu_seconds"] = time.process_time() - cpu0
    return out


def run_unit(job: tuple) -> dict[str, Any]:
    return control_unit(job) if len(job) == 2 else rep_unit(job)  # (cfg, "C1") or (cfg, variant, ρ, start, stop)


def units(cfg: Config) -> list[tuple]:
    out: list[tuple] = [(cfg, c) for c in ("C1", "C2", "C4", "C5")]
    for var in variants(cfg):
        for rho in var.rhos:
            rho_idx = cfg.grid.rhos.index(rho)
            for start in range(0, cfg.grid.replications, CHUNK):
                out.append((cfg, var.name, rho_idx, start, min(start + CHUNK, cfg.grid.replications)))
    return out


def unit_key(job: tuple) -> str:
    return f"unit|control|{job[1]}" if len(job) == 2 else f"unit|{job[1]}|rho{job[2]}|{job[3]:04d}"


# --- summary -------------------------------------------------------------------------------------------------


def mean_ci(values: list[float]) -> dict[str, Any]:
    a = np.asarray(values, dtype=float)
    if len(a) < 2:
        return {"mean": float(a.mean()) if len(a) else None, "ci": None, "n": len(a)}
    m, se = float(a.mean()), float(a.std(ddof=1) / math.sqrt(len(a)))
    return {"mean": m, "se": se, "ci": [m - 1.96 * se, m + 1.96 * se], "n": len(a)}


def summarise(cfg: Config, reps: list[dict[str, Any]], controls: dict[str, dict], wall: float) -> dict[str, Any]:
    pl = cfg.pipelines
    main_market = market_of(cfg.market)
    b_marg = beta_marg(main_market)
    prim = f"rl{pl.primary_sigma:g}"
    cells: dict[str, Any] = {}
    censored_max = 0.0
    for var in variants(cfg):
        vm = market_of(var.market)
        vb = beta_marg(vm) if var.name != "main" else b_marg
        for rho in var.rhos:
            rs = [x for x in reps if x["variant"] == var.name and x["rho"] == rho]
            if not rs:
                continue
            ok_nv = [x for x in rs if x["nv_converged"]]
            cens_nv = 1 - len(ok_nv) / len(rs)
            if var.name == "main":  # deviation 1: C6 covers the primary grid only
                censored_max = max(censored_max, cens_nv)
            cell: dict[str, Any] = {"replications": len(rs), "censored_nv": cens_nv, "beta_marg": vb,
                                    "b_nv": mean_ci([x["b_nv"] for x in ok_nv]),
                                    "loss_nv": mean_ci([x["loss_nv"] for x in ok_nv]),
                                    "mirage_nv": sum(1 for x in ok_nv if x["mirage_nv"])}
            cell["attenuation"] = 1 - cell["b_nv"]["mean"] / vb if cell["b_nv"]["mean"] is not None else None
            for sj in var.sigmas:
                tag = f"rl{sj:g}"
                ok = [x for x in ok_nv if x.get(f"{tag}_converged")]
                cens = 1 - len(ok) / len(rs)
                if var.name == "main":
                    censored_max = max(censored_max, cens)
                cell[tag] = {"censored": cens, "delta": mean_ci([x[f"{tag}_delta"] for x in ok]),
                             "b": mean_ci([x[f"{tag}_b"] for x in ok]),
                             "jitter_loss": mean_ci([x[f"{tag}_jitter_loss"] for x in ok])}
            if var.with_rg:
                cell["rg"] = {"delta": mean_ci([x["rg_delta"] for x in ok_nv if "rg_delta" in x])}
            cells[f"{var.name}|rho={rho}"] = cell
    main = {rho: cells[f"main|rho={rho}"] for rho in cfg.grid.rhos}
    delta_ci = {rho: main[rho][prim]["delta"]["ci"] for rho in cfg.grid.rhos}
    positive_rhos = [rho for rho in cfg.grid.rhos if rho > 0]
    naive_ci = {rho: main[rho]["b_nv"]["ci"] for rho in positive_rhos}
    if all(ci[1] < b_marg for ci in naive_ci.values()):
        naive = "holds"
    elif any(ci[0] >= b_marg for ci in naive_ci.values()):
        naive = "fails"
    else:
        naive = "inconclusive"
    means = [(rho, main[rho][prim]["delta"]["mean"]) for rho in cfg.grid.rhos]
    break_even = None
    for (r0, d0), (r1, d1) in zip(means, means[1:]):
        if d0 <= 0 < d1:
            break_even = r0 + (0 - d0) * (r1 - r0) / (d1 - d0)
            break
    controls_ok = {k: v["ok"] for k, v in controls.items()}
    controls_ok["C3"] = abs(main[0.0]["b_nv"]["mean"] - b_marg) <= 3 * main[0.0]["b_nv"]["se"] if 0.0 in main else False
    controls_ok["C6"] = censored_max <= cfg.run.max_censored_fraction
    main_market_oracle = {"prices": main_market.oracle_prices.tolist(), "value": main_market.oracle_value}
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "controls": {k: controls_ok[k] for k in sorted(controls_ok)},
        "controls_pass": all(controls_ok.values()) and wall <= cfg.run.wall_cap_s,
        "beta": cfg.market.beta,
        "beta_marg": b_marg,
        "oracle": main_market_oracle,
        "primary_sigma": pl.primary_sigma,
        "delta_ci": {str(k): v for k, v in delta_ci.items()},
        "naive_inelastic": naive,
        "break_even_rho": break_even,
        "cells": cells,
        "censored_max": censored_max,
        "censored_oat": {k: {"nv": c["censored_nv"], **{t: c[t]["censored"] for t in c if t.startswith("rl")}}
                         for k, c in cells.items() if not k.startswith("main|")},
        "control_detail": controls,
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


def _lo(s: dict, rho: float) -> float:
    return s["delta_ci"][str(rho)][0]


def _hi(s: dict, rho: float) -> float:
    return s["delta_ci"][str(rho)][1]


RULES: list[Rule[dict]] = [
    Rule("invalid", "any control fails", "debug, record a deviation, re-run", lambda s: not s["controls_pass"]),
    Rule("pays-always", "CI lower Δ(RL, 2) > 0 at every ρ, including 0", "run x06; carry the result to G1",
         lambda s: all(ci[0] > 0 for ci in s["delta_ci"].values())),
    Rule("pays-when-confounded", "CI lower Δ(RL, 2) > 0 at ρ = 0.5 and at ρ = 0.8",
         "run x06; G1 records the claim as conditional on confounding", lambda s: _lo(s, 0.5) > 0 and _lo(s, 0.8) > 0),
    Rule("pays-only-strong", "CI lower Δ(RL, 2) > 0 at ρ = 0.8 only", "run x06; G1",
         lambda s: _lo(s, 0.8) > 0 and all(ci[0] <= 0 for k, ci in s["delta_ci"].items() if k != "0.8")),
    Rule("never-pays", "CI upper Δ(RL, 2) ≤ 0 at ρ = 0.8", "run x06; G1", lambda s: _hi(s, 0.8) <= 0),
    Rule("inconclusive", "otherwise", "run x06; G1", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started = time.monotonic()
    done = ctx.done_keys()
    pending = [j for j in units(cfg) if unit_key(j) not in done]
    for job, result in parallel_map(run_unit, pending, workers=ctx.workers):
        if "records" in result:
            for rec in result["records"]:
                ctx.append_record(rec)
            ctx.append_record({"key": unit_key(job), "cpu_seconds": result["cpu_seconds"]})
        else:
            ctx.append_record({"key": unit_key(job), **result})
        ctx.save_checkpoint("units", {"done": sorted(k.removeprefix("unit|") for k in ctx.done_keys()
                                                      if k.startswith("unit|"))})
    records = ctx.read_records()
    reps = [r for r in records if r["key"].startswith("rep|")]
    controls = {r["key"].removeprefix("unit|control|"): r for r in records if r["key"].startswith("unit|control|")}
    summary = summarise(cfg, reps, controls, time.monotonic() - started)
    unit_cpu = sum(r.get("cpu_seconds", 0.0) for r in records if r["key"].startswith("unit|"))
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=unit_cpu)
    d = {k: (round(v[0], 2), round(v[1], 2)) for k, v in summary["delta_ci"].items()}
    print(f"{EXPERIMENT}: {summary['class']} (Δ(RL, {cfg.pipelines.primary_sigma:g}) CIs by ρ: {d}); "
          f"naive-inelastic: {summary['naive_inelastic']}; β_marg = {summary['beta_marg']:.4f}; run {ctx.run_dir}")
    return 0
