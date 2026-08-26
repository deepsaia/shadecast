"""The H5 and H6 rules for the surface temperature channel."""

from shadecast.experiments.channel import verdict


def _row(grass: float, cobble: float) -> dict:
    return {
        "city": "x",
        "cells": [
            {"kind": "depave", "pixels": 100, "treated_drop_C": grass},
            {"kind": "permeable", "pixels": 100, "treated_drop_C": cobble},
        ],
    }


def test_cooling_in_the_predicted_order_supports_both():
    """The finding this guards: cooling must follow the surface temperature coefficient."""
    result = verdict([_row(1.8, 0.9), _row(1.4, 0.7)])
    assert result["h5_cools"]
    assert result["h5_in_predicted_range"]
    assert result["h6_monotone"]
    assert not result["h6_falsified"]


def test_warming_falsifies_h5():
    """De-paving warming would mean the longwave channel is as broken as the albedo one."""
    result = verdict([_row(-0.4, -0.2)])
    assert result["h5_falsified"]
    assert not result["h5_cools"]


def test_cobble_out_cooling_grass_falsifies_h6():
    """A rougher, hotter surface out-cooling grass would mean the channel is not physical."""
    result = verdict([_row(0.6, 1.5)])
    assert result["h6_falsified"]
    assert not result["h6_monotone"]


def test_cooling_outside_the_predicted_band_is_recorded_not_hidden():
    """A prediction that misses its own band should say so rather than round into it."""
    result = verdict([_row(6.0, 2.0)])
    assert result["h5_cools"]
    assert not result["h5_in_predicted_range"]


def test_verdict_is_inconclusive_without_placed_cells():
    assert not verdict([{"city": "x", "cells": [{"kind": "depave", "pixels": 0}]}])["conclusive"]
