"""Command line for the surrogate: train a model on a tile's physics, assess it, describe it.

Kept in its own module so the main command surface stays readable, and registered on the
root app as a sub-command group. The physics a model learns from comes from ``sdc simulate``.
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
from .service.channels import channel
from .service.null_progress import NullProgress
from .service.training_request import TrainingRequest
from .service.training_service import TrainingService
from .surrogate import manifest
from .surrogate.training_progress import TrainingProgress
from .surrogate.training_settings import TrainingSettings

logger = logging.getLogger(__name__)


app = typer.Typer(
    name="surrogate",
    help="The learned response models that make search affordable, one per physical channel.",
    no_args_is_help=True,
)
treeshade = typer.Typer(
    name="treeshade",
    help="The tree shade surrogate: trees added to the canopy model. Train, assess, describe.",
    no_args_is_help=True,
)
app.add_typer(treeshade, name="treeshade")

TREESHADE = channel("treeshade")


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
        typer.Argument(help="A city key such as savannah, or a tile's physics directory."),
    ] = None,
    bundle: Annotated[
        Path | None, typer.Argument(help="The matching tile bundle, when a directory was given.")
    ] = None,
    pair: Annotated[
        list[str] | None,
        typer.Option(
            "--pair",
            help="Train across cities: a city key or PHYSICS_DIR=BUNDLE, repeatable.",
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

    A dashboard shows the epochs as they run, with the best so far, how long the skill has
    stalled against the patience, and how to stop and resume. Put -v before the command for
    debug logging in its log box.
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
    progress = TrainingProgress(
        console,
        patience=TrainingSettings().patience,
        kind=TREESHADE.label,
        target=target or " ".join(request.pair),
        resume_command=train_resume_command(request),
    )
    try:
        with progress:
            outcome = service.train(request, progress)
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
    physics_dir: Annotated[
        Path | None,
        typer.Argument(help="The tile's physics directory, when a model directory was given."),
    ] = None,
    bundle: Annotated[
        Path | None,
        typer.Argument(help="The matching tile bundle, when a model directory was given."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="A model id of the city, else its newest model."),
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
    newest model; a model directory needs the physics directory and bundle after it.
    """
    request = AssessmentRequest(
        target=target,
        physics_dir=physics_dir,
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
        typer.Option("--model", help="A model id of the city, else its newest model."),
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
    console.print(f"[dim]{manifest.INTENDED_USE}[/]")


def _model_dir(target: str, model: str | None) -> Path:
    service = AssessmentService(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT)
    return Path(service.model_summary(target, model).path)
