"""A trained model carries a manifest a reader can understand without the code."""

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


def _pair(root: Path, key: str, tile_id: str) -> tuple[Path, Path]:
    tile = root / "6143" / tile_id
    bundle = tile / "bundle"
    surrogate = tile / "surrogate"
    (surrogate / "baseline").mkdir(parents=True)
    bundle.mkdir()
    (bundle / "provenance.json").write_text(
        json.dumps({"city": {"key": key}, "tile": {"id": tile_id, "urban_centre": 6143}})
    )
    (surrogate / "baseline" / "engine.json").write_text(
        json.dumps({"engine": "solweig-gpu", "version": "solweig_gpu 2.0.0", "seconds": 185.1})
    )
    (surrogate / "manifest.json").write_text(
        json.dumps(
            {
                "manifest": [
                    {"id": "sparse_probe_0000", "family": "sparse_probe", "engine_seconds": 358.3},
                    {"id": "clustered_0105", "family": "clustered", "engine_seconds": 210.0},
                ]
            }
        )
    )
    (surrogate / "model.pt").write_bytes(b"weights")
    return surrogate, bundle


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
        "checkpoint": "model.pt",
    }


def _inputs(tmp_path: Path) -> ManifestInputs:
    surrogate, bundle = _pair(tmp_path, "ahmedabad", "t43N_249_2547")
    return ManifestInputs(
        model_id="response-unet-ahmedabad-20261023T120000",
        created="2026-10-23T12:00:00+00:00",
        pairs=[(surrogate, bundle)],
        report=_report(),
        patch_px=256,
        per_entry=24,
        model_path=surrogate / "model.pt",
    )


def test_manifest_has_every_required_section(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    manifest.check(built)
    assert set(manifest.REQUIRED_SECTIONS) <= set(built)


def test_manifest_describes_the_architecture_and_inputs(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    assert built["architecture"]["class"] == "ResponseUNet"
    assert built["architecture"]["parameters"] == 7_764_193
    assert built["architecture"]["widths"] == [32, 64, 128, 256]
    assert built["architecture"]["receptive_field_m"] == 152
    assert [channel["name"] for channel in built["inputs"]["channels"]][:2] == [
        "placement",
        "baseline_tmrt",
    ]
    assert built["inputs"]["channels"][1]["scale"] == 80.0
    assert built["output"]["units"] == "degrees Celsius"


def test_manifest_records_the_data_training_and_provenance(tmp_path):
    built = manifest.build(_inputs(tmp_path))
    assert built["data"]["tiles"] == [
        {"city": "ahmedabad", "tile": "t43N_249_2547", "urban_centre": 6143, "designs": 2}
    ]
    assert built["data"]["design_families"] == {"sparse_probe": 1, "clustered": 1}
    assert built["data"]["held_out_designs"] == ["clustered_0105"]
    assert built["data"]["patch_px"] == 256
    assert built["training"]["settings"]["patience"] == 3
    assert built["training"]["best_epoch"] == 4
    assert built["metrics"]["best_skill"] == 0.71
    assert built["provenance"]["engine"] == "solweig_gpu 2.0.0"
    assert len(built["provenance"]["code_commit"]) >= 7
    assert built["weights"]["file"] == "model.pt"
    assert len(built["weights"]["sha256"]) == 64
    assert built["licence"] == "Apache-2.0"


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
    result = runner.invoke(app, ["surrogate", "describe", str(tmp_path / "model"), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["model_id"] == built["model_id"]
    table = runner.invoke(app, ["surrogate", "describe", str(tmp_path / "model")])
    assert "ResponseUNet" in table.stdout


def test_describe_refuses_a_model_without_a_manifest(tmp_path):
    (tmp_path / "old").mkdir()
    result = runner.invoke(app, ["surrogate", "describe", str(tmp_path / "old")])
    assert result.exit_code == 1
    assert "manifest" in result.output


def test_new_model_id_names_cities_and_the_time(tmp_path):
    surrogate, bundle = _pair(tmp_path, "ahmedabad", "t43N_249_2547")
    created = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
    assert manifest.new_model_id([(surrogate, bundle)], created) == (
        "response-unet-ahmedabad-20261023T120000"
    )
