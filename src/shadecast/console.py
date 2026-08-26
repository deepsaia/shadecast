"""Shared rich console and result rendering.

Kept apart from the command definitions so that presentation can change without
touching the commands, and so tests can render a table without invoking Typer.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .cities import City

console = Console()
error_console = Console(stderr=True)

TIER_STYLE = {"A": "green", "B": "yellow", "C": "red"}


def corpus_table(cities: list[City]) -> Table:
    """Render the city corpus."""
    table = Table(title="shadecast corpus", title_style="bold", header_style="dim")
    table.add_column("key", style="cyan", no_wrap=True)
    table.add_column("city")
    table.add_column("cc", style="dim", no_wrap=True)
    table.add_column("koppen", no_wrap=True)
    table.add_column("income", no_wrap=True)
    table.add_column("region", style="dim")
    table.add_column("wri", justify="center")

    for city in cities:
        table.add_row(
            city.key,
            city.name,
            city.country,
            city.koppen,
            city.income,
            city.region,
            "[green]yes[/]" if city.in_wri else "",
        )
    return table


def build_table() -> Table:
    """An empty table ready to accept one row per built bundle."""
    table = Table(header_style="dim")
    table.add_column("tier", justify="center", no_wrap=True)
    table.add_column("city", style="cyan", no_wrap=True)
    table.add_column("secs", justify="right", no_wrap=True)
    table.add_column("buildings", justify="right", no_wrap=True)
    table.add_column("built", justify="right", no_wrap=True)
    table.add_column("canopy", justify="right", no_wrap=True)
    table.add_column("population", justify="right", no_wrap=True)
    table.add_column("design day", no_wrap=True)
    table.add_column("note", style="dim")
    return table


def add_build_row(table: Table, key: str, elapsed: float, provenance: dict) -> None:
    """Append one completed bundle to a build table."""
    quality = provenance["quality"]
    metrics = quality["metrics"]
    tier = quality["tier"]
    note = "; ".join(quality["reasons"] or quality.get("notes") or [])
    table.add_row(
        f"[{TIER_STYLE.get(tier, 'white')}]{tier}[/]",
        key,
        f"{elapsed:.1f}",
        f"{provenance['buildings']['count']:,}",
        f"{metrics['built_fraction']:.0%}",
        f"{metrics['canopy_gt2m']:.0%}",
        f"{metrics['population']:,.0f}",
        provenance["met"]["design_day"],
        note,
    )


def result_table(result: dict) -> Table:
    """Render one plan-and-evaluate outcome."""
    benefit = result["benefit"]
    table = Table(
        title=f"{result['city']}  {result['intervention']}  {result['design_day']}",
        title_style="bold",
        header_style="dim",
    )
    table.add_column("metric")
    table.add_column("baseline", justify="right")
    table.add_column("with plan", justify="right")
    table.add_column("change", justify="right", style="bold")

    table.add_row(
        "outdoor Tmrt, population weighted",
        f"{result['baseline']['exposure']:.2f} C",
        f"{result['plan']['exposure']:.2f} C",
        f"[green]-{benefit['delta_exposure_C']:.2f} C[/]",
    )
    table.add_row(
        "people above the stress threshold",
        f"{result['baseline']['people_at_risk']:,.0f}",
        f"{result['plan']['people_at_risk']:,.0f}",
        f"[green]-{benefit['delta_people_at_risk']:,.0f}[/]",
    )
    table.add_section()
    table.add_row("Tmrt drop where planted", "", "", f"{result['tmrt_drop_where_planted_C']:.2f} C")
    table.add_row("spillover to unplanted ground", "", "", f"{result['spillover_C']:.2f} C")
    table.add_row("cost", "", f"${result['plan']['cost_usd']:,.0f}", "")
    table.add_row(
        "excess reduced per 1,000 USD", "", "", f"{benefit['excess_reduced_per_1k_usd']:.2f}"
    )
    return table
