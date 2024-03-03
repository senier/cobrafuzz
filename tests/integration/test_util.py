import numpy as np
import pytest
from scipy.stats import chisquare

from cobrafuzz import util


def test_large_adaptive_range_preferred_value() -> None:
    r = util.AdaptiveRange()
    for _ in range(1, 1000):
        r.update(success=r.sample(1, 10) == 5)
    assert len([d for d in [r.sample(1, 10) for _ in range(1, 100)] if d == 5]) > 40

    for _ in range(1, 10000):
        r.update(success=r.sample(1, 10) != 5)
    assert len([d for d in [r.sample(1, 10) for _ in range(1, 100)] if d == 5]) < 25


def test_adaptive_rand_uniform() -> None:
    r = util.AdaptiveRange()
    data = [r.sample(lower=0, upper=1000) for _ in range(1, 100000)]
    result = chisquare(f_obs=list(np.bincount(data)))
    assert result.pvalue > 0.05


def test_large_adaptive_range_uniform() -> None:  # pragma: no cover
    for _ in range(5):
        r = util.AdaptiveRange()
        data = [r.sample(0, 2**16 - 1) for _ in range(1, 10000)]
        result = chisquare(f_obs=list(np.bincount(data)))
        if result.pvalue > 0.05:
            break
    else:
        pytest.fail("Non-uniform random numbers")
