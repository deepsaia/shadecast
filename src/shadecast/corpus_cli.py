"""Command line for the corpus: search, show and sample urban centres.

The corpus is the GHS Urban Centre Database, fetched once with no credentials and read from
the cache after that. These commands are the way into it: find a centre, see its strata and
tile count, or draw a stratified set with a seed so the benchmark selection is reproducible.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

import typer

from .console import (
    centre_details,
    centres_table,
    console,
    error_console,
    pairs_table,
    records_table,
    stage_line,
)
from .corpus import tile_paths
from .corpus.draw import Draw
from .corpus.sampling import sample as draw_sample
from .corpus.sampling import strata
from .corpus.slugs import slugify
from .corpus.statistics import corpus_stats
from .corpus.urban_centre import UrbanCentre
from .corpus.urban_centres import UrbanCentres
from .service.stage_counting import count_stages

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="corpus",
    help="Search, inspect and sample the urban centres any city is drawn from.",
    no_args_is_help=True,
)


def load_centres() -> UrbanCentres:
    """The database, fetched on first use and cached after that."""
    return UrbanCentres.load()


def matched_name(centre: UrbanCentre, text: str) -> str:
    """The name that made a centre match a search, which is often not its main name."""
    key = slugify(text)
    for name in centre.names:
        if key and key in slugify(name):
            return name
    return centre.name


def as_record(centre: UrbanCentre) -> dict:
    return {
        "id": centre.id,
        "slug": centre.slug,
        "name": centre.name,
        "country": centre.country,
        "population_2025": centre.population_2025,
        "area_km2": centre.area_km2,
        "tiles": centre.tiles,
        "income": centre.income,
        "koppen": centre.koppen,
        "koppen_code": centre.koppen_code,
        "lat": centre.lat,
        "lon": centre.lon,
    }


@app.command("search")
def search(
    text: Annotated[str, typer.Argument(help="Part of a name; empty matches everything.")] = "",
    country: Annotated[str | None, typer.Option("--country", help="Country name.")] = None,
    min_population: Annotated[
        int, typer.Option("--min-population", help="Smallest 2025 population to list.")
    ] = 0,
    limit: Annotated[int, typer.Option("--limit", help="Rows to show.")] = 30,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """List urban centres whose names contain the text, most populous first."""
    found = load_centres().search(text, country=country, min_population=min_population)
    shown = found[:limit]
    matched = {centre.id: matched_name(centre, text) for centre in shown}
    if as_json:
        rows = [{**as_record(centre), "matched": matched.get(centre.id)} for centre in shown]
        console.print_json(json.dumps(rows))
        return
    console.print(centres_table(shown, matched))
    console.print(f"[dim]{len(shown)} of {len(found)} matches shown.[/]")


@app.command("show")
def show(
    centre: Annotated[str, typer.Argument(help="An id, a slug such as ahmedabad, or a name.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Show one urban centre: strata, population, and how many 1 km tiles it holds."""
    try:
        found = load_centres().resolve(centre)
    except (KeyError, ValueError) as exc:
        error_console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from exc
    counts = count_stages(tile_paths.TILES_ROOT, found.id, found.tiles)
    if as_json:
        console.print_json(json.dumps({**as_record(found), "status": counts.model_dump()}))
        return
    console.print(centre_details(found))
    console.print(f"[dim]{stage_line(counts)}.[/]")


@app.command("sample")
def sample(
    per_stratum: Annotated[
        int, typer.Option("--per-stratum", help="Centres per Koppen and income stratum.")
    ] = 2,
    min_population: Annotated[
        int, typer.Option("--min-population", help="Smallest 2025 population to draw from.")
    ] = 500_000,
    seed: Annotated[
        int, typer.Option("--seed", help="Random seed, so the draw is reproducible.")
    ] = 0,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
) -> None:
    """Draw a stratified set of urban centres, k per Koppen class and income group."""
    draw = Draw(per_stratum=per_stratum, min_population_2025=min_population, seed=seed)
    drawn = draw_sample(load_centres().all(), draw)
    if as_json:
        console.print_json(json.dumps([as_record(centre) for centre in drawn]))
        return
    console.print(centres_table(drawn))
    console.print(
        f"[dim]{len(drawn)} centres across {len(strata(drawn))} strata, "
        f"2025 population at least {min_population:,}, seed {seed}.[/]"
    )


@app.command("stats")
def stats(
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON instead of tables.")] = False,
) -> None:
    """Statistics over the whole corpus: totals, continents, countries, strata and sizes."""
    summary = corpus_stats(load_centres().all())
    if as_json:
        console.print_json(json.dumps(summary))
        return
    console.print(pairs_table("Corpus", summary.get("totals", {})))
    console.print(records_table("By continent", summary.get("by_continent", [])))
    console.print(
        records_table("Countries with most urban centres", summary.get("top_countries", []))
    )
    console.print(pairs_table("By Koppen class", summary.get("by_koppen", {})))
    console.print(pairs_table("By income group", summary.get("by_income", {})))
    console.print(
        pairs_table("Urban centres by size, in 1 km tiles", summary.get("size_bands", {}))
    )
