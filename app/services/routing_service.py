"""
Stage 4 — Route Optimization.

Builds a graph from road_nodes + road_edges (the seeded NER town network)
and finds routes using networkx's shortest-path algorithm — this plays the
same role OSRM would play with full OSM data, just over a much smaller,
hand-seeded graph. Good enough to demonstrate risk-aware routing end to
end; swapping in real OSRM later means replacing this file, not the API
or the frontend that calls it.

Edge weight = distance_km * (1 + current_risk / 100 * RISK_PENALTY)
So a high-risk edge costs more to traverse, and the "safest" route and
the "fastest" route can genuinely differ.
"""

import networkx as nx
from app.db import get_pool

RISK_PENALTY = 3.0  # how strongly risk discourages a route; tune to taste


async def _load_graph(conn) -> nx.DiGraph:
    graph = nx.DiGraph()

    nodes = await conn.fetch(
        "SELECT id, name, ST_Y(location) AS lat, ST_X(location) AS lon FROM road_nodes"
    )
    for n in nodes:
        graph.add_node(n["id"], name=n["name"], lat=n["lat"], lon=n["lon"])

    edges = await conn.fetch(
        "SELECT from_node_id, to_node_id, road_name, distance_km, current_risk FROM road_edges"
    )
    for e in edges:
        weight = e["distance_km"] * (1 + (e["current_risk"] / 100.0) * RISK_PENALTY)
        graph.add_edge(
            e["from_node_id"], e["to_node_id"],
            weight=weight,
            distance_km=e["distance_km"],
            risk=e["current_risk"],
            road_name=e["road_name"],
        )
    return graph


async def find_route(from_name: str, to_name: str) -> dict:
    """
    Finds the risk-weighted shortest path between two named towns/nodes.
    Returns the path, total distance, and an average risk for the route.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        graph = await _load_graph(conn)

        from_id = _find_node_id_by_name(graph, from_name)
        to_id = _find_node_id_by_name(graph, to_name)

        if from_id is None:
            raise ValueError(f"Unknown location: '{from_name}'")
        if to_id is None:
            raise ValueError(f"Unknown location: '{to_name}'")

        try:
            path_node_ids = nx.shortest_path(graph, from_id, to_id, weight="weight")
        except nx.NetworkXNoPath:
            raise ValueError(f"No route found between '{from_name}' and '{to_name}'")

        segments = []
        total_distance = 0.0
        risk_weighted_sum = 0.0
        for a, b in zip(path_node_ids[:-1], path_node_ids[1:]):
            edge = graph.edges[a, b]
            segments.append({
                "from": graph.nodes[a]["name"],
                "to": graph.nodes[b]["name"],
                "road_name": edge["road_name"],
                "distance_km": edge["distance_km"],
                "risk": round(edge["risk"], 1),
            })
            total_distance += edge["distance_km"]
            risk_weighted_sum += edge["risk"] * edge["distance_km"]

        avg_risk = risk_weighted_sum / total_distance if total_distance > 0 else 0.0

        return {
            "from": from_name,
            "to": to_name,
            "path": [graph.nodes[n]["name"] for n in path_node_ids],
            "segments": segments,
            "total_distance_km": round(total_distance, 1),
            "average_risk": round(avg_risk, 1),
        }


def _find_node_id_by_name(graph: nx.DiGraph, name: str) -> int | None:
    name_lower = name.strip().lower()
    for node_id, data in graph.nodes(data=True):
        if data["name"].lower() == name_lower:
            return node_id
    return None


async def list_node_names() -> list[str]:
    """Returns all known town/node names — useful for populating a dropdown in the UI."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM road_nodes ORDER BY name")
    return [r["name"] for r in rows]

async def list_node_coordinates() -> list[dict]:
    """Returns name + lat/lon for every node — lets the frontend draw the network on the map."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, ST_Y(location) AS lat, ST_X(location) AS lon "
            "FROM road_nodes ORDER BY name"
        )
    return [{"name": r["name"], "lat": r["lat"], "lon": r["lon"]} for r in rows]
