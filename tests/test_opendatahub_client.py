from unittest.mock import Mock

import pytest
import requests

from src.opendatahub_client import (
    API_URL,
    OpenDataHubClientError,
    SHARING_STATION_COLUMNS,
    get_sharing_stations,
)
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


def station(station_id="station-1", longitude=9.37, latitude=47.42):
    return {
        "scode": station_id,
        "sname": "Test Station",
        "scoordinate": {"srid": 4326, "x": longitude, "y": latitude},
        "pname": "Test System",
        "pcode": "test-system",
    }


def test_normalizes_nearby_stations_and_excludes_outside_radius(
    monkeypatch, settings
):
    response = Mock()
    response.json.return_value = {
        "offset": 0,
        "limit": -1,
        "data": [
            station(),
            station("outside-radius", longitude=9.4107, latitude=47.4645),
        ],
    }
    response.raise_for_status.return_value = None
    request = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", request)

    stations = get_sharing_stations(settings)

    assert list(stations.columns) == SHARING_STATION_COLUMNS
    assert len(stations) == 1
    assert stations.iloc[0]["id"] == "station-1"
    assert stations.iloc[0]["name"] == "Test Station"
    assert stations.iloc[0]["anbieter"] == "Test System"
    assert stations.iloc[0]["lat"] == 47.42
    assert stations.iloc[0]["lon"] == 9.37
    assert request.call_args.args[0] == API_URL
    assert "scoordinate.bbi." in request.call_args.kwargs["params"]["where"]


def test_empty_response_returns_expected_columns(monkeypatch, settings):
    response = Mock()
    response.json.return_value = {"data": []}
    response.raise_for_status.return_value = None
    monkeypatch.setattr(requests, "get", Mock(return_value=response))

    stations = get_sharing_stations(settings)

    assert stations.empty
    assert list(stations.columns) == SHARING_STATION_COLUMNS


def test_timeout_raises_clear_client_error(monkeypatch, settings):
    monkeypatch.setattr(
        requests,
        "get",
        Mock(side_effect=requests.Timeout("too slow")),
    )

    with pytest.raises(OpenDataHubClientError, match="Zeitüberschreitung"):
        get_sharing_stations(settings)