"""Command line for the surrogate workflow.

Kept in its own module so the main command surface stays readable, and registered
on the root app as a sub-command group.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Annotated

import numpy as np
import typer

from .console import console, error_console, pairs_table
from .corpus import tile_lookup, tile_paths
from .surrogate import manifest
from .surrogate.assessment import assess
from .surrogate.assessment_inputs import AssessmentInputs
from .surrogate.dataset import default_plan, engine_threads, generate, tile_label
from .surrogate.features import CHANNEL_SETS
from .surrogate.generation_progress import GenerationProgress
from .surrogate.generation_settings import GenerationSettings
from .surrogate.manifest_inputs import ManifestInputs
from .surrogate.patch_set import PatchSet
from .surrogate.patch_settings import PatchSettings
from .surrogate.patches import crop_batch, crop_cities
from .surrogate.training import save_report, train
from .surrogate.training_settings import TrainingSettings

logger = logging.getLogger(__name__)

# Models trained on several tiles belong to no tile and live here.
MODELS_ROOT = Path("data/models")


def models_root(pairs: list[tuple[Path, Path]]) -> Path:
    """One tile's models live beside its surrogate directory; multi-tile models at the root."""
    if len(pairs) == 1:
        return Path(pairs[0][0]).parent / "models"
    return MODELS_ROOT


def default_out(bundle: Path) -> Path:
    """Where generated physics goes: the tile's surrogate directory, else data/surrogate/<name>.

    Every bundle in the tile layout is a directory named ``bundle`` three levels under the
    tiles root, so the old default of data/surrogate/<name> would send every tile to the same
    place. A bundle anywhere else keeps the old default.
    """
    bundle = Path(bundle)
    in_tile = bundle.name == "bundle" and bundle.resolve().parent.parent.parent == (
        tile_paths.TILES_ROOT.resolve()
    )
    if in_tile:
        return bundle.parent / "surrogate"
    return Path("data/surrogate") / bundle.name


app = typer.Typer(
    name="surrogate",
    help="Fit and evaluate the learned response model that makes search affordable.",
    no_args_is_help=True,
)


def resolve_tile(target: str, tile: str | None) -> tuple[Path, Path]:
    """A bundle path, or a city key with an optional tile id, as (bundle, surrogate dir)."""
    if Path(target).is_dir():
        return Path(target), default_out(Path(target))
    try:
        paths = tile_lookup.one_built_tile(target, tile, tile_paths.TILES_ROOT)
    except ValueError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    return paths.bundle, paths.surrogate


def newest_model(target: str, model: str | None) -> tuple[Path, Path, Path]:
    """For a city key: (model dir, surrogate dir, bundle), the newest model unless one is named."""
    try:
        paths = tile_lookup.one_built_tile(target, None, tile_paths.TILES_ROOT)
    except ValueError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    if model is not None:
        return paths.models / model, paths.surrogate, paths.bundle
    models = paths.model_dirs()
    if not models:
        error_console.print(
            f"{target} has no trained model yet; run 'sdc surrogate train {target}'"
        )
        raise typer.Exit(code=1)
    return models[-1], paths.surrogate, paths.bundle


def resume_command(target: str, tile: str | None, out: Path | None, kind: str, jobs: int) -> str:
    """The exact command that continues this run after a stop."""
    parts = ["sdc surrogate generate", target]
    if tile:
        parts += ["--tile", tile]
    if out:
        parts += ["--out", str(out)]
    if kind != "tree":
        parts += ["--kind", kind]
    if jobs != 1:
        parts += ["--jobs", str(jobs)]
    return " ".join(parts)


