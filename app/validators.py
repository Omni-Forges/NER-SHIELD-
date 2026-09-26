"""
Stage 2 — Processing & GIS Layer: geotag validation.

Before any location-tagged data (a field report, a GPS ping, a weather
reading) gets stored, we check it actually falls inside the Northeast India
region this platform covers. This catches obvious bad data early — a GPS
glitch, a typo'd coordinate, a test submission from the wrong place — before
it pollutes the spatial database.
"""

from app.config import settings


def is_within_ner(lat: float, lon: float) -> bool:
    """Returns True if the given coordinate falls inside the NER bounding box."""
    return (
        settings.ner_min_lat <= lat <= settings.ner_max_lat
        and settings.ner_min_lon <= lon <= settings.ner_max_lon
    )


def validate_coordinates(lat: float, lon: float) -> None:
    """Raises a ValueError with a clear message if the coordinate is invalid."""
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude {lat} is not a valid latitude.")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude {lon} is not a valid longitude.")
    if not is_within_ner(lat, lon):
        raise ValueError(
            f"Coordinate ({lat}, {lon}) falls outside the Northeast India "
            f"service region and was rejected."
        )
