"""Seeded random streams. A stream is keyed by an entropy list, as the PREREGs write them
(`SeedSequence([20260926, s, entity])`), so a result never depends on worker order.

Never derive a seed from `hash()`: it is salted per process."""

from __future__ import annotations

import numpy as np


def seed_sequence(*entropy: int) -> np.random.SeedSequence:
    if not entropy:
        raise ValueError("a stream needs at least one entropy value")
    return np.random.SeedSequence([int(e) for e in entropy])


def generator(*entropy: int) -> np.random.Generator:
    """`default_rng(SeedSequence([...entropy]))`: PCG64 on the registered key."""
    return np.random.default_rng(seed_sequence(*entropy))
