"""x03: the dominance ratio, the verdicts, the classifier, and a reduced end-to-end run."""

import json

import numpy as np

from epmlib.outcomes import first_match
from epmlib.toy import ToyEngine, BASE
from epmlib.xp import x03_congestion_vs_shape as x03
from conftest import EXPERIMENTS_DIR

EXP = EXPERIMENTS_DIR / "x03-congestion-vs-shape"
CORE = (10, 20, 30, 40, 60, 100)


def test_dominance_ratio():
    # Each archetype falls by 0.6 over the core books; the spread across archetypes is at most 0.2.
    s = {}
    for i, n in enumerate(CORE):
        for j, a in enumerate(("office", "24/7", "evening")):
            s[(n, a)] = 0.8 - 0.12 * i - 0.1 * j
    assert abs(x03.dominance(s, CORE) - 3.0) < 1e-12
    sb = {k: np.array([v, v]) for k, v in s.items()}
    assert np.allclose(x03.boot_dominance(sb, CORE), 3.0)


def test_verdict_and_classes():
    assert x03.verdict([4.0, 5.0], 3.86) == "holds"
    assert x03.verdict([3.0, 3.5], 3.86) == "fails"
    assert x03.verdict([3.5, 4.5], 3.86) == "inconclusive"
    base = {"controls_pass": True, "dominance_threshold": 2.0}
    assert first_match(x03.RULES, {**base, "controls_pass": False, "R_ci": [5, 6]}).cls == "invalid"
    assert first_match(x03.RULES, {**base, "R_ci": [2.0, 4.0]}).cls == "congestion-dominant"
    assert first_match(x03.RULES, {**base, "R_ci": [1.2, 3.0]}).cls == "congestion-larger"
    assert first_match(x03.RULES, {**base, "R_ci": [0.5, 0.9]}).cls == "shape-comparable"
    assert first_match(x03.RULES, {**base, "R_ci": [0.8, 1.5]}).cls == "inconclusive"


def test_books_include_the_empty_book():
    e = ToyEngine(BASE, 2)
    pts = np.array([0, 5, 17])
    (n0, c0, s0), (n2, c2, s2) = list(e.books([0, 2], keep_sites_at=pts))
    assert n0 == 0 and not c0.any() and s0.shape == (0, 3)
    assert s2.shape == (2, 3) and np.allclose(s2.sum(axis=0), c2.ravel()[pts])


def test_end_to_end_reduced(tmp_path, monkeypatch):
    full = x03.all_configs
    keep = {"base", "fit-theta_s=0.3", "phi_c=0.5", "phi_w=0.9", "phi_i=0.5", "lhs-00", "theta_s=0.25"}
    monkeypatch.setattr(x03, "all_configs", lambda cfg: {k: v for k, v in full(cfg).items() if k in keep})
    text = (EXP / "config_smoke.toml").read_text()
    for old, new in (("scenarios = 12", "scenarios = 6"), ("bootstrap = 200", "bootstrap = 40"),
                     ("highs_halfhours = 20", "highs_halfhours = 4"), ("workers = 2", "workers = 1"),
                     ("books = [0, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]",
                      "books = [0, 1, 10, 20, 30, 40, 60, 100]")):
        assert old in text
        text = text.replace(old, new, 1)
    cfg = tmp_path / "tiny.toml"
    cfg.write_text(text)
    assert x03.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    s = json.loads((next((tmp_path / "out").iterdir()) / "summary.json").read_text())
    assert s["class"] in {r.cls for r in x03.RULES}
    assert s["controls"]["C1"] and s["controls"]["C2"] and s["controls"]["C3"] and s["controls"]["C4"]
    assert s["c3"]["checked"] > 0 and s["c3"]["failures"] == 0
