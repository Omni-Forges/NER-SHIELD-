"""
Stage 1 — Data Collection: field incident reports.

Takes a field officer's report (pothole, landslide, blocked road, etc.),
validates the location falls inside the service region, and saves it.
"""

from datetime import datetime
from app.db import get_pool
from app.validators import validate_coordinates


async def create_incident_report(
    incident_type: str,
    lat: float,
    lon: float,
    description: str,
    reporter_id: str | None = None,
    photo_url: str | None = None,
) -> dict:
    validate_coordinates(lat, lon)

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO incident_reports
                (reporter_id, incident_type, location, description, photo_url)
            VALUES
                ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, $6)
            RETURNING id, reported_at
            """,
            reporter_id, incident_type, lon, lat, description, photo_url,
        )

    return {
        "incident_id": row["id"],
        "incident_type": incident_type,
        "reported_at": row["reported_at"],
    }


async def find_nearest_road(lat: float, lon: float) -> dict | None:
    """
    Stage 2 — Processing: links an incident's location to the nearest known
    road segment, using PostGIS's <-> nearest-neighbour operator (fast, uses
    the spatial index instead of scanning every row).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name,
                   ST_Distance(
                       geom::geography,
                       ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                   ) AS distance_m
            FROM roads
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint($1, $2), 4326)
            LIMIT 1
            """,
            lon, lat,
        )

    if row is None:
        return None
    return {"road_id": row["id"], "road_name": row["name"], "distance_m": row["distance_m"]}
