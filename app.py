"""Streamlit-Oberfläche für die E-Scooter-Karte und den ML-Platzhalter."""

from html import escape

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.api_client import APIClientError, SOURCE_URL, get_scooters
from src.settings import load_settings


SETTINGS = load_settings()
st.set_page_config(page_title="E-Scooter Finder", page_icon="🛴", layout="wide")


@st.cache_data(ttl=SETTINGS.cache_ttl_seconds)
def load_scooters():
    return get_scooters(SETTINGS)


st.title("E-Scooter Finder")
page = st.sidebar.radio("Seite", ["Karte", "Prognose"])

if page == "Prognose":
    st.header("Prognose (kommt bald)")
    st.info(
        "Hier werden später Dichteprognosen nach Stadt, Datum und Stunde "
        "angezeigt. Das ML-Modul ist derzeit nur eine Schnittstelle."
    )
else:
    st.header(f"Verfügbare E-Scooter in {SETTINGS.city}")
    if st.sidebar.button("Aktualisieren"):
        load_scooters.clear()

    try:
        scooters = load_scooters()
    except APIClientError as exc:
        st.error(f"Die Scooter-Daten konnten nicht geladen werden: {exc}")
        st.stop()

    providers = sorted(scooters["anbieter"].dropna().unique().tolist())
    selected_providers = st.sidebar.multiselect(
        "Anbieter",
        providers,
        default=providers,
    )
    visible_scooters = scooters[scooters["anbieter"].isin(selected_providers)]
    st.metric("Verfügbare Scooter", len(visible_scooters))

    scooter_map = folium.Map(
        location=[SETTINGS.latitude, SETTINGS.longitude],
        zoom_start=13,
        control_scale=True,
    )
    for scooter in visible_scooters.itertuples(index=False):
        battery = "Nicht verfügbar"
        if scooter.akkustand is not None and not pd.isna(scooter.akkustand):
            battery = f"{scooter.akkustand}%"
        popup = (
            f"<b>Anbieter:</b> {escape(str(scooter.anbieter))}<br>"
            f"<b>Akku:</b> {escape(str(battery))}<br>"
            f"<b>ID:</b> {escape(str(scooter.id))}"
        )
        folium.Marker(
            location=[scooter.lat, scooter.lon],
            tooltip=escape(str(scooter.anbieter)),
            popup=folium.Popup(popup, max_width=300),
            icon=folium.Icon(color="green", icon="flash", prefix="fa"),
        ).add_to(scooter_map)

    st_folium(scooter_map, use_container_width=True, height=600, key="scooter_map")
    if visible_scooters.empty:
        st.info(
            "Im eingestellten Umkreis wurden keine frei fahrenden E-Scooter "
            "gemeldet. Station-basierte Parkzonen sind keine einzelnen "
            "Scooter-Positionen und werden nicht mitgezählt."
        )

st.caption(
    f"Quelle: Schweizerisches Bundesamt für Energie (BFE), "
    f"[Shared-Mobility-Datensatz]({SOURCE_URL})."
)
