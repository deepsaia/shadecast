"""Command line for the pre-registered experiments.

Each command runs a design written down in PREREGISTRATION.md before any result was
seen. The verdict rules live in the experiment modules rather than here, so what counts
as support cannot be adjusted from the command line after the fact.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from .console import console
from .experiments.factorial import run_factorial
from .experiments.targeting import run_targeting

logger = logging.getLogger(__name__)

DEFAULT_SURROGATE = Path("data/surrogate")

app = typer.Typer(
    name="experiments",
    help="Run the pre-registered experiments and apply their fixed verdict rules.",
    no_args_is_help=True,
)


def _corpus(bundles: list[Path], surrogate_root: Path) -> list[tuple[str, Path, Path]]:
    """Pair each bundle with the surrogate directory holding its baseline field."""
    corpus = []
    for bundle in bundles:
        name = bundle.name
        surrogate_dir = surrogate_root / name
        if not (surrogate_dir / "baseline" / "tmrt_daylight.npy").exists():
            raise typer.BadParameter(
                f"{name} has no baseline field at {surrogate_dir}. Run the baseline first."
            )
        corpus.append((name, bundle, surrogate_dir))
    return corpus


@app.command("factorial")
def factorial(
    bundles: Annotated[list[Path], typer.Argument(help="Built city bundle directories.")],
    out: Annotated[Path, typer.Option("--out", help="Where to write results.")] = Path(
        "data/factorial.json"
    ),
    surrogate_root: Annotated[
        Path, typer.Option("--surrogate-root", help="Root holding per-city baselines.")
    ] = DEFAULT_SURROGATE,
) -> None:
    """Which intervention type buys the most cooling per dollar (H3, H4)?

    Every cell is a real engine run. The albedo arms are excluded while their sign is
    unresolved, so this covers the geometry and surface temperature channels only.
    """
    corpus = _corpus(bundles, surrogate_root)
    rows = run_factorial(corpus, out)
    console.print(f"[green]{len(rows)} cells written to {out}[/]")


@app.command("targeting")
def targeting(
    bundles: Annotated[list[Path], typer.Argument(help="Built city bundle directories.")],
    budget: Annotated[float, typer.Option("--budget", help="Budget in USD.")] = 2_288_000.0,
    out: Annotated[Path, typer.Option("--out", help="Where to write results.")] = Path(
        "data/targeting.json"
    ),
    surrogate_root: Annotated[
        Path, typer.Option("--surrogate-root", help="Root holding per-city baselines.")
    ] = DEFAULT_SURROGATE,
) -> None:
    """Does targeting corridors select a different plan than targeting hot ground (H8)?

    Two plans per city at one budget, both simulated, each scored on both objectives.
    A high overlap falsifies H8 and is reported as a null rather than quietly dropped.
    """
    corpus = _corpus(bundles, surrogate_root)
    result = run_targeting(corpus, out, budget=budget)
    console.print_json(json.dumps(result["verdict"]))
    console.print(f"[green]written to {out}[/]")
