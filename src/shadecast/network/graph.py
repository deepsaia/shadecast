"""The walkable street network a plan is ultimately judged on.

Area-averaged cooling is not what a pedestrian buys. People meet heat along the paths
they actually walk, so a plan that cools a courtyard nobody crosses scores well on an
area objective and helps no one. This module pulls the pedestrian network from
OpenStreetMap and projects it onto the same grid as every raster in the bundle, so
route geometry and Tmrt pixels are directly comparable without a reprojection step.

Overpass needs no credential, which keeps the build-time-only credential rule intact.
The graph is cached as GraphML per AOI, because Overpass is a shared free service and
re-querying it on every experiment would be rude as well as slow.
"""

from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx
import osmnx as ox

from ..aoi import AOI

logger = logging.getLogger(__name__)

# Ways a person on foot may use. Excludes motorways, which OSM's "walk" filter
# already drops, and keeps service roads, which in much of the world carry most
# of the actual walking.
NETWORK_TYPE = "walk"


def cache_path(aoi: AOI, cache_dir: Path) -> Path:
    return Path(cache_dir) / f"walk_{aoi.name}_{aoi.side_m}m.graphml"


def fetch(aoi: AOI, cache_dir: Path, *, refresh: bool = False) -> nx.MultiDiGraph:
    """Return the walkable network for this AOI, projected to the AOI's UTM CRS.

    Nodes carry x and y in projected metres, so they can be indexed straight into
    the raster grid with the AOI transform.
    """
    path = cache_path(aoi, cache_dir)
    if path.exists() and not refresh:
        logger.info("loading cached walk network from %s", path)
        return ox.io.load_graphml(path)

    west, south, east, north = aoi.bounds_wgs84
    logger.info("querying Overpass for the walk network in %s", aoi.name)
    graph = ox.graph.graph_from_bbox((west, south, east, north), network_type=NETWORK_TYPE)
    graph = ox.projection.project_graph(graph, to_crs=aoi.crs)
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.io.save_graphml(graph, path)
    logger.info(
        "walk network: %d nodes, %d edges", graph.number_of_nodes(), graph.number_of_edges()
    )
    return graph


def largest_component(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Drop islands the rest of the network cannot reach.

    A bbox cut leaves stubs that connect to nothing inside the AOI. Routing over them
    produces unreachable pairs that would otherwise be silently dropped from the mean.
    """
    if graph.number_of_nodes() == 0:
        return graph
    nodes = max(nx.weakly_connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()
