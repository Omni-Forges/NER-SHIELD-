"""
Seeds the database with a small but real road graph covering major NER
towns, plus a couple of sample weather/incident rows — so the prototype
has something to route through and show risk on immediately, without
needing the full OSM download + osm2pgsql pipeline.

Run with:
    python -m scripts.seed_demo_data
"""

import asyncio
import asyncpg
from app.config import settings

# Real NER towns/junctions with approximate coordinates (lat, lon)
NODES = [
    ("Guwahati", 26.1445, 91.7362, "Kamrup"),
    ("Nagaon", 26.3480, 92.6840, "Nagaon"),
    ("Jorhat", 26.7509, 94.2037, "Jorhat"),
    ("Dibrugarh", 27.4728, 94.9120, "Dibrugarh"),
    ("Diphu", 25.8430, 93.4390, "Karbi Anglong"),
    ("Dimapur", 25.9091, 93.7267, "Dimapur"),
    ("Kohima", 25.6751, 94.1086, "Kohima"),
    ("Imphal", 24.8170, 93.9368, "Imphal West"),
    ("Silchar", 24.8333, 92.7789, "Cachar"),
    ("Shillong", 25.5788, 91.8933, "East Khasi Hills"),
    ("Aizawl", 23.7271, 92.7176, "Aizawl"),
    ("Agartala", 23.8315, 91.2868, "West Tripura"),
]

# Edges: (from, to, road_name, distance_km, base_risk)
# base_risk is a rough static terrain-difficulty estimate (0-100) —
# hillier / more landslide-prone stretches start higher.
EDGES = [
    ("Guwahati", "Shillong", "NH-6", 100, 25),
    ("Guwahati", "Nagaon", "NH-27", 115, 15),
    ("Nagaon", "Diphu", "NH-36", 130, 35),
    ("Nagaon", "Jorhat", "NH-27", 140, 15),
    ("Jorhat", "Dibrugarh", "NH-37", 135, 15),
    ("Diphu", "Dimapur", "NH-39", 90, 40),
    ("Dimapur", "Kohima", "NH-29", 75, 45),
    ("Kohima", "Imphal", "NH-2", 145, 50),
    ("Guwahati", "Silchar", "NH-27/NH-6", 320, 30),
    ("Silchar", "Aizawl", "NH-306", 180, 55),
    ("Silchar", "Imphal", "NH-37", 260, 50),
    ("Shillong", "Silchar", "NH-6", 220, 40),
    ("Agartala", "Silchar", "NH-8", 190, 35),
    ("Agartala", "Aizawl", "NH-8", 250, 45),
]

SAMPLE_WEATHER = [
    # (lat, lon, rainfall_mm, forecast_mm, district)
    (25.9091, 93.7267, 12.5, 18.0, "Dimapur"),   # heavy rain near Dimapur
    (25.6751, 94.1086, 22.0, 30.0, "Kohima"),    # heavier rain near Kohima
]

SAMPLE_INCIDENTS = [
    # (incident_type, lat, lon, description)
    ("landslide", 25.78, 93.92, "Landslide reported on NH-39 near Diphu-Dimapur stretch"),
]


async def seed():
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        node_ids = {}
        print("Seeding road_nodes...")
        for name, lat, lon, district in NODES:
            row = await conn.fetchrow(
                """
                INSERT INTO road_nodes (name, location, district)
                VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4)
                RETURNING id
                """,
                name, lon, lat, district,
            )
            node_ids[name] = row["id"]
            print(f"  {name} -> id {row['id']}")

        print("Seeding road_edges...")
        for from_name, to_name, road_name, distance_km, base_risk in EDGES:
            from_id = node_ids[from_name]
            to_id = node_ids[to_name]
            # store both directions so routing works either way
            await conn.execute(
                """
                INSERT INTO road_edges (from_node_id, to_node_id, road_name, distance_km, base_risk, current_risk)
                VALUES ($1, $2, $3, $4, $5, $5), ($2, $1, $3, $4, $5, $5)
                """,
                from_id, to_id, road_name, distance_km, base_risk,
            )
            print(f"  {from_name} <-> {to_name} ({road_name}, {distance_km} km, base risk {base_risk})")

        print("Seeding sample weather...")
        for lat, lon, rainfall, forecast, district in SAMPLE_WEATHER:
            await conn.execute(
                """
                INSERT INTO weather_data (location, rainfall_mm, forecast_rainfall_mm, district)
                VALUES (ST_SetSRID(ST_MakePoint($1, $2), 4326), $3, $4, $5)
                """,
                lon, lat, rainfall, forecast, district,
            )
            print(f"  weather at ({lat}, {lon}) -> {rainfall}mm")

        print("Seeding sample incidents...")
        for incident_type, lat, lon, description in SAMPLE_INCIDENTS:
            await conn.execute(
                """
                INSERT INTO incident_reports (incident_type, location, description)
                VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4)
                """,
                incident_type, lon, lat, description,
            )
            print(f"  incident: {incident_type} at ({lat}, {lon})")

    await pool.close()
    print("\nSeed complete. You can now call POST /risk/recalculate and POST /route.")


if __name__ == "__main__":
    asyncio.run(seed())
