"""A trained model carries a manifest under a kilobyte that says what cannot be recomputed."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shadecast.cli import app
from shadecast.surrogate import manifest
from shadecast.surrogate.manifest_inputs import ManifestInputs
from shadecast.surrogate.training_settings import TrainingSettings

runner = CliRunner()
TILE = "t43N_249_2547"


def _pair(root: Path, key: str, tile_id: str) -> tuple[Path, Path]:
    tile = root / "6143" / tile_id
    bundle = tile / "bundle"
    physics = tile / "physics"
    (physics / "baseline").mkdir(parents=True)
    bundle.mkdir()
    (bundle / "provenance.json").write_text(
        json.dumps({"city": {"key": key}, "tile": {"id": tile_id, "urban_centre": 6143}})
    )
    (physics / "baseline" / "engine.json").write_text(
        json.dumps({"engine": "solweig-gpu", "version": "solweig_gpu 2.0.0", "seconds": 185.1})
    )
    (physics / "manifest.json").write_text(
        json.dumps(
            {
                "manifest": [
                    {"id": "sparse_probe_0000", "family": "sparse_probe", "engine_seconds": 358.3},
                    {"id": "clustered_0105", "family": "clustered", "engine_seconds": 210.0},
                ]
            }
        )
    )
    (physics / "model.pt").write_bytes(b"weights")
    return physics, bundle


def _report() -> dict:
    return {
        "device": "cpu",
        "settings": TrainingSettings(epochs=6, patience=3, device="cpu").as_dict(),
        "best_epoch": 4,
        "last_epoch": 6,
        "stopped_early": False,
        "selection": "best held-out skill",
        "best_skill": 0.71,
        "final_skill": 0.71,
        "final_test_mae_C": 0.4,
        "zero_baseline_mae_C": 1.4,
        "train_patches": 9,
        "test_patches": 3,
        "held_out_designs": ["clustered_0105"],
        "holdout_mode": "design",
        "holdout_city": None,
        "train_seconds": 12.5,
        "history": [{"epoch": 1, "train_loss": 0.5, "test_mae_C": 0.6, "skill": 0.5}],
    }


def _inputs(tmp_path: Path) -> ManifestInputs:
    physics, bundle = _pair(tmp_path, "ahmedabad", TILE)
    return ManifestInputs(
        model_id="response-unet-ahmedabad-20261023T120000",
        created="2026-10-23T12:00:00+00:00",
        pairs=[(physics, bundle)],
        report=_report(),
        patch_px=256,
        per_entry=24,
        model_path=physics / "model.pt",
    )


def test_manifest_has_every_required_section_and_nothing_the_code_can_recompute(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    manifest.check(built)
    assert set(built) == set(manifest.REQUIRED_SECTIONS)
    assert built["model"] == {
        "class": "ResponseUNet",
        "width": 32,
        "depth": 4,
        "channel_set": "engine",
    }
    assert len(json.dumps(built, separators=(",", ":"))) < 1024  # under a kilobyte of facts


def test_manifest_records_the_data_training_metrics_and_provenance(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    assert built["data"]["tiles"] == [f"6143/{TILE}"]
    assert built["data"]["held_out_designs"] == ["clustered_0105"]
    assert built["data"]["patch_px"] == 256 and built["data"]["patches_per_design"] == 24
    assert built["data"]["train_patches"] == 9 and built["data"]["test_patches"] == 3
    assert built["training"]["patience"] == 3 and built["training"]["epochs"] == 6
    assert built["training"]["best_epoch"] == 4 and built["training"]["device"] == "cpu"
    assert built["metrics"] == {"best_skill": 0.71, "test_mae_C": 0.4, "zero_baseline_mae_C": 1.4}
    assert built["provenance"]["engine"] == "solweig_gpu 2.0.0"
    assert built["provenance"]["torch"] and len(built["provenance"]["code_commit"]) >= 7
    assert len(built["weights_sha256"]) == 64


def test_size_and_reach_are_recomputed_from_the_model_section():
    engine = manifest.architecture({"width": 32, "depth": 4, "channel_set": "engine"})
    assert engine["parameters"] == 7_765_345  # eleven input channels
    assert engine["receptive_field_m"] == 204 and engine["receptive_field_min_m"] == 188
    assert engine["channels"][7] == "sky_view_factor"
    base = manifest.architecture({"channel_set": "base"})
    assert base["parameters"] == 7_764_193 and base["channels"][-1] == "is_vegetated"


def test_a_bundle_without_a_tile_record_is_refused(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "provenance.json").write_text(json.dumps({"city": {"key": "phoenix"}}))
    with pytest.raises(ValueError, match="tile record"):
        manifest.tile_ref(bundle)


def test_city_keys_name_each_city_once(tmp_path):
    first = _pair(tmp_path, "ahmedabad", TILE)
    second = _pair(tmp_path, "ahmedabad", "t43N_250_2547")
    assert manifest.city_keys([first, second]) == ["ahmedabad"]


def test_the_training_curve_is_a_rounded_table(tmp_path):
    history = [{"epoch": 1, "train_loss": 0.48496803, "test_mae_C": 1.13163745, "skill": 0.157724}]
    path = manifest.save_epochs(history, tmp_path / "model" / manifest.EPOCHS_FILE)
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {"epoch": "1", "train_loss": "0.485", "test_mae_C": "1.1316", "skill": "0.1577"}
    ]


def test_check_names_a_missing_section():
    with pytest.raises(ValueError, match="training"):
        manifest.check({"model_id": "x"})


def test_write_and_read_round_trip(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    path = manifest.write(tmp_path / "model", built)
    assert path.name == "manifest.json"
    assert manifest.read(tmp_path / "model") == built


def test_describe_command_prints_the_manifest(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    manifest.write(tmp_path / "model", built)
    result = runner.invoke(
        app, ["surrogate", "treeshade", "describe", str(tmp_path / "model"), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["model_id"] == built["model_id"]
    table = runner.invoke(app, ["surrogate", "treeshade", "describe", str(tmp_path / "model")])
    assert "ResponseUNet" in table.stdout and "188 to 204 m" in table.stdout


def test_describe_refuses_a_model_without_a_manifest(tmp_path):
    (tmp_path / "old").mkdir()
    result = runner.invoke(app, ["surrogate", "treeshade", "describe", str(tmp_path / "old")])
    assert result.exit_code == 1
    assert "manifest" in result.output


def test_new_model_id_names_cities_and_the_time(tmp_path):
    physics, bundle = _pair(tmp_path, "ahmedabad", TILE)
    created = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
    assert manifest.new_model_id([(physics, bundle)], created) == (
        "response-unet-ahmedabad-20261023T120000"
    )


def test_describe_shows_the_receptive_field_as_a_range():
    assert manifest.receptive_field_text(
        {"receptive_field_m": 204, "receptive_field_min_m": 188}
    ) == ("188 to 204 m")
    assert manifest.receptive_field_text({"receptive_field_m": 152}) == "152 m"


def test_a_report_without_a_channel_key_is_read_as_base():
    assert manifest.channel_set_of({"settings": {}}) == "base"
    assert manifest.channel_set_of({"settings": {"channels": "engine"}}) == "engine"


def test_new_model_id_names_each_city_once_and_counts_pooled_tiles(tmp_path):
    first = _pair(tmp_path, "ahmedabad", TILE)
    second = _pair(tmp_path, "ahmedabad", "t43N_250_2547")
    created = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
    assert manifest.new_model_id([first, second], created) == (
        "response-unet-ahmedabad-2tiles-20261023T120000"
    )
