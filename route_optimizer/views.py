"""
Main API view for fuel route optimization.
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .optimizer import optimize_fuel_stops
from .routing import geocode, get_route
from .serializers import RouteRequestSerializer, RouteResponseSerializer

logger = logging.getLogger(__name__)


class FuelRouteView(APIView):
    """
    POST /api/route/

    Request body:
        {
            "start": "New York, NY",
            "end": "Los Angeles, CA"
        }

    Returns an optimised fuel route with cheapest stops and total cost.
    """

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_str = serializer.validated_data["start"]
        end_str = serializer.validated_data["end"]

        # Step 1: Geocode both locations (2 Nominatim calls)
        try:
            start_coords = geocode(start_str)
        except Exception as exc:
            return Response(
                {"error": f"Could not geocode start location: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            end_coords = geocode(end_str)
        except Exception as exc:
            return Response(
                {"error": f"Could not geocode end location: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 2: Get route from OSRM (1 API call)
        try:
            route_info = get_route(start_coords, end_coords)
        except Exception as exc:
            logger.exception("OSRM routing failed")
            return Response(
                {"error": f"Routing service error: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Step 3: Optimise fuel stops (no external calls - uses local CSV data)
        try:
            fuel_result = optimize_fuel_stops(start_coords, end_coords, route_info)
        except Exception as exc:
            logger.exception("Fuel optimisation failed")
            return Response(
                {"error": f"Optimisation error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Step 4: Build response
        response_data = {
            "start_location": start_str,
            "end_location": end_str,
            "start_coords": list(start_coords),
            "end_coords": list(end_coords),
            "total_distance_miles": route_info["distance_miles"],
            "estimated_duration_hours": round(route_info["duration_seconds"] / 3600, 2),
            "num_fuel_stops": fuel_result["num_fuel_stops"],
            "total_gallons_used": fuel_result["total_gallons_used"],
            "total_fuel_cost_usd": fuel_result["total_fuel_cost_usd"],
            "fuel_stops": fuel_result["fuel_stops"],
            "route_geometry": route_info["geometry"],
        }

        return Response(response_data, status=status.HTTP_200_OK)


class HealthView(APIView):
    """GET /api/health/ - liveness probe."""

    def get(self, request):
        from .fuel_data import load_fuel_stations
        stations_df, _, _ = load_fuel_stations()
        return Response({
            "status": "ok",
            "fuel_stations_loaded": len(stations_df),
        })
