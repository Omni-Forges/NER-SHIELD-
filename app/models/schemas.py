"""
These classes define the exact shape of data going in and out of the API.
FastAPI uses them to automatically validate incoming requests (e.g. reject a
request missing a required field) and to auto-generate the interactive docs
at /docs.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class WeatherIngestRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the location to fetch weather for")
    lon: float = Field(..., description="Longitude of the location to fetch weather for")
    district: str = Field(..., description="District name, for grouping/filtering later")


class WeatherIngestResponse(BaseModel):
    status: str
    rainfall_mm: float
    district: str


class IncidentReportResponse(BaseModel):
    status: str
    incident_id: int
    incident_type: str
    reported_at: datetime


class GpsPingRequest(BaseModel):
    vehicle_id: str = Field(..., description="Vehicle or device identifier")
    lat: float = Field(..., description="Latitude of the ping")
    lon: float = Field(..., description="Longitude of the ping")
    speed: float | None = Field(None, description="Speed in km/h (optional)")
    recorded_at: datetime | None = Field(None, description="Timestamp of the ping; defaults to server time if omitted")


class GpsPingResponse(BaseModel):
    status: str
    ping_id: int
    vehicle_id: str
    recorded_at: datetime
