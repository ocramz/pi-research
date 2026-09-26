"""The half-hour LP: merit order is optimal, the corrected dual table certifies it, and HiGHS agrees."""

from fractions import Fraction

import numpy as np
from hypothesis import assume, given
from hypothesis import strategies as st

from epmlib.allocation import HHInstance, Regime, certify, greedy, note_regime, regime, table_duals
from epmlib.lpcheck import solve_hh_lp
from epmlib.xp.x01_lp_shadow_prices import is_degenerate

eighths = st.integers(1, 40).map(lambda k: Fraction(k, 8))


@st.composite
def exact_instances(draw):
    """Ties allowed: premiums are integers, quantities multiples of 1/8."""
    n_c = draw(st.integers(1, 5))
    n_a = draw(st.integers(1, 5))
    return HHInstance(Fraction(45), tuple(draw(st.lists(eighths, min_size=n_c, max_size=n_c))),
                      tuple(draw(st.lists(eighths, min_size=n_a, max_size=n_a))),
                      tuple(Fraction(p) for p in draw(st.lists(st.integers(0, 60), min_size=n_a, max_size=n_a))))


@st.composite
def float_instances(draw):
    n_c = draw(st.integers(1, 6))
    n_a = draw(st.integers(1, 6))
    pos = st.floats(0.05, 3.0, allow_nan=False)
    return HHInstance(45.0, tuple(draw(st.lists(pos, min_size=n_c, max_size=n_c))),
                      tuple(draw(st.lists(pos, min_size=n_a, max_size=n_a))),
                      tuple(draw(st.lists(st.floats(0.0, 60.0), min_size=n_a, max_size=n_a))))


@given(exact_instances())
def test_greedy_and_table_duals_certify_even_with_ties(inst):
    sol = greedy(inst)
    assert certify(inst, sol.m, sol.nu, sol.mu).ok


@given(exact_instances())
def test_a_planted_wrong_dual_fails_the_certificate(inst):
    sol = greedy(inst)
    assert not certify(inst, sol.m, (sol.nu[0] + 1, *sol.nu[1:]), sol.mu).ok


@given(float_instances())
def test_highs_value_equals_greedy(inst):
    res = solve_hh_lp(inst)
    assert res.optimal
    value = float(greedy(inst.exact()).value)
    assert abs(res.value - value) <= 1e-9 * max(1.0, value)


@given(float_instances())
def test_highs_duals_equal_the_table_on_nondegenerate_instances(inst):
    assume(not is_degenerate(inst))
    ex = inst.exact()
    gaps = [abs(float(sum(ex.gen[a] for a in range(ex.n_assets) if ex.premium[a] < ex.lam) - sum(ex.cap_demand)))]
    assume(min(gaps) > 1e-6)
    nu, mu, _ = table_duals(ex)
    res = solve_hh_lp(inst)
    assert np.allclose(res.nu, [float(x) for x in nu], atol=1e-6)
    assert np.allclose(res.mu, [float(x) for x in mu], atol=1e-6)


def test_inframarginal_assets_earn_rent():
    """A counterexample to the note's "μ = 0 for inframarginal assets"."""
    inst = HHInstance(45.0, (1.0,), (0.5, 1.0), (5.0, 20.0))  # demand-scarce; asset 1 is marginal
    assert regime(inst) is Regime.DEMAND_SCARCE
    res = solve_hh_lp(inst)
    assert np.allclose(res.nu, [25.0]) and np.allclose(res.mu, [15.0, 0.0])  # μ_0 = π_k − π_0 = 15


def test_generation_scarce_mu_is_clipped_and_regime_uses_profitable_generation():
    inst = HHInstance(45.0, (2.0,), (1.0, 3.0), (10.0, 50.0))  # ΣG = 4 > C = 2 but G⁺ = 1 < C
    assert regime(inst) is Regime.GENERATION_SCARCE
    assert note_regime(inst) is Regime.DEMAND_SCARCE  # the note's ΣG rule misclassifies
    res = solve_hh_lp(inst)
    assert np.allclose(res.mu, [35.0, 0.0])  # not λ − π = −5 for the unprofitable asset
