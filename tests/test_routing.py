"""The network objective: does routing over heat find what an area average cannot?"""

import networkx as nx
import numpy as np

from shadecast.aoi import AOI
from shadecast.network import heat, routing

AOI_TEST = AOI("synthetic", 23.03, 72.58, side_m=200, res_m=1.0)
PITCH, NODES, OFFSET = 20.0, 9, 20.0

# One scorching north-south avenue laid exactly on lattice column 4, with cool
# parallel streets a block either side, so dodging it is cheap. Heat nobody can
# dodge tells us nothing about routing.
TMRT = np.full((200, 200), 35.0)
TMRT[:, 96:105] = 58.0
POP = np.ones((200, 200))


def _lattice(cut_col: int | None = None, beta: float = routing.BETA) -> nx.DiGraph:
    """A regular grid, optionally severed so one row carries every crossing."""
    minx, miny, _, _ = AOI_TEST.bounds_utm
    graph = nx.MultiDiGraph()
    for i in range(NODES):
        for j in range(NODES):
            graph.add_node(i * NODES + j, x=minx + OFFSET + j * PITCH, y=miny + OFFSET + i * PITCH)
    for i in range(NODES):
        for j in range(NODES):
            for di, dj in ((0, 1), (1, 0)):
                if i + di >= NODES or j + dj >= NODES:
                    continue
                if cut_col is not None and dj == 1 and j == cut_col and i != 4:
                    continue
                a, b = i * NODES + j, (i + di) * NODES + (j + dj)
                graph.add_edge(a, b, length=PITCH)
                graph.add_edge(b, a, length=PITCH)
    heat.annotate(graph, TMRT, AOI_TEST)
    routing.set_perceived(graph, beta=beta)
    return routing.to_routable(graph)


def _scored(graph: nx.DiGraph) -> routing.RouteScore:
    weights = routing.node_population(graph, POP, AOI_TEST, radius_m=30.0)
    return routing.evaluate(graph, weights, routing.sample_nodes(weights, 24, seed=1))


def test_edge_heat_follows_the_raster():
    """Edges are sampled along their length, not at their midpoint."""
    graph = _lattice()
    values = np.array([d["heat"] for _, _, d in graph.edges(data=True)])
    assert values.max() > 55.0, "an edge lying in the hot avenue must read hot"
    assert values.min() < 36.0, "an edge a block away must read cool"


def test_cool_routing_trades_distance_for_shade():
    """The finding this guards: real shade is bought with a small, bounded detour."""
    score = _scored(_lattice())
    assert score.experienced_tmrt < score.shortest_tmrt
    assert score.detour_ratio >= 1.0, "a cool route cannot beat the shortest on length"
    assert score.shortest_tmrt - score.experienced_tmrt > 1.0


def test_zero_detour_aversion_is_a_null_control():
    """Without this, the objective could be measuring its own tie-breaking, not shade."""
    score = _scored(_lattice(beta=0.0))
    assert abs(score.detour_ratio - 1.0) < 1e-9
    assert abs(score.shortest_tmrt - score.experienced_tmrt) < 1e-9


def test_trip_heat_concentrates_on_a_forced_crossing():
    """Corridor targeting only beats spraying if trip heat is concentrated."""
    score = _scored(_lattice(cut_col=3))
    bridge = {(4 * NODES + 3, 4 * NODES + 4), (4 * NODES + 4, 4 * NODES + 3)}
    ranked = sorted(score.corridor, key=lambda e: -score.corridor[e])
    rank = min(ranked.index(edge) for edge in bridge if edge in score.corridor)
    values = np.array(sorted(score.corridor.values())[::-1])
    assert rank < 5, "the only crossing should rank among the busiest edges"
    assert values[: max(1, len(values) // 10)].sum() > 0.25


def test_corridor_weighting_discounts_heat_people_can_walk_around():
    """The whole case for routing over area: avoidable heat and trapped heat differ.

    An area average scores both the same. This objective discounts the avenue people
    detour around and amplifies the crossing they cannot, which is the difference
    between spending a budget where it shows and where it counts.
    """
    open_score = _scored(_lattice())
    open_graph = _lattice()
    avoidable = sum(v for e, v in open_score.corridor.items() if open_graph.edges[e]["heat"] > 45)
    hot_area = float((TMRT > 45).mean())

    cut_score = _scored(_lattice(cut_col=3))
    bridge = {(4 * NODES + 3, 4 * NODES + 4), (4 * NODES + 4, 4 * NODES + 3)}
    trapped = sum(v for e, v in cut_score.corridor.items() if e in bridge)
    bridge_share = 2.0 / len(cut_score.corridor)

    assert avoidable / hot_area < 0.8, "heat with a way round should be discounted"
    assert trapped / bridge_share > 3.0, "heat with no way round should be amplified"


def test_missing_coverage_does_not_become_a_cool_shortcut():
    """A hole in the raster must not read as shade, or plans will route into gaps."""
    graph = nx.MultiDiGraph()
    minx, miny, _, _ = AOI_TEST.bounds_utm
    graph.add_node(0, x=minx + 20, y=miny + 20)
    graph.add_node(1, x=minx + 40, y=miny + 20)
    graph.add_node(2, x=minx + 10_000, y=miny + 10_000)  # far outside the raster
    graph.add_edge(0, 1, length=20.0)
    graph.add_edge(1, 2, length=20.0)
    heat.annotate(graph, TMRT, AOI_TEST)
    routing.set_perceived(graph)
    assert np.isfinite(graph.edges[1, 2, 0]["heat"])
    assert graph.edges[1, 2, 0]["heat"] > 30.0, "an uncovered edge must not look comfortable"
