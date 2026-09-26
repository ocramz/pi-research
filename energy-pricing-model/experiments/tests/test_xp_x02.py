"""x02: the closed form, the estimator, peak detection, the classifier, and a reduced end-to-end run."""

import json

import numpy as np
import pytest
from scipy import integrate
from scipy.stats import norm

from epmlib.outcomes import first_match
from epmlib.toy.matching import jensen_terms, resampled_overstatement
from epmlib.xp import x02_jensen_gap as x02
from conftest import EXPERIMENTS_DIR

EXP = EXPERIMENTS_DIR / "x02-jensen-gap"


@pytest.mark.parametrize("mu,sd,d", [(0.5, 0.3, 1.0), (1.0, 0.3, 1.0), (2.0, 0.3, 1.0), (1.0, 0.03, 1.0)])
def test_expected_min_closed_form(mu, sd, d):
    numeric, _ = integrate.quad(lambda x: min(x, d) * norm.pdf(x, mu, sd), mu - 12 * sd, mu + 12 * sd,
                                points=[d], limit=200)
    assert x02.expected_min(mu, sd, d) == pytest.approx(numeric, abs=1e-10)


def test_estimator_is_zero_without_noise_and_positive_with_it():
    g = np.tile(np.linspace(0, 2, 50), (7, 1))
    c = np.ones_like(g)
    point, m = jensen_terms(g, c)
    assert abs(point - m) <= 1e-12 * m
    noisy = g + np.random.default_rng(0).normal(0, 0.3, g.shape)
    point, m = jensen_terms(noisy, c)
    assert point > m


def test_resampled_overstatement_with_identity_weights_is_the_point_estimate():
    rng = np.random.default_rng(1)
    g, c = rng.uniform(0, 2, (5, 40)), rng.uniform(0, 2, (5, 40))
    w = np.ones((1, 5))
    m_s = np.minimum(g, c).sum(axis=1)
    point, m = jensen_terms(g, c)
    got = resampled_overstatement(w @ g / 5, w @ c / 5, w, m_s)
    assert got[0] == pytest.approx((point - m) / m, rel=1e-12)


def test_peaks():
    rs = [4, 3, 2, 1.5, 1, 0.8, 0.5]
    assert x02.peaks(rs, [1, 2, 5, 4, 3, 2, 1], 0.8) == {"r_peak": 2, "O_max": 5, "edge": False, "local_peaks": [2]}
    bi = x02.peaks(rs, [1, 5, 2, 1, 2, 4.5, 1], 0.8)
    assert bi["local_peaks"] == [3, 0.8] and not bi["edge"]
    assert x02.peaks(rs, [9, 5, 2, 1, 2, 4.5, 1], 0.8)["edge"]


def _summary(**kw):
    s = {"controls_pass": True, "balance_band": [0.75, 1.33], "class_probability": 0.8, "r_peak": 2.6,
         "local_peaks": [2.6], "P_B": {"balance": 0.0, "above": 0.95, "below": 0.05}}
    s.update(kw)
    return s


def test_every_class_is_reachable():
    assert first_match(x02.RULES, _summary(controls_pass=False)).cls == "invalid"
    assert first_match(x02.RULES, _summary()).cls == "peak-above-balance"
    assert first_match(x02.RULES, _summary(r_peak=1.0, P_B={"balance": 0.85, "above": 0.1, "below": 0.05})
                       ).cls == "peak-at-balance"
    assert first_match(x02.RULES, _summary(r_peak=0.5, P_B={"balance": 0.1, "above": 0.0, "below": 0.9})
                       ).cls == "peak-below-balance"
    assert first_match(x02.RULES, _summary(P_B={"balance": 0.3, "above": 0.6, "below": 0.1},
                                           local_peaks=[5.2, 0.39])).cls == "multimodal"
    assert first_match(x02.RULES, _summary(P_B={"balance": 0.3, "above": 0.6, "below": 0.1})).cls == "inconclusive"
    # The band is inclusive at both ends.
    assert first_match(x02.RULES, _summary(r_peak=1.33, P_B={"balance": 0.8, "above": 0.2, "below": 0.0})
                       ).cls == "peak-at-balance"


def test_end_to_end_reduced(tmp_path, monkeypatch):
    keep = {"base", "theta_s=0", "theta_s=1", "gen-noise-only", "demand-noise-only", "zero-noise",
            "theta_s=0.25", "theta_s=0.75", "phi_c=0.5", "phi_w=0.9", "phi_i=0.5", "lhs-00"}
    full = x02.all_configs()
    monkeypatch.setattr(x02, "all_configs", lambda: {k: v for k, v in full.items() if k in keep})
    text = (EXP / "config_smoke.toml").read_text()
    for old, new in (("scenarios = 12\n", "scenarios = 6\n"), ("bootstrap = 100", "bootstrap = 30"),
                     ("replications = 20", "replications = 10"), ("workers = 2", "workers = 1")):
        text = text.replace(old, new, 1)
    text = text.replace("books = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 45, 50, 60, 70, 80, 100, 125, 160, 200]",
                        "books = [4, 10, 20, 30, 40, 60, 100]")
    cfg = tmp_path / "tiny.toml"
    cfg.write_text(text)
    assert x02.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    run = next((tmp_path / "out").iterdir())
    s = json.loads((run / "summary.json").read_text())
    assert s["class"] in {r.cls for r in x02.RULES}
    assert s["controls"]["C1"] and s["controls"]["C2"]
    assert len(s["curve"]) == 7 and s["secondary"]["verdict"] in {"holds", "fails", "inconclusive"}
