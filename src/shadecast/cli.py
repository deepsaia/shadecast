"""shadecast command line.

    shadecast list                 show the corpus and its stratification
    shadecast build <city>         assemble one bundle from open sources
    shadecast build --all          assemble the whole corpus
    shadecast run <bundle> <date>  run the physics engine over a bundle

Every build is credential-free and deterministic given a corpus version.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .build import build_city
from .cities import CORPUS, summary
from .logging_setup import configure
from .pipeline import evaluate
from .sim.runner import run

logger = logging.getLogger("shadecast")

DEFAULT_OUT = Path("data/cities")


def cmd_list(args: argparse.Namespace) -> int:
    """Print the corpus and how it is stratified."""
    del args
    sys.stdout.write(json.dumps(summary(), indent=2) + "\n\n")
    header = f"{'key':14s} {'city':20s} {'cc':4s} {'koppen':7s} {'inc':4s} {'region':12s} wri\n"
    sys.stdout.write(header)
    for city in CORPUS.values():
        sys.stdout.write(
            f"{city.key:14s} {city.name:20s} {city.country:4s} {city.koppen:7s} "
            f"{city.income:4s} {city.region:12s} {'yes' if city.in_wri else ''}\n"
        )
    return 0


def describe_build(key: str, elapsed: float, provenance: dict) -> str:
    """One readable line summarising a completed bundle."""
    quality = provenance["quality"]
    metrics = quality["metrics"]
    line = (
        f"[{quality['tier']}] {key:14s} {elapsed:6.1f}s  "
        f"{provenance['buildings']['count']:>6,} bldg  "
        f"built {metrics['built_fraction']:.0%}  "
        f"canopy {metrics['canopy_gt2m']:.0%}  "
        f"pop {metrics['population']:>8,.0f}  "
        f"{provenance['met']['design_day']}"
    )
    if quality["reasons"]:
        line += "  <- " + "; ".join(quality["reasons"])
    if quality.get("notes"):
        line += "  (" + "; ".join(quality["notes"]) + ")"
    return line


def cmd_build(args: argparse.Namespace) -> int:
    """Assemble one bundle or the whole corpus."""
    keys = list(CORPUS) if args.all else [args.city]
    unknown = [key for key in keys if key not in CORPUS]
    if unknown:
        logger.error("unknown city keys %s, try 'shadecast list'", unknown)
        return 2

    root = Path(args.out) if args.out else DEFAULT_OUT
    built = 0
    failed: list[str] = []

    for key in keys:
        started = time.time()
        try:
            provenance = build_city(CORPUS[key], root / key, side_m=args.side, res_m=args.res)
        # One unreachable source must not abandon the remaining cities. The failure
        # is logged with its type and never swallowed, and the run exits non-zero.
        except Exception:
            logger.exception("build failed for %s after %.1fs", key, time.time() - started)
            failed.append(key)
            continue
        sys.stdout.write(describe_build(key, time.time() - started, provenance) + "\n")
        built += 1

    logger.info("%d built, %d failed", built, len(failed))
    if failed:
        logger.error("failed cities: %s", ", ".join(failed))
    return 0 if not failed else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run the physics engine over an already-built bundle."""
    result = run(Path(args.bundle), args.date)
    sys.stdout.write(json.dumps(result.as_dict(), indent=2) + "\n")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Plan an intervention over a built bundle and score it against baseline."""
    result = evaluate(Path(args.bundle), kind=args.kind, budget_usd=args.budget)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Assemble the argument parser."""
    parser = argparse.ArgumentParser(prog="shadecast")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show the city corpus").set_defaults(fn=cmd_list)

    build = sub.add_parser("build", help="assemble city bundles from open sources")
    build.add_argument("city", nargs="?", help="corpus key, for example ahmedabad")
    build.add_argument("--all", action="store_true", help="build the whole corpus")
    build.add_argument("--out", help=f"output root, default {DEFAULT_OUT}")
    build.add_argument("--side", type=int, default=1000, help="study area side in metres")
    build.add_argument("--res", type=float, default=1.0, help="grid resolution in metres")
    build.set_defaults(fn=cmd_build)

    plan = sub.add_parser("plan", help="plan an intervention and score it")
    plan.add_argument("bundle")
    plan.add_argument("--kind", default="tree", help="intervention type")
    plan.add_argument("--budget", type=float, default=10_000_000, help="budget in USD")
    plan.set_defaults(fn=cmd_plan)

    runner = sub.add_parser("run", help="run the physics engine over a bundle")
    runner.add_argument("bundle")
    runner.add_argument("date", help="YYYY-MM-DD design day")
    runner.set_defaults(fn=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure(verbose=args.verbose)
    if args.cmd == "build" and not args.all and not args.city:
        parser.error("give a city key or --all")
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
