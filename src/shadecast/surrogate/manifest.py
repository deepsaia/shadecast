"""The manifest written beside every trained model.

A checkpoint is a bag of weights; a manifest says what they are, in under a kilobyte. It keeps
what cannot be re-derived: the tiles and designs the model learned from and the designs it was
tested on, every training setting and how the run went, the held-out metrics, and the engine,
package and commit that produced it. What the code at that commit can recompute stays in the
code: the architecture's size and reach, the channels' scales and meanings, what the output
means. ``describe`` recomputes them from the manifest's four model fields. The training curve
is not metadata and goes to a small table beside the weights.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from pathlib import Path

import torch

from ..corpus.tile_ref import ref_of
from ..data.checksum import sha256
from .features import CHANNEL_SETS
from .manifest_inputs import ManifestInputs
from .model import DEPTH
from .model import WIDTH
from .model import ResponseUNet

MANIFEST_FILE = "manifest.json"
EPOCHS_FILE = "epochs.csv"
EPOCH_COLUMNS = ("epoch", "train_loss", "test_mae_C", "skill")
DECIMALS = 4  # enough for a training curve; a float prints seventeen digits otherwise
REQUIRED_SECTIONS = (
    "model_id",
    "created",
    "model",
    "data",
    "training",
    "metrics",
    "provenance",
    "weights_sha256",
)
INTENDED_USE = (
    "Predict the daylight-mean change in mean radiant temperature a tree planting plan causes "
    "on the tile it was trained on or on tiles with similar morphology; verify any plan chosen "
    "with it against the physics engine before reporting it."
)
RESOLUTION_M = 1.0


def build(built: ManifestInputs) -> dict:
    return {
        "model_id": built.model_id,
        "created": built.created,
        "model": model_section(built.report),
        "data": data_section(built),
        "training": training_section(built.report),
        "metrics": metrics_section(built.report),
        "provenance": provenance_section(built),
        "weights_sha256": sha256(built.model_path),
    }


def model_section(report: dict) -> dict:
    """The four facts the code turns back into the network: class, width, depth, channel set."""
    return {
        "class": ResponseUNet.__name__,
        "width": WIDTH,
        "depth": DEPTH,
        "channel_set": channel_set_of(report),
    }


def channel_set_of(report: dict) -> str:
    """The channel set a training report says it used; reports older than the key used base."""
    return str(report.get("settings", {}).get("channels", "base"))


def data_section(built: ManifestInputs) -> dict:
    report = built.report
    return {
        "tiles": [tile_ref(bundle) for _, bundle in built.pairs],
        "held_out_designs": report.get("held_out_designs", []),
        "patch_px": built.patch_px,
        "patches_per_design": built.per_entry,
        "train_patches": report.get("train_patches"),
        "test_patches": report.get("test_patches"),
    }


def tile_ref(bundle: Path) -> str:
    """``<urban centre id>/<tile id>`` for a bundle, from the tile record in its provenance."""
    tile = _provenance(bundle).get("tile", {})
    centre, tile_id = tile.get("urban_centre"), tile.get("id")
    if not centre or not tile_id:
        raise ValueError(f"{bundle} has no tile record in its provenance; rebuild it with 'sdc build'")
    return ref_of(int(centre), str(tile_id))


def city_keys(pairs: list[tuple[Path, Path]]) -> list[str]:
    """Each city once, in training order, from the bundles' provenance."""
    keys = [str(_provenance(bundle).get("city", {}).get("key")) for _, bundle in pairs]
    return list(dict.fromkeys(keys))


def _provenance(bundle: Path) -> dict:
    return json.loads((Path(bundle) / "provenance.json").read_text())


def training_section(report: dict) -> dict:
    """Every setting the run was given, flat, and how the run went."""
    return {
        **report.get("settings", {}),
        "device": report.get("device"),
        "best_epoch": report.get("best_epoch"),
        "last_epoch": report.get("last_epoch"),
        "interrupted": report.get("interrupted", False),
        "resumed_from_epoch": report.get("resumed_from_epoch", 0),
        "train_seconds": report.get("train_seconds"),
    }


def metrics_section(report: dict) -> dict:
    return {
        "best_skill": report.get("best_skill"),
        "test_mae_C": report.get("final_test_mae_C"),
        "zero_baseline_mae_C": report.get("zero_baseline_mae_C"),
    }


