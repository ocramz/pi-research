"""Toy model v1: calibration, shapes, AR(1) streams and common random numbers."""

import json
from pathlib import Path

import numpy as np
import pytest

from epmlib.toy import BASE, Pool, ToyEngine, ar1, lhs_configs, named_config, oat_configs
from epmlib.toy.calibrate import expected_solar, expected_wind_per_mw, solar_eta, wind_mu
from epmlib.toy.shapes import archetype_shape
from epmlib.toy.spec import ARCHETYPES, SOLAR_MWH_PER_MW

GOLDEN = Path(__file__).parent / "golden" / "toy_v1_small.json"


def test_calibration_hits_its_targets_exactly():
    assert abs(expected_solar(BASE).sum() - SOLAR_MWH_PER_MW) < 1e-8
    assert abs(expected_wind_per_mw(BASE).sum() / 8760 - 0.30) < 1e-12
    assert abs(solar_eta(1.5, "halfsine") - 0.653966) < 5e-6
    assert abs(wind_mu(0.0, 1.2) + 1.081914) < 5e-6
    zero = BASE.with_(s_c=0.0, s_w=0.0)
    assert abs(expected_solar(zero).sum() - SOLAR_MWH_PER_MW) < 1e-8


def test_every_archetype_is_250_mwh():
    for a in ARCHETYPES:
        for p in (BASE, BASE.with_(b_o=0.2, a_f=0.25, e_m=0.65)):
            assert abs(archetype_shape(a, p).sum() - 250.0) < 1e-9


def test_ar1_is_stationary_with_unit_variance():
    eps = np.random.default_rng(1).standard_normal((4, 200_000))
    y = ar1(eps, 0.9)
    assert abs(y.var() - 1.0) < 0.02
    assert abs(np.corrcoef(y[0, :-1], y[0, 1:])[0, 1] - 0.9) < 0.01
    assert np.array_equal(ar1(eps, 0.0), eps)


def test_streams_are_common_random_numbers():
    a = ToyEngine(BASE, 3)
    b = ToyEngine(BASE.with_(s_c=2.0, theta_s=0.25), 3)
    assert np.array_equal(a.wind_per_mw, b.wind_per_mw)  # wind does not depend on s_c or the mix
    assert np.array_equal(a.site_demand(7), b.site_demand(7))
    c = ToyEngine(BASE, 5)
    assert np.array_equal(a.site_demand(4), c.site_demand(4)[:3])  # scenario s is its own stream


def test_books_are_nested_and_capped_sums():
    e = ToyEngine(BASE, 2)
    books = {n: c for n, c, _ in e.books([2, 5])}
    direct = sum(np.minimum(e.site_demand(i), 2.5) for i in range(5))
    assert np.allclose(books[5], direct, rtol=1e-12)
    assert (books[5] >= books[2]).all()


def test_named_configs():
    assert len(oat_configs()) == 21 and len(lhs_configs()) == 40
    assert named_config("lhs-07") == dict(lhs_configs())["lhs-07"]
    assert named_config("book_order=shuffled").book_order == "shuffled"
    for _, p in lhs_configs():
        assert 0.2 <= p.theta_s <= 0.8 and -0.3 <= p.rho_dg <= 0.3


def _golden_stats() -> dict:
    e = ToyEngine(BASE, 4)
    books = {str(n): float(c.sum()) for n, c, _ in e.books([3, 10])}
    return {
        "p71_sum": float(e.generation(Pool.P71).sum()),
        "p72_sum": float(e.generation(Pool.P72).sum()),
        "books": books,
        "prospects": {a.value: float(e.prospect_demand(a).sum()) for a in ARCHETYPES},
        "shuffled_archetypes": [ToyEngine(BASE.with_(book_order="shuffled"), 1).site_archetype(i).value
                                for i in range(9)],
    }


def test_golden_toy_v1():
    """Pins toy v1: x02 and x03 depend on it. Regenerate only with tests/golden/generate.py --force."""
    if not GOLDEN.exists():
        pytest.skip("golden fixture not generated yet")
    want = json.loads(GOLDEN.read_text())
    got = _golden_stats()
    assert got["shuffled_archetypes"] == want["shuffled_archetypes"]
    assert set(got["books"]) == set(want["books"])
    for k in ("p71_sum", "p72_sum"):
        assert got[k] == pytest.approx(want[k], rel=1e-12)
    for k, v in want["books"].items():
        assert got["books"][k] == pytest.approx(v, rel=1e-12)
    for k, v in want["prospects"].items():
        assert got["prospects"][k] == pytest.approx(v, rel=1e-12)
