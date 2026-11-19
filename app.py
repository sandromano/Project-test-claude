"""Streamlit-Oberfläche für die E-Scooter-Karte und den ML-Platzhalter."""

from html import escape

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.api_client import APIClientError, SOURCE_URL, get_scooters
from src.opendatahub_client import (
    OPENDATAHUB_SOURCE_URL,
    OpenDataHubClientError,
    SHARING_STATION_COLUMNS,
    get_sharing_stations,
)
from src.settings import load_settings


SETTINGS = load_settings()
st.set_page_config(page_title="E-Scooter Finder", page_icon="🛴", layout="wide")


@st.cache_data(ttl=SETTINGS.cache_ttl_seconds)
def load_scooters():
    return get_scooters(SETTINGS)


@st.cache_data(ttl=SETTINGS.cache_ttl_seconds)
def load_sharing_stations():
    return get_sharing_stations(SETTINGS)


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
        load_sharing_stations.clear()

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
    show_sharing_stations = st.sidebar.checkbox(
        "Open Data Hub-Stationen anzeigen",
        value=True,
    )
    sharing_station_error = None
    try:
        sharing_stations = load_sharing_stations()
    except OpenDataHubClientError as exc:
        sharing_stations = pd.DataFrame(columns=SHARING_STATION_COLUMNS)
        sharing_station_error = exc
        if show_sharing_stations:
            st.warning(f"Open-Data-Hub-Stationen konnten nicht geladen werden: {exc}")

    metric_scooters, metric_stations = st.columns(2)
    metric_scooters.metric("Verfügbare Scooter", len(visible_scooters))
    metric_stations.metric("Leihstationen", len(sharing_stations))

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

    station_layer = folium.FeatureGroup(
        name="Open Data Hub: Leihstationen",
        show=show_sharing_stations,
    )
    for station in sharing_stations.itertuples(index=False):
        popup = (
            f"<b>System:</b> {escape(str(station.anbieter))}<br>"
            f"<b>Station:</b> {escape(str(station.name))}<br>"
            f"<b>ID:</b> {escape(str(station.id))}<br>"
            "Standort einer Sharing-Station, kein einzelner Scooter"
        )
        folium.Marker(
            location=[station.lat, station.lon],
            tooltip=escape(str(station.name)),
            popup=folium.Popup(popup, max_width=300),
            icon=folium.Icon(color="blue", icon="bicycle", prefix="fa"),
        ).add_to(station_layer)
    station_layer.add_to(scooter_map)
    folium.LayerControl().add_to(scooter_map)

    st_folium(scooter_map, use_container_width=True, height=600, key="scooter_map")
    if visible_scooters.empty:
        st.info(
            "Im eingestellten Umkreis wurden keine frei fahrenden E-Scooter "
            "gemeldet. Station-basierte Parkzonen sind keine einzelnen "
            "Scooter-Positionen und werden nicht mitgezählt."
        )
    if show_sharing_stations and sharing_stations.empty and not sharing_station_error:
        st.info(
            "Open Data Hub meldet im eingestellten Umkreis keine Sharing-Stationen. "
            "Die veröffentlichten Scooter-Sharing-Stationen liegen derzeit ausserhalb "
            "von St. Gallen."
        )

st.caption(
    f"Quellen: Schweizerisches Bundesamt für Energie (BFE), "
    f"[Shared-Mobility-Datensatz]({SOURCE_URL}); "
    f"[Open Data Hub Mobility API]({OPENDATAHUB_SOURCE_URL})."
)
