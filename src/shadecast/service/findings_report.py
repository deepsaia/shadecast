"""What the experiments found, read from their result files so the page cannot drift from the runs.

Experiments that have not finished answer a pending entry instead of a blank, because a reader
should see what is still open as clearly as what is settled.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..experiments.factorial import verdict as factorial_verdict
from .findings import Findings
from .json_file import read_json, read_object

logger = logging.getLogger(__name__)

COMMANDS = {
    "Corridor targeting": "sdc experiments targeting <city> [<city> ...]",
    "De-paving": "sdc experiments channel <city> [<city> ...]",
    "Surrogate": "sdc surrogate treeshade assess <city>",
    "Factorial": "sdc experiments factorial <city> [<city> ...]",
}


class FindingsReport:
    """Answers what has been established so far, from the data root's experiment files."""

    def __init__(self, data_root: Path) -> None:
        self._root = Path(data_root)

    def collect(self) -> Findings:
        rows = read_json(self._root / "factorial.json")
        verdict = factorial_verdict(rows) if isinstance(rows, list) and rows else {}
        findings = Findings(
            surrogate=surrogate_summary(
                self.latest_assessment(), self._root / "transfer_curve.json"
            ),
            factorial=factorial_summary(self._root / "factorial.json", verdict),
            targeting=targeting_summary(self._root / "targeting.json"),
            channel=channel_summary(self._root / "channel.json"),
        )
        done = [
            name for name, part in findings.model_dump().items() if part.get("status") == "done"
        ]
        logger.info("findings: %d settled, %d pending", len(done), 4 - len(done))
        return findings

    def latest_assessment(self) -> Path | None:
        """The most recently created assessed model across every tile, or None when none is."""
        newest: tuple[str, Path] | None = None
        for assessment in (self._root / "tiles").glob("*/*/models/*/assessment.json"):
            created = str(read_object(assessment.parent / "manifest.json").get("created", ""))
            if newest is None or created > newest[0]:
                newest = (created, assessment)
        return newest[1] if newest else None


def surrogate_summary(assessment_path: Path | None, transfer_path: Path) -> dict:
    """How good the learned response model is, and whether more cities help it."""
    assessment = read_object(assessment_path) if assessment_path else {}
    transfer = read_object(transfer_path)
    head = assessment.get("headline", {})
    speed = assessment.get("speed", {})
    return {
        "status": "done" if head else "pending",
        "name": "Surrogate",
        "command": COMMANDS.get("Surrogate", ""),
        "skill": head.get("mean_skill"),
        "ranking_spearman": assessment.get("ranking", {}).get("spearman"),
        "aggregate_error": head.get("mean_aggregate_relative_error"),
        "engine_seconds": speed.get("engine_seconds"),
        "surrogate_seconds": speed.get("surrogate_seconds"),
        "speedup": speed.get("speedup"),
        "transfer": [
            {
                "cities": point.get("n_train_cities"),
                "skill": point.get("skill"),
                "mae_C": point.get("mae_C"),
            }
            for point in transfer.get("points", [])
        ],
        "transfer_verdict": transfer.get("verdict"),
    }


def factorial_summary(path: Path, verdict: dict) -> dict:
    """Which intervention type wins, by how much, and how that splits by city."""
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        return {"status": "pending", "name": "Factorial", "command": COMMANDS.get("Factorial", "")}
    placed = [row for row in rows if row.get("units", 0) > 0]
    budgets = sorted({row.get("budget_usd") for row in placed})
    cities = sorted({str(row.get("city")) for row in placed})
    return {
        "status": "done",
        "cells": len(rows),
        "cities": cities,
        "budgets": budgets,
        "verdict": verdict,
        "spreads": _spreads(placed, budgets),
        "rows": [
            {
                "city": row.get("city"),
                "kind": row.get("kind"),
                "budget_usd": row.get("budget_usd"),
                "units": row.get("units"),
                "exposure_drop_C": row.get("exposure_drop_C"),
                "people": row.get("people"),
                "efficiency": row.get("efficiency"),
            }
            for row in placed
        ],
    }


def _spreads(placed: list[dict], budgets: list) -> list[dict]:
    """The same money buys similar physics everywhere and very different human benefit."""
    spreads = []
    for budget in budgets:
        trees = [r for r in placed if r.get("budget_usd") == budget and r.get("kind") == "tree"]
        if len(trees) < 2:
            continue
        drops = [float(row.get("exposure_drop_C", 0.0)) for row in trees]
        people = [max(float(row.get("people", 0.0)), 1.0) for row in trees]
        spreads.append(
            {
                "budget_usd": budget,
                "cooling_spread": round(max(drops) / min(drops), 2) if min(drops) else None,
                "people_spread": round(max(people) / min(people), 1),
            }
        )
    return spreads


# Four arguments because a pending finding is a name, a question, its hypotheses and what it
# would take; the command that produces it is looked up by name.
def pending(name: str, question: str, hypotheses: list[str], detail: str) -> dict:
    return {
        "status": "pending",
        "name": name,
        "question": question,
        "hypotheses": hypotheses,
        "detail": detail,
        "command": COMMANDS.get(name, ""),
    }


def targeting_summary(path: Path) -> dict:
    """H8: does targeting walking corridors pick a different plan than targeting hot ground?"""
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload.get("complete"):
        return pending(
            "Corridor targeting",
            "Should a budget cool the hottest ground, or the ground people actually walk on?",
            ["H8 plans differ", "H9 gain grows with how irregular the street network is"],
            "Two plans per city at one budget, both simulated. If they overlap above "
            "90 percent the corridor objective is redundant and gets reported as a null.",
        )
    return {
        "status": "done",
        "verdict": payload.get("verdict", {}),
        "rows": payload.get("rows", []),
    }


def channel_summary(path: Path) -> dict:
    """H5 and H6: does removing sealed surface cool, and does it scale with its parameter?"""
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload.get("complete"):
        return pending(
            "De-paving",
            "Does replacing asphalt with grass cool pedestrians, through a channel we trust?",
            ["H5 de-paving cools by 0.5 to 3 C", "H6 grass out-cools cobble"],
            "Each city pays for an extra control run holding land cover unchanged, so the "
            "result cannot confound de-paving with switching land cover on.",
        )
    return {
        "status": "done",
        "verdict": payload.get("verdict", {}),
        "rows": payload.get("rows", []),
    }
