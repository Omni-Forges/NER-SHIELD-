"""
SIH26002 — main FastAPI application.

Run with:
    uvicorn app.main:app --reload

Then open http://localhost:8000/docs for the interactive API tester,
or http://localhost:8000/ for the dashboard.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import uuid

from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import connect_db, disconnect_db
from app.models.schemas import (
    WeatherIngestRequest, WeatherIngestResponse,
    IncidentReportResponse, GpsPingRequest, GpsPingResponse,
)
from app.services import weather_service, incident_service, risk_service, routing_service
from app.services import gps_service

_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the app starts
    _UPLOADS_DIR.mkdir(exist_ok=True)
    await connect_db()
    yield
    # Runs once when the app shuts down
    await disconnect_db()


app = FastAPI(
    title="SIH26002 — Smart Logistics & Accessibility Intelligence Platform",
    description="Working prototype: Data Collection, Processing, Risk Engine, Route Optimization",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/ingest/weather", response_model=WeatherIngestResponse)
async def ingest_weather(payload: WeatherIngestRequest):
    """
    Stage 1: pulls current weather for a location from Open-Meteo and stores it.
    Also re-triggers the risk engine (Stage 6 in miniature) so road risk
    reflects the new weather immediately.
    """
    try:
        result = await weather_service.ingest_weather(
            lat=payload.lat, lon=payload.lon, district=payload.district
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await risk_service.recalculate_all_risk()

    return WeatherIngestResponse(status="stored", **result)


@app.post("/incident-report", response_model=IncidentReportResponse)
async def submit_incident_report(
    incident_type: str = Form(..., description="e.g. landslide, flood, road_damage, congestion"),
    lat: float = Form(...),
    lon: float = Form(...),
    description: str = Form(...),
    reporter_id: str | None = Form(None),
    photo: Any = File(None),
):
    """
    Stage 1: a field officer submits an incident report from the mobile app.
    Also re-triggers the risk engine (Stage 6) so affected roads update
    immediately, same as the weather endpoint above.

    Photo upload handling is stubbed here — wire up actual file storage
    (S3, local disk, etc.) before going to production.

    `photo` is typed as `Any` instead of `UploadFile | None` on purpose:
    Swagger UI sometimes sends an empty string ("") for an untouched file
    field instead of omitting it, and FastAPI would reject that against a
    strict UploadFile type. Typing it as Any skips that validation, and we
    check the real type ourselves below.
    """
    photo_url = None
    if isinstance(photo, UploadFile) and photo.filename:
        # Save with a collision-resistant filename (UUID + original extension).
        ext = Path(photo.filename).suffix.lower() or ".bin"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = _UPLOADS_DIR / safe_name
        contents = await photo.read()
        dest.write_bytes(contents)
        photo_url = f"/uploads/{safe_name}"

    try:
        result = await incident_service.create_incident_report(
            incident_type=incident_type,
            lat=lat,
            lon=lon,
            description=description,
            reporter_id=reporter_id,
            photo_url=photo_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await risk_service.recalculate_all_risk()

    return IncidentReportResponse(status="received", **result)


@app.get("/incidents")
async def list_incidents(limit: int = 30):
    """
    Recent incident reports, newest first — used by the app's Incident
    Details and Alerts & Notifications screens.
    """
    return await incident_service.list_incidents(limit=limit)


@app.get("/incident-report/{incident_id}/nearest-road")
async def get_nearest_road(incident_id: int, lat: float, lon: float):
    """
    Stage 2: given a location, finds the nearest known road segment.
    (Takes lat/lon directly for now — swap for a DB lookup by incident_id
    once you want this wired end-to-end.)
    """
    road = await incident_service.find_nearest_road(lat=lat, lon=lon)
    if road is None:
        raise HTTPException(status_code=404, detail="No road data loaded yet. Run scripts/load_road_network.sh first.")
    return road


# ============================================================
# Stage 3 — AI Risk Engine
# ============================================================

@app.post("/risk/recalculate")
async def recalculate_risk():
    """
    Stage 3: recomputes the risk score for every road edge, based on
    current weather and incident data. Normally triggered automatically
    by the weather/incident endpoints above — exposed here too so it can
    be re-run manually (e.g. from the dashboard's "Refresh" button).
    """
    updated = await risk_service.recalculate_all_risk()
    return {"status": "recalculated", "edges_updated": len(updated), "edges": updated}


@app.get("/risk/edges")
async def get_edge_risk():
    """Stage 3: returns the current risk score for every road edge."""
    return await risk_service.get_all_edge_risk()


# ============================================================
# Stage 4 — Route Optimization
# ============================================================

@app.get("/nodes")
async def get_nodes():
    """Returns known town/node names — for populating a route-search dropdown."""
    return await routing_service.list_node_names()

@app.get("/nodes/coordinates")
async def get_node_coordinates():
    """Returns name + lat/lon for every node — lets the frontend draw the network on the map."""
    return await routing_service.list_node_coordinates()


@app.get("/route")
async def get_route(from_: str, to: str):
    """
    Stage 4: finds the risk-weighted route between two towns.
    Example: GET /route?from_=Dimapur&to=Kohima
    """
    try:
        return await routing_service.find_route(from_, to)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ============================================================
# GPS Pings — vehicle/device tracking
# ============================================================

@app.post("/gps-ping", response_model=GpsPingResponse)
async def submit_gps_ping(payload: GpsPingRequest):
    """
    Accepts a GPS ping from a vehicle or device.
    Validates coordinates fall inside the NER bounding box, stores to
    gps_pings table. Timestamp defaults to server time if not supplied.
    """
    try:
        result = await gps_service.record_ping(
            vehicle_id=payload.vehicle_id,
            lat=payload.lat,
            lon=payload.lon,
            speed=payload.speed,
            recorded_at=payload.recorded_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return GpsPingResponse(status="recorded", **result)


@app.get("/gps-pings/{vehicle_id}")
async def get_gps_pings(vehicle_id: str, limit: int = 50):
    """
    Returns recent GPS pings for a vehicle, most recent first.
    Default limit is 50; pass ?limit=N to adjust.
    """
    pings = await gps_service.get_recent_pings(vehicle_id, limit=min(limit, 500))
    return {"vehicle_id": vehicle_id, "count": len(pings), "pings": pings}


# ============================================================
# Stage 5 — Dashboard (static single-page frontend)
# ============================================================

# Serve uploaded incident photos at /uploads/...
if _UPLOADS_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(_UPLOADS_DIR)), name="uploads")

_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")