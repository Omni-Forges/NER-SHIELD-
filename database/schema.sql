-- SIH26002 — Database schema
-- Run with: psql "$DATABASE_URL" -f database/schema.sql

-- Enable PostGIS extension (adds spatial data types & functions to PostgreSQL)
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- Road network — populated by scripts/load_road_network.sh
-- ============================================================
CREATE TABLE IF NOT EXISTS roads (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT,
    name TEXT,
    road_type TEXT,
    geom GEOMETRY(LineString, 4326),
    district TEXT
);

-- ============================================================
-- Weather readings — populated by app/services/weather_service.py
-- ============================================================
CREATE TABLE IF NOT EXISTS weather_data (
    id SERIAL PRIMARY KEY,
    location GEOMETRY(Point, 4326) NOT NULL,
    rainfall_mm FLOAT,
    forecast_rainfall_mm FLOAT,
    recorded_at TIMESTAMP DEFAULT NOW(),
    district TEXT
);

-- ============================================================
-- Field incident reports — populated by app/services/incident_service.py
-- ============================================================
CREATE TABLE IF NOT EXISTS incident_reports (
    id SERIAL PRIMARY KEY,
    reporter_id TEXT,
    incident_type TEXT NOT NULL,   -- landslide / flood / road_damage / congestion
    location GEOMETRY(Point, 4326) NOT NULL,
    photo_url TEXT,
    description TEXT,
    reported_at TIMESTAMP DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    road_id INTEGER REFERENCES roads(id)
);

-- ============================================================
-- GPS pings from vehicles — for the future route-tracking stage
-- ============================================================
CREATE TABLE IF NOT EXISTS gps_pings (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    speed FLOAT,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- Route graph — nodes (towns/junctions) and edges (road links)
-- Used by the routing engine (app/services/routing_service.py).
--
-- Why a simple graph instead of full OSM road geometry: loading and
-- routing over the complete OSM network needs osm2pgsql + OSRM, which
-- is heavy to set up for a fast prototype. This graph covers real NER
-- towns and real highway connections, with distances and risk scores,
-- which is enough to demonstrate risk-aware routing end-to-end.
-- ============================================================
CREATE TABLE IF NOT EXISTS road_nodes (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    district TEXT
);

CREATE TABLE IF NOT EXISTS road_edges (
    id SERIAL PRIMARY KEY,
    from_node_id INTEGER NOT NULL REFERENCES road_nodes(id),
    to_node_id INTEGER NOT NULL REFERENCES road_nodes(id),
    road_name TEXT,
    distance_km FLOAT NOT NULL,
    base_risk FLOAT NOT NULL DEFAULT 10,   -- static terrain risk (0-100), set at seed time
    current_risk FLOAT NOT NULL DEFAULT 10, -- live risk, updated by the risk engine
    last_updated TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- Spatial indexes — makes "find nearby X" queries fast
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_roads_geom ON roads USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_data USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_incidents_location ON incident_reports USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_gps_location ON gps_pings USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_road_nodes_location ON road_nodes USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_road_edges_from ON road_edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_road_edges_to ON road_edges(to_node_id);
