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
from .surrogate.patches import crop_batch, crop_cities
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
    surrogate_dir: Annotated[
        Path | None, typer.Argument(help="Directory of generated responses.")
    ] = None,
    bundle: Annotated[Path | None, typer.Argument(help="The matching city bundle.")] = None,
    pair: Annotated[
        list[str] | None,
        typer.Option(
            "--pair",
            help="Train across cities: SURROGATE_DIR=BUNDLE, repeatable.",
        ),
    ] = None,
    holdout_city: Annotated[
        str | None,
        typer.Option("--holdout-city", help="Hold out this whole city to measure transfer."),
    ] = None,
    epochs: Annotated[int, typer.Option("--epochs")] = 30,
    patch: Annotated[int, typer.Option("--patch", help="Patch side in pixels.")] = 256,
    per_entry: Annotated[int, typer.Option("--per-entry", help="Patches per design.")] = 24,
) -> None:
    """Fit the response model.

    By default a whole design is held out, which measures generalisation to an unseen
    intervention pattern. With --holdout-city a whole city is held out instead, which
    measures transfer to unseen geometry. Those are different questions.
    """
    pairs: list[tuple[Path, Path]] = []
    if pair:
        for item in pair:
            if "=" not in item:
                raise typer.BadParameter(f"--pair needs SURROGATE_DIR=BUNDLE, got {item!r}")
            left, right = item.split("=", 1)
            pairs.append((Path(left), Path(right)))
    elif surrogate_dir and bundle:
        pairs.append((surrogate_dir, bundle))
    else:
        raise typer.BadParameter("give SURROGATE_DIR and BUNDLE, or one or more --pair")

    if holdout_city and len(pairs) < 2:
        raise typer.BadParameter("--holdout-city needs at least two cities")

    started = time.time()
    with console.status("[cyan]cropping patches[/]"):
        if len(pairs) == 1:
            inputs, targets, origins = crop_batch(
                pairs[0][0], pairs[0][1], size=patch, per_entry=per_entry
            )
        else:
            inputs, targets, origins = crop_cities(pairs, size=patch, per_entry=per_entry)

    console.print(
        f"{len(inputs):,} patches of {patch}px from {len(set(origins))} designs "
        f"across {len(pairs)} cities in {time.time() - started:.1f}s"
    )

    destination = pairs[0][0] if len(pairs) == 1 else Path("data/surrogate/multi")
    destination.mkdir(parents=True, exist_ok=True)

    report = train(
        inputs,
        targets,
        origins,
        epochs=epochs,
        holdout_city=holdout_city,
        out_path=destination / "model.pt",
    )
    report["patch_px"] = patch
    report["cities"] = [str(b) for _, b in pairs]
    report["target_stats"] = {
        "mean_C": round(float(np.mean(targets)), 4),
        "max_C": round(float(np.max(targets)), 3),
    }
    save_report(report, destination / "training_report.json")
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
