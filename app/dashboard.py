import folium
import osmnx as ox
import streamlit as st
from geopy.geocoders import Nominatim


st.set_page_config(layout="wide", page_title="Street Highlighter", page_icon="🗺️")

geolocator = Nominatim(user_agent="street-highlighter")
location = location = geolocator.geocode(f"Półwiejska, Poznań")


with st.sidebar:
    city = st.text_input("Enter a city:", "Poznań").title()
    street = st.text_input("Enter a street:", "Półwiejska").title()
    street_length = st.slider(
        "Street length *m* (only change for large streets):", 0, 10000, 1000
    )

    if st.button("Show"):
        location = geolocator.geocode(f"{street}, {city}")


if location:
    m = folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=15,
    )

    streets = ox.features_from_address(
        f"{street}, {city}",
        dist=street_length,
        tags={
            "highway": [
                "primary",
                "secondary",
                "tertiary",
                "residential",
                "pedestrian",
                "service",
                "living_street",
                "unclassified",
            ]
        },
    )
    street = streets[streets["name"] == street]  # maybe change to contains

    folium.GeoJson(
        street,
        style_function=lambda x: {"color": "#ff0000", "weight": 5, "opacity": 0.5},
    ).add_to(m)

    st.components.v1.html(m._repr_html_(), height=800)

    st.write(street)
else:
    pass
