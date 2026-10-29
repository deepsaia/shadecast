"""Shared rich console and result rendering.

Kept apart from the command definitions so that presentation can change without
touching the commands, and so tests can render a table without invoking Typer.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .corpus.tile_stages import STAGE_NAMES
from .corpus.tile_stages import TileStages
from .corpus.urban_centre import UrbanCentre
from .service.city_summary import CitySummary
from .service.plan import Plan
from .service.ranking_row import RankingRow
from .service.run_summary import RunSummary
from .service.scenario_outcome import ScenarioOutcome
from .service.stage_counts import StageCounts
from .service.tile_summary import TileSummary

console = Console()
error_console = Console(stderr=True)

TIER_STYLE = {"A": "green", "B": "yellow", "C": "red"}


def corpus_table(cities: list[CitySummary]) -> Table:
    """Render the selected cities and how far each has come: built, with physics, modeled."""
    table = Table(title="selected cities", title_style="bold", header_style="dim")
    table.add_column("key", style="cyan", no_wrap=True)
    table.add_column("city")
    table.add_column("cc", style="dim", no_wrap=True)
    table.add_column("koppen", no_wrap=True)
    table.add_column("income", no_wrap=True)
    table.add_column("region", style="dim")
    table.add_column("wri", justify="center")
    table.add_column("built", justify="right", no_wrap=True)
    table.add_column("physics", justify="right", no_wrap=True)
    table.add_column("models", justify="right", no_wrap=True)

    for city in cities:
        table.add_row(
            city.key,
            city.name,
            city.country,
            city.koppen,
            city.income,
            city.region,
            "[green]yes[/]" if city.in_wri else "",
            _of_tiles(city.stages.bundle, city.stages.tiles),
            _of_tiles(city.stages.physics, city.stages.tiles),
            _of_tiles(city.stages.model, city.stages.tiles),
        )
    return table


def _of_tiles(count: int, tiles: int) -> str:
    return f"{count}/{tiles:,}" if count else "[dim]0[/]"


def plans_table(plans: list[Plan]) -> Table:
    """Render scored plans, one row each, in the order the report gives them."""
    table = Table(header_style="dim")
    table.add_column("plan", style="cyan", no_wrap=True)
    table.add_column("arrangement", no_wrap=True)
    table.add_column("coverage", justify="right", no_wrap=True)
    table.add_column("trees", justify="right", no_wrap=True)
    table.add_column("cost", justify="right", no_wrap=True)
    table.add_column("exposure drop", justify="right", no_wrap=True)
    table.add_column("people", justify="right", no_wrap=True)
    table.add_column("per $1k", justify="right", no_wrap=True)
    for plan in plans:
        table.add_row(
            plan.id,
            plan.arrangement,
            f"{plan.coverage:.1%}",
            f"{plan.trees:,}",
            f"${plan.cost_m:,.2f}M",
            f"{plan.exposure_drop:.3f} C",
            f"{plan.people:,}",
            f"{plan.efficiency:,.1f}",
        )
    return table


def ranking_table(rows: list[RankingRow]) -> Table:
    """Render tiles ranked by cooling per dollar of their scattered plans."""
    table = Table(title="cooling per dollar", title_style="bold", header_style="dim")
    table.add_column("tile", style="cyan")
    table.add_column("canopy", justify="right", no_wrap=True)
    table.add_column("built", justify="right", no_wrap=True)
    table.add_column("clustered per $1k", justify="right", no_wrap=True)
    table.add_column("scattered per $1k", justify="right", no_wrap=True)
    table.add_column("gain", justify="right", no_wrap=True)
    for row in rows:
        table.add_row(
            row.name,
            _percent(row.canopy),
            _percent(row.built_fraction),
            _cell(row.clustered_per_1k),
            _cell(row.scattered_per_1k),
            f"{row.gain:.1f}x" if row.gain is not None else "",
        )
    return table


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else ""


def runs_table(runs: list[RunSummary]) -> Table:
    """Render the runs in progress, one row each."""
    table = Table(title="runs in progress", title_style="bold", header_style="dim")
    table.add_column("kind", no_wrap=True)
    table.add_column("city", style="cyan", no_wrap=True)
    table.add_column("tile", no_wrap=True)
    table.add_column("model")
    table.add_column("started", no_wrap=True)
    table.add_column("process", no_wrap=True)
    table.add_column("progress", justify="right", no_wrap=True)
    for run in runs:
        table.add_row(
            run.kind,
            run.city,
            run.tile or "",
            run.model or "",
            run.started,
            _liveness(run.alive),
            f"{run.designs_done} of {run.designs_planned}" if run.designs_done is not None else "",
        )
    return table


def _liveness(alive: bool | None) -> str:
    if alive is None:
        return "[dim]unknown[/]"
    return "[green]alive[/]" if alive else "[red]gone[/]"


def stage_line(counts: StageCounts) -> str:
    """One line a reader can scan: how many tiles have reached each stage, out of all."""
    reached = counts.model_dump()
    return ", ".join(f"{reached.get(stage, 0)} of {counts.tiles} {stage}" for stage in STAGE_NAMES)


def stages_reached(stages: TileStages) -> str:
    """The stages a tile has reached, named in pipeline order, or none."""
    reached = [stage for stage, flag in stages.model_dump().items() if flag]
    return ", ".join(reached) or "none"


def centres_table(centres: list[UrbanCentre], matched: dict[int, str] | None = None) -> Table:
    """Render urban centres from the database, one row each.

    `matched` names the alias that made each centre match a search, shown when it is not the
    main name, because a San Jose found inside the San Francisco centre is a surprise otherwise.
    """
    aliases = matched or {}
    table = Table(header_style="dim")
    table.add_column("id", justify="right", style="dim", no_wrap=True)
    table.add_column("slug", style="cyan", no_wrap=True)
    table.add_column("name")
    table.add_column("country", style="dim")
    table.add_column("population 2025", justify="right", no_wrap=True)
    table.add_column("income", no_wrap=True)
    table.add_column("koppen", no_wrap=True)
    table.add_column("tiles", justify="right", no_wrap=True)
    for centre in centres:
        alias = aliases.get(centre.id)
        shown = centre.name if alias in (None, centre.name) else f"{centre.name} [dim](via {alias})[/]"
        table.add_row(
            str(centre.id),
            centre.slug,
            shown,
            centre.country,
            f"{centre.population_2025:,}",
            centre.income or "?",
            centre.koppen or "?",
            f"{centre.tiles:,}",
        )
    return table


def centre_details(centre: UrbanCentre) -> Table:
    """Render one urban centre as a two column table."""
    table = Table(title=centre.name, title_style="bold", header_style="dim", show_header=False)
    table.add_column("field", style="dim")
    table.add_column("value")
    rows = (
        ("id", str(centre.id)),
        ("slug", centre.slug),
        ("names", ", ".join(centre.names)),
        ("country", centre.country),
        ("population 2025", f"{centre.population_2025:,}"),
        ("area", f"{centre.area_km2:,} km2, {centre.tiles:,} tiles of 1 km"),
        ("income group", centre.income or "unknown"),
        ("Koppen", f"{centre.koppen} ({centre.koppen_code})" if centre.koppen else "unknown"),
        ("centroid", f"{centre.lat:.4f}, {centre.lon:.4f}"),
    )
    for field, value in rows:
        table.add_row(field, value)
    return table


def tiles_table(tiles: list[TileSummary]) -> Table:
    """Render described tiles, one row each, with the stages each has reached."""
    table = Table(header_style="dim")
    table.add_column("tile", style="cyan", no_wrap=True)
    table.add_column("people 2020", justify="right", no_wrap=True)
    table.add_column("built", justify="right", no_wrap=True)
    table.add_column("height", justify="right", no_wrap=True)
    table.add_column("centre", style="dim", no_wrap=True)
    table.add_column("stages", style="dim")
    for tile in tiles:
        centre = tile.centre or [float("nan"), float("nan")]
        table.add_row(
            tile.id,
            f"{tile.population_2020:,.0f}",
            f"{tile.built_fraction:.0%}",
            f"{tile.mean_height_m:.1f} m",
            f"{centre[0]:.4f}, {centre[1]:.4f}",
            stages_reached(tile.stages),
        )
    return table


def _cell(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def pairs_table(title: str, pairs: dict) -> Table:
    """Render a name to value mapping as two columns."""
    table = Table(title=title, title_style="bold", show_header=False)
    table.add_column("name", style="dim")
    table.add_column("value", justify="right")
    for name, value in pairs.items():
        table.add_row(str(name), _cell(value))
    return table


def scenario_table(outcome: ScenarioOutcome) -> Table:
    """One scenario's outcomes against doing nothing, with the levers as the tile resolved them."""
    return pairs_table(
        f"{outcome.city}  {outcome.tile}  {outcome.kind}, {outcome.arrangement}",
        {
            "coverage of feasible ground": f"{outcome.coverage:.1%}",
            "trees": f"{outcome.trees:,}",
            "cost": f"{outcome.cost_usd / 1e6:.2f} M USD",
            "priced at": f"{outcome.unit_cost:g} USD per m2, {outcome.maintenance:.0%} a year to maintain",
            "baseline": f"{outcome.baseline_exposure:.2f} C, {outcome.baseline_at_risk:,} people above 45 C",
            "exposure drop": f"{outcome.exposure_drop:.2f} C",
            "degree-hours removed": f"{outcome.excess_removed:,.0f}",
            "people moved below 45 C": f"{outcome.people:,}",
            "equity gap change": f"{outcome.equity_gap_change:+.2f} C",
            "excess removed per 1,000 USD": f"{outcome.efficiency:.2f}",
            "model": outcome.model_id,
            "answered in": f"{outcome.surrogate_seconds:.2f} s",
        },
    )


def records_table(title: str, rows: list[dict]) -> Table:
    """Render a list of like records, one row each, columns from the first record."""
    table = Table(title=title, title_style="bold", header_style="dim")
    columns = list(rows[0]) if rows else []
    for column in columns:
        table.add_column(column, justify="left" if column == columns[0] else "right")
    for row in rows:
        table.add_row(*(_cell(row.get(column)) for column in columns))
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
    table.add_row("excess reduced per 1,000 USD", "", "", f"{benefit['excess_reduced_per_1k_usd']:.2f}")
    return table
