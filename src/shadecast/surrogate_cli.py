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

from .console import console
from .surrogate.assessment import assess
from .surrogate.dataset import default_plan, generate
from .surrogate.patches import crop_batch
from .surrogate.training import save_report, train

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="surrogate",
    help="Fit and evaluate the learned response model that makes search affordable.",
    no_args_is_help=True,
)


@app.command("generate")
def generate_data(
    bundle: Annotated[Path, typer.Argument(help="A built city bundle directory.")],
    out: Annotated[Path | None, typer.Option("--out", help="Where to write responses.")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Intervention type.")] = "tree",
) -> None:
    """Run the designed experiments through the physics engine.

    Sparse probe designs make one engine call yield roughly a hundred independent
    single intervention responses, which is what keeps the physics budget affordable.
    """
    destination = out if out else Path("data/surrogate") / bundle.name
    plan = default_plan()
    console.print(
        f"[cyan]{bundle.name}[/]: {len(plan)} designs, "
        f"about {len(plan) * 200 / 60:.0f} minutes of engine time"
    )
    summary = generate(bundle, destination, plan=plan, kind=kind)
    console.print(f"[green]{summary['entries']}[/] responses written to {destination}")


@app.command("train")
def train_model(
    surrogate_dir: Annotated[Path, typer.Argument(help="Directory of generated responses.")],
    bundle: Annotated[Path, typer.Argument(help="The matching city bundle.")],
    epochs: Annotated[int, typer.Option("--epochs")] = 30,
    patch: Annotated[int, typer.Option("--patch", help="Patch side in pixels.")] = 256,
    per_entry: Annotated[int, typer.Option("--per-entry", help="Patches per design.")] = 24,
) -> None:
    """Fit the response model, holding out whole designs rather than patches."""
    started = time.time()
    with console.status("[cyan]cropping patches[/]"):
        inputs, targets, origins = crop_batch(
            surrogate_dir, bundle, size=patch, per_entry=per_entry
        )
    console.print(
        f"{len(inputs):,} patches of {patch}px from "
        f"{len(set(origins))} designs in {time.time() - started:.1f}s"
    )

    report = train(
        inputs,
        targets,
        origins,
        epochs=epochs,
        out_path=surrogate_dir / "model.pt",
    )
    report["patch_px"] = patch
    report["target_stats"] = {
        "mean_C": round(float(np.mean(targets)), 4),
        "max_C": round(float(np.max(targets)), 3),
    }
    save_report(report, surrogate_dir / "training_report.json")
    console.print_json(json.dumps({k: v for k, v in report.items() if k != "history"}))


@app.command("assess")
def assess_model(
    surrogate_dir: Annotated[Path, typer.Argument(help="Directory of generated responses.")],
    bundle: Annotated[Path, typer.Argument(help="The matching city bundle.")],
    design: Annotated[
        list[str] | None,
        typer.Option("--design", help="Assess these designs instead of the held-out set."),
    ] = None,
) -> None:
    """Compare the surrogate against engine truth on designs it never trained on.

    Reports skill against predicting nothing, whether the spillover tail survives,
    error in the plan score, and how well plans are ordered.
    """
    with console.status("[cyan]comparing surrogate against engine truth[/]"):
        report = assess(surrogate_dir, bundle, only=design)

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
    (Path(surrogate_dir) / "assessment.json").write_text(json.dumps(report, indent=2))
    console.print(f"[dim]full report written to {surrogate_dir}/assessment.json[/]")
