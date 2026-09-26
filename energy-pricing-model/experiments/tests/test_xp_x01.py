"""x01: instance construction, statements, the outcome classifier, and a small end-to-end run."""

import json

import pytest

from epmlib.config import load_toml
from epmlib.outcomes import first_match
from epmlib.xp import x01_lp_shadow_prices as x01
from conftest import EXPERIMENTS_DIR

EXP = EXPERIMENTS_DIR / "x01-lp-shadow-prices"
CFG = x01.load(load_toml(EXP / "config.toml")[0])


def test_degenerate_instances_are_degenerate_and_random_ones_are_not():
    for j in range(0, 500, 7):
        kind, inst = x01.degenerate_instance(CFG, j)
        assert x01.is_degenerate(inst), (j, kind)
        assert all(0 < c <= 2.5 for c in inst.cap_demand)
    assert sum(x01.is_degenerate(x01.random_instance(CFG, k)) for k in range(300)) == 0


def test_evaluate_instance_certifies_and_finds_witnesses():
    found = set()
    for k in range(200):
        rec, wit = x01.evaluate_instance(CFG, f"A|rnd|{k:05d}", "random", x01.random_instance(CFG, k))
        assert rec["c1"] and rec["c3"] and rec["c2"]
        found |= {w["statement"] for w in wit}
    assert found == {"S1", "S2", "S3"}


def _summary(**kw):
    base = {"controls_pass": True, "tolerance": 0.05, "e_star_ci": [0.01, 0.03],
            "rule_cells": [{"N": 40, "ci": [0.01, 0.02]}, {"N": 100, "ci": [0.01, 0.03]}]}
    base.update(kw)
    return base


def test_every_class_is_reachable_and_invalid_comes_first():
    assert first_match(x01.RULES, _summary(controls_pass=False)).cls == "invalid"
    assert first_match(x01.RULES, _summary()).cls == "rule-holds"
    sat = _summary(e_star_ci=[0.051, 0.07], rule_cells=[{"N": 40, "ci": [0.01, 0.049]}, {"N": 100, "ci": [0.051, 0.07]}])
    assert first_match(x01.RULES, sat).cls == "rule-fails-saturated"
    broad = _summary(e_star_ci=[0.06, 0.08], rule_cells=[{"N": 40, "ci": [0.055, 0.08]}, {"N": 100, "ci": [0.06, 0.07]}])
    assert first_match(x01.RULES, broad).cls == "rule-fails-broadly"
    inc = _summary(e_star_ci=[0.04, 0.06])
    assert first_match(x01.RULES, inc).cls == "inconclusive"
    edge = _summary(e_star_ci=[0.01, 0.05])  # CI upper exactly 5% still holds (≤)
    assert first_match(x01.RULES, edge).cls == "rule-holds"


def test_end_to_end_tiny(tmp_path):
    cfg_text = (EXP / "config_smoke.toml").read_text()
    for old, new in (("instances = 300", "instances = 40"), ("degenerate_per_kind = 10", "degenerate_per_kind = 3"),
                     ("scenarios = 12", "scenarios = 4"), ("books = [10, 20, 40, 60, 100]", "books = [10, 60]"),
                     ("bootstrap = 200", "bootstrap = 50"), ("lhs_cells = 2", "lhs_cells = 1"),
                     ("highs_check_halfhours = 20", "highs_check_halfhours = 5"), ("workers = 2", "workers = 1")):
        assert old in cfg_text
        cfg_text = cfg_text.replace(old, new)
    cfg = tmp_path / "tiny.toml"
    cfg.write_text(cfg_text)
    assert x01.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    run = next((tmp_path / "out").iterdir())
    summary = json.loads((run / "summary.json").read_text())
    assert summary["class"] in {r.cls for r in x01.RULES}
    assert summary["controls"]["C1"] and summary["controls"]["C4"]
    assert json.loads((run / "manifest.json").read_text())["smoke"] is True
