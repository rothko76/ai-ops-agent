"""Weather-related tools."""

import requests


def get_weather(city: str) -> dict[str, str | float]:
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=15,
    ).json()

    if not geo.get("results"):
        return {"city": city, "error": "City not found"}

    loc = geo["results"][0]
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current_weather": True,
        },
        timeout=15,
    ).json()

    return {
        "city": city,
        "temperature_c": weather["current_weather"]["temperature"],
        "windspeed_kmh": weather["current_weather"]["windspeed"],
    }
