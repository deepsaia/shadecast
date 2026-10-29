"""Command line for the pre-registered experiments.

Each command names an experiment and the cities to run it over; the experiment service pairs
every city's densest tile with a baseline to its simulated physics and applies the fixed verdict
rule. These commands only parse flags and render the outcome.
What a command runs is imported inside it, so ``sdc --help`` answers before any heavy library loads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from .console import console
from .corpus import tile_paths
from .exit_codes import fail
from .service.experiment_request import ExperimentRequest
from .service.missing_stage import MissingStage
from .service.null_progress import NullProgress
from .service.unknown_city import UnknownCity

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="experiments",
    help="Run the pre-registered experiments and apply their fixed verdict rules.",
    no_args_is_help=True,
)

CITIES_HELP = "City keys, ids, slugs or names; each contributes its densest tile with a baseline."
DEFAULT_BUDGET = 2_288_000.0


def _run(request: ExperimentRequest, as_json: bool) -> None:
    from .service.city_catalog import CityCatalog
    from .service.experiment_service import ExperimentService

    service = ExperimentService(
        CityCatalog.open(tile_paths.TILES_ROOT, tile_paths.MODELS_ROOT),
        tile_paths.TILES_ROOT.parent,
    )
    try:
        with console.status(f"[cyan]{request.name}[/]: every cell is a real engine run"):
            outcome = service.run(request, NullProgress())
    except (ValueError, UnknownCity, MissingStage) as exc:
        fail(exc)
    if as_json:
        console.print_json(outcome.model_dump_json())
        return
    if outcome.verdict:
        console.print_json(data=outcome.verdict)
    console.print(f"[green]{outcome.rows} rows written to {outcome.out}[/]")


@app.command("factorial")
def factorial(
    cities: Annotated[list[str], typer.Argument(help=CITIES_HELP)],
    out: Annotated[Path | None, typer.Option("--out", help="Where to write results.")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a line.")] = False,
) -> None:
    """Which intervention type buys the most cooling per dollar (H3, H4)?

    Every cell is a real engine run. The albedo arms are excluded while their sign is
    unresolved, so this covers the geometry and surface temperature channels only.
    """
    _run(ExperimentRequest(name="factorial", cities=cities, out=out), as_json)


@app.command("targeting")
def targeting(
    cities: Annotated[list[str], typer.Argument(help=CITIES_HELP)],
    budget: Annotated[float, typer.Option("--budget", help="Budget in USD.")] = DEFAULT_BUDGET,
    out: Annotated[Path | None, typer.Option("--out", help="Where to write results.")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a line.")] = False,
) -> None:
    """Does targeting corridors select a different plan than targeting hot ground (H8)?

    Two plans per city at one budget, both simulated, each scored on both objectives.
    A high overlap falsifies H8 and is reported as a null rather than quietly dropped.
    """
    _run(ExperimentRequest(name="targeting", cities=cities, out=out, budget=budget), as_json)


@app.command("channel")
def channel(
    cities: Annotated[list[str], typer.Argument(help=CITIES_HELP)],
    budget: Annotated[float, typer.Option("--budget", help="Budget in USD.")] = DEFAULT_BUDGET,
    out: Annotated[Path | None, typer.Option("--out", help="Where to write results.")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a line.")] = False,
) -> None:
    """Does the surface temperature channel cool, and behave like its parameter (H5, H6)?

    Each city pays for one extra engine run holding land cover unchanged. Without that
    matched control the result would confound de-paving with switching land cover on.
    """
    _run(ExperimentRequest(name="channel", cities=cities, out=out, budget=budget), as_json)
