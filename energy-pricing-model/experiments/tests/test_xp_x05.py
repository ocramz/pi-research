"""x05: the market, the logit fit, IPS, the classifier, and a reduced end-to-end run."""

import json
import math

import numpy as np
import pytest
from scipy.optimize import minimize
from scipy.special import log_expit

from epmlib.elasticity import CENTER, Market, ips_segment_values, logit_irls
from epmlib.outcomes import first_match
from epmlib.xp import x05_confounded_elasticity as x05
from conftest import EXPERIMENTS_DIR

EXP = EXPERIMENTS_DIR / "x05-confounded-elasticity"
M = Market((159.0, 161.0, 163.0, 165.0), 0.33, 3.0, 2.0, 150.34, 64)


def _simulate(n, rng, beta=0.33, tau=0.0):
    x = rng.integers(0, 4, n)
    p = np.array(M.bases)[x] + rng.uniform(-8, 4, n)
    u = rng.normal(0, tau, n) if tau else np.zeros(n)
    y = (rng.random(n) < 1 / (1 + np.exp(-beta * (np.array(M.bases)[x] + u - p)))).astype(float)
    return x, p, y


def test_irls_recovers_beta_and_matches_bfgs():
    x, p, y = _simulate(60_000, np.random.default_rng(3))
    fit = logit_irls(x, p, y, 4)
    assert fit.converged and abs(fit.b - 0.33) <= 3 * fit.se_b
    xm = np.zeros((len(y), 5))
    xm[np.arange(len(y)), x] = 1
    xm[:, 4] = p - CENTER

    def nll(t):
        eta = xm @ t
        return -np.sum(y * log_expit(eta) + (1 - y) * log_expit(-eta))
    bfgs = minimize(nll, np.zeros(5), method="BFGS", options={"gtol": 1e-8})
    assert -bfgs.x[4] == pytest.approx(fit.b, rel=1e-4)


def test_irls_flags_separation():
    x = np.array([0, 0, 1, 1, 2, 2, 3, 3] * 10)
    p = np.linspace(150, 170, len(x))
    y = np.zeros(len(x))
    y[x != 0] = (np.arange(len(x))[x != 0] % 2).astype(float)  # segment 0 never wins
    assert not logit_irls(x, p, y, 4, max_iter=50).converged


def test_beta_marg_is_close_to_the_probit_approximation():
    approx = 0.33 / math.sqrt(1 + math.pi * 0.33 ** 2 * 9 / 8)
    assert x05.beta_marg(M) == pytest.approx(approx, rel=0.02)


def test_oracle_matches_a_grid():
    for s in range(4):
        grid = np.arange(150.34, 190.0, 1e-3)
        vals = M.value(np.full(len(grid), s), grid)
        assert abs(grid[np.argmax(vals)] - M.oracle_prices[s]) <= 2e-3


def test_ips_formula():
    x = np.array([0, 0, 0, 1])
    idx = np.array([0, 1, 0, 1])
    wins = np.array([1.0, 1.0, 0.0, 1.0])
    prices = np.array([160.0, 162.0, 160.0, 161.0])
    v = ips_segment_values(x, idx, wins, prices, 150.0, 2, 2)
    assert v[0, 0] == pytest.approx(2 * 10.0 / 3) and v[0, 1] == pytest.approx(2 * 12.0 / 3)
    assert v[1, 1] == pytest.approx(2 * 11.0) and v[1, 0] == 0.0


def _s(**ci):
    base = {"0.0": [-1.1, -0.9], "0.3": [-0.7, -0.4], "0.5": [2.3, 3.7], "0.8": [28, 33]}
    base.update(ci)
    return {"controls_pass": True, "delta_ci": base}


def test_every_class_is_reachable():
    assert first_match(x05.RULES, {**_s(), "controls_pass": False}).cls == "invalid"
    assert first_match(x05.RULES, _s()).cls == "pays-when-confounded"
    assert first_match(x05.RULES, _s(**{"0.0": [0.1, 0.2], "0.3": [0.1, 0.3]})).cls == "pays-always"
    assert first_match(x05.RULES, _s(**{"0.5": [-0.5, 0.5]})).cls == "pays-only-strong"
    assert first_match(x05.RULES, _s(**{"0.5": [-2, -1], "0.8": [-3, -1]})).cls == "never-pays"
    assert first_match(x05.RULES, _s(**{"0.5": [-2, -1], "0.8": [-1, 1]})).cls == "inconclusive"


def test_end_to_end_reduced(tmp_path, monkeypatch):
    full = x05.variants
    monkeypatch.setattr(x05, "variants", lambda cfg: [v for v in full(cfg) if v.name in ("main", "n_log=500")])
    text = (EXP / "config_smoke.toml").read_text()
    for old, new in (("replications = 100", "replications = 30"), ("ips_logs = 200", "ips_logs = 60"),
                     ("workers = 2", "workers = 1")):
        assert old in text
        text = text.replace(old, new, 1)
    cfg = tmp_path / "tiny.toml"
    cfg.write_text(text)
    assert x05.main(["--config", str(cfg), "--out", str(tmp_path / "out")], EXP) == 0
    s = json.loads((next((tmp_path / "out").iterdir()) / "summary.json").read_text())
    assert s["class"] in {r.cls for r in x05.RULES}
    assert set(s["controls"]) == {"C1", "C2", "C3", "C4", "C5", "C6"}
