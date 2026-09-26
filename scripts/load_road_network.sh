#!/usr/bin/env bash
# Downloads Northeast India's road network from Geofabrik (free OSM mirror)
# and loads it into the local PostGIS database.
#
# Requires: osm2pgsql (install via `apt install osm2pgsql` or `brew install osm2pgsql`)
# Run once, before starting the app, to populate the `roads` table.

set -e

DATA_DIR="$(dirname "$0")/../data"
mkdir -p "$DATA_DIR"

DB_NAME="${DB_NAME:-sih26002}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"

echo "Downloading Northeast India OSM extract from Geofabrik..."
curl -L -o "$DATA_DIR/india-northeast-latest.osm.pbf" \
  "https://download.geofabrik.de/asia/india-northeast-latest.osm.pbf"

echo "Loading into PostGIS database '$DB_NAME'..."
osm2pgsql \
  --database "$DB_NAME" \
  --username "$DB_USER" \
  --host "$DB_HOST" \
  --slim \
  --cache 2000 \
  "$DATA_DIR/india-northeast-latest.osm.pbf"

echo "Done. Road network loaded into PostGIS."
echo "Note: osm2pgsql creates its own default tables (planet_osm_line, etc.)."
echo "You may want to write a follow-up INSERT ... SELECT to populate the"
echo "simplified 'roads' table from schema.sql, filtered to road-type ways only."
