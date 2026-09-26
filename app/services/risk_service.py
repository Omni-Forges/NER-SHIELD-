"""
Stage 3 — AI Risk Engine (rule-based, for the prototype).

Combines rainfall, nearby incident reports, and each edge's static terrain
risk into a single 0-100 risk score per road edge. This is the weighted
formula that was designed earlier:

    risk = 0.35 * rainfall_factor
         + 0.25 * incident_factor
         + 0.20 * base_terrain_risk
         + 0.20 * report_recency_factor

A rule-based formula is used instead of a trained ML model because it
needs no training data, is fast to compute, and is easy to explain — all
useful properties for a hackathon prototype. Swapping in a scikit-learn/
XGBoost model later just means replacing `compute_edge_risk()` below;
nothing else in the pipeline needs to change.
"""

from datetime import datetime, timedelta
from app.db import get_pool

# Weights for the formula — tweak here without touching the rest of the code.
WEIGHT_RAINFALL = 0.35
WEIGHT_INCIDENTS = 0.25
WEIGHT_BASE_RISK = 0.20
WEIGHT_RECENCY = 0.20

NEARBY_RADIUS_KM = 25  # how far from an edge's midpoint we look for weather/incidents


async def recalculate_all_risk() -> list[dict]:
    """
    Recomputes current_risk for every edge in road_edges, based on nearby
    weather and incident data. Returns the list of updated edges.

    This is Stage 6 in miniature: "new data arrives -> risk recalculates".
    For the prototype this runs synchronously on request rather than via a
    background task queue (Celery/Redis) — simpler to run, same end result.
    """
    pool = get_pool()
    updated = []

    async with pool.acquire() as conn:
        edges = await conn.fetch(
            """
            SELECT e.id, e.from_node_id, e.to_node_id, e.base_risk, e.road_name,
                   ST_X(ST_Centroid(ST_MakeLine(n1.location, n2.location))) AS mid_lon,
                   ST_Y(ST_Centroid(ST_MakeLine(n1.location, n2.location))) AS mid_lat
            FROM road_edges e
            JOIN road_nodes n1 ON e.from_node_id = n1.id
            JOIN road_nodes n2 ON e.to_node_id = n2.id
            """
        )

        for edge in edges:
            risk = await compute_edge_risk(conn, edge)
            await conn.execute(
                "UPDATE road_edges SET current_risk = $1, last_updated = NOW() WHERE id = $2",
                risk, edge["id"],
            )
            updated.append({
                "edge_id": edge["id"],
                "road_name": edge["road_name"],
                "current_risk": round(risk, 1),
            })

    return updated


async def compute_edge_risk(conn, edge) -> float:
    """Computes a single edge's 0-100 risk score from nearby live data."""
    mid_lat, mid_lon = edge["mid_lat"], edge["mid_lon"]

    # --- rainfall factor: max nearby rainfall reading, scaled to 0-100 ---
    rainfall_row = await conn.fetchrow(
        """
        SELECT COALESCE(MAX(rainfall_mm), 0) AS max_rainfall
        FROM weather_data
        WHERE ST_DWithin(
            location::geography,
            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
            $3 * 1000
        )
        """,
        mid_lon, mid_lat, NEARBY_RADIUS_KM,
    )
    # 20mm+ rainfall is treated as "very high" for this prototype's scale
    rainfall_factor = min(100.0, (rainfall_row["max_rainfall"] / 20.0) * 100.0)

    # --- incident factor: how many incidents reported nearby ---
    incident_row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS incident_count,
               MAX(reported_at) AS latest_report
        FROM incident_reports
        WHERE ST_DWithin(
            location::geography,
            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
            $3 * 1000
        )
        """,
        mid_lon, mid_lat, NEARBY_RADIUS_KM,
    )
    # 3+ incidents nearby is treated as "very high" for this prototype's scale
    incident_factor = min(100.0, (incident_row["incident_count"] / 3.0) * 100.0)

    # --- recency factor: how recently was the last report near here ---
    recency_factor = 0.0
    if incident_row["latest_report"] is not None:
        age = datetime.utcnow() - incident_row["latest_report"].replace(tzinfo=None)
        if age < timedelta(hours=6):
            recency_factor = 100.0
        elif age < timedelta(hours=24):
            recency_factor = 60.0
        elif age < timedelta(days=3):
            recency_factor = 30.0
        else:
            recency_factor = 10.0

    base_risk = float(edge["base_risk"])

    risk = (
        WEIGHT_RAINFALL * rainfall_factor
        + WEIGHT_INCIDENTS * incident_factor
        + WEIGHT_BASE_RISK * base_risk
        + WEIGHT_RECENCY * recency_factor
    )
    return max(0.0, min(100.0, risk))


async def get_all_edge_risk() -> list[dict]:
    """Returns the current stored risk for every edge, with endpoint names."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.id, n1.name AS from_name, n2.name AS to_name,
                   e.road_name, e.distance_km, e.base_risk, e.current_risk, e.last_updated
            FROM road_edges e
            JOIN road_nodes n1 ON e.from_node_id = n1.id
            JOIN road_nodes n2 ON e.to_node_id = n2.id
            ORDER BY e.current_risk DESC
            """
        )
    return [dict(r) for r in rows]
