"""x04: the classifier, the §7.4 comparison, and a small end-to-end run."""

import json

from epmlib.config import load_toml
from epmlib.outcomes import first_match
from epmlib.xp import x04_price_and_jitter_cost as x04
from conftest import EXPERIMENTS_DIR

EXP = EXPERIMENTS_DIR / "x04-price-and-jitter-cost"
CFG = x04.load(load_toml(EXP / "config.toml")[0])


def _s(**matches):
    labels = [c[0] for c in x04.CANDIDATES]
    return {"controls_pass": True, "candidates": {lab: {"match": matches.get(lab, False)} for lab in labels}}


def test_every_class_is_reachable():
    assert first_match(x04.RULES, {**_s(), "controls_pass": False}).cls == "invalid"
    assert first_match(x04.RULES, _s(**{"symmetric at p*": True})).cls == "note-confirmed"
    assert first_match(x04.RULES, _s(**{"symmetric at p_cap": True})).cls == "misattributed-cap"
    assert first_match(x04.RULES, _s(**{"cap-respecting at p*": True})).cls == "misattributed-other"
    assert first_match(x04.RULES, _s()).cls == "unexplained"


def test_table_7_4_is_at_least_rounding_consistent():
    t = x04.table_7_4(CFG)
    assert len(t["cells"]) == 11
    assert t["verdict"] in {"exact", "rounding"}


def test_end_to_end_small(tmp_path):
    text = (EXP / "config_smoke.toml").read_text().replace("mc_draws = 1000000", "mc_draws = 200000")
    cfg = tmp_path / "small.toml"
    cfg.write_text(text)
    assert x04.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    s = json.loads((next((tmp_path / "out").iterdir()) / "summary.json").read_text())
    assert s["class"] in {r.cls for r in x04.RULES}
    assert s["controls"]["C1"] and s["controls"]["C3"] and s["controls"]["C4"] and s["controls"]["C5"]