@app.command("generate")
def generate_data(
    target: Annotated[
        str, typer.Argument(help="A city key such as savannah, or a bundle directory.")
    ],
    tile: Annotated[
        str | None, typer.Option("--tile", help="Which of a city's built tiles, if several.")
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Where to write responses.")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Intervention type.")] = "tree",
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs", "-j", help="Engine runs side by side. The baseline runs alone first."
        ),
    ] = 1,
) -> None:
    """Run the designed experiments through the physics engine.

    Shows a bar over the plan and a line per finished design with its engine time. Designs
    already on disk are skipped, so an interrupted run resumes where it stopped. Put -v
    before the command for debug logging.
    """
    bundle, tile_surrogate = resolve_tile(target, tile)
    destination = out if out else tile_surrogate
    provenance = json.loads((bundle / "provenance.json").read_text())
    plan = default_plan()
    console.print(
        f"[cyan]{tile_label(bundle, provenance)}[/]: {len(plan)} designs, {jobs} at a time, "
        f"into {destination}. The engine has taken 4 to 10 minutes a design so far."
    )
    settings = GenerationSettings(plan=plan, kind=kind, jobs=jobs)
    started = time.time()
    progress = GenerationProgress(
        console,
        jobs=jobs,
        threads=engine_threads(settings),
        kind=kind,
        resume_command=resume_command(target, tile, out, kind, jobs),
    )
    try:
        with progress:
            summary = generate(bundle, destination, settings, progress)
    except RuntimeError as error:
        error_console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error
    mean = progress.mean_seconds()
    pace = f", {mean:.0f} s a design" if mean else ""
    console.print(
        f"[green]{summary['entries']}[/] responses in {destination}  "
        f"({(time.time() - started) / 60:.0f} min{pace})"
    )


def training_pairs(
    target: str | None, bundle: Path | None, pair: list[str] | None
) -> list[tuple[Path, Path]]:
    """(surrogate dir, bundle) pairs from a city key, a path pair, or repeated --pair values."""
    pairs: list[tuple[Path, Path]] = []
    for item in pair or []:
        if "=" in item:
            left, right = item.split("=", 1)
            pairs.append((Path(left), Path(right)))
        else:
            found = tile_lookup.one_built_tile(item, None, tile_paths.TILES_ROOT)
            pairs.append((found.surrogate, found.bundle))
    if target is not None and bundle is not None:
        pairs.append((Path(target), bundle))
    elif target is not None:
        found = tile_lookup.one_built_tile(target, None, tile_paths.TILES_ROOT)
        pairs.append((found.surrogate, found.bundle))
    if not pairs:
        raise ValueError("give a city key, SURROGATE_DIR and BUNDLE, or one or more --pair")
    return pairs


@app.command("train")
def train_model(
    target: Annotated[
        str | None,
        typer.Argument(help="A city key such as savannah, or a directory of generated responses."),
    ] = None,
    bundle: Annotated[
        Path | None, typer.Argument(help="The matching city bundle, when a directory was given.")
    ] = None,
    pair: Annotated[
        list[str] | None,
        typer.Option(
            "--pair",
            help="Train across cities: a city key or SURROGATE_DIR=BUNDLE, repeatable.",
        ),
    ] = None,
    holdout_city: Annotated[
        str | None,
        typer.Option("--holdout-city", help="Hold out this whole city to measure transfer."),
    ] = None,
    epochs: Annotated[
        int, typer.Option("--epochs", help="Upper bound; patience stops early.")
    ] = 60,
    patch: Annotated[int, typer.Option("--patch", help="Patch side in pixels.")] = 256,
    per_entry: Annotated[int, typer.Option("--per-entry", help="Patches per design.")] = 24,
    channels: Annotated[
        str,
        typer.Option(
            "--channels", help="Channel set: engine (all eleven) or base (the first seven)."
        ),
    ] = "engine",
) -> None:
    """Fit the response model.

    By default a whole design is held out, which measures generalisation to an unseen
    intervention pattern. With --holdout-city a whole city is held out instead, which
    measures transfer to unseen geometry. Those are different questions.
    """
    try:
        pairs = training_pairs(target, bundle, pair)
    except ValueError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc

    if holdout_city and len(pairs) < 2:
        raise typer.BadParameter("--holdout-city needs at least two cities")

    if channels not in CHANNEL_SETS:
        raise typer.BadParameter(f"--channels must be one of {sorted(CHANNEL_SETS)}")
    patch_settings = PatchSettings(size=patch, per_entry=per_entry, channels=channels)
    started = time.time()
    with console.status("[cyan]cropping patches[/]"):
        if len(pairs) == 1:
            inputs, targets, origins = crop_batch(pairs[0][0], pairs[0][1], patch_settings)
        else:
            inputs, targets, origins = crop_cities(pairs, patch_settings)

    console.print(
        f"{len(inputs):,} patches of {patch}px from {len(set(origins))} designs "
        f"across {len(pairs)} cities in {time.time() - started:.1f}s"
    )

    created = manifest.now()
    model_id = manifest.new_model_id(pairs, created)
    destination = models_root(pairs) / model_id
    destination.mkdir(parents=True, exist_ok=True)

    settings = TrainingSettings(epochs=epochs, holdout_city=holdout_city, channels=channels)
    report = train(PatchSet(inputs, targets, origins), settings, out_path=destination / "model.pt")
    report["patch_px"] = patch
    report["cities"] = [str(b) for _, b in pairs]
    report["target_stats"] = {
        "mean_C": round(float(np.mean(targets)), 4),
        "max_C": round(float(np.max(targets)), 3),
    }
    save_report(report, destination / "training_report.json")
    built = manifest.build(
        ManifestInputs(
            model_id=model_id,
            created=created.isoformat(timespec="seconds"),
            pairs=pairs,
            report=report,
            patch_px=patch,
            per_entry=per_entry,
            model_path=destination / "model.pt",
        )
    )
    manifest.write(destination, built)
    verdict = "green" if report["beats_predicting_nothing"] else "red"
    console.print(
        f"[{verdict}]skill {report['final_skill']:+.3f}[/]  "
        f"MAE {report['final_test_mae_C']:.4f} C against a zero baseline of "
        f"{report['zero_baseline_mae_C']:.4f} C  "
        f"(holdout: {report['holdout_mode']})"
    )
    console.print(f"[dim]model and report written to {destination}[/]")


