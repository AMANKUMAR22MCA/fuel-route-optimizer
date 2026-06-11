"""
Routing and geocoding helpers.

* Geocoding  → Nominatim (OpenStreetMap, free, no key needed)
* Route      → OSRM public demo server (free, no key needed)
              Returns polyline + waypoints every ~50 miles for fuel planning.
"""
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

# Respect Nominatim's 1 req/sec policy
_last_nominatim_call = 0.0

HEADERS = {
    "User-Agent": "FuelRouteOptimizer/1.0 (assessment project)",
}


def geocode(address: str) -> tuple[float, float]:
    """
    Convert a US address / city string to (lat, lon).
    Raises ValueError if nothing found.
    """
    global _last_nominatim_call
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)

    params = {
        "q": address + ", USA",
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
    }
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
    _last_nominatim_call = time.time()
    resp.raise_for_status()
    results = resp.json()

    if not results:
        raise ValueError(f"Could not geocode address: '{address}'")

    best = results[0]
    return float(best["lat"]), float(best["lon"])


def get_route(start_coords: tuple[float, float], end_coords: tuple[float, float]) -> dict[str, Any]:
    """
    Fetch a driving route from OSRM.

    Returns a dict with:
      - distance_miles: float
      - duration_seconds: float
      - geometry: list of [lon, lat] coordinate pairs (decoded from polyline)
      - waypoints_every_50mi: list of (lat, lon) sampled ~every 50 miles
    """
    start_lon, start_lat = start_coords[1], start_coords[0]
    end_lon, end_lat = end_coords[1], end_coords[0]

    url = f"{OSRM_BASE_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "annotations": "false",
    }

    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok":
        raise ValueError(f"OSRM error: {data.get('message', data.get('code'))}")

    route = data["routes"][0]
    distance_meters = route["distance"]
    distance_miles = distance_meters / 1609.344
    duration_seconds = route["duration"]

    coords = route["geometry"]["coordinates"]  # list of [lon, lat]

    # Sample waypoints approximately every 50 miles for fuel stop candidates
    waypoints = _sample_waypoints(coords, distance_miles, interval_miles=50)

    return {
        "distance_miles": round(distance_miles, 2),
        "duration_seconds": round(duration_seconds),
        "geometry": coords,
        "waypoints_every_50mi": waypoints,
    }


def _sample_waypoints(
    coords: list[list[float]], total_miles: float, interval_miles: float = 50
) -> list[tuple[float, float]]:
    """
    Sample (lat, lon) points roughly every interval_miles along the route polyline.
    """
    if not coords:
        return []

    # We'll walk the coordinate list and emit a sample every interval_miles.
    # Distance is approximated linearly.
    import math

    def haversine(c1, c2):
        """Distance in miles between two [lon, lat] points."""
        lon1, lat1 = math.radians(c1[0]), math.radians(c1[1])
        lon2, lat2 = math.radians(c2[0]), math.radians(c2[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 3958.8 * 2 * math.asin(math.sqrt(a))

    waypoints = []
    accumulated = 0.0
    next_sample = interval_miles

    for i in range(1, len(coords)):
        seg_dist = haversine(coords[i - 1], coords[i])
        accumulated += seg_dist
        if accumulated >= next_sample:
            waypoints.append((coords[i][1], coords[i][0]))  # (lat, lon)
            next_sample += interval_miles

    return waypoints
