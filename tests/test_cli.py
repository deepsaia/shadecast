"""Command line surface. No network and no engine, so these stay fast."""

from typer.testing import CliRunner

from shadecast.cities import CORPUS
from shadecast.cli import app
from shadecast.console import build_table, corpus_table, result_table

runner = CliRunner()


def test_help_lists_every_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("list", "build", "plan", "run"):
        assert command in result.stdout


def test_list_renders_the_corpus():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "ahmedabad" in result.stdout
    assert "Global South" in result.stdout


def test_list_json_is_parseable():
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    assert '"cities"' in result.stdout


def test_build_without_a_city_is_rejected():
    result = runner.invoke(app, ["build"])
    assert result.exit_code != 0


def test_build_rejects_an_unknown_city():
    result = runner.invoke(app, ["build", "atlantis"])
    assert result.exit_code != 0


def test_corpus_table_has_a_row_per_city():
    table = corpus_table(list(CORPUS.values()))
    assert table.row_count == len(CORPUS)


def test_build_table_starts_empty():
    assert build_table().row_count == 0


def test_result_table_renders_a_scored_plan():
    payload = {
        "city": "testville",
        "intervention": "tree",
        "design_day": "2024-05-23",
        "baseline": {"exposure": 55.0, "people_at_risk": 40000.0, "cost_usd": 0.0},
        "plan": {"exposure": 49.0, "people_at_risk": 32000.0, "cost_usd": 1000.0},
        "benefit": {
            "delta_exposure_C": 6.0,
            "delta_people_at_risk": 8000.0,
            "excess_reduced_per_1k_usd": 31.7,
        },
        "tmrt_drop_where_planted_C": 17.8,
        "spillover_C": 1.5,
    }
    assert result_table(payload).row_count > 0
