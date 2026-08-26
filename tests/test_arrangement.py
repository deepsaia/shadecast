"""The arrangement experiment: does spatial pattern change what a budget buys?"""

import numpy as np

from shadecast.experiments.arrangement import verdict


def test_verdict_detects_disagreeing_objectives():
    """The finding this guards: two standard objectives can select opposite plans."""
    rows = [
        {"arrangement": "clustered", "exposure_drop_C": 1.0, "people_below_threshold": 900.0},
        {"arrangement": "random", "exposure_drop_C": 3.0, "people_below_threshold": 200.0},
    ]
    result = verdict(rows)
    assert result["conclusive"]
    assert result["scattered_beats_clustered_on_exposure_by"] == 3.0
    assert result["clustered_beats_scattered_on_threshold_by"] == 4.5
    assert result["objectives_disagree"]


def test_verdict_reports_agreement_when_one_plan_wins_both():
    rows = [
        {"arrangement": "clustered", "exposure_drop_C": 1.0, "people_below_threshold": 100.0},
        {"arrangement": "random", "exposure_drop_C": 3.0, "people_below_threshold": 400.0},
    ]
    assert not verdict(rows)["objectives_disagree"]


def test_verdict_is_inconclusive_without_both_arrangements():
    rows = [{"arrangement": "clustered", "exposure_drop_C": 1.0, "people_below_threshold": 1.0}]
    assert not verdict(rows)["conclusive"]


def test_verdict_survives_a_zero_denominator():
    rows = [
        {"arrangement": "clustered", "exposure_drop_C": 0.0, "people_below_threshold": 0.0},
        {"arrangement": "random", "exposure_drop_C": 0.0, "people_below_threshold": 0.0},
    ]
    result = verdict(rows)
    assert np.isfinite(result["scattered_beats_clustered_on_exposure_by"])
