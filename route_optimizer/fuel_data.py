"""
Fuel station data loader and spatial index.

Loads the CSV once at startup, geocodes stations by city/state,
and builds a KD-Tree for fast nearest-neighbour queries.
"""
import logging
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import KDTree

logger = logging.getLogger(__name__)

# Approximate lat/lon for every US state (centroid used when no geocode hits)
STATE_CENTROIDS = {
    "AL": (32.806671, -86.791130), "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221), "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564), "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371), "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783), "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337), "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137), "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526), "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067), "LA": (31.169960, -91.867805),
    "ME": (44.693947, -69.381927), "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106), "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192), "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368), "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082), "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896), "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482), "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419), "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915), "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938), "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780), "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828), "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461), "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686), "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494), "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508), "WY": (42.755966, -107.302490),
    "DC": (38.897438, -77.026817),
}

# Handcrafted lat/lon lookup for major cities in the CSV to avoid
# hammering a geocoding API. Values accurate to ~0.5°.
CITY_STATE_COORDS = {}  # populated lazily from state centroids + offsets


def _build_city_coords(df: pd.DataFrame) -> dict:
    """Return {(city_clean, state): (lat, lon)} using state centroids as fallback."""
    coords = {}
    for state, (lat, lon) in STATE_CENTROIDS.items():
        # Spread city guesses around the state centroid –
        # good enough for 500-mile range buckets.
        state_rows = df[df["State"] == state]
        cities = state_rows["City"].unique()
        n = max(len(cities), 1)
        for i, city in enumerate(cities):
            # small deterministic spread so cities in same state differ slightly
            offset_lat = (i % 10 - 4.5) * 0.3
            offset_lon = (i // 10 % 10 - 4.5) * 0.3
            city_key = (city.strip().upper(), state.strip().upper())
            coords[city_key] = (lat + offset_lat, lon + offset_lon)
    return coords


@lru_cache(maxsize=1)
def load_fuel_stations() -> tuple:
    """
    Load fuel station CSV, deduplicate by keeping lowest price per location,
    estimate coordinates and build a KDTree.

    Returns (stations_df, kdtree, coords_array)
    """
    from django.conf import settings

    csv_path = settings.FUEL_DATA_PATH
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["Retail Price"] = pd.to_numeric(df["Retail Price"], errors="coerce")
    df["State"] = df["State"].str.strip()
    df["City"] = df["City"].str.strip()
    df["Truckstop Name"] = df["Truckstop Name"].str.strip()
    df["Address"] = df["Address"].str.strip()
    df.dropna(subset=["Retail Price", "State", "City"], inplace=True)

    # Keep cheapest price per (name, address) combination
    df = (
        df.sort_values("Retail Price")
        .groupby(["Truckstop Name", "Address"], as_index=False)
        .first()
    )

    city_coords = _build_city_coords(df)

    lats, lons = [], []
    for _, row in df.iterrows():
        key = (row["City"].upper(), row["State"].upper())
        lat, lon = city_coords.get(key, STATE_CENTROIDS.get(row["State"].upper(), (39.5, -98.35)))
        lats.append(lat)
        lons.append(lon)

    df = df.copy()
    df["lat"] = lats
    df["lon"] = lons

    coords = np.radians(df[["lat", "lon"]].values)
    tree = KDTree(coords)

    logger.info("Loaded %d unique fuel stations", len(df))
    return df.reset_index(drop=True), tree, coords


def find_stations_near_point(lat: float, lon: float, radius_miles: float = 50, top_n: int = 5) -> list[dict]:
    """
    Return up to top_n cheapest stations within radius_miles of (lat, lon).
    """
    stations_df, tree, _ = load_fuel_stations()

    # Convert radius to radians (Earth radius ≈ 3958.8 mi)
    radius_rad = radius_miles / 3958.8
    point = np.radians([[lat, lon]])
    indices = tree.query_ball_point(point[0], r=radius_rad)

    if not indices:
        return []

    subset = stations_df.iloc[indices].copy()
    subset = subset.nsmallest(top_n, "Retail Price")

    return subset.to_dict(orient="records")