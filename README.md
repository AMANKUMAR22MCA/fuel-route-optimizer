<div align="center">

# 🚛 Fuel Route Optimizer API

### Find the cheapest fuel stops on any US road trip — with a single API call.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/REST%20Framework-3.15-ff1709?style=flat&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ What it does

Send a **start** and **end** location anywhere in the USA. Get back:

- 🗺️ The full driving route (ready to render on a map)
- ⛽ Optimal fuel stops along the way — cheapest price within reach
- 💰 Total fuel cost for the trip, based on a 500-mile range / 10 MPG vehicle
- ⏱️ Estimated drive time and distance

All in **one API call**, with only **3 external requests** total (2 geocoding + 1 routing).

---

## 🏗️ How it works

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────┐
│   Geocode    │ ──▶ │  Get Route    │ ──▶ │  Optimize Fuel  │ ──▶ │   Response   │
│  (Nominatim) │     │   (OSRM)      │     │  Stops (local)  │     │    (JSON)    │
└─────────────┘     └──────────────┘     └────────────────┘     └─────────────┘
```

| Step | Service | Cost |
|------|---------|------|
| Geocoding addresses → coordinates | [Nominatim](https://nominatim.org/) (OpenStreetMap) | Free, no API key |
| Driving route + distance + geometry | [OSRM](http://project-osrm.org/) | Free, no API key |
| Cheapest fuel stop search | Local CSV + KD-Tree | Zero external calls |

The fuel station dataset (~7,000 unique stations) is loaded into memory **once at startup** and indexed with a `scipy.spatial.KDTree` for millisecond spatial lookups.

---
## Screenshot

<img width="1409" height="962" alt="image" src="https://github.com/user-attachments/assets/ef4b83ee-a8df-4d1a-bf9e-3ae364da19e5" />


## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/fuel-route-api.git
cd fuel-route-api
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Activate it
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Start the server

```bash
python manage.py runserver
```

You should see:
```
Loaded 6960 unique fuel stations
Starting development server at http://127.0.0.1:8000/
```

---

## 📡 API Reference

### `POST /api/route/`

**Request body**

```json
{
  "start": "Chicago, IL",
  "end": "Houston, TX"
}
```

**Response**

```json
{
  "start_location": "Chicago, IL",
  "end_location": "Houston, TX",
  "start_coords": [41.8755616, -87.6244212],
  "end_coords": [29.7589382, -95.3676974],

  "total_distance_miles": 1082.19,
  "estimated_duration_hours": 19.56,

  "num_fuel_stops": 2,
  "total_gallons_used": 108.22,
  "total_fuel_cost_usd": 268.25,

  "fuel_stops": [
    {
      "truckstop_name": "CIRCLE K #2723445",
      "address": "I-20, EXIT 5A & US-61/SR-27",
      "city": "Vicksburg",
      "state": "MS",
      "lat": 34.091646,
      "lon": -90.428696,
      "price_per_gallon": 2.959,
      "gallons_filled": 47.25,
      "stop_cost_usd": 139.82,
      "approx_route_mile": 472.5
    },
    {
      "truckstop_name": "STUCKEYS TRAVEL CENTER",
      "city": "Beaumont",
      "state": "TX",
      "price_per_gallon": 2.824,
      "gallons_filled": 45.48,
      "stop_cost_usd": 128.43,
      "approx_route_mile": 927.3
    }
  ],

  "route_geometry": [[-87.624351, 41.875563], "..."]
}
```

### `GET /api/health/`

Liveness check — confirms the app is running and fuel data is loaded.

```json
{
  "status": "ok",
  "fuel_stations_loaded": 6960
}
```

---

## 🧪 Testing with cURL

```bash
curl -X POST http://localhost:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Chicago, IL", "end": "Houston, TX"}'
```

**Try these routes:**

| Route | Distance | Stops |
|-------|----------|-------|
| Chicago, IL → Houston, TX | ~1,082 mi | 2 |
| New York, NY → Los Angeles, CA | ~2,790 mi | 5–6 |
| Boston, MA → Atlanta, GA | ~1,100 mi | 2–3 |
| Seattle, WA → Miami, FL | ~3,300 mi | 6–7 |

---

## ⚙️ Fuel Stop Algorithm

A **greedy** strategy that mirrors how a real driver plans fuel stops:

1. Start with a full tank (500-mile range)
2. Sample route waypoints every ~50 miles
3. At each waypoint, check: *"Can I reach the next one with a 10-mile safety buffer?"*
4. If not → search the KD-Tree for the **cheapest station within 50 miles**, refuel to full
5. Repeat until destination reached

Refuel amount = `tank capacity − fuel remaining` (i.e. top off to full, not always 50 gallons).

---

## 📁 Project Structure

```
fuel_route_api/
├── config/                  # Django project settings & URLs
├── route_optimizer/
│   ├── apps.py              # Pre-loads fuel data on startup
│   ├── fuel_data.py         # CSV loader + KD-Tree spatial index
│   ├── routing.py           # Nominatim geocoding + OSRM routing
│   ├── optimizer.py         # Greedy fuel stop algorithm
│   ├── serializers.py       # DRF request/response schemas
│   ├── views.py             # API endpoints
│   └── urls.py
├── data/
│   └── fuel_prices.csv      # Fuel station price dataset
├── requirements.txt
└── README.md
```

---

## 🗺️ Rendering the Route on a Map

`route_geometry` is a list of `[longitude, latitude]` pairs (GeoJSON order) — drop straight into Leaflet:

```javascript
const latlngs = routeGeometry.map(([lon, lat]) => [lat, lon]);
L.polyline(latlngs, { color: "#3388ff" }).addTo(map);

fuelStops.forEach(stop => {
  L.marker([stop.lat, stop.lon])
    .bindPopup(`${stop.truckstop_name}<br>$${stop.price_per_gallon}/gal`)
    .addTo(map);
});
```

---

## 🛠️ Tech Stack

- **Django 5** + **Django REST Framework**
- **pandas** + **scipy** (KD-Tree spatial indexing)
- **Nominatim** (geocoding) & **OSRM** (routing) — both free, no API keys

---

<div align="center">

Built as part of a backend engineering assessment.

</div>
