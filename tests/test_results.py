"""The results page's payload is derived from scored plans and experiment files, never typed in."""

import json
from pathlib import Path

from shadecast import dash_cli
from shadecast.dash import results

SOURCE = Path(dash_cli.__file__).parent / "dash"


def _city(key: str, plans: list[tuple[str, float, float, float, float, float]]) -> dict:
    return {
        "city": key,
        "name": key.title(),
        "provenance": {"canopy": 0.1, "built_fraction": 0.3, "population_2020": 1000, "tier": "A"},
        "baseline": {"exposure": 55.0, "at_risk": 400},
        "plans": {
            "list": [
                {
                    "id": f"{arr}_{i}",
                    "arrangement": arr,
                    "coverage": cov,
                    "cost_m": cost,
                    "exposure_drop": drop,
                    "people": people,
                    "efficiency": eff,
                }
                for i, (arr, cov, cost, drop, people, eff) in enumerate(plans)
            ]
        },
    }


def _payload():
    a = _city(
        "ahmedabad",
        [
            ("clustered", 0.026, 2.28, 0.60, 858, 14.4),
            ("clustered", 0.052, 4.56, 1.29, 2199, 15.3),
            ("scattered", 0.026, 2.28, 2.29, 239, 56.5),
            ("corridor", 0.026, 2.28, 2.08, 100, 51.6),
        ],
    )
    b = _city(
        "lagos",
        [
            ("clustered", 0.021, 1.82, 0.67, 4153, 30.2),
            ("scattered", 0.021, 1.82, 2.75, 4602, 156.3),
        ],
    )
    return [a, b]


def _pairs(tmp_path: Path):
    pairs = []
    for key in ("ahmedabad", "lagos"):
        surrogate = tmp_path / key / "surrogate"
        surrogate.mkdir(parents=True)
        (surrogate / "manifest.json").write_text(
            json.dumps({"manifest": [{"engine_seconds": 300.0}, {"engine_seconds": 360.0}]})
        )
        pairs.append((key, tmp_path / key / "bundle", surrogate))
    return pairs


def test_collect_derives_totals_matched_pairs_and_verdicts(tmp_path):
    payload = results.collect(_payload(), _pairs(tmp_path), tmp_path)
    assert payload["totals"] == {
        "cities": 2,
        "plans": 6,
        "budget_min_m": 1.82,
        "budget_max_m": 4.56,
    }
    ahmedabad = payload["cities"][0]
    assert ahmedabad["matched"]["clustered"]["coverage"] == 0.026
    assert ahmedabad["matched"]["ratio"] == round(56.5 / 14.4, 2)
    assert ahmedabad["physics"] == {
        "designs": 2,
        "engine_minutes": 11.0,
        "seconds_per_design_min": 300,
        "seconds_per_design_max": 360,
    }
    verdict = payload["arrangement"]
    assert verdict["cities_compared"] == 2 and verdict["scattered_wins"] == 2
    assert verdict["ratio_min"] == round(56.5 / 14.4, 2) and verdict["ratio_max"] == round(
        156.3 / 30.2, 2
    )


def test_ranking_orders_cities_by_scattered_efficiency_and_measures_the_spread(tmp_path):
    payload = results.collect(_payload(), _pairs(tmp_path), tmp_path)
    rows = payload["ranking"]["rows"]
    assert [row["key"] for row in rows] == ["lagos", "ahmedabad"]
    assert rows[0]["scattered_per_1k"] == 156.3 and rows[1]["clustered_per_1k"] == 14.85
    assert payload["ranking"]["spread"] == round(156.3 / 56.5, 1)


def test_experiment_files_are_passed_through_when_present(tmp_path):
    (tmp_path / "factorial.json").write_text(json.dumps([{"city": "ahmedabad", "kind": "tree"}]))
    payload = results.collect(_payload(), _pairs(tmp_path), tmp_path)
    assert payload["factorial"] == [{"city": "ahmedabad", "kind": "tree"}]
    assert payload["targeting"] is None or payload["targeting"] == {}


def test_matched_pair_ties_resolve_to_the_largest_coverage(tmp_path):
    city = _city(
        "x",
        [
            ("clustered", 0.01, 1.0, 0.1, 10, 10.0),
            ("scattered", 0.01, 1.0, 0.5, 5, 50.0),
            ("clustered", 0.10, 10.0, 1.0, 100, 12.0),
            ("scattered", 0.10, 10.0, 4.0, 50, 40.0),
        ],
    )
    payload = results.collect([city], [], tmp_path)
    matched = payload["cities"][0]["matched"]
    assert matched["clustered"]["coverage"] == 0.10 and matched["ratio"] == round(40 / 12, 2)


def test_a_city_with_a_baseline_but_no_plans_is_left_off_the_page(tmp_path):
    payload = results.collect([_city("empty", [])], [], tmp_path)
    assert payload["cities"] == [] and payload["totals"]["plans"] == 0


def test_a_city_without_both_arrangements_has_no_matched_pair(tmp_path):
    only = [_city("rio", [("corridor", 0.01, 1.0, 0.5, 10, 20.0)])]
    payload = results.collect(only, [], tmp_path)
    assert payload["cities"][0]["matched"] is None
    assert payload["arrangement"]["cities_compared"] == 0
    assert payload["ranking"]["spread"] is None


def test_the_results_page_carries_no_typed_numbers():
    page = (SOURCE / "result.html").read_text()
    for stale in ("39 plans", "3.5x", "Ahmedabad, Lagos, Rio", "2026-08-26"):
        assert stale not in page
    assert '<script src="result.js"></script>' in page
    assert "result.js" in dash_cli.RESULT_FILES
