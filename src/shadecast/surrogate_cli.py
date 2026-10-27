"""Command line for the surrogate workflow.

Kept in its own module so the main command surface stays readable, and registered
on the root app as a sub-command group.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from .console import console, error_console, pairs_table
from .corpus import tile_paths
from .service.assessment_request import AssessmentRequest
from .service.assessment_service import AssessmentService
from .service.city_catalog import CityCatalog
from .service.generation_request import GenerationRequest
from .service.generation_service import GenerationService, settings_for
from .service.missing_stage import MissingStage
from .service.null_progress import NullProgress
from .service.training_request import TrainingRequest
from .service.training_service import TrainingService
from .service.unknown_city import UnknownCity
from .surrogate import manifest
from .surrogate.dataset import engine_threads
from .surrogate.generation_progress import GenerationProgress
from .surrogate.training_progress import TrainingProgress

logger = logging.getLogger(__name__)


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
    service = GenerationService(CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT))
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


def train_resume_command(request: TrainingRequest) -> str:
    """The exact command that continues an interrupted training run."""
    parts = ["sdc surrogate treeshade train"]
    if request.target:
        parts.append(request.target)
    if request.bundle:
        parts.append(str(request.bundle))
    for item in request.pair:
        parts += ["--pair", item]
    if request.tiles is not None:
        parts += ["--tiles", request.tiles]
    if request.holdout_city:
        parts += ["--holdout-city", request.holdout_city]
    if request.channels != "engine":
        parts += ["--channels", request.channels]
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
    request = TrainingRequest(
        target=target,
        bundle=bundle,
        pair=pair or [],
        tiles=tiles,
        holdout_city=holdout_city,
        epochs=epochs,
        patch=patch,
        per_entry=per_entry,
        channels=channels,
        densest=densest,
        stratified=stratified,
        resume=resume,
    )
    service = TrainingService(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT)
    try:
        outcome = service.train(request, TrainingProgress(console))
    except ValueError as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        console.print("\n[bold]stopped[/] before the first epoch finished; nothing was saved.")
        raise typer.Exit(code=130) from None
    if outcome.interrupted:
        console.print(
            f"\n[bold]stopped[/] after epoch {outcome.last_epoch}; the best weights, epoch "
            f"{outcome.best_epoch}, are saved in {outcome.destination}.\n"
            f"Continue with: [cyan]{train_resume_command(request)}[/]"
        )
        raise typer.Exit(code=130)
    verdict = "green" if outcome.beats_nothing else "red"
    console.print(
        f"[{verdict}]skill {outcome.skill:+.3f}[/]  "
        f"MAE {outcome.mae_c:.4f} C against a zero baseline of {outcome.zero_mae_c:.4f} C  "
        f"(holdout: {outcome.holdout_mode})"
    )
    console.print(f"[dim]model and report written to {outcome.destination}[/]")


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
    request = AssessmentRequest(
        target=target,
        surrogate_dir=surrogate_dir,
        bundle=bundle,
        model=model,
        tile=tile,
        design=design,
    )
    service = AssessmentService(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT)
    try:
        with console.status("[cyan]comparing surrogate against engine truth[/]"):
            outcome = service.assess(request, NullProgress())
    except (ValueError, LookupError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    verdict = "green" if outcome.beats_nothing else "red"
    console.print(f"[dim]assessed {outcome.model_dir}[/]")
    console.print(
        f"[{verdict}]mean skill {outcome.skill:+.3f}[/]  "
        f"(above zero means it beats predicting nothing)"
    )
    speedup = f"{outcome.speedup:,.0f}x" if outcome.speedup is not None else "unknown"
    console.print(
        f"plan score error {outcome.error:.1%}, ranking spearman {outcome.spearman}, "
        f"speedup {speedup}"
    )
    console.print(f"[dim]full report written to {outcome.report_path}[/]")


@treeshade.command("describe")
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
    try:
        model_dir = Path(target) if Path(target).is_dir() else _model_dir(target, model)
        found = manifest.read(model_dir)
    except (FileNotFoundError, ValueError, LookupError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    if as_json:
        console.print_json(json.dumps(found))
        return
    console.print(pairs_table(found.get("model_id", "model"), manifest.summary(found)))
    console.print(f"[dim]{found.get('intended_use')}[/]")


def _model_dir(target: str, model: str | None) -> Path:
    service = AssessmentService(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT)
    return Path(service.model_summary(target, model).path)
