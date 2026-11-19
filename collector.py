"""Sammelt regelmässig Scooter-Snapshots in der lokalen SQLite-Datenbank."""

import logging
import sqlite3
import time

from src.api_client import APIClientError, get_scooters
from src.database import save_snapshot
from src.settings import load_settings


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    next_run = time.monotonic()
    logging.info(
        "Sammler für %s gestartet; Intervall: %s Sekunden",
        settings.city,
        settings.interval_seconds,
    )

    try:
        while True:
            try:
                scooters = get_scooters(settings)
                stored = save_snapshot(scooters, settings.city, settings.database_path)
                logging.info("Snapshot: %s Scooter gespeichert", stored)
            except (APIClientError, OSError, ValueError, sqlite3.Error) as exc:
                logging.exception("Snapshot fehlgeschlagen: %s", exc)

            next_run += settings.interval_seconds
            now = time.monotonic()
            if next_run < now:
                next_run = now + settings.interval_seconds
            delay = next_run - now
            time.sleep(delay)
    except KeyboardInterrupt:
        logging.info("Sammler beendet.")


if __name__ == "__main__":
    main()
