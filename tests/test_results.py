"""The results across cities are derived from tile reports and experiment files, never typed in."""

import json
from pathlib import Path

from support import synthetic_tile
from support.fixtures import fixture_centres
from support.fixtures import fixture_corpus
from support.fixtures import fixture_tiles

from shadecast.corpus.tile_stages import TileStages
from shadecast.service.baseline_score import BaselineScore
from shadecast.service.city_catalog import CityCatalog
from shadecast.service.model_catalog import ModelCatalog
from shadecast.service.physics_facts import PhysicsFacts
from shadecast.service.plan import Plan
from shadecast.service.results_report import ResultsReport
from shadecast.service.selection import Selection
from shadecast.service.tile_facts import TileFacts
from shadecast.service.tile_index import TileIndex
from shadecast.service.tile_report import TileReport

PHYSICS = PhysicsFacts(designs=2, engine_minutes=11.0, seconds_per_design_min=300, seconds_per_design_max=360)
Row = tuple[str, float, float, float, int, float]


def _report(key: str, plans: list[Row], tile: str = "t43N_249_2547") -> TileReport:
    facts = TileFacts(
        key=key,
        name=key.title(),
        design_day=None,
        tier="A",
        buildings=None,
        built_fraction=0.3,
        canopy=0.1,
        population_2020=1000,
        lat=None,
        lon=None,
        urban_centre=None,
        sources={},
    )
    return TileReport(
        city=key,
        tile=tile,
        name=key.title(),
        stages=TileStages(bundle=True, baseline=True, physics=True),
        facts=facts,
        baseline=BaselineScore(exposure=55.0, at_risk=400),
        physics=PHYSICS,
        plans=[
            Plan(
                id=f"{arrangement}_{index}",
                arrangement=arrangement,
                coverage=coverage,
                trees=0,
                cost_usd=cost * 1e6,
                cost_m=cost,
                exposure_drop=drop,
                people=people,
                efficiency=efficiency,
            )
            for index, (arrangement, coverage, cost, drop, people, efficiency) in enumerate(plans)
        ],
    )


def _reports() -> list[TileReport]:
    ahmedabad = _report(
        "ahmedabad",
        [
            ("clustered", 0.026, 2.28, 0.60, 858, 14.4),
            ("clustered", 0.052, 4.56, 1.29, 2199, 15.3),
            ("scattered", 0.026, 2.28, 2.29, 239, 56.5),
            ("corridor", 0.026, 2.28, 2.08, 100, 51.6),
        ],
    )
    lagos = _report(
        "lagos",
        [
            ("clustered", 0.021, 1.82, 0.67, 4153, 30.2),
            ("scattered", 0.021, 1.82, 2.75, 4602, 156.3),
        ],
    )
    return [ahmedabad, lagos]


def _service(tmp_path: Path) -> ResultsReport:
    catalog = CityCatalog(
        Selection.resolved(fixture_corpus()),
        fixture_centres,
        TileIndex(tmp_path / "tiles", fixture_tiles),
        ModelCatalog(tmp_path / "models"),
    )
    return ResultsReport(catalog, tmp_path)


def test_collect_derives_totals_matched_pairs_and_verdicts(tmp_path):
    payload = _service(tmp_path).collect_from(_reports()).model_dump()
    assert payload["totals"] == {
        "cities": 2,
        "plans": 6,
        "budget_min_m": 1.82,
        "budget_max_m": 4.56,
    }
    ahmedabad = payload["cities"][0]
    assert ahmedabad["key"] == "ahmedabad" and ahmedabad["name"] == "Ahmedabad"
    assert ahmedabad["matched"]["clustered"]["coverage"] == 0.026
    assert ahmedabad["matched"]["ratio"] == round(56.5 / 14.4, 2)
    assert ahmedabad["physics"]["designs"] == 2 and ahmedabad["physics"]["engine_minutes"] == 11.0
    verdict = payload["arrangement"]
    assert verdict["cities_compared"] == 2 and verdict["scattered_wins"] == 2
    assert verdict["ratio_min"] == round(56.5 / 14.4, 2)
    assert verdict["ratio_max"] == round(156.3 / 30.2, 2)
    assert payload["as_of"]


def test_ranking_orders_cities_by_scattered_efficiency_and_measures_the_spread(tmp_path):
    ranking = _service(tmp_path).collect_from(_reports()).ranking
    assert [row.key for row in ranking.rows] == ["lagos", "ahmedabad"]
    assert ranking.rows[0].scattered_per_1k == 156.3 and ranking.rows[1].clustered_per_1k == 14.85
    assert ranking.spread == round(156.3 / 56.5, 1)


def test_experiment_files_are_passed_through_when_present(tmp_path):
    (tmp_path / "factorial.json").write_text(json.dumps([{"city": "ahmedabad", "kind": "tree"}]))
    results = _service(tmp_path).collect_from(_reports())
    assert results.factorial == [{"city": "ahmedabad", "kind": "tree"}]
    assert results.targeting is None


def test_matched_pair_ties_resolve_to_the_largest_coverage(tmp_path):
    city = _report(
        "x",
        [
            ("clustered", 0.01, 1.0, 0.1, 10, 10.0),
            ("scattered", 0.01, 1.0, 0.5, 5, 50.0),
            ("clustered", 0.10, 10.0, 1.0, 100, 12.0),
            ("scattered", 0.10, 10.0, 4.0, 50, 40.0),
        ],
    )
    matched = _service(tmp_path).collect_from([city]).cities[0].matched
    assert matched.clustered.coverage == 0.10 and matched.ratio == round(40 / 12, 2)


def test_a_tile_with_a_baseline_but_no_plans_is_left_off_the_page(tmp_path):
    results = _service(tmp_path).collect_from([_report("empty", [])])
    assert results.cities == [] and results.totals.plans == 0


def test_a_tile_without_both_arrangements_has_no_matched_pair(tmp_path):
    results = _service(tmp_path).collect_from([_report("rio", [("corridor", 0.01, 1.0, 0.5, 10, 20.0)])])
    assert results.cities[0].matched is None
    assert results.arrangement.cities_compared == 0
    assert results.ranking.spread is None


def test_two_tiles_of_one_city_are_labeled_apart(tmp_path):
    rows: list[Row] = [("clustered", 0.01, 1.0, 0.1, 10, 10.0)]
    reports = [_report("ahmedabad", rows), _report("ahmedabad", rows, tile="t43N_250_2547")]
    cities = _service(tmp_path).collect_from(reports).cities
    assert [city.key for city in cities] == ["ahmedabad-t43N_249_2547", "ahmedabad-t43N_250_2547"]
    assert cities[0].name == "Ahmedabad, tile t43N_249_2547"


def test_collect_reads_every_tile_with_physics_from_disk(tmp_path):
    tile = synthetic_tile.write_bundle(tmp_path / "tiles")
    synthetic_tile.write_baseline(tile)
    synthetic_tile.write_designs(tile)
    results = _service(tmp_path).collect()
    assert [city.key for city in results.cities] == ["ahmedabad"]
    assert results.totals.plans == 3 and results.arrangement.cities_compared == 1
