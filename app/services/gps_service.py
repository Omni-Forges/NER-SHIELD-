"""
Stage 1 — Data Collection: GPS pings from vehicles.

Accepts live GPS pings from vehicles/devices, validates the coordinates
fall inside the NER service region, and stores them for route tracking
and speed analytics.
"""

from datetime import datetime
from app.db import get_pool
from app.validators import validate_coordinates


async def record_ping(
    vehicle_id: str,
    lat: float,
    lon: float,
    speed: float | None = None,
    recorded_at: datetime | None = None,
) -> dict:
    """Validates and stores a single GPS ping."""
    validate_coordinates(lat, lon)

    pool = get_pool()
    async with pool.acquire() as conn:
        if recorded_at is not None:
            row = await conn.fetchrow(
                """
                INSERT INTO gps_pings (vehicle_id, location, speed, recorded_at)
                VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5)
                RETURNING id, recorded_at
                """,
                vehicle_id, lon, lat, speed, recorded_at,
            )
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO gps_pings (vehicle_id, location, speed)
                VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4)
                RETURNING id, recorded_at
                """,
                vehicle_id, lon, lat, speed,
            )

    return {
        "ping_id": row["id"],
        "vehicle_id": vehicle_id,
        "recorded_at": row["recorded_at"],
    }


async def get_recent_pings(vehicle_id: str, limit: int = 50) -> list[dict]:
    """Returns the most recent pings for a vehicle, newest first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id,
                   ST_Y(location) AS lat,
                   ST_X(location) AS lon,
                   speed,
                   recorded_at
            FROM gps_pings
            WHERE vehicle_id = $1
            ORDER BY recorded_at DESC
            LIMIT $2
            """,
            vehicle_id, limit,
        )

    return [
        {
            "ping_id": r["id"],
            "vehicle_id": vehicle_id,
            "lat": r["lat"],
            "lon": r["lon"],
            "speed": r["speed"],
            "recorded_at": r["recorded_at"],
        }
        for r in rows
    ]
