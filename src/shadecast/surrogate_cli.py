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
from .corpus.tile_paths import TilePaths
from .corpus.tile_selection import TileSelection
from .service.city_catalog import CityCatalog
from .service.generation_request import GenerationRequest
from .service.generation_service import GenerationService, settings_for
from .service.json_file import read_object
from .service.missing_stage import MissingStage
from .service.model_catalog import MODELS_ROOT, ModelCatalog, model_created
from .service.model_summary import ModelSummary
from .service.unknown_city import UnknownCity
from .surrogate import manifest
from .surrogate.assessment import assess
from .surrogate.assessment_inputs import AssessmentInputs
from .surrogate.dataset import engine_threads
from .surrogate.features import CHANNEL_SETS
from .surrogate.generation_progress import GenerationProgress
from .surrogate.manifest_inputs import ManifestInputs
from .surrogate.patch_set import PatchSet
from .surrogate.patch_settings import PatchSettings
from .surrogate.patches import crop_batch, crop_cities, tile_key
from .surrogate.training import save_report, train
from .surrogate.training_settings import TrainingSettings
from .surrogate.training_state import CHECKPOINT_NAME

logger = logging.getLogger(__name__)


def models_root(pairs: list[tuple[Path, Path]]) -> Path:
    """One tile's models live beside its surrogate directory; multi-tile models at the root."""
    if len(pairs) == 1:
        return Path(pairs[0][0]).parent / "models"
    return MODELS_ROOT


app = typer.Typer(
    name="surrogate",
    help="The learned response models that make search affordable, one per physical channel.",
    no_args_is_help=True,
)
treeshade = typer.Typer(
    name="treeshade",
    help="The tree shade surrogate: trees added to the canopy model. Generate, train, assess.",
    no_args_is_help=True,
)
app.add_typer(treeshade, name="treeshade")

KIND = "tree"  # the engine's intervention kind this surrogate learns
LABEL = "tree shade"  # how the dashboard and the pages name it


