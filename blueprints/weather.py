"""Backend proxy for OpenWeatherMap current-weather API.

Keeps the API key server-side so it is never exposed to the browser.
Endpoint: GET /api/weather?city=Pune  OR  /api/weather?lat=18.52&lon=73.86
"""
import logging

import requests
from flask import Blueprint, jsonify, request

import config

logger = logging.getLogger("agritech.weather")
weather_bp = Blueprint("weather", __name__)


@weather_bp.route("/weather", methods=["GET"])
def get_weather():
    if not config.OPENWEATHER_KEY:
        logger.warning("GET /api/weather called but OPENWEATHER_KEY is not set.")
        return jsonify({
            "error": "Weather API key not configured.",
            "message": (
                "Open the .env file, set OPENWEATHER_KEY=<your_key>, "
                "then restart the server. "
                "Get a free key at https://openweathermap.org/api"
            ),
        }), 503

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    city = request.args.get("city", "Pune")

    params = {"appid": config.OPENWEATHER_KEY, "units": "metric"}
    if lat and lon:
        params.update({"lat": lat, "lon": lon})
        location_label = f"lat={lat},lon={lon}"
    else:
        params["q"] = city
        location_label = city

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"OpenWeatherMap data fetched for: {location_label}")
        return jsonify(resp.json())
    except requests.HTTPError as e:
        status = e.response.status_code
        logger.error(f"OpenWeatherMap HTTP {status} for {location_label}: {e.response.text}")
        if status == 401:
            return jsonify({"error": "Invalid API key. Check OPENWEATHER_KEY in .env."}), 502
        if status == 404:
            return jsonify({"error": f"Location '{city}' not found. Try a different city name."}), 404
        return jsonify({"error": f"Weather API error: {status}"}), 502
    except requests.Timeout:
        logger.warning(f"OpenWeatherMap request timed out for {location_label}")
        return jsonify({"error": "Weather service timed out. Please try again."}), 504
    except Exception as e:
        logger.error(f"Unexpected weather error: {e}", exc_info=True)
        return jsonify({"error": "Unexpected error fetching weather data."}), 500
