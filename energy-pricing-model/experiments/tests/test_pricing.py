"""The §5 pricing layer and the jitter integrators (theory note §2.4–2.5)."""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy.optimize import brentq

from epmlib.jitter import Design, loss_gauss_hermite, loss_monte_carlo, loss_quad
from epmlib.pricing import (CostStack, WinModel, markup_sign_rule, optimal_price, profit, profit_slope,
                            second_order_loss_at_optimum)

GOLDEN = Path(__file__).parent / "golden" / "pricing_7_4.json"
STACK = CostStack(78.0, 34.0, 45.0, 35.0, 0.276, 0.5, 6.0)
WIN = WinModel(0.33, 162.0)


@given(st.floats(120.0, 170.0), st.floats(0.05, 1.0))
def test_bisection_equals_brentq_on_the_profit_slope(c_hat, beta):
    win = WinModel(beta, 162.0)
    p = optimal_price(c_hat, win)
    root = brentq(lambda x: profit_slope(x, c_hat, win, 1.0), c_hat + 1e-9, c_hat + 100, xtol=1e-12)
    assert p == pytest.approx(root, abs=1e-8)


def test_the_note_inputs():
    assert STACK.c_hat(with_match=True) == pytest.approx(150.34)
    assert STACK.pass_through_cap(0.6) == pytest.approx(154.204)
    p = optimal_price(150.34, WIN)
    assert p == pytest.approx(159.746, abs=1e-3)
    assert second_order_loss_at_optimum(150.34, WIN) == pytest.approx(0.5 * 0.33 ** 2 * (1 - WIN.prob(p)))


@given(st.floats(125.0, 160.0), st.floats(0.1, 0.6))
def test_markup_sign_rule_matches_the_derivative(c_hat, beta):
    rule = markup_sign_rule(c_hat, WinModel(beta, 162.0))
    if abs(rule) < 1e-3:
        return
    h = 1e-6
    dm = (optimal_price(c_hat, WinModel(beta + h, 162.0)) - optimal_price(c_hat, WinModel(beta - h, 162.0))) / (2 * h)
    assert np.sign(dm) == np.sign(rule)


def test_curvature_at_the_optimum():
    p = optimal_price(150.34, WIN)
    h = 1e-3
    fd = (profit(p + h, 150.34, WIN, 250) - 2 * profit(p, 150.34, WIN, 250) + profit(p - h, 150.34, WIN, 250)) / h ** 2
    assert fd == pytest.approx(-0.33 * WIN.prob(p) * 250, rel=1e-6)


@pytest.mark.parametrize("design", list(Design))
def test_zero_jitter_costs_nothing(design):
    assert loss_quad(159.0, 150.34, WIN, 250, 0.0, design) == 0.0


def test_integrators_agree():
    z = np.random.default_rng(7).standard_normal(400_000)
    for p in (154.204, 159.746):
        for s in (0.5, 2.0):
            lq = loss_quad(p, 150.34, WIN, 250, s, Design.SYMMETRIC)
            assert lq == pytest.approx(loss_gauss_hermite(p, 150.34, WIN, 250, s, 200), abs=1e-10)
            lm, se = loss_monte_carlo(p, 150.34, WIN, 250, s, Design.SYMMETRIC, z)
            assert abs(lq - lm) <= 4 * se
            lq2 = loss_quad(p, 150.34, WIN, 250, s, Design.CAP_RESPECTING)
            lm2, se2 = loss_monte_carlo(p, 150.34, WIN, 250, s, Design.CAP_RESPECTING, z)
            assert abs(lq2 - lm2) <= 4 * se2


def test_small_sigma_limits():
    p = optimal_price(150.34, WIN)
    assert loss_quad(p, 150.34, WIN, 250, 0.05, Design.SYMMETRIC) / 0.05 ** 2 == pytest.approx(
        second_order_loss_at_optimum(150.34, WIN), rel=1e-3)
    cap = 154.204
    slope = math.sqrt(2 / math.pi) * profit_slope(cap, 150.34, WIN, 250) / profit(cap, 150.34, WIN, 250)
    assert loss_quad(cap, 150.34, WIN, 250, 0.01, Design.CAP_RESPECTING) / 0.01 == pytest.approx(slope, rel=1e-2)


def golden_stats() -> dict:
    p = optimal_price(150.34, WIN)
    return {"p_star": p, "p_no_match": optimal_price(160.0, WIN),
            "loss_sym_p_star_1": loss_quad(p, 150.34, WIN, 250, 1.0, Design.SYMMETRIC),
            "loss_sym_cap_1": loss_quad(154.204, 150.34, WIN, 250, 1.0, Design.SYMMETRIC)}


def test_golden_pricing():
    """Pins the pricing layer: x05 depends on it. Regenerate only with tests/golden/generate.py --force."""
    if not GOLDEN.exists():
        pytest.skip("golden fixture not generated yet")
    want = json.loads(GOLDEN.read_text())
    for k, v in golden_stats().items():
        assert v == pytest.approx(want[k], rel=1e-12), k
