"""Client für die Shared-Mobility-REST-API des BFE."""

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from src.settings import Settings, load_settings


PAGE_SIZE = 50
SCOOTER_COLUMNS = ["id", "anbieter", "lat", "lon", "akkustand", "zeitstempel"]
SOURCE_URL = "https://opendata.swiss/en/dataset/standorte-und-verfugbarkeit-von-shared-mobility-angeboten"


class APIClientError(RuntimeError):
    """Fehler bei Anfrage oder Verarbeitung der BFE-API."""


def _features(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        return payload["features"]
    raise APIClientError("Unerwartetes Antwortformat der BFE-API.")


def _normalize_feature(feature: dict[str, Any], fetched_at: str) -> dict[str, Any] | None:
    properties = feature.get("properties") or {}
    if properties.get("available") is not True:
        return None

    # Stationen beschreiben Parkzonen, nicht einzelne Scooter-Standorte.
    if properties.get("pickup_type") != "free_floating":
        return None

    vehicle_types = properties.get("vehicle_type", [])
    if isinstance(vehicle_types, str):
        vehicle_types = [vehicle_types]
    if not isinstance(vehicle_types, list) or "E-Scooter" not in vehicle_types:
        return None

    coordinates = (feature.get("geometry") or {}).get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None

    scooter_id = properties.get("id") or feature.get("id")
    provider = properties.get("provider") or {}
    if not scooter_id or not provider.get("name"):
        return None

    try:
        latitude = float(coordinates[1])
        longitude = float(coordinates[0])
    except (TypeError, ValueError) as exc:
        raise APIClientError("Die BFE-API lieferte ungültige Scooter-Koordinaten.") from exc

    return {
        "id": str(scooter_id),
        "anbieter": str(provider["name"]),
        "lat": latitude,
        "lon": longitude,
        "akkustand": properties.get("battery_level", properties.get("battery")),
        "zeitstempel": fetched_at,
    }


def get_scooters(settings: Settings | None = None) -> pd.DataFrame:
    """Ruft verfügbare, frei abgestellte Scooter im konfigurierten Umkreis ab."""
    settings = settings or load_settings()
    endpoint = f"{settings.api_base_url}/identify"
    fetched_at = datetime.now(timezone.utc).isoformat()
    filters = [
        "ch.bfe.sharedmobility.vehicle_type=E-Scooter",
        "ch.bfe.sharedmobility.available=true",
        "ch.bfe.sharedmobility.pickup_type=free_floating",
    ]
    scooters: dict[str, dict[str, Any]] = {}
    offset = 0

    while True:
        params = [
            ("Geometry", f"{settings.longitude},{settings.latitude}"),
            ("Tolerance", settings.radius_m),
            ("geometryFormat", "geojson"),
            ("offset", offset),
            *(("filters", value) for value in filters),
        ]
        try:
            response = requests.get(
                endpoint,
                params=params,
                timeout=settings.api_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise APIClientError("Zeitüberschreitung beim Abruf der BFE-API.") from exc
        except requests.RequestException as exc:
            raise APIClientError(f"BFE-API-Anfrage fehlgeschlagen: {exc}") from exc
        except ValueError as exc:
            raise APIClientError("Die BFE-API lieferte kein gültiges JSON.") from exc

        page = _features(payload)
        for feature in page:
            scooter = _normalize_feature(feature, fetched_at)
            if scooter:
                scooters[scooter["id"]] = scooter

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return pd.DataFrame(scooters.values(), columns=SCOOTER_COLUMNS)
