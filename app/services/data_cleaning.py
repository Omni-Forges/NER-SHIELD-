"""
Stage 2 — Processing & GIS Layer: data cleaning.

Before a batch of incoming reports (e.g. pulled from the database for the
future risk engine) is used, this removes duplicate submissions and drops
rows missing the fields the rest of the pipeline depends on.
"""

import geopandas as gpd
import pandas as pd


def clean_field_reports(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Expects a DataFrame with at least these columns:
    reporter_id, incident_type, lat, lon, reported_at

    Returns a cleaned GeoDataFrame with a proper `geometry` column, ready
    for spatial joins or analysis.
    """
    before = len(df)

    df = df.drop_duplicates(subset=["reporter_id", "lat", "lon", "reported_at"])
    df = df.dropna(subset=["incident_type", "lat", "lon"])

    after = len(df)
    if before != after:
        print(f"[data_cleaning] Dropped {before - after} duplicate/incomplete rows "
              f"({before} -> {after})")

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    return gdf
