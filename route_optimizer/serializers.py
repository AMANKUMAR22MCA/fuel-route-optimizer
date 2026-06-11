from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=300,
        help_text="Starting location (e.g. 'New York, NY' or '123 Main St, Chicago, IL')",
    )
    end = serializers.CharField(
        max_length=300,
        help_text="Destination location (e.g. 'Los Angeles, CA')",
    )


class FuelStopSerializer(serializers.Serializer):
    truckstop_name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    gallons_filled = serializers.FloatField()
    stop_cost_usd = serializers.FloatField()
    approx_route_mile = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    start_location = serializers.CharField()
    end_location = serializers.CharField()
    start_coords = serializers.ListField(child=serializers.FloatField())
    end_coords = serializers.ListField(child=serializers.FloatField())

    # Route summary
    total_distance_miles = serializers.FloatField()
    estimated_duration_hours = serializers.FloatField()

    # Fuel analysis
    num_fuel_stops = serializers.IntegerField()
    total_gallons_used = serializers.FloatField()
    total_fuel_cost_usd = serializers.FloatField()
    fuel_stops = FuelStopSerializer(many=True)

    # Map data
    route_geometry = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        help_text="List of [longitude, latitude] coordinate pairs for map rendering",
    )
