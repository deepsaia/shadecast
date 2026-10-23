"""The manifest written beside every trained model.

A checkpoint is a bag of weights; a manifest says what they are. It records the architecture
and its size, every input channel and its scale, what the output means, which tiles and designs
the model saw and which it was tested on, every training setting and how the kept epoch was
chosen, the metrics, the engine and code that produced it, and a digest of the weights file.
A reader with the manifest and no code can say what the model is and whether to trust it.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import torch

from ..data.checksum import sha256
from . import features
from .manifest_inputs import ManifestInputs
from .model import ResponseUNet
from .patches import entries

MANIFEST_FILE = "manifest.json"
REQUIRED_SECTIONS = (
    "model_id",
    "created",
    "architecture",
    "inputs",
    "output",
    "data",
    "training",
    "metrics",
    "provenance",
    "weights",
    "licence",
    "intended_use",
)
INTENDED_USE = (
    "Predict the daylight-mean change in mean radiant temperature a tree planting plan causes "
    "on the tile it was trained on or on tiles with similar morphology; verify any plan chosen "
    "with it against the physics engine before reporting it."
)
LAND_COVER_FLAGS = {
    "is_water": {"worldcover_classes": [features.WATER_CLASS]},
    "is_vegetated": {"worldcover_classes": list(features.VEGETATED_CLASSES)},
}
RESOLUTION_M = 1.0
RECEPTIVE_FIELD_METHOD = (
    "gradient probe of a one-dimensional analog over one pooling cell, every path open; "
    "the field varies with the output pixel's place in the cell"
)
SCALES = {
    "baseline_tmrt": features.TMRT_SCALE,
    "building_height": features.HEIGHT_SCALE,
    "canopy_height": features.CANOPY_SCALE,
    "sun_noon_elevation": features.ELEVATION_SCALE,
}
DEFINITIONS = {
    "sky_openness": (
        f"1 minus mean obstruction height within {features.OPENNESS_RADIUS_M:.0f} m "
        f"over {features.HEIGHT_SCALE:.0f} m, clipped to 0 to 1"
    ),
    "sky_view_factor": "the engine's ray-cast sky view factor from the baseline run, 0 to 1",
    "sunlit_fraction": (
        "share of the daylight hours, 08:00 to 18:00, in which the sun reaches the pixel, "
        "from the baseline run's hourly shadow stack"
    ),
    "sun_noon_elevation": (
        "solar noon elevation on the design day from latitude and Cooper's declination, "
        "constant over the tile"
    ),
    "sun_noon_side": (
        "+1 when the noon sun is to the south, -1 when to the north, constant over the tile"
    ),
}


def architecture(in_channels: int) -> dict:
    model = ResponseUNet(in_channels=in_channels)
    return {
        "class": type(model).__name__,
        "depth": model.depth,
        "widths": [model.width * 2**level for level in range(model.depth)],
        "bottleneck": model.width * 2**model.depth,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "receptive_field_m": round(model.receptive_field_m(RESOLUTION_M)),
        "receptive_field_min_m": round(model.receptive_field_px()[0] * RESOLUTION_M),
        "receptive_field_method": RECEPTIVE_FIELD_METHOD,
        "output_constraint": "none, warming near a new tree is a measured effect",
    }


def inputs(channel_set: str) -> dict:
    channels = []
    for name in features.CHANNEL_SETS[channel_set]:
        channel: dict = {"name": name, "scale": SCALES.get(name)}
        channel.update(LAND_COVER_FLAGS.get(name, {}))
        if name in DEFINITIONS:
            channel["definition"] = DEFINITIONS[name]
        channels.append(channel)
    return {"resolution_m": RESOLUTION_M, "channel_set": channel_set, "channels": channels}


def channel_set_of(report: dict) -> str:
    """The channel set a training report says it used; reports older than the key used base."""
    return str(report.get("settings", {}).get("channels", "base"))


def output() -> dict:
    return {
        "quantity": "baseline minus plan mean radiant temperature, daylight mean",
        "daylight_window": "08:00 to 18:00 local",
        "units": "degrees Celsius",
        "sign": "positive is cooling",
    }


def _tile_record(surrogate_dir: Path, bundle: Path) -> dict:
    provenance = json.loads((Path(bundle) / "provenance.json").read_text())
    return {
        "city": provenance.get("city", {}).get("key"),
        "tile": provenance.get("tile", {}).get("id"),
        "urban_centre": provenance.get("tile", {}).get("urban_centre"),
        "designs": len(entries(surrogate_dir)),
    }


def _design_families(pairs: list[tuple[Path, Path]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for surrogate_dir, _ in pairs:
        for meta in entries(surrogate_dir):
            family = str(meta.get("family"))
            counts[family] = counts.get(family, 0) + 1
    return counts


def data_section(built: ManifestInputs) -> dict:
    report = built.report
    return {
        "tiles": [_tile_record(surrogate_dir, bundle) for surrogate_dir, bundle in built.pairs],
        "design_families": _design_families(built.pairs),
        "held_out_designs": report.get("held_out_designs", []),
        "holdout_mode": report.get("holdout_mode"),
        "holdout_city": report.get("holdout_city"),
        "patch_px": built.patch_px,
        "patches_per_design": built.per_entry,
        "train_patches": report.get("train_patches"),
        "test_patches": report.get("test_patches"),
    }


def training_section(report: dict) -> dict:
    return {
        "settings": report.get("settings", {}),
        "device": report.get("device"),
        "torch": torch.__version__,
        "selection": report.get("selection"),
        "best_epoch": report.get("best_epoch"),
        "last_epoch": report.get("last_epoch"),
        "stopped_early": report.get("stopped_early"),
        "train_seconds": report.get("train_seconds"),
        "history": report.get("history", []),
    }


def metrics_section(report: dict) -> dict:
    return {
        "best_skill": report.get("best_skill"),
        "final_test_mae_C": report.get("final_test_mae_C"),
        "zero_baseline_mae_C": report.get("zero_baseline_mae_C"),
        "beats_predicting_nothing": report.get("beats_predicting_nothing"),
    }


def _engine_version(pairs: list[tuple[Path, Path]]) -> str | None:
    for surrogate_dir, _ in pairs:
        engine = Path(surrogate_dir) / "baseline" / "engine.json"
        if engine.exists():
            return str(json.loads(engine.read_text()).get("version"))
    return None


def _code_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _package_version() -> str:
    try:
        return version("shadecast")
    except PackageNotFoundError:
        return "unknown"


def provenance_section(built: ManifestInputs) -> dict:
    return {
        "engine": _engine_version(built.pairs),
        "shadecast": _package_version(),
        "code_commit": _code_commit(),
    }


def weights_section(model_path: Path) -> dict:
    path = Path(model_path)
    return {
        "file": path.name,
        "format": "torch state_dict, pickle",
        "sha256": sha256(path) if path.exists() else None,
        "bytes": path.stat().st_size if path.exists() else None,
    }


def new_model_id(pairs: list[tuple[Path, Path]], created: datetime) -> str:
    """response-unet-<cities>-<timestamp>, unique per training run and readable."""
    tiles = "+".join(
        str(json.loads((Path(bundle) / "provenance.json").read_text()).get("city", {}).get("key"))
        for _, bundle in pairs
    )
    return f"response-unet-{tiles}-{created.strftime('%Y%m%dT%H%M%S')}"


def now() -> datetime:
    return datetime.now(UTC)


def build(built: ManifestInputs) -> dict:
    return {
        "model_id": built.model_id,
        "created": built.created,
        "architecture": architecture(len(features.CHANNEL_SETS[channel_set_of(built.report)])),
        "inputs": inputs(channel_set_of(built.report)),
        "output": output(),
        "data": data_section(built),
        "training": training_section(built.report),
        "metrics": metrics_section(built.report),
        "provenance": provenance_section(built),
        "weights": weights_section(built.model_path),
        "licence": "Apache-2.0",
        "intended_use": INTENDED_USE,
    }


def check(manifest: dict) -> None:
    missing = [section for section in REQUIRED_SECTIONS if section not in manifest]
    if missing:
        raise ValueError(f"manifest lacks {missing}")


def write(model_dir: Path, manifest: dict) -> Path:
    check(manifest)
    path = Path(model_dir) / MANIFEST_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
    return path


def read(model_dir: Path) -> dict:
    path = Path(model_dir) / MANIFEST_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist; this model has no manifest. Retrain to create one."
        )
    manifest = json.loads(path.read_text())
    check(manifest)
    return manifest


def receptive_field_text(architecture: dict) -> str:
    """The field as a range when the manifest has both ends, else the one figure it has."""
    largest = architecture.get("receptive_field_m")
    smallest = architecture.get("receptive_field_min_m")
    if smallest is None or smallest == largest:
        return f"{largest} m"
    return f"{smallest} to {largest} m"


def summary(manifest: dict) -> dict:
    """The dozen facts a reader wants first, for a table."""
    architecture = manifest.get("architecture", {})
    data = manifest.get("data", {})
    weights = manifest.get("weights", {})
    return {
        "created": manifest.get("created"),
        "architecture": architecture.get("class"),
        "parameters": architecture.get("parameters"),
        "receptive field": receptive_field_text(architecture),
        "inputs": ", ".join(
            c.get("name", "") for c in manifest.get("inputs", {}).get("channels", [])
        ),
        "tiles": ", ".join(f"{t.get('city')} {t.get('tile')}" for t in data.get("tiles", [])),
        "held out": ", ".join(data.get("held_out_designs", [])),
        "best epoch": manifest.get("training", {}).get("best_epoch"),
        "best skill": manifest.get("metrics", {}).get("best_skill"),
        "engine": manifest.get("provenance", {}).get("engine"),
        "code commit": str(manifest.get("provenance", {}).get("code_commit"))[:12],
        "weights": f"{weights.get('file')} {str(weights.get('sha256'))[:12]}",
        "licence": manifest.get("licence"),
    }
