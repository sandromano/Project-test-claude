"""SQLite-Speicherung der einzelnen Scooter-Snapshots."""

from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from src.api_client import SCOOTER_COLUMNS, SOURCE_URL


SNAPSHOT_COLUMNS = [
    "id",
    "anbieter",
    "lat",
    "lon",
    "akkustand",
    "zeitstempel",
    "stadt",
]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshot_runs (
            id INTEGER PRIMARY KEY,
            captured_at TEXT NOT NULL,
            city TEXT NOT NULL,
            source TEXT NOT NULL,
            scooter_count INTEGER NOT NULL,
            UNIQUE (city, captured_at)
        );
        CREATE TABLE IF NOT EXISTS scooter_snapshots (
            snapshot_id INTEGER NOT NULL REFERENCES snapshot_runs(id),
            scooter_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            battery REAL,
            PRIMARY KEY (snapshot_id, scooter_id)
        );
        CREATE INDEX IF NOT EXISTS idx_snapshot_runs_captured_at
            ON snapshot_runs(captured_at);
        """
    )
    return connection


def _timestamp(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def save_snapshot(
    scooters: pd.DataFrame,
    city: str,
    db_path: Path,
    captured_at: datetime | None = None,
    source: str = SOURCE_URL,
) -> int:
    """Speichert einen Snapshot genau einmal und gibt die Anzahl neuer Scooter zurück."""
    missing_columns = set(SCOOTER_COLUMNS) - set(scooters.columns)
    if missing_columns:
        raise ValueError(f"DataFrame-Spalten fehlen: {', '.join(sorted(missing_columns))}")

    captured = _timestamp(captured_at)
    rows = scooters.drop_duplicates(subset=["id"])
    with closing(_connect(db_path)) as connection, connection:
        existing = connection.execute(
            "SELECT id FROM snapshot_runs WHERE city = ? AND captured_at = ?",
            (city, captured),
        ).fetchone()
        if existing:
            return 0

        cursor = connection.execute(
            """
            INSERT INTO snapshot_runs (captured_at, city, source, scooter_count)
            VALUES (?, ?, ?, ?)
            """,
            (captured, city, source, len(rows)),
        )
        snapshot_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO scooter_snapshots
                (snapshot_id, scooter_id, provider, lat, lon, battery)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_id,
                    str(row.id),
                    str(row.anbieter),
                    float(row.lat),
                    float(row.lon),
                    None if pd.isna(row.akkustand) else float(row.akkustand),
                )
                for row in rows.itertuples(index=False)
            ],
        )
    return len(rows)


def load_recent_snapshots(
    db_path: Path,
    days: int = 7,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Lädt Scooter-Messungen der letzten Tage inklusive Stadt und Messzeit."""
    if days <= 0:
        raise ValueError("days muss grösser als 0 sein.")
    cutoff = _timestamp((now or datetime.now(timezone.utc)) - timedelta(days=days))
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT s.scooter_id, s.provider, s.lat, s.lon, s.battery,
                   r.captured_at, r.city
            FROM scooter_snapshots AS s
            JOIN snapshot_runs AS r ON r.id = s.snapshot_id
            WHERE r.captured_at >= ?
            ORDER BY r.captured_at, s.scooter_id
            """,
            (cutoff,),
        ).fetchall()
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def load_recent_runs(
    db_path: Path,
    days: int = 7,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Lädt auch leere Erfassungsläufe, damit 0-Scooter-Snapshots erhalten bleiben."""
    if days <= 0:
        raise ValueError("days muss grösser als 0 sein.")
    cutoff = _timestamp((now or datetime.now(timezone.utc)) - timedelta(days=days))
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT captured_at, city, source, scooter_count
            FROM snapshot_runs
            WHERE captured_at >= ?
            ORDER BY captured_at
            """,
            (cutoff,),
        ).fetchall()
    return pd.DataFrame(rows, columns=["zeitstempel", "stadt", "quelle", "anzahl_scooter"])
