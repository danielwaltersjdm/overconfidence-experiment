"""
Weather domain: predict tomorrow's high temperature for 30 major US cities.
Ground truth: Open-Meteo forecast API (past_days parameter).
No API key required.
"""
from datetime import date, timedelta

import requests

from .base import Question

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_CITIES = [
    {"name": "New York, NY",       "lat": 40.7128,  "lon": -74.0060},
    {"name": "Los Angeles, CA",    "lat": 34.0522,  "lon": -118.2437},
    {"name": "Chicago, IL",        "lat": 41.8781,  "lon": -87.6298},
    {"name": "Houston, TX",        "lat": 29.7604,  "lon": -95.3698},
    {"name": "Phoenix, AZ",        "lat": 33.4484,  "lon": -112.0740},
    {"name": "Philadelphia, PA",   "lat": 39.9526,  "lon": -75.1652},
    {"name": "San Antonio, TX",    "lat": 29.4241,  "lon": -98.4936},
    {"name": "San Diego, CA",      "lat": 32.7157,  "lon": -117.1611},
    {"name": "Dallas, TX",         "lat": 32.7767,  "lon": -96.7970},
    {"name": "San Jose, CA",       "lat": 37.3382,  "lon": -121.8863},
    {"name": "Austin, TX",         "lat": 30.2672,  "lon": -97.7431},
    {"name": "Columbus, OH",       "lat": 39.9612,  "lon": -82.9988},
    {"name": "Charlotte, NC",      "lat": 35.2271,  "lon": -80.8431},
    {"name": "Indianapolis, IN",   "lat": 39.7684,  "lon": -86.1581},
    {"name": "San Francisco, CA",  "lat": 37.7749,  "lon": -122.4194},
    {"name": "Seattle, WA",        "lat": 47.6062,  "lon": -122.3321},
    {"name": "Denver, CO",         "lat": 39.7392,  "lon": -104.9903},
    {"name": "Nashville, TN",      "lat": 36.1627,  "lon": -86.7816},
    {"name": "Las Vegas, NV",      "lat": 36.1699,  "lon": -115.1398},
    {"name": "Atlanta, GA",        "lat": 33.7490,  "lon": -84.3880},
    {"name": "Miami, FL",          "lat": 25.7617,  "lon": -80.1918},
    {"name": "Minneapolis, MN",    "lat": 44.9778,  "lon": -93.2650},
    {"name": "Portland, OR",       "lat": 45.5231,  "lon": -122.6765},
    {"name": "Boston, MA",         "lat": 42.3601,  "lon": -71.0589},
    {"name": "Salt Lake City, UT", "lat": 40.7608,  "lon": -111.8910},
    {"name": "Kansas City, MO",    "lat": 39.0997,  "lon": -94.5786},
    {"name": "Pittsburgh, PA",     "lat": 40.4406,  "lon": -79.9959},
    {"name": "Cincinnati, OH",     "lat": 39.1031,  "lon": -84.5120},
    {"name": "Memphis, TN",        "lat": 35.1495,  "lon": -90.0490},
    {"name": "New Orleans, LA",    "lat": 29.9511,  "lon": -90.0715},
]


def _get_forecast(lat: float, lon: float) -> tuple[float | None, float | None]:
    """
    Returns (today_high, tomorrow_high) in °F.
    Uses past_days=0 + forecast_days=2 to get today and tomorrow.
    """
    resp = requests.get(FORECAST_URL, params={
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "forecast_days": 2,
        "timezone": "auto",
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    highs = data["daily"]["temperature_2m_max"]
    today_high = highs[0] if len(highs) > 0 else None
    tomorrow_high = highs[1] if len(highs) > 1 else None
    return today_high, tomorrow_high


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    cities = config.get("domains", {}).get("weather", {}).get("cities", DEFAULT_CITIES)
    target_date = pred_date + timedelta(days=1)
    questions = []

    for city in cities:
        try:
            today_high, tomorrow_forecast = _get_forecast(city["lat"], city["lon"])
            if today_high is None:
                continue
            forecast_str = (
                f" The official forecast for tomorrow's high is {tomorrow_forecast:.0f}°F."
                if tomorrow_forecast is not None else ""
            )
            safe_id = city["name"].replace(", ", "_").replace(" ", "-")
            questions.append(Question(
                domain="weather",
                question_id=f"weather_{safe_id}",
                question_text=(
                    f"What will the high temperature be in {city['name']} "
                    f"tomorrow ({target_date.isoformat()})?"
                ),
                context=(
                    f"Today's high in {city['name']} is {today_high:.0f}°F.{forecast_str}"
                ),
                unit="°F",
                current_value=float(today_high),
                target_date=target_date.isoformat(),
                metadata={
                    "city": city["name"],
                    "lat": city["lat"],
                    "lon": city["lon"],
                    "official_forecast": tomorrow_forecast,
                },
            ))
        except Exception:
            pass
    return questions


def fetch_actual(question: Question) -> tuple[float | None, str | None]:
    """
    Fetch actual high temperature using Open-Meteo forecast API with past_days.
    This returns reanalysis-quality data (ERA5-based), accurate to ~1-2°F.
    Data is available ~1 day after the target date.
    """
    lat = question.metadata["lat"]
    lon = question.metadata["lon"]
    target = question.target_date

    try:
        resp = requests.get(FORECAST_URL, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max",
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
            "past_days": 7,
            "forecast_days": 1,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        dates = data["daily"]["time"]
        highs = data["daily"]["temperature_2m_max"]

        if target in dates:
            idx = dates.index(target)
            val = highs[idx]
            if val is not None:
                return float(val), target
        return None, None
    except Exception:
        return None, None
