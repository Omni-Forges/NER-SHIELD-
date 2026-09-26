# SIH26002 — Smart Logistics & Accessibility Intelligence Platform (NER)

Team OMNI · Smart India Hackathon 2026
**Working prototype** — covers Stages 1, 2, 3, 4 and a simplified Stage 6, with a
single-page dashboard (Stage 5) to demo all of it. Built to be *working*, not
polished — see "What's simplified" at the bottom for exactly what's real vs
scoped-down for time.

## What's in this folder

```
sih26002_project/
├── README.md
├── requirements.txt
├── .env.example
├── docker-compose.yml
│
├── database/
│   └── schema.sql              ← all tables: roads, weather, incidents, GPS,
│                                   + road_nodes/road_edges (the routing graph)
│
├── scripts/
│   ├── load_road_network.sh    ← optional: real OSM road geometry (not required for the demo)
│   └── seed_demo_data.py       ← REQUIRED: seeds the routing graph + sample data
│
├── frontend/
│   └── index.html              ← the dashboard — map, risk list, route finder,
│                                   incident form, weather form. No build step.
│
└── app/
    ├── main.py                 ← FastAPI app — every endpoint, and serves the dashboard
    ├── config.py / db.py / validators.py
    ├── models/schemas.py
    └── services/
        ├── weather_service.py      (Stage 1)
        ├── incident_service.py     (Stage 1 + 2)
        ├── data_cleaning.py        (Stage 2)
        ├── risk_service.py         (Stage 3 — NEW)
        └── routing_service.py      (Stage 4 — NEW)
```

## How to run it (same as before, plus one new step)

1. **Start the database:**
   ```bash
   docker compose up -d
   ```

2. **Env file:**
   ```bash
   cp .env.example .env
   ```

3. **Install dependencies** (adds `networkx` for routing):
   ```bash
   pip install -r requirements.txt
   ```

4. **Create tables:**
   ```bash
   docker cp database/schema.sql sih26002_postgis:/schema.sql
   docker exec -it sih26002_postgis psql -U postgres -d sih26002 -f /schema.sql
   ```

5. **NEW — seed the demo road graph.** This is what makes the map, risk list,
   and route finder actually have something to show, without needing the full
   OSM/osm2pgsql pipeline:
   ```bash
   python -m scripts.seed_demo_data
   ```
   This inserts 12 real NER towns (Guwahati, Dimapur, Kohima, Imphal, Silchar,
   etc.) connected by real highway links, plus one sample rainfall reading and
   one sample landslide report — so the dashboard isn't empty on first load.

6. **Run the app:**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Open the dashboard:**
   ```
   http://localhost:8000/
   ```
   (API docs still available at `http://localhost:8000/docs`)

## What you'll see on the dashboard

- A map of the NER region
- A live risk list — every road link between towns, color-coded by current risk
- A route finder — pick two towns, get the risk-weighted route (not just the
  shortest one)
- An incident report form — submit a landslide/flood/etc report, and watch
  the risk list update automatically
- A weather-fetch form — pull real Open-Meteo data for a location, and watch
  the risk list update automatically

The incident and weather forms both **automatically re-trigger the risk
engine** after saving — that's Stage 6 (the update loop) working in a
simplified, synchronous form.

## What each new piece does

**`database/schema.sql` (updated)** — added two tables: `road_nodes` (towns/
junctions with coordinates) and `road_edges` (the links between them, each
with a `base_risk` and a live `current_risk`).

**`scripts/seed_demo_data.py`** — inserts a real, hand-built graph of NER
towns and highway connections. This stands in for a full OSM road network,
which needs `osm2pgsql` and a much bigger download — not practical to set up
reliably in two days. The towns and distances are real; the graph is just
simplified to town-to-town links instead of every individual road segment.

**`app/services/risk_service.py` (Stage 3)** — implements the weighted risk
formula designed earlier:
```
risk = 0.35 x rainfall_factor + 0.25 x incident_factor + 0.20 x base_terrain_risk + 0.20 x recency_factor
```
For each road edge, it looks at weather and incident reports within 25km of
that edge's midpoint, and recomputes a 0-100 risk score. Rule-based, not a
trained ML model — this was a deliberate choice: it needs no training data,
runs instantly, and is easy to explain to judges. Swapping in scikit-learn/
XGBoost later only means changing `compute_edge_risk()`; nothing else in the
pipeline changes.

**`app/services/routing_service.py` (Stage 4)** — uses `networkx` (a
lightweight, pure-Python graph library) to find the risk-weighted shortest
path between two towns. This plays OSRM's role over the seeded graph. Edge
cost = `distance_km x (1 + current_risk/100 x penalty)`, so a high-risk edge
genuinely gets avoided when a lower-risk alternative exists.

**`frontend/index.html` (Stage 5)** — a single static HTML file using
Leaflet.js (loaded from a CDN, no npm/build step). Served directly by FastAPI
via `StaticFiles`, so `uvicorn app.main:app --reload` is the only command
needed to run the whole thing, backend and frontend together.

## What's simplified (be upfront about this with judges)

This is a **working prototype**, not the full production design from the
architecture doc. Here's exactly what's scoped down and why:

| Full design | What's actually built | Why |
|---|---|---|
| Full OSM road network + OSRM routing | A hand-seeded graph of 12 real NER towns + `networkx` routing | OSRM setup (osm2pgsql, Lua profiles, full India-NE download) isn't reliable to finish in 2 days |
| React/Next.js web app + Flutter mobile app | One static HTML dashboard, works on both desktop and mobile browsers | No build tooling needed, runs instantly, still demoes every stage |
| Celery + Redis background task queue | Risk recalculation runs synchronously in the request | Same end result for a demo-sized dataset (14 edges); no extra services to install |
| Offline-first mobile sync (SQLite) | Not implemented | Needs a real mobile app shell first; call this out as "designed, not built yet" if asked |
| scikit-learn/XGBoost risk model | Rule-based weighted formula | No training data available yet; formula is transparent and defensible in a demo |

**How to talk about this if asked:** "We built the real pipeline end-to-end —
data in, risk computed, routes adjust live — over a representative subset of
the network so we could prove the architecture works, rather than spending
the two days on infrastructure setup (OSRM, Celery) that wouldn't have
changed what we could show."

## Quick end-to-end test (to confirm everything works)

1. Open `http://localhost:8000/` — you should see the risk list already
   populated (from the seed data) and the map loaded.
2. Pick "Nagaon" -> "Dimapur" in the route finder, click Find route.
3. Submit an incident report near Diphu-Dimapur (default form values are
   already set for this) — risk list updates automatically.
4. Re-run the same route — the risk on that stretch should now be higher,
   and if the seeded graph has a lower-risk alternative, the route may change.
