"""Objectives, exposure weighting and the intervention model."""

import numpy as np
import pytest

from shadecast import interventions as IV
from shadecast.data.landcover import ASPHALT, GRASS, ROOF, WATER, to_umep
from shadecast.exposure import outdoor_mask, outdoor_weights
from shadecast.objectives import benefit, score


def _toy(n=60):
    bh = np.zeros((n, n), dtype="float32")
    bh[10:25, 10:25] = 12.0  # a block of buildings
    pop = np.zeros((n, n), dtype="float32")
    pop[10:25, 10:25] = 4.0  # everyone lives in it
    tmrt = np.full((n, n), 60.0, dtype="float32")
    tmrt[30:40, 30:40] = 40.0  # a cool patch
    return bh, pop, tmrt


def test_outdoor_weights_conserve_population():
    bh, pop, _ = _toy()
    w = outdoor_weights(pop, bh)
    assert w.sum() == pytest.approx(pop.sum(), rel=1e-4)


def test_outdoor_weights_place_nobody_on_buildings():
    bh, pop, _ = _toy()
    w = outdoor_weights(pop, bh)
    assert w[bh > 0].sum() == pytest.approx(0.0, abs=1e-6)


def test_outdoor_weights_reach_the_street():
    """The whole point: residents must get weight on nearby outdoor pixels."""
    bh, pop, _ = _toy()
    w = outdoor_weights(pop, bh, reach_m=8.0)
    assert w[26:30, 10:25].sum() > 0


def test_cooling_reduces_every_harm_metric():
    bh, pop, tmrt = _toy()
    w = outdoor_weights(pop, bh)
    m = outdoor_mask(bh)
    b = score(np.where(m, tmrt, 0), w, 0.0)
    a = score(np.where(m, tmrt - 6.0, 0), w, 1000.0)
    assert a.exposure < b.exposure
    assert a.excess < b.excess
    assert a.people_at_risk <= b.people_at_risk


def test_benefit_efficiency_is_zero_for_free_plans():
    bh, pop, tmrt = _toy()
    w = outdoor_weights(pop, bh)
    m = outdoor_mask(bh)
    s = score(np.where(m, tmrt, 0), w, 0.0)
    assert benefit(s, s)["excess_reduced_per_1k_usd"] == 0.0


# --- interventions --------------------------------------------------------


def test_buildings_override_landcover():
    wc = np.full((4, 4), 80, dtype="uint8")  # all water per WorldCover
    bh = np.zeros((4, 4))
    bh[1, 1] = 9.0
    umep = to_umep(wc, bh)
    assert umep[1, 1] == ROOF
    assert umep[0, 0] == WATER


def test_nothing_is_planted_on_a_building():
    umep = np.full((5, 5), GRASS, dtype="uint8")
    bh = np.zeros((5, 5))
    bh[2, 2] = 10.0
    for kind in ("tree", "shade", "cool_paving"):
        assert not IV.feasibility_mask(umep, bh, kind)[2, 2], kind


def test_cool_roof_only_on_roofs():
    umep = np.array([[ROOF, ASPHALT], [GRASS, ROOF]], dtype="uint8")
    bh = np.array([[5.0, 0.0], [0.0, 5.0]])
    m = IV.feasibility_mask(umep, bh, "cool_roof")
    assert m.tolist() == [[True, False], [False, True]]


def test_tree_raises_canopy_and_never_lowers_it():
    cdsm = np.array([[0.0, 12.0]], dtype="float32")
    place = np.array([[True, True]])
    new, _ = IV.apply("tree", place, cdsm, np.zeros((1, 2), dtype="uint8"))
    assert new[0, 0] == 8.0  # bare ground gains a tree
    assert new[0, 1] == 12.0  # an existing taller tree is not shrunk


def test_cost_is_linear_in_area_and_includes_maintenance():
    one = IV.cost("tree", np.ones(1, dtype=bool), 1.0)
    ten = IV.cost("tree", np.ones(10, dtype=bool), 1.0)
    assert ten == pytest.approx(10 * one)
    capital = IV.CATALOGUE["tree"].unit_cost
    assert one > capital  # discounted maintenance must be added on top
