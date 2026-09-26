"""x04-price-and-jitter-cost: do the §7.4 prices and the §7.5 jitter losses follow from the note's own
model? A deterministic audit, with Monte Carlo as the checker.

Registered in PREREG.md (203328d)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..config import build, section
from ..jitter import Design, loss_gauss_hermite, loss_monte_carlo, loss_quad
from ..outcomes import Rule, first_match, otherwise
from ..pricing import (CostStack, WinModel, markup_sign_rule, optimal_price, profit, profit_slope,
                       second_order_loss_at_optimum)
from ..rng import generator
from ..runlib import RunStatus, open_run, parse_args

EXPERIMENT = "x04-price-and-jitter-cost"


@dataclass(frozen=True)
class Note:
    commodity: float
    network: float
    levies: float
    nu_bar: float
    matched_share: float
    phi: float
    sigma_cost: float
    beta: float
    p_ref: float
    volume_mwh: float
    gamma: float
    jitter_sigmas: tuple[float, ...]
    jitter_loss_percent: tuple[float, ...]
    jitter_tolerance_pp: tuple[float, ...]


@dataclass(frozen=True)
class Row74:
    price: float
    win_percent: float
    margin_gbp: float
    markup: float | None = None


@dataclass(frozen=True)
class Analysis:
    sigmas: tuple[float, ...]
    exact_tolerance: dict
    rounding_tolerance: dict
    statics_c_hat: tuple[float, ...]
    statics_beta: tuple[float, ...]


@dataclass(frozen=True)
class Checker:
    mc_draws: int
    gh_nodes: int
    grid_step: float
    fd_step: float
    statics_fd_step: float
    se_multiple: float


@dataclass(frozen=True)
class RunCfg:
    workers: int
    wall_cap_s: float


@dataclass(frozen=True)
class Config:
    seed: int
    note: Note
    table_7_4: dict[str, Row74]
    analysis: Analysis
    checker: Checker
    run: RunCfg


def load(data: dict[str, Any]) -> Config:
    note = dict(section(data, "note"))
    table = note.pop("table_7_4")
    return Config(seed=int(section(data, "experiment")["seed"]), note=build(Note, note, where="note"),
                  table_7_4={k: build(Row74, v, where=f"note.table_7_4.{k}") for k, v in table.items()},
                  analysis=build(Analysis, section(data, "analysis"), where="analysis"),
                  checker=build(Checker, section(data, "checker"), where="checker"),
                  run=build(RunCfg, section(data, "run"), where="run"))


def model(cfg: Config) -> tuple[CostStack, WinModel, float]:
    n = cfg.note
    stack = CostStack(n.commodity, n.network, n.levies, n.nu_bar, n.matched_share, n.phi, n.sigma_cost)
    return stack, WinModel(n.beta, n.p_ref), n.volume_mwh


def prices(cfg: Config) -> dict[str, tuple[float, float]]:
    """{policy: (price, ĉ)} for the three §7.4 rows."""
    stack, win, _ = model(cfg)
    c_match, c_none = stack.c_hat(with_match=True), stack.c_hat(with_match=False)
    p_star = optimal_price(c_match, win)
    return {"unconstrained": (p_star, c_match),
            "pass_through": (min(p_star, stack.pass_through_cap(cfg.note.gamma)), c_match),
            "no_match": (optimal_price(c_none, win), c_none)}


def table_7_4(cfg: Config) -> dict[str, Any]:
    _, win, q = model(cfg)
    ex, rd = cfg.analysis.exact_tolerance, cfg.analysis.rounding_tolerance
    cells, all_exact, all_round = [], True, True
    for name, (p, c) in prices(cfg).items():
        got = {"price": p, "win_percent": 100 * win.prob(p), "markup": p - c, "margin_gbp": profit(p, c, win, q)}
        note = cfg.table_7_4[name]
        for field in ("price", "win_percent", "markup", "margin_gbp"):
            want = getattr(note, field)
            if want is None:
                continue
            diff = got[field] - want
            if field == "margin_gbp":
                exact = abs(diff) <= ex["margin_gbp"]
                rounding = abs(diff) <= rd["margin_rel"] * abs(want)
            elif field == "win_percent":
                exact, rounding = abs(diff) <= ex["win_pp"], abs(diff) <= rd["win_pp"]
            else:
                exact, rounding = abs(diff) <= ex[field], abs(diff) <= rd[field]
            all_exact &= exact
            all_round &= rounding
            cells.append({"row": name, "field": field, "model": got[field], "note": want, "diff": diff,
                          "exact": exact, "rounding": rounding})
    verdict = "exact" if all_exact else "rounding" if all_round else "mismatch"
    return {"verdict": verdict, "cells": cells}


CANDIDATES = (("symmetric at p*", "unconstrained", Design.SYMMETRIC),
              ("symmetric at p_cap", "pass_through", Design.SYMMETRIC),
              ("symmetric at the no-match price", "no_match", Design.SYMMETRIC),
              ("cap-respecting at p_cap", "pass_through", Design.CAP_RESPECTING),
              ("cap-respecting at p*", "unconstrained", Design.CAP_RESPECTING))


def jitter_grid(cfg: Config) -> tuple[list[dict[str, Any]], bool, bool]:
    """Every (price, σ, design) with quad, Monte Carlo and, if symmetric, Gauss–Hermite."""
    _, win, q = model(cfg)
    ch = cfg.checker
    z = generator(cfg.seed, 401).standard_normal(ch.mc_draws)
    sigmas = sorted(set(cfg.analysis.sigmas) | set(cfg.note.jitter_sigmas))
    rows, c2, c4 = [], True, True
    for name, (p, c) in prices(cfg).items():
        for design in Design:
            for sigma in (0.0, *sigmas):
                lq = loss_quad(p, c, win, q, sigma, design)
                rec: dict[str, Any] = {"key": f"jitter|{name}|{design.value}|s{sigma:05.2f}", "policy": name,
                                       "design": design.value, "sigma": sigma, "price": p, "loss_quad": lq}
                if sigma == 0.0:
                    c4 &= lq == 0.0
                else:
                    lm, se = loss_monte_carlo(p, c, win, q, sigma, design, z)
                    ok = abs(lq - lm) <= ch.se_multiple * se
                    rec.update({"loss_mc": lm, "mc_se": se, "mc_ok": ok})
                    c2 &= ok
                    if design is Design.SYMMETRIC:
                        lg = loss_gauss_hermite(p, c, win, q, sigma, ch.gh_nodes)
                        gh_ok = abs(lq - lg) <= 1e-9 * max(1.0 - lq, 1e-300)
                        rec.update({"loss_gh": lg, "gh_ok": gh_ok})
                        c2 &= gh_ok
                rows.append(rec)
    return rows, c2, c4


def matches(cfg: Config, rows: list[dict[str, Any]], policy: str, design: Design) -> dict[str, Any]:
    n = cfg.note
    losses = []
    for sigma in n.jitter_sigmas:
        r = next(x for x in rows if x["policy"] == policy and x["design"] == design.value and x["sigma"] == sigma)
        losses.append(100 * r["loss_quad"])
    ok = all(abs(l - want) <= tol for l, want, tol in zip(losses, n.jitter_loss_percent, n.jitter_tolerance_pp))
    return {"losses_percent": losses, "match": ok}


def statics(cfg: Config) -> tuple[list[dict[str, Any]], bool]:
    p_ref = cfg.note.p_ref
    h = cfg.checker.statics_fd_step
    rows, agree_all = [], True
    for c_hat in cfg.analysis.statics_c_hat:
        for beta in cfg.analysis.statics_beta:
            win = WinModel(beta, p_ref)
            m = optimal_price(c_hat, win) - c_hat
            dm = ((optimal_price(c_hat, WinModel(beta + h, p_ref)) - c_hat)
                  - (optimal_price(c_hat, WinModel(beta - h, p_ref)) - c_hat)) / (2 * h)
            rule = markup_sign_rule(c_hat, win)
            checked = abs(rule) > 1e-3
            agree = (np.sign(dm) == np.sign(rule)) if checked else None
            if checked:
                agree_all &= bool(agree)
            rows.append({"key": f"statics|c{c_hat:06.2f}|b{beta:.2f}", "c_hat": c_hat, "beta": beta, "markup": m,
                         "dm_dbeta": dm, "sign_rule": rule, "checked": checked, "agree": agree,
                         "markup_falls": dm < 0})
    return rows, agree_all


def optimum_controls(cfg: Config) -> dict[str, Any]:
    _, win, q = model(cfg)
    step, out = cfg.checker.grid_step, {}
    ok = True
    for name in ("unconstrained", "no_match"):
        p_star, c = prices(cfg)[name]
        grid = c + step * np.arange(1, int(round(50 / step)) + 1)
        prof = q * (1 / (1 + np.exp(-win.beta * (win.p_ref - grid)))) * (grid - c)
        p_grid = float(grid[int(np.argmax(prof))])
        second = np.diff(np.log(prof), 2)
        concave = bool((second < 0).all())
        close = abs(p_grid - p_star) <= 2e-4
        ok &= concave and close
        out[name] = {"p_bisection": p_star, "p_grid": p_grid, "close": close, "log_concave": concave}
    p_star, c = prices(cfg)["unconstrained"]
    h = cfg.checker.fd_step
    fd = (profit(p_star + h, c, win, q) - 2 * profit(p_star, c, win, q) + profit(p_star - h, c, win, q)) / h ** 2
    closed = -win.beta * win.prob(p_star) * q
    c3 = abs(fd - closed) <= 1e-6 * abs(closed)
    return {"C1": ok, "C1_detail": out, "C3": c3, "C3_detail": {"fd": fd, "closed_form": closed}}


def describe(cfg: Config, rows: list[dict[str, Any]]) -> dict[str, Any]:
    stack, win, q = model(cfg)
    pr = prices(cfg)
    p_star, c_m = pr["unconstrained"]
    p_cap, _ = pr["pass_through"]
    p_nm, c_nm = pr["no_match"]

    def loss(policy: str, design: Design, sigma: float) -> float:
        return next(x["loss_quad"] for x in rows
                    if x["policy"] == policy and x["design"] == design.value and x["sigma"] == sigma)

    envelope = second_order_loss_at_optimum(c_m, win)
    first_order = math.sqrt(2 / math.pi) * profit_slope(p_cap, c_m, win, q) / profit(p_cap, c_m, win, q)
    margins = {k: profit(p, c, win, q) for k, (p, c) in pr.items()}
    return {
        "envelope_second_order": {"closed_form": envelope,
                                  "ratio": {s: loss("unconstrained", Design.SYMMETRIC, s) / s ** 2 for s in (0.25, 0.5)}},
        "cap_respecting_first_order": {"closed_form_slope": first_order,
                                       "ratio": {s: loss("pass_through", Design.CAP_RESPECTING, s) / s
                                                 for s in (0.25, 0.5, 1.0)},
                                       "loss_at_1": loss("pass_through", Design.CAP_RESPECTING, 1.0)},
        "quadratic_scaling": {pol: {s: loss(pol, Design.SYMMETRIC, s) / loss(pol, Design.SYMMETRIC, 1.0)
                                    for s in (2.0, 4.0)} for pol in ("unconstrained", "pass_through")},
        "rent_split": {"credit": stack.credit, "customer_saving": p_nm - p_star,
                       "tem_markup_gain": (p_star - c_m) - (p_nm - c_nm)},
        "margin_ratio": {"unconstrained_over_no_match": margins["unconstrained"] / margins["no_match"],
                         "pass_through_over_no_match": margins["pass_through"] / margins["no_match"],
                         "win_percent": {k: 100 * win.prob(p) for k, (p, _) in pr.items()}},
        "gamma_binding": (stack.gross + stack.loading - p_star) / stack.credit,
        "prices": {k: {"price": p, "c_hat": c} for k, (p, c) in pr.items()},
    }


def summarise(cfg: Config, rows: list[dict[str, Any]], statics_rows: list[dict[str, Any]], c2: bool, c4: bool,
              c5: bool, opt: dict[str, Any], wall: float) -> dict[str, Any]:
    cands = {label: matches(cfg, rows, policy, design) for label, policy, design in CANDIDATES}
    checked = [r for r in statics_rows if r["checked"]]
    controls = {"C1": opt["C1"], "C2": c2, "C3": opt["C3"], "C4": c4, "C5": c5}
    summary: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "controls": controls,
        "controls_pass": all(controls.values()) and wall <= cfg.run.wall_cap_s,
        "candidates": cands,
        "s74_reproduction": table_7_4(cfg),
        "statics": {"grid_points": len(statics_rows), "checked": len(checked),
                    "sign_rule_agreement": float(np.mean([r["agree"] for r in checked])) if checked else None,
                    "share_markup_falls": float(np.mean([r["markup_falls"] for r in statics_rows])),
                    "counterexamples": [{"c_hat": r["c_hat"], "beta": r["beta"]} for r in statics_rows
                                        if not r["markup_falls"]][:20]},
        "optimum": opt,
        **describe(cfg, rows),
    }
    rule = first_match(RULES, summary)
    summary["class"] = rule.cls
    summary["action"] = rule.action
    return summary


def _m(s: dict, label: str) -> bool:
    return s["candidates"][label]["match"]


RULES: list[Rule[dict]] = [
    Rule("invalid", "any control fails", "debug, record a deviation, re-run", lambda s: not s["controls_pass"]),
    Rule("note-confirmed", "symmetric jitter at p* matches §7.5", "run x05; carry the result to G1",
         lambda s: _m(s, "symmetric at p*")),
    Rule("misattributed-cap", "p* does not match, and symmetric jitter at p_cap(0.6) matches",
         "run x05; G1 records the correct attribution, and that symmetric jitter at a binding cap breaks the "
         "cap on half of all quotes", lambda s: _m(s, "symmetric at p_cap")),
    Rule("misattributed-other",
         "neither of the above, but one of the following matches: symmetric at the no-match price; "
         "cap-respecting at p_cap(0.6); cap-respecting at p*", "run x05; G1",
         lambda s: _m(s, "symmetric at the no-match price") or _m(s, "cap-respecting at p_cap")
         or _m(s, "cap-respecting at p*")),
    Rule("unexplained", "nothing matches", "run x05; G1", otherwise),
]


def main(argv: list[str] | None, exp_dir: Path) -> int:
    args = parse_args(argv, exp_dir=exp_dir, description=__doc__)
    ctx = open_run(EXPERIMENT, exp_dir, args)
    cfg = load(ctx.config)
    started, cpu0 = time.monotonic(), time.process_time()
    rows, c2, c4 = jitter_grid(cfg)
    statics_rows, c5 = statics(cfg)
    opt = optimum_controls(cfg)
    for r in rows + statics_rows:
        ctx.append_record(r)
    summary = summarise(cfg, rows, statics_rows, c2, c4, c5, opt, time.monotonic() - started)
    ctx.finish(summary, RunStatus.COMPLETE, unit_cpu_seconds=time.process_time() - cpu0)
    print(f"{EXPERIMENT}: {summary['class']}; s74-reproduction: {summary['s74_reproduction']['verdict']}; "
          f"p* losses {['%.2f' % x for x in summary['candidates']['symmetric at p*']['losses_percent']]}; "
          f"p_cap losses {['%.2f' % x for x in summary['candidates']['symmetric at p_cap']['losses_percent']]}; "
          f"run {ctx.run_dir}")
    return 0
