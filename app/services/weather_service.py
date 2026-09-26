"""
Stage 1 — Data Collection: weather.

Calls Open-Meteo (free, no API key needed) for a given location, pulls the
current rainfall reading and next-hour forecast, and writes it into the
weather_data table.
"""

import httpx
from app.config import settings
from app.db import get_pool
from app.validators import validate_coordinates


async def fetch_weather(lat: float, lon: float) -> dict:
    """Calls the Open-Meteo API and returns the raw JSON response."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.weather_api_base_url, params=params)
        response.raise_for_status()
        return response.json()


async def ingest_weather(lat: float, lon: float, district: str) -> dict:
    """
    Fetches weather for a location and stores it in the database.
    Returns the stored rainfall value so the caller/API response can show it.
    """
    validate_coordinates(lat, lon)

    data = await fetch_weather(lat, lon)
    hourly_precip = data.get("hourly", {}).get("precipitation", [])
    current_rainfall = hourly_precip[0] if hourly_precip else 0.0
    forecast_rainfall = hourly_precip[1] if len(hourly_precip) > 1 else 0.0

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO weather_data (location, rainfall_mm, forecast_rainfall_mm, district)
            VALUES (ST_SetSRID(ST_MakePoint($1, $2), 4326), $3, $4, $5)
            """,
            lon, lat, current_rainfall, forecast_rainfall, district,
        )

    return {"rainfall_mm": current_rainfall, "district": district}
