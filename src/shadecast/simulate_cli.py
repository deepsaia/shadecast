"""Command line for the physics engine: the baseline over a tile, and the designs over it.

Every command here is an engine run written under the tile's physics directory. The baseline
is the tile as it is, run once and kept. The designs are the planting patterns a surrogate
learns from, one engine run each. The surrogate commands read what these write.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .console import console, error_console
from .corpus import tile_paths
from .service.baseline_request import BaselineRequest
from .service.city_catalog import CityCatalog
from .service.engine_service import EngineService
from .service.generation_request import GenerationRequest
from .service.generation_service import GenerationService, settings_for
from .service.missing_stage import MissingStage
from .service.null_progress import NullProgress
from .service.unknown_city import UnknownCity
from .service.unknown_tile import UnknownTile
from .surrogate.dataset import engine_threads
from .surrogate.generation_progress import GenerationProgress

app = typer.Typer(
    name="simulate",
    help="Run the physics engine over a tile: the baseline as it is, or the tree shade designs.",
    no_args_is_help=True,
)

KIND = "tree"  # the engine's intervention kind the tree shade designs add
LABEL = "tree shade"  # how the dashboard and the pages name the channel


@app.command("baseline")
def baseline(
    city: Annotated[str, typer.Argument(help="A city key, an id, a slug or a name.")],
    tile: Annotated[
        str | None, typer.Option("--tile", help="A tile id; else the densest built tile.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a line.")] = False,
) -> None:
    """Run the engine over a tile as it is, once, and keep the baseline beside its bundle.

    The engine is a separate subprocess. A baseline already on disk is kept, not rerun.
    """
    service = EngineService(CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT))
    try:
        with console.status(f"[cyan]{city}[/]: baseline physics"):
            outcome = service.run_baseline(BaselineRequest(target=city, tile=tile), NullProgress())
    except (UnknownCity, UnknownTile, MissingStage) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    if as_json:
        console.print_json(outcome.model_dump_json())
        return
    if outcome.kept:
        console.print(f"[green]{outcome.tile}[/]: baseline kept from disk at {outcome.destination}")
        return
    console.print(
        f"[green]{outcome.tile}[/]: baseline for {outcome.design_day} in {outcome.seconds:.0f}s "
        f"at {outcome.destination}"
    )


@app.command("treeshade")
def treeshade(
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
    """Run the tree shade designs through the engine, one tile at a time.

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


def resume_command(target: str, tile: str | None, out: Path | None, jobs: int) -> str:
    """The exact command that continues this run after a stop."""
    parts = ["sdc simulate treeshade", target]
    if tile:
        parts += ["--tiles", tile]
    if out:
        parts += ["--out", str(out)]
    if jobs != 1:
        parts += ["--jobs", str(jobs)]
    return " ".join(parts)
