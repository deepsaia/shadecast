"""The H8 rule: route targeting must earn its place or be reported as redundant."""

import numpy as np

from shadecast.experiments.targeting import plan_overlap, verdict


def _row(overlap: float, area_drop: float, route_drop: float) -> dict:
    return {
        "city": "x",
        "plan_overlap": overlap,
        "area": {"route_exposure_drop_C": area_drop},
        "route": {"route_exposure_drop_C": route_drop},
    }


def test_plans_that_differ_and_help_support_h8():
    """The finding this guards: corridor targeting is only worth keeping if it does both."""
    result = verdict([_row(0.4, 0.5, 1.2), _row(0.5, 0.6, 1.1)])
    assert result["plans_differ"]
    assert result["route_targeting_helps"]
    assert result["supported"]
    assert not result["h8_falsified"]


def test_near_identical_plans_falsify_h8():
    """If both objectives pick the same plan, the network objective adds nothing."""
    result = verdict([_row(0.95, 0.9, 0.92), _row(0.97, 0.8, 0.81)])
    assert result["h8_falsified"]
    assert not result["supported"]


def test_different_plans_that_do_not_help_are_not_support():
    """Selecting a different plan is not the same as selecting a better one."""
    result = verdict([_row(0.3, 1.0, 1.05)])
    assert result["plans_differ"]
    assert not result["route_targeting_helps"]
    assert not result["supported"]


def test_verdict_is_inconclusive_without_scored_cities():
    assert not verdict([{"city": "x", "placed": 0}])["conclusive"]


def test_plan_overlap_is_symmetric_and_bounded():
    a = np.zeros((10, 10), dtype=bool)
    b = np.zeros((10, 10), dtype=bool)
    a[:5, :5] = True
    b[3:8, 3:8] = True
    value = plan_overlap(a, b)
    assert value == plan_overlap(b, a)
    assert 0.0 < value < 1.0
    assert plan_overlap(a, a) == 1.0


def test_two_empty_plans_do_not_divide_by_zero():
    empty = np.zeros((4, 4), dtype=bool)
    assert plan_overlap(empty, empty) == 1.0
