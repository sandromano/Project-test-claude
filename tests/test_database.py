from datetime import datetime, timedelta, timezone

import pandas as pd

from src.database import load_recent_runs, load_recent_snapshots, save_snapshot


def scooters_frame():
    return pd.DataFrame(
        [
            {
                "id": "scooter-1",
                "anbieter": "Test Anbieter",
                "lat": 47.42,
                "lon": 9.37,
                "akkustand": None,
                "zeitstempel": "2026-11-19T08:00:00+00:00",
            }
        ]
    )


def test_saves_snapshots_once_and_loads_recent_data(tmp_path):
    db_path = tmp_path / "nested" / "scooters.sqlite3"
    captured_at = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)

    assert save_snapshot(scooters_frame(), "St. Gallen", db_path, captured_at) == 1
    assert save_snapshot(scooters_frame(), "St. Gallen", db_path, captured_at) == 0

    loaded = load_recent_snapshots(
        db_path,
        days=7,
        now=captured_at + timedelta(hours=1),
    )
    assert len(loaded) == 1
    assert loaded.iloc[0]["id"] == "scooter-1"
    assert loaded.iloc[0]["stadt"] == "St. Gallen"
    assert pd.isna(loaded.iloc[0]["akkustand"])


def test_records_empty_snapshots_for_zero_scooter_days(tmp_path):
    db_path = tmp_path / "scooters.sqlite3"
    captured_at = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)

    assert save_snapshot(scooters_frame().iloc[0:0], "St. Gallen", db_path, captured_at) == 0

    runs = load_recent_runs(db_path, days=7, now=captured_at + timedelta(hours=1))
    assert len(runs) == 1
    assert runs.iloc[0]["anzahl_scooter"] == 0