def newest_model(
    target: str, model: str | None, tile: str | None = None
) -> tuple[Path, Path, Path]:
    """For a city key: (model dir, surrogate dir, bundle), the newest model unless one is named."""
    try:
        paths = assessment_tile(target, tile)
        found = chosen_model(target, model)
    except (ValueError, LookupError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    return Path(found.path), paths.surrogate, paths.bundle


def assessment_tile(target: str, tile: str | None) -> TilePaths:
    """The tile to assess a model on: the named one, else the densest with physics."""
    if tile is None:
        return tile_lookup.densest_generated_tile(target, tile_paths.TILES_ROOT)
    found = tile_lookup.generated_tiles(target, None, tile_paths.TILES_ROOT)
    chosen = [paths for paths in found if paths.tile.id == tile]
    if not chosen:
        raise ValueError(f"{target} tile {tile} has no generated physics")
    return chosen[0]


def chosen_model(target: str, model: str | None) -> ModelSummary:
    """The named model of the city, or its newest."""
    models = ModelCatalog(tile_paths.TILES_ROOT, MODELS_ROOT)
    centre = tile_lookup.centre_id(target)
    return models.named(centre, model) if model else models.newest(centre)


def assessment_name(model_dir: Path, bundle: Path) -> str:
    """assessment.json for a model of one tile; assessment-<tile>.json for a pooled model."""
    tiles = read_object(Path(model_dir) / "manifest.json").get("data", {}).get("tiles", [])
    if len(tiles) <= 1:
        return "assessment.json"
    return f"assessment-{tile_key(bundle).replace(':', '-')}.json"


def resume_command(target: str, tile: str | None, out: Path | None, jobs: int) -> str:
    """The exact command that continues this run after a stop."""
    parts = ["sdc surrogate treeshade generate", target]
    if tile:
        parts += ["--tiles", tile]
    if out:
        parts += ["--out", str(out)]
    if jobs != 1:
        parts += ["--jobs", str(jobs)]
    return " ".join(parts)


@treeshade.command("generate")
def generate_data(
    target: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tiles: Annotated[
        str | None,
        typer.Option(
            "--tiles",
            help="Built tile ids separated by commas, or 'all'. Default: the densest built tile.",
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", help="Where to write responses, for one tile.")
    ] = None,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs", "-j", help="Engine runs side by side. The baseline runs alone first."
        ),
    ] = 1,
) -> None:
    """Run the designed experiments through the physics engine, one tile at a time.

    Each tile gets its own dashboard: a bar over the plan, a line per finished design with
    its engine time, how to stop and how to resume. Designs already on disk are skipped, so
    an interrupted run resumes where it stopped. Put -v before the command for debug logging.
    """
    request = GenerationRequest(target=target, tiles=tiles, out=out, jobs=jobs, kind=KIND)
    service = GenerationService(CityCatalog.open(tile_paths.TILES_ROOT))
    try:
        chosen = service.tiles_for(request)
    except (UnknownCity, MissingStage, ValueError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    failures: list[str] = []
    for index, paths in enumerate(chosen, start=1):
        if len(chosen) > 1:
            console.print(f"[bold]tile {index} of {len(chosen)}[/]")
        picked = paths.tile.id if tiles is not None else None
        progress = GenerationProgress(
            console,
            jobs=jobs,
            threads=engine_threads(settings_for(request)),
            kind=LABEL,
            resume_command=resume_command(target, picked, out, jobs),
        )
        try:
            with progress:
                outcome = service.generate(paths, request, progress)
        except KeyboardInterrupt:
            console.print(
                f"\n[bold]stopped[/] with {progress.completed()} of {progress.total} designs on "
                f"disk. Resume with: [cyan]{progress.resume_command}[/]"
            )
            raise typer.Exit(code=130) from None
        except RuntimeError as error:
            error_console.print(f"[red]{error}[/]")
            failures.append(paths.tile.id)
            continue
        mean = progress.mean_seconds()
        pace = f", {mean:.0f} s a design" if mean else ""
        console.print(
            f"[green]{outcome.entries}[/] responses in {outcome.destination}  "
            f"({outcome.seconds / 60:.0f} min{pace})"
        )
    if failures:
        error_console.print(
            f"[red]{len(failures)} tile(s) had failed designs:[/] {', '.join(failures)}"
        )
        raise typer.Exit(code=1)


def training_pairs(
    target: str | None,
    bundle: Path | None,
    pair: list[str] | None,
    tiles: str | None = None,
    selection: TileSelection | None = None,
) -> list[tuple[Path, Path]]:
    """(surrogate dir, bundle) pairs: a city's densest tile with physics, named or all tiles pooled,
    a path pair, or --pair values."""
    pairs: list[tuple[Path, Path]] = []
    for item in pair or []:
        if "=" in item:
            left, right = item.split("=", 1)
            pairs.append((Path(left), Path(right)))
        else:
            for found in tile_lookup.generated_tiles(item, None, tile_paths.TILES_ROOT):
                pairs.append((found.surrogate, found.bundle))
    if target is not None and bundle is not None:
        pairs.append((Path(target), bundle))
    elif target is not None:
        found_tiles = tile_lookup.generated_tiles(target, tiles, tile_paths.TILES_ROOT, selection)
        pairs.extend((paths.surrogate, paths.bundle) for paths in found_tiles)
    if not pairs:
        raise ValueError("give a city key, SURROGATE_DIR and BUNDLE, or one or more --pair")
    return pairs


def unfinished_model(root: Path) -> Path | None:
    """The newest model directory with a checkpoint and no manifest, else None."""
    if not root.is_dir():
        return None
    candidates = [
        child
        for child in root.iterdir()
        if (child / CHECKPOINT_NAME).exists() and not (child / "manifest.json").exists()
    ]
    return max(candidates, key=model_created) if candidates else None


def train_resume_command(
    target: str | None,
    bundle: Path | None,
    pair: list[str] | None,
    tiles: str | None,
    holdout_city: str | None,
    channels: str,
) -> str:
    """The exact command that continues an interrupted training run. Six inputs, one string."""
    parts = ["sdc surrogate treeshade train"]
    if target:
        parts.append(target)
    if bundle:
        parts.append(str(bundle))
    for item in pair or []:
        parts += ["--pair", item]
    if tiles is not None:
        parts += ["--tiles", tiles]
    if holdout_city:
        parts += ["--holdout-city", holdout_city]
    if channels != "engine":
        parts += ["--channels", channels]
    parts.append("--resume")
    return " ".join(parts)


@treeshade.command("train")
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
    tiles: Annotated[
        str | None,
        typer.Option(
            "--tiles",
            help="Tile ids separated by commas to train on. Default: every tile with physics.",
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
    densest: Annotated[
        int | None,
        typer.Option(
            "--densest", help="Train on the K tiles with physics that have most residents."
        ),
    ] = None,
    stratified: Annotated[
        int | None,
        typer.Option("--stratified", help="Train on K tiles with physics spread over terciles."),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Continue the newest unfinished run from its checkpoint."),
    ] = False,
) -> None:
    """Fit the response model.

    By default a whole design is held out, which measures generalisation to an unseen
    intervention pattern. With --holdout-city a whole city is held out instead, which
    measures transfer to unseen geometry. Those are different questions.
    """
    try:
        pairs = training_pairs(target, bundle, pair, tiles, TileSelection(densest, stratified))
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
    if resume:
        unfinished = unfinished_model(models_root(pairs))
        if unfinished is None:
            error_console.print(f"nothing to resume under {models_root(pairs)}")
            raise typer.Exit(code=1)
        destination, model_id = unfinished, unfinished.name
        console.print(f"[dim]resuming {destination}[/]")
    destination.mkdir(parents=True, exist_ok=True)

    settings = TrainingSettings(epochs=epochs, holdout_city=holdout_city, channels=channels)
    try:
        report = train(
            PatchSet(inputs, targets, origins), settings, out_path=destination / "model.pt"
        )
    except KeyboardInterrupt:
        console.print("\n[bold]stopped[/] before the first epoch finished; nothing was saved.")
        raise typer.Exit(code=130) from None
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
    if report.get("interrupted"):
        again = train_resume_command(target, bundle, pair, tiles, holdout_city, channels)
        console.print(
            f"\n[bold]stopped[/] after epoch {report['last_epoch']}; the best weights, epoch "
            f"{report['best_epoch']}, are saved in {destination}.\n"
            f"Continue with: [cyan]{again}[/]"
        )
        raise typer.Exit(code=130)
    verdict = "green" if report["beats_predicting_nothing"] else "red"
    console.print(
        f"[{verdict}]skill {report['final_skill']:+.3f}[/]  "
        f"MAE {report['final_test_mae_C']:.4f} C against a zero baseline of "
        f"{report['zero_baseline_mae_C']:.4f} C  "
        f"(holdout: {report['holdout_mode']})"
    )
    console.print(f"[dim]model and report written to {destination}[/]")


@treeshade.command("assess")
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
    tile: Annotated[
        str | None, typer.Option("--tile", help="Which built tile, when the city has several.")
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
        model_dir, surrogate_dir, bundle = newest_model(target, model, tile)
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
    report_path = Path(model_dir) / assessment_name(Path(model_dir), bundle)
    report_path.write_text(json.dumps(report, indent=2))
    console.print(f"[dim]full report written to {report_path}[/]")


@treeshade.command("describe")
def describe(
    target: Annotated[
        str, typer.Argument(help="A city key such as savannah, or a trained model directory.")
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", help="A model id under the tile's models/, else the newest."),
    ] = None,
    tile: Annotated[
        str | None, typer.Option("--tile", help="Which built tile, when the city has several.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the manifest as JSON.")] = False,
) -> None:
    """Say what a trained model is, from its manifest alone."""
    model_dir = Path(target) if Path(target).is_dir() else newest_model(target, model, tile)[0]
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
