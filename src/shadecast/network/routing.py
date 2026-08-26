"""Routing over heat, and the corridor leverage that makes the inverse problem work.

The published work on shaded routing solves the forward problem: given the shade a
city already has, find the coolest way across it. That is useful to a walker and no
use at all to a planner, who has to decide where shade should go in the first place.

This module holds the inverse. A trip is routed on *perceived* cost, because a walker
trades distance against sun rather than minimising either alone, and is then scored on
the heat actually met along the route it chose. Separating the two matters: routing
behaviour and planning value are different questions, and collapsing them would let a
plan claim credit for cooling a street that no reasonable walker would have taken.

The planning quantity is `corridor`, the trip-weighted heat carried by each edge. It
is high where many optimal routes are forced through the same hot ground, which is
exactly where a fixed budget buys the most relief and is invisible to any area average.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx
import numpy as np
from scipy.ndimage import uniform_filter

from ..aoi import AOI

logger = logging.getLogger(__name__)

# Tmrt a walker treats as unremarkable, and the span over which discomfort scales.
TMRT_COMFORT_C = 30.0
TMRT_SCALE_C = 20.0
# Detour aversion. At beta = 1.0 a street at Tmrt 50 feels twice its length, so a
# walker will accept roughly a doubled route to escape full sun and no more.
BETA = 1.0


@dataclass
class RouteScore:
    """What the network objective reports. All temperatures are degrees Celsius."""

    experienced_tmrt: float  # trip-weighted mean Tmrt on the routes walkers choose
    shortest_tmrt: float  # same, had they walked the shortest path instead
    detour_ratio: float  # chosen length over shortest length
    trips: int
    unreachable: int
    corridor: dict[tuple[int, int], float]  # share of all trip heat carried, sums to 1

    def as_dict(self) -> dict[str, float]:
        return {
            "experienced_tmrt": round(self.experienced_tmrt, 4),
            "shortest_tmrt": round(self.shortest_tmrt, 4),
            "detour_ratio": round(self.detour_ratio, 4),
            "avoided_tmrt": round(self.shortest_tmrt - self.experienced_tmrt, 4),
            "trips": self.trips,
            "unreachable": self.unreachable,
        }


def set_perceived(graph: nx.MultiDiGraph, *, beta: float = BETA) -> nx.MultiDiGraph:
    """Attach perceived walking cost to each edge: metres, inflated by heat.

    Edges with no Tmrt coverage take the network median rather than zero, so a gap in
    the raster cannot masquerade as a cool shortcut.
    """
    values = np.array(
        [d.get("tmrt", np.nan) for _, _, d in graph.edges(data=True)], dtype=np.float64
    )
    fallback = float(np.nanmedian(values)) if np.isfinite(values).any() else TMRT_COMFORT_C
    for u, v, key, data in graph.edges(keys=True, data=True):
        tmrt = data.get("tmrt", np.nan)
        if not np.isfinite(tmrt):
            tmrt = fallback
        penalty = max(0.0, (tmrt - TMRT_COMFORT_C) / TMRT_SCALE_C)
        length = float(data.get("length", 1.0))
        graph.edges[u, v, key]["heat"] = tmrt
        graph.edges[u, v, key]["perceived"] = length * (1.0 + beta * penalty)
    return graph


def to_routable(graph: nx.MultiDiGraph) -> nx.DiGraph:
    """Collapse parallel edges to the cheapest one, so a path implies a unique edge."""
    out = nx.DiGraph()
    out.add_nodes_from(graph.nodes(data=True))
    for u, v, data in graph.edges(data=True):
        best = out.get_edge_data(u, v)
        if best is None or data["perceived"] < best["perceived"]:
            out.add_edge(
                u, v, perceived=data["perceived"], length=float(data["length"]), heat=data["heat"]
            )
    return out


def node_population(
    graph: nx.DiGraph, pop: np.ndarray, aoi: AOI, *, radius_m: float = 100.0
) -> dict[int, float]:
    """People within walking reach of each node, used as trip weight.

    A node is a junction, not a home, so the population it represents is the people who
    would plausibly start or finish a trip there.
    """
    size = max(1, int(2 * radius_m / aoi.res_m))
    density = uniform_filter(np.nan_to_num(pop).astype(np.float64), size=size) * size * size
    minx, _, _, maxy = aoi.bounds_utm
    height, width = pop.shape
    weights: dict[int, float] = {}
    for node, data in graph.nodes(data=True):
        col = int((data["x"] - minx) / aoi.res_m)
        row = int((maxy - data["y"]) / aoi.res_m)
        if 0 <= row < height and 0 <= col < width:
            weights[node] = float(density[row, col])
        else:
            weights[node] = 0.0
    return weights


def sample_nodes(weights: dict[int, float], n: int, *, seed: int = 0) -> list[int]:
    """Draw trip endpoints in proportion to the people near them."""
    nodes = np.array(list(weights.keys()))
    mass = np.array([weights[k] for k in nodes], dtype=np.float64)
    if mass.sum() <= 0:
        mass = np.ones_like(mass)
    probability = mass / mass.sum()
    take = min(n, int((probability > 0).sum()))
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(nodes), size=take, replace=False, p=probability)
    return [int(nodes[i]) for i in chosen]


def _walk(path: list[int], graph: nx.DiGraph) -> tuple[float, float]:
    """Total length and total heat-metres along a node path."""
    length = 0.0
    heat = 0.0
    for u, v in pairwise(path):
        data = graph.edges[u, v]
        length += data["length"]
        heat += data["length"] * data["heat"]
    return length, heat


def evaluate(graph: nx.DiGraph, weights: dict[int, float], endpoints: list[int]) -> RouteScore:
    """Score the network on the heat met along the routes people would actually walk."""
    chosen_len = chosen_heat = short_len = short_heat = 0.0
    trips = 0
    unreachable = 0
    corridor: dict[tuple[int, int], float] = {}

    for origin in endpoints:
        _, cool_paths = nx.single_source_dijkstra(graph, origin, weight="perceived")
        _, fast_paths = nx.single_source_dijkstra(graph, origin, weight="length")
        for target in endpoints:
            if target == origin:
                continue
            if target not in cool_paths or target not in fast_paths:
                unreachable += 1
                continue
            weight = weights[origin] * weights[target]
            if weight <= 0:
                continue
            path = cool_paths[target]
            length, heat = _walk(path, graph)
            fast_length, fast_heat = _walk(fast_paths[target], graph)
            chosen_len += weight * length
            chosen_heat += weight * heat
            short_len += weight * fast_length
            short_heat += weight * fast_heat
            trips += 1
            for u, v in pairwise(path):
                edge = graph.edges[u, v]
                carried = weight * edge["length"] * edge["heat"]
                corridor[u, v] = corridor.get((u, v), 0.0) + carried

    if chosen_len <= 0 or short_len <= 0:
        logger.warning("no routable trips with positive population weight")
        return RouteScore(float("nan"), float("nan"), float("nan"), 0, unreachable, {})

    # Normalised to shares of total trip heat. The absolute figure is a product of
    # people, metres and degrees, which is not a quantity anyone has intuition for;
    # "this edge carries 3 percent of all trip heat" is directly actionable.
    flow = sum(corridor.values())
    if flow > 0:
        corridor = {edge: value / flow for edge, value in corridor.items()}

    return RouteScore(
        experienced_tmrt=chosen_heat / chosen_len,
        shortest_tmrt=short_heat / short_len,
        detour_ratio=chosen_len / short_len,
        trips=trips,
        unreachable=unreachable,
        corridor=corridor,
    )
