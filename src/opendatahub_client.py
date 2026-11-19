"""Client für Scooter-Sharing-Stationen der Open Data Hub Mobility API."""

import math
from typing import Any

import pandas as pd
import requests

from src.settings import Settings, load_settings


API_URL = "https://mobility.api.opendatahub.com/v2/flat/ScooterSharingStation"
OPENDATAHUB_SOURCE_URL = "https://mobility.api.opendatahub.com/v2/apispec"
SHARING_STATION_COLUMNS = ["id", "name", "anbieter", "lat", "lon"]
EARTH_RADIUS_M = 6_371_000


class OpenDataHubClientError(RuntimeError):
    """Fehler bei Anfrage oder Verarbeitung der Open Data Hub API."""


def _radius_bounds(settings: Settings) -> tuple[float, float, float, float]:
    latitude_delta = settings.radius_m / 111_320
    longitude_scale = max(math.cos(math.radians(settings.latitude)), 0.01)
    longitude_delta = settings.radius_m / (111_320 * longitude_scale)
    return (
        max(-180, settings.longitude - longitude_delta),
        max(-90, settings.latitude - latitude_delta),
        min(180, settings.longitude + longitude_delta),
        min(90, settings.latitude + latitude_delta),
    )


def _within_radius(latitude: float, longitude: float, settings: Settings) -> bool:
    latitude_1 = math.radians(settings.latitude)
    latitude_2 = math.radians(latitude)
    latitude_delta = latitude_2 - latitude_1
    longitude_delta = math.radians(longitude - settings.longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(longitude_delta / 2) ** 2
    )
    distance = 2 * EARTH_RADIUS_M * math.asin(math.sqrt(haversine))
    return distance <= settings.radius_m


def _normalize_station(station: dict[str, Any]) -> dict[str, Any] | None:
    coordinate = station.get("scoordinate")
    if not isinstance(coordinate, dict) or coordinate.get("srid") != 4326:
        return None

    station_id = station.get("scode")
    station_name = station.get("sname")
    if not station_id or not station_name:
        return None

    try:
        longitude = float(coordinate["x"])
        latitude = float(coordinate["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenDataHubClientError(
            "Open Data Hub lieferte ungültige Stationskoordinaten."
        ) from exc

    return {
        "id": str(station_id),
        "name": str(station_name),
        "anbieter": str(station.get("pname") or station.get("pcode") or "Unbekannt"),
        "lat": latitude,
        "lon": longitude,
    }


def get_sharing_stations(settings: Settings | None = None) -> pd.DataFrame:
    """Lädt scooter-sharing station locations im konfigurierten Umkreis."""
    settings = settings or load_settings()
    min_longitude, min_latitude, max_longitude, max_latitude = _radius_bounds(settings)
    where = (
        "sactive.eq.true,scoordinate.bbi."
        f"({min_longitude:.6f},{min_latitude:.6f},"
        f"{max_longitude:.6f},{max_latitude:.6f},4326)"
    )
    try:
        response = requests.get(
            API_URL,
            params={
                "where": where,
                "select": "scode,sname,scoordinate,pname,pcode",
                "limit": -1,
            },
            timeout=settings.api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise OpenDataHubClientError(
            "Zeitüberschreitung beim Abruf der Open Data Hub API."
        ) from exc
    except requests.RequestException as exc:
        raise OpenDataHubClientError(
            f"Open Data Hub API-Anfrage fehlgeschlagen: {exc}"
        ) from exc
    except ValueError as exc:
        raise OpenDataHubClientError(
            "Open Data Hub lieferte kein gültiges JSON."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise OpenDataHubClientError("Unerwartetes Antwortformat der Open Data Hub API.")

    stations = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        station = _normalize_station(item)
        if station and _within_radius(station["lat"], station["lon"], settings):
            stations.append(station)

    return pd.DataFrame(stations, columns=SHARING_STATION_COLUMNS)