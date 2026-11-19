from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from src.api_client import APIClientError, SCOOTER_COLUMNS, get_scooters
from src.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        city="St. Gallen",
        latitude=47.4245,
        longitude=9.3767,
        radius_m=5000,
        interval_seconds=900,
        cache_ttl_seconds=60,
        api_base_url="https://api.example.test/v1/sharedmobility",
        api_timeout_seconds=5,
        database_path=tmp_path / "scooters.sqlite3",
    )


def feature(
    scooter_id="scooter-1",
    pickup_type="free_floating",
    vehicle_type="E-Scooter",
    available=True,
):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [9.37, 47.42]},
        "properties": {
            "id": scooter_id,
            "available": available,
            "pickup_type": pickup_type,
            "vehicle_type": [vehicle_type],
            "provider": {"name": "Test Anbieter"},
        },
    }


def test_normalizes_scooters_and_skips_stations_and_other_vehicles(monkeypatch, settings):
    response = Mock()
    response.json.return_value = [
        feature(),
        feature("station-1", pickup_type="station_based"),
        feature("bike-1", vehicle_type="E-Bike"),
    ]
    response.raise_for_status.return_value = None
    monkeypatch.setattr(requests, "get", Mock(return_value=response))

    scooters = get_scooters(settings)

    assert list(scooters.columns) == SCOOTER_COLUMNS
    assert len(scooters) == 1
    assert scooters.iloc[0]["id"] == "scooter-1"
    assert scooters.iloc[0]["anbieter"] == "Test Anbieter"
    assert scooters.iloc[0]["lat"] == 47.42
    assert scooters.iloc[0]["lon"] == 9.37
    assert pd.isna(scooters.iloc[0]["akkustand"])


def test_empty_api_response_returns_empty_dataframe(monkeypatch, settings):
    response = Mock()
    response.json.return_value = []
    response.raise_for_status.return_value = None
    monkeypatch.setattr(requests, "get", Mock(return_value=response))

    scooters = get_scooters(settings)

    assert scooters.empty
    assert list(scooters.columns) == SCOOTER_COLUMNS


def test_fetches_next_page_when_api_returns_50_results(monkeypatch, settings):
    first_page = [feature(f"scooter-{number}") for number in range(50)]
    second_page = [feature("scooter-50")]
    first_response = Mock()
    first_response.json.return_value = first_page
    first_response.raise_for_status.return_value = None
    second_response = Mock()
    second_response.json.return_value = second_page
    second_response.raise_for_status.return_value = None
    request = Mock(side_effect=[first_response, second_response])
    monkeypatch.setattr(requests, "get", request)

    scooters = get_scooters(settings)

    assert len(scooters) == 51
    second_params = request.call_args_list[1].kwargs["params"]
    assert ("offset", 50) in second_params


def test_timeout_raises_clear_client_error(monkeypatch, settings):
    monkeypatch.setattr(
        requests,
        "get",
        Mock(side_effect=requests.Timeout("too slow")),
    )

    with pytest.raises(APIClientError, match="Zeitüberschreitung"):
        get_scooters(settings)
