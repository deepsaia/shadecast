"""Assemble what the experiments actually found, for the walkthrough to render.

Every number here is read from a result file rather than typed in, so the page cannot
drift away from the runs that produced it. Experiments that have not finished return a
pending entry instead of a blank, because a visitor should be able to see what is still
open as clearly as what is settled.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def surrogate_summary(assessment_path: Path, transfer_path: Path) -> dict:
    """How good the learned response model is, and whether more cities help it."""
    assessment = load_json(assessment_path) or {}
    transfer = load_json(transfer_path) or {}
    head = assessment.get("headline", {})
    speed = assessment.get("speed", {})
    points = transfer.get("points", [])
    return {
        "status": "done" if head else "pending",
        "skill": head.get("mean_skill"),
        "ranking_spearman": assessment.get("ranking", {}).get("spearman"),
        "aggregate_error": head.get("mean_aggregate_relative_error"),
        "engine_seconds": speed.get("engine_seconds"),
        "surrogate_seconds": speed.get("surrogate_seconds"),
        "speedup": speed.get("speedup"),
        "transfer": [
            {"cities": p["n_train_cities"], "skill": p["skill"], "mae_C": p["mae_C"]}
            for p in points
        ],
        "transfer_verdict": transfer.get("verdict"),
    }


def factorial_summary(path: Path, verdict: dict) -> dict:
    """Which intervention type wins, by how much, and how that splits by city."""
    rows = load_json(path)
    if not isinstance(rows, list) or not rows:
        return {"status": "pending"}
    placed = [r for r in rows if r.get("units", 0) > 0]
    budgets = sorted({r["budget_usd"] for r in placed})
    cities = sorted({r["city"] for r in placed})

    # The same money buys similar physics everywhere and very different human benefit.
    spreads = []
    for budget in budgets:
        trees = [r for r in placed if r["budget_usd"] == budget and r["kind"] == "tree"]
        if len(trees) < 2:
            continue
        drops = [r["exposure_drop_C"] for r in trees]
        people = [max(r["people"], 1) for r in trees]
        spreads.append(
            {
                "budget_usd": budget,
                "cooling_spread": round(max(drops) / min(drops), 2),
                "people_spread": round(max(people) / min(people), 1),
            }
        )

    return {
        "status": "done",
        "cells": len(rows),
        "cities": cities,
        "budgets": budgets,
        "verdict": verdict,
        "spreads": spreads,
        "rows": [
            {
                "city": r["city"],
                "kind": r["kind"],
                "budget_usd": r["budget_usd"],
                "units": r["units"],
                "exposure_drop_C": r["exposure_drop_C"],
                "people": r["people"],
                "efficiency": r["efficiency"],
            }
            for r in placed
        ],
    }


def pending(name: str, question: str, hypotheses: list[str], detail: str) -> dict:
    return {
        "status": "pending",
        "name": name,
        "question": question,
        "hypotheses": hypotheses,
        "detail": detail,
    }


def targeting_summary(path: Path) -> dict:
    """H8: does targeting walking corridors pick a different plan than targeting hot ground?"""
    payload = load_json(path)
    if not isinstance(payload, dict) or not payload.get("complete"):
        return pending(
            "Corridor targeting",
            "Should a budget cool the hottest ground, or the ground people actually walk on?",
            ["H8 plans differ", "H9 gain grows with how irregular the street network is"],
            "Two plans per city at one budget, both simulated. If they overlap above "
            "90 percent the corridor objective is redundant and gets reported as a null.",
        )
    return {"status": "done", "verdict": payload.get("verdict", {}), "rows": payload["rows"]}


def channel_summary(path: Path) -> dict:
    """H5 and H6: does removing sealed surface cool, and does it scale with its parameter?"""
    payload = load_json(path)
    if not isinstance(payload, dict) or not payload.get("complete"):
        return pending(
            "De-paving",
            "Does replacing asphalt with grass cool pedestrians, through a channel we trust?",
            ["H5 de-paving cools by 0.5 to 3 C", "H6 grass out-cools cobble"],
            "Each city pays for an extra control run holding land cover unchanged, so the "
            "result cannot confound de-paving with switching land cover on.",
        )
    return {"status": "done", "verdict": payload.get("verdict", {}), "rows": payload["rows"]}


def collect(data_root: Path, verdict: dict) -> dict:
    """Everything the walkthrough needs about what has been established so far."""
    root = Path(data_root)
    result = {
        "surrogate": surrogate_summary(
            root / "surrogate" / "ahmedabad" / "assessment.json",
            root / "surrogate" / "transfer_curve.json",
        ),
        "factorial": factorial_summary(root / "factorial.json", verdict),
        "targeting": targeting_summary(root / "targeting.json"),
        "channel": channel_summary(root / "channel.json"),
    }
    done = [k for k, v in result.items() if v.get("status") == "done"]
    logger.info("findings: %d settled, %d pending", len(done), len(result) - len(done))
    return result
