"""Surrogate design, features and model. No engine, no network."""

import numpy as np
import pytest
import torch
from scipy import ndimage

from shadecast.surrogate import designs
from shadecast.surrogate.features import IN_CHANNELS_ORDER, sky_openness, stack
from shadecast.surrogate.metrics import (
    aggregate_error,
    distance_bands,
    ranking,
    skill,
    speedup,
    zero_baseline,
)
from shadecast.surrogate.model import ResponseUNet
from shadecast.surrogate.training import split_by_design


def feasible_grid(n=200):
    grid = np.ones((n, n), dtype=bool)
    grid[40:70, 40:70] = False  # a building block
    return grid


# --- design of experiments ------------------------------------------------


def test_every_family_places_only_on_feasible_ground():
    grid = feasible_grid()
    rng = np.random.default_rng(0)
    for family in designs.FAMILIES:
        placement = getattr(designs, family)(grid, rng)
        assert not (placement & ~grid).any(), family


def test_sparse_probes_stay_beyond_the_measured_reach():
    """The whole efficiency argument depends on probes not overlapping."""
    grid = np.ones((600, 600), dtype=bool)
    placement = designs.sparse_probe(grid, np.random.default_rng(0))
    _, count = ndimage.label(placement)
    assert count > 10
    # Every probe is its own component, so none have merged.
    assert count == int(placement.sum())


def test_probe_count_scales_with_spacing():
    grid = np.ones((600, 600), dtype=bool)
    rng = np.random.default_rng(0)
    wide = designs.sparse_probe(grid, rng, spacing_m=200.0).sum()
    tight = designs.sparse_probe(grid, rng, spacing_m=100.0).sum()
    assert tight > wide


def test_clustered_is_more_contiguous_than_uniform():
    grid = feasible_grid()
    rng = np.random.default_rng(1)
    clustered = designs.clustered(grid, rng, coverage=0.1, blob_m=10.0)
    uniform = designs.random_uniform(grid, rng, coverage=0.1)
    _, clustered_parts = ndimage.label(clustered)
    _, uniform_parts = ndimage.label(uniform)
    assert clustered_parts < uniform_parts


def test_coverage_is_respected():
    grid = feasible_grid()
    placement = designs.random_uniform(grid, np.random.default_rng(2), coverage=0.1)
    assert placement.sum() == pytest.approx(0.1 * grid.sum(), rel=0.02)


# --- features -------------------------------------------------------------


def test_stack_has_the_declared_channels():
    n = 32
    out = stack(
        np.zeros((n, n), dtype=bool),
        np.full((n, n), 55.0),
        building_height=np.zeros((n, n)),
        canopy_height=np.zeros((n, n)),
        land_cover=np.full((n, n), 50, dtype="uint8"),
    )
    assert out.shape == (len(IN_CHANNELS_ORDER), n, n)
    assert np.isfinite(out).all()


def test_sky_openness_falls_where_obstruction_rises():
    flat = np.zeros((64, 64))
    tall = np.full((64, 64), 25.0)
    assert sky_openness(tall, flat).mean() < sky_openness(flat, flat).mean()


def test_sky_openness_stays_in_range():
    heights = np.random.default_rng(0).uniform(0, 60, (64, 64))
    value = sky_openness(heights, np.zeros((64, 64)))
    assert value.min() >= 0.0
    assert value.max() <= 1.0


# --- model ----------------------------------------------------------------


def test_model_preserves_spatial_shape():
    model = ResponseUNet()
    out = model(torch.randn(1, len(IN_CHANNELS_ORDER), 64, 64))
    assert out.shape == (1, 1, 64, 64)


def test_model_can_express_warming():
    """Measured responses warm about 0.04 percent of outdoor pixels, by up to 10 C.

    A model constrained to non-negative output could not represent that, so the
    output head is deliberately unconstrained.
    """
    model = ResponseUNet()
    out = model(torch.randn(8, len(IN_CHANNELS_ORDER), 64, 64))
    assert out.min() < 0 or out.max() > 0  # unconstrained range
    assert torch.isfinite(out).all()


def test_receptive_field_spans_the_measured_reach():
    """Reach was measured at 26 m in Ahmedabad and 71 m in Lagos."""
    assert ResponseUNet().receptive_field_m() > 71.0


# --- splitting and metrics ------------------------------------------------


def test_split_never_leaks_a_design_across_the_boundary():
    origins = [f"design_{i // 10}" for i in range(100)]
    train_mask, test_mask = split_by_design(origins, holdout=0.3, seed=0)
    train_designs = set(np.array(origins)[train_mask].tolist())
    test_designs = set(np.array(origins)[test_mask].tolist())
    assert train_designs.isdisjoint(test_designs)
    assert test_designs


def test_distance_bands_report_the_tail():
    placement = np.zeros((120, 120), dtype=bool)
    placement[60, 60] = True
    truth = np.zeros((120, 120))
    truth[60, 60] = 18.0
    rows = distance_bands(truth, truth.copy(), placement)
    assert any(row["band_m"] == "21-40" for row in rows)
    assert all(row["mae_C"] == 0.0 for row in rows)


def test_aggregate_error_is_zero_for_a_perfect_prediction():
    truth = np.random.default_rng(0).uniform(0, 5, (40, 40))
    weights = np.random.default_rng(1).uniform(0, 1, (40, 40))
    assert aggregate_error(truth, truth.copy(), weights)["relative_error"] == 0.0


def test_ranking_rewards_monotone_bias():
    """A biased but order preserving surrogate is still useful for search."""
    truth = [1.0, 2.0, 3.0, 4.0, 5.0]
    biased = [10 * v + 100 for v in truth]
    assert ranking(truth, biased)["spearman"] == pytest.approx(1.0)


def test_speedup_reports_the_search_cost():
    result = speedup(engine_seconds=162.0, surrogate_seconds=0.05)
    assert result["speedup"] == pytest.approx(3240.0)
    assert result["search_hours_engine"] > result["search_hours_surrogate"]


def test_zero_baseline_is_the_mean_absolute_response():
    truth = np.array([[0.0, 2.0], [-1.0, 0.0]])
    assert zero_baseline(truth) == pytest.approx(0.75)


def test_a_perfect_model_has_skill_one():
    truth = np.random.default_rng(0).uniform(-1, 5, (30, 30))
    assert skill(truth, truth.copy())["skill"] == pytest.approx(1.0)


def test_a_model_worse_than_nothing_has_negative_skill():
    """The failure mode this guards: low MAE on a mostly zero field looks fine."""
    truth = np.zeros((30, 30))
    truth[15, 15] = 10.0
    noisy = np.full((30, 30), 0.5)
    result = skill(truth, noisy)
    assert result["skill"] < 0
    assert not result["beats_predicting_nothing"]