def provenance_section(built: ManifestInputs) -> dict:
    return {
        "engine": _engine_version(built.pairs),
        "shadecast": _package_version(),
        "torch": torch.__version__,
        "code_commit": _code_commit(),
    }


def _engine_version(pairs: list[tuple[Path, Path]]) -> str | None:
    for physics_dir, _ in pairs:
        engine = Path(physics_dir) / "baseline" / "engine.json"
        if engine.exists():
            return str(json.loads(engine.read_text()).get("version"))
    return None


def _package_version() -> str:
    try:
        return version("shadecast")
    except PackageNotFoundError:
        return "unknown"


def _code_commit() -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def new_model_id(pairs: list[tuple[Path, Path]], created: datetime) -> str:
    """response-unet-<cities>-<timestamp>, unique per training run and readable."""
    keys = [str(_provenance(bundle).get("city", {}).get("key")) for _, bundle in pairs]
    cities = "+".join(dict.fromkeys(keys))  # each city once, in order
    pooled = f"-{len(keys)}tiles" if len(keys) > len(set(keys)) else ""
    return f"response-unet-{cities}{pooled}-{created.strftime('%Y%m%dT%H%M%S')}"


def now() -> datetime:
    return datetime.now(UTC)


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
        raise FileNotFoundError(f"{path} does not exist; this model has no manifest. Retrain to create one.")
    manifest = json.loads(path.read_text())
    check(manifest)
    return manifest


def save_epochs(history: list[dict], path: Path) -> Path:
    """The training curve as a four-column table, one row per epoch, rounded."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EPOCH_COLUMNS)
        writer.writeheader()
        for row in history:
            writer.writerow(_epoch_row(row))
    return path


def _epoch_row(row: dict) -> dict:
    rounded = {name: round(float(row.get(name, 0.0)), DECIMALS) for name in EPOCH_COLUMNS[1:]}
    return {"epoch": int(row.get("epoch", 0)), **rounded}


def channel_names(manifest: dict) -> tuple[str, ...]:
    """The input channels, in order, from the channel set the manifest names."""
    return CHANNEL_SETS[str(manifest.get("model", {}).get("channel_set"))]


def architecture(model: dict) -> dict:
    """Size and reach recomputed from the model section, as the code at the commit defines them."""
    channels = CHANNEL_SETS[str(model.get("channel_set"))]
    network = ResponseUNet(
        in_channels=len(channels),
        width=int(model.get("width", WIDTH)),
        depth=int(model.get("depth", DEPTH)),
    )
    smallest, largest = network.receptive_field_px()
    return {
        "parameters": sum(parameter.numel() for parameter in network.parameters()),
        "receptive_field_m": round(largest * RESOLUTION_M),
        "receptive_field_min_m": round(smallest * RESOLUTION_M),
        "channels": list(channels),
    }


def receptive_field_text(architecture: dict) -> str:
    """The field as a range when both ends are known, else the one figure there is."""
    largest = architecture.get("receptive_field_m")
    smallest = architecture.get("receptive_field_min_m")
    if smallest is None or smallest == largest:
        return f"{largest} m"
    return f"{smallest} to {largest} m"


def summary(manifest: dict) -> dict:
    """The dozen facts a reader wants first, for a table; size and reach are recomputed."""
    derived = architecture(manifest.get("model", {}))
    data = manifest.get("data", {})
    return {
        "created": manifest.get("created"),
        "architecture": manifest.get("model", {}).get("class"),
        "parameters": derived.get("parameters"),
        "receptive field": receptive_field_text(derived),
        "inputs": ", ".join(derived.get("channels", [])),
        "tiles": ", ".join(str(ref) for ref in data.get("tiles", [])),
        "held out": ", ".join(data.get("held_out_designs", [])),
        "best epoch": manifest.get("training", {}).get("best_epoch"),
        "best skill": manifest.get("metrics", {}).get("best_skill"),
        "engine": manifest.get("provenance", {}).get("engine"),
        "code commit": str(manifest.get("provenance", {}).get("code_commit"))[:12],
        "weights": str(manifest.get("weights_sha256"))[:12],
    }