@app.command("assess")
def assess_model(
    target: Annotated[
        str, typer.Argument(help="A city key such as savannah, or a trained model directory.")
    ],
    surrogate_dir: Annotated[
        Path | None,
        typer.Argument(help="Directory of generated responses, with a model directory."),
    ] = None,
    bundle: Annotated[
        Path | None, typer.Argument(help="The matching city bundle, with a model directory.")
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="A model id under the tile's models/, else the newest."),
    ] = None,
    design: Annotated[
        list[str] | None,
        typer.Option("--design", help="Assess these designs instead of the held-out set."),
    ] = None,
) -> None:
    """Compare the surrogate against engine truth on designs it never trained on.

    Reports skill against predicting nothing, whether the spillover tail survives,
    error in the plan score, and how well plans are ordered. A city key assesses its
    newest model; a model directory needs the surrogate directory and bundle after it.
    """
    if Path(target).is_dir():
        if surrogate_dir is None or bundle is None:
            raise typer.BadParameter("a model directory needs SURROGATE_DIR and BUNDLE after it")
        model_dir = Path(target)
    else:
        model_dir, surrogate_dir, bundle = newest_model(target, model)
    console.print(f"[dim]assessing {model_dir}[/]")
    with console.status("[cyan]comparing surrogate against engine truth[/]"):
        report = assess(AssessmentInputs(model_dir, surrogate_dir, bundle, only=design))

    headline = report["headline"]
    verdict = "green" if headline["all_beat_predicting_nothing"] else "red"
    console.print(
        f"[{verdict}]mean skill {headline['mean_skill']:+.3f}[/]  "
        f"(above zero means it beats predicting nothing)"
    )
    console.print(
        f"plan score error {headline['mean_aggregate_relative_error']:.1%}, "
        f"ranking spearman {report['ranking']['spearman']}, "
        f"speedup {report['speed']['speedup']:,.0f}x"
    )
    (Path(model_dir) / "assessment.json").write_text(json.dumps(report, indent=2))
    console.print(f"[dim]full report written to {model_dir}/assessment.json[/]")


@app.command("describe")
def describe(
    target: Annotated[
        str, typer.Argument(help="A city key such as savannah, or a trained model directory.")
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", help="A model id under the tile's models/, else the newest."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the manifest as JSON.")] = False,
) -> None:
    """Say what a trained model is, from its manifest alone."""
    model_dir = Path(target) if Path(target).is_dir() else newest_model(target, model)[0]
    try:
        found = manifest.read(model_dir)
    except (FileNotFoundError, ValueError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    if as_json:
        console.print_json(json.dumps(found))
        return
    console.print(pairs_table(found.get("model_id", "model"), manifest.summary(found)))
    console.print(f"[dim]{found.get('intended_use')}[/]")
