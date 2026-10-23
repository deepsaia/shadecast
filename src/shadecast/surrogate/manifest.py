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
SCALES = {
    "baseline_tmrt": features.TMRT_SCALE,
    "building_height": features.HEIGHT_SCALE,
    "canopy_height": features.CANOPY_SCALE,
}


def architecture() -> dict:
    model = ResponseUNet()
    return {
        "class": type(model).__name__,
        "depth": model.depth,
        "widths": [model.width * 2**level for level in range(model.depth)],
        "bottleneck": model.width * 2**model.depth,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "receptive_field_m": round(model.receptive_field_m()),
        "output_constraint": "none, warming near a new tree is a measured effect",
    }


def inputs() -> dict:
    channels = []
    for name in features.IN_CHANNELS_ORDER:
        channel: dict = {"name": name, "scale": SCALES.get(name)}
        channel.update(LAND_COVER_FLAGS.get(name, {}))
        if name == "sky_openness":
            channel["definition"] = (
                f"1 minus mean obstruction height within {features.OPENNESS_RADIUS_M:.0f} m "
                f"over {features.HEIGHT_SCALE:.0f} m, clipped to 0 to 1"
            )
        channels.append(channel)
    return {"resolution_m": 1.0, "channels": channels}


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
        "architecture": architecture(),
        "inputs": inputs(),
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


def summary(manifest: dict) -> dict:
    """The dozen facts a reader wants first, for a table."""
    architecture = manifest.get("architecture", {})
    data = manifest.get("data", {})
    weights = manifest.get("weights", {})
    return {
        "created": manifest.get("created"),
        "architecture": architecture.get("class"),
        "parameters": architecture.get("parameters"),
        "receptive field": f"{architecture.get('receptive_field_m')} m",
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
