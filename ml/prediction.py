"""Schnittstelle für zukünftige Scooter-Prognosen."""

import pandas as pd


def predict_density(stadt: str, datum: str, stunde: int) -> pd.DataFrame:
    """Gibt später die prognostizierte Scooter-Dichte als DataFrame zurück."""
    # Mögliche Features: Wochentag, Stunde, Wetter und Rasterzelle der Stadt.
    raise NotImplementedError("Die Prognose wird in einer späteren Projektphase umgesetzt.")
