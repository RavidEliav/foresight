import numpy as np
import pytest

from app.wafer import DIE, PATTERNS, die_grid, simulate


def test_every_die_lies_inside_the_wafer():
    x, y = die_grid()
    assert len(x) > 300
    assert np.all(np.hypot(np.abs(x) + DIE / 2, np.abs(y) + DIE / 2) <= 1)


def test_same_run_gives_the_same_wafer():
    a, b = simulate(1458, True, 0.8), simulate(1458, True, 0.8)
    assert a.pattern == b.pattern
    assert np.array_equal(a.bad, b.bad)
    assert not np.array_equal(a.bad, simulate(1459, True, 0.8).bad)


def test_a_passing_run_has_no_pattern_and_few_defects():
    for run_id in range(50):
        wafer = simulate(run_id, False, 1.0)
        assert wafer.pattern is None
        assert wafer.die_yield > 0.93


def test_a_failing_run_gets_a_defect_pattern_on_top_of_the_scatter():
    patterns = set()
    for run_id in range(60):
        failed, passed = simulate(run_id, True, 0.5), simulate(run_id, False, 0.5)
        patterns.add(failed.pattern)
        assert failed.bad_dies > passed.bad_dies
    assert patterns == set(PATTERNS)


def test_scattered_defects_grow_with_the_risk_score():
    low = sum(simulate(i, False, 0.0).bad_dies for i in range(40))
    high = sum(simulate(i, False, 1.0).bad_dies for i in range(40))
    assert high > 2 * low


def test_risk_is_clipped_to_zero_to_one():
    assert simulate(1, False, 7.0).risk == 1.0
    assert simulate(1, False, -1.0).risk == 0.0


def test_unknown_pattern_is_an_error():
    from app.wafer import _pattern

    x, y = die_grid()
    with pytest.raises(ValueError):
        _pattern("spiral", x, y, np.random.default_rng(0))
