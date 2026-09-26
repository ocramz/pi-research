"""Identities of prospect valuation and the Jensen gap (theory note §2.2–2.3)."""

from fractions import Fraction

import numpy as np
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from epmlib.toy.matching import dual_error, dual_increment, increment, matched

q = st.fractions(min_value=0, max_value=10, max_denominator=64)


@given(q, q, q)
def test_delta_v_identity_is_exact(g, d_book, d):
    assert min(g, d_book + d) - min(g, d_book) == min(d, max(g - d_book, Fraction(0)))


shape = st.tuples(st.integers(1, 6), st.integers(1, 30))
nonneg = st.floats(0.0, 5.0, allow_nan=False, allow_infinity=False)


@given(shape.flatmap(lambda s: st.tuples(arrays(float, s, elements=nonneg), arrays(float, s, elements=nonneg),
                                         arrays(float, s, elements=nonneg))))
def test_dual_bounds_exact_and_error_identity(arrs):
    g, c, d = arrs
    dual, exact, err = dual_increment(g, c, d), increment(g, c, d), dual_error(g, c, d)
    assert (dual - exact >= -1e-12 * np.maximum(1, dual)).all()
    assert np.allclose(dual - exact, err, rtol=1e-12, atol=1e-12)
    assert np.allclose(matched(g, c + d) - matched(g, c), exact, rtol=1e-12, atol=1e-12)


@given(shape.flatmap(lambda s: st.tuples(arrays(float, s, elements=nonneg), arrays(float, s, elements=nonneg))))
def test_jensen_in_sample(arrs):
    g, c = arrs
    lhs = np.minimum(g.mean(axis=0), c.mean(axis=0))
    rhs = np.minimum(g, c).mean(axis=0)
    assert (lhs >= rhs - 1e-12).all()
