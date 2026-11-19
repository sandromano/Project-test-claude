"""Lädt die zentralen Projekteinstellungen aus config.toml."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.toml"


@dataclass(frozen=True)
class Settings:
    city: str
    latitude: float
    longitude: float
    radius_m: int
    interval_seconds: int
    cache_ttl_seconds: int
    api_base_url: str
    api_timeout_seconds: int
    database_path: Path


def load_settings(config_path: Path = CONFIG_PATH) -> Settings:
    """Liest die TOML-Konfiguration und macht relative Pfade projektbezogen."""
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    database_path = Path(config["database"]["path"])
    if not database_path.is_absolute():
        database_path = config_path.parent / database_path

    return Settings(
        city=config["city"]["name"],
        latitude=float(config["city"]["latitude"]),
        longitude=float(config["city"]["longitude"]),
        radius_m=int(config["city"]["radius_m"]),
        interval_seconds=int(config["collector"]["interval_seconds"]),
        cache_ttl_seconds=int(config["app"]["cache_ttl_seconds"]),
        api_base_url=config["api"]["base_url"].rstrip("/"),
        api_timeout_seconds=int(config["api"]["timeout_seconds"]),
        database_path=database_path,
    )
