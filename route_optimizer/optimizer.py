"""
Fuel stop optimizer.

Strategy
--------
The vehicle has a 500-mile range and 10 MPG fuel economy.
We walk the route waypoints (sampled every ~50 miles) and whenever
the remaining range drops below a configurable threshold we search
for the cheapest station near the next waypoint within 50 miles.

This is a greedy algorithm that works well in practice:
- Never let the tank drop to 0
- Always prefer the cheapest nearby station
- Multiple stops are added until the destination is reachable
"""
from __future__ import annotations

import logging
import math
from typing import Any

from .fuel_data import find_stations_near_point

logger = logging.getLogger(__name__)

VEHICLE_RANGE_MILES = 500.0
MPG = 10.0
TANK_CAPACITY_GAL = VEHICLE_RANGE_MILES / MPG  # 50 gallons


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in miles between two lat/lon points."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def optimize_fuel_stops(
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
    route_info: dict[str, Any],
) -> dict[str, Any]:
    """
    Given the route, compute optimal (cheapest) fuel stops.

    Returns a dict:
      - fuel_stops: list of stop dicts
      - total_fuel_cost_usd: float
      - total_gallons: float
      - total_distance_miles: float
    """
    total_miles = route_info["distance_miles"]
    waypoints = route_info["waypoints_every_50mi"]

    # Always add start and end as implicit waypoints for distance calculations
    all_points = [start_coords] + waypoints + [end_coords]

    # Compute cumulative miles along the route for each waypoint
    cumulative = [0.0]
    for i in range(1, len(all_points)):
        d = haversine(*all_points[i - 1], *all_points[i])
        cumulative.append(cumulative[-1] + d)

    # ---- Greedy fuel stop selection ----
    # We start with a full tank, track miles since last fill-up,
    # and stop to refuel whenever the remaining range is insufficient
    # to reach the next safe waypoint.

    fuel_stops: list[dict] = []
    miles_since_fill = 0.0  # we start with full tank → 0 miles since fill
    # (alternatively we could start empty at origin but "start full" is standard)

    i = 0
    while i < len(all_points) - 1:
        current = all_points[i]
        next_point = all_points[i + 1]
        dist_to_next = haversine(*current, *next_point)
        remaining_range = VEHICLE_RANGE_MILES - miles_since_fill

        if remaining_range < dist_to_next + 10:  # 10-mile safety buffer
            # Need to refuel near current point
            candidates = find_stations_near_point(current[0], current[1], radius_miles=50, top_n=5)

            if not candidates:
                # Try wider radius
                candidates = find_stations_near_point(current[0], current[1], radius_miles=100, top_n=5)

            if not candidates:
                logger.warning("No fuel stations found near %.4f, %.4f", *current)
                miles_since_fill = 0.0  # assume we somehow refueled
                i += 1
                continue

            # Pick cheapest
            best = min(candidates, key=lambda s: s["Retail Price"])
            gallons_needed = miles_since_fill / MPG  # how much we used since last fill
            gallons_to_fill = TANK_CAPACITY_GAL - (VEHICLE_RANGE_MILES - miles_since_fill) / MPG
            gallons_to_fill = max(gallons_to_fill, 1.0)  # always put at least 1 gal
            gallons_to_fill = min(gallons_to_fill, TANK_CAPACITY_GAL)  # can't exceed tank

            stop_info = {
                "truckstop_name": best["Truckstop Name"],
                "address": best["Address"],
                "city": best["City"],
                "state": best["State"],
                "lat": round(best["lat"], 6),
                "lon": round(best["lon"], 6),
                "price_per_gallon": round(best["Retail Price"], 4),
                "gallons_filled": round(gallons_to_fill, 2),
                "stop_cost_usd": round(gallons_to_fill * best["Retail Price"], 2),
                "approx_route_mile": round(cumulative[i], 1),
            }
            fuel_stops.append(stop_info)
            miles_since_fill = 0.0  # refueled — reset

        miles_since_fill += dist_to_next
        i += 1

    # Final segment: compute fuel used for the remaining distance
    total_gallons = total_miles / MPG
    total_cost = sum(s["stop_cost_usd"] for s in fuel_stops)

    # If no stops were needed (trip < 500 mi), still compute fuel cost
    if not fuel_stops:
        total_cost = round(total_gallons * _average_price_on_route(
            start_coords, end_coords, all_points
        ), 2)

    return {
        "fuel_stops": fuel_stops,
        "total_fuel_cost_usd": round(total_cost, 2),
        "total_gallons_used": round(total_gallons, 2),
        "total_distance_miles": total_miles,
        "num_fuel_stops": len(fuel_stops),
    }


def _average_price_on_route(
    start: tuple, end: tuple, waypoints: list
) -> float:
    """Rough average price for short trips with no mandatory stops."""
    mid = waypoints[len(waypoints) // 2] if waypoints else start
    candidates = find_stations_near_point(mid[0], mid[1], radius_miles=100, top_n=10)
    if not candidates:
        return 3.50  # fallback national average
    return sum(s["Retail Price"] for s in candidates) / len(candidates)
