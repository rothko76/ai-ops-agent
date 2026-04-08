"""Weather-related tools."""

import requests
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
import logging

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=8),
    retry=retry_if_exception_type(requests.RequestException),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _http_get_json(url: str, params: dict[str, str | int | float | bool]) -> dict:
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def get_weather(city: str) -> dict[str, str | float | int]:
    try:
        geo = _http_get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": city, "count": 1},
        )
    except requests.RequestException as err:
        return {"city": city, "error": f"Weather geocoding request failed: {err}"}

    if not geo.get("results"):
        return {"city": city, "error": "City not found"}

    loc = geo["results"][0]
    try:
        weather = _http_get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current_weather": True,
            },
        )
    except requests.RequestException as err:
        return {"city": city, "error": f"Weather forecast request failed: {err}"}

    current = weather.get("current_weather") or {}
    if "temperature" not in current or "windspeed" not in current:
        return {"city": city, "error": "Weather service returned an unexpected response"}

    return {
        "city": city,
        "temperature_c": current["temperature"],
        "windspeed_kmh": current["windspeed"],
    }
