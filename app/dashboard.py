import folium
import osmnx as ox
import streamlit as st
from geopy.geocoders import Nominatim


def draw_street(street_name):
    street = geo_data[geo_data["name"].str.contains(street_name, case=False)].unary_union

    try:
        benches = geo_data[(geo_data["amenity"] == "bench") & (geo_data.distance(street) < 0.0001)]
    except:
        benches = []

    color = "red" if len(benches) <= 1 else "green"
    # calculate the distance between each bench:
    distances = [benches.iloc[i].geometry.distance(benches.iloc[i-1].geometry) * 100000 for i in range(1, len(benches))]
    # check if any of the distances is greater than 150 meters:
    if any([distance > 150 for distance in distances]):
        color = "red"

    # draw the distance that is greater than 150 meters:
    for i, distance in enumerate(distances):
        if distance > 150 and show_yellow:
            folium.PolyLine(
                locations=[
                    [benches.iloc[i].geometry.y, benches.iloc[i].geometry.x],
                    [benches.iloc[i+1].geometry.y, benches.iloc[i+1].geometry.x],
                ],
                color="yellow",
                weight=3,
                opacity=0.3,
            ).add_to(m)

    if (show_without_benches) or (not show_without_benches and len(benches) > 0):
        if color == "red" and show_red: # why is color dynamic >:(
            folium.GeoJson(
                street,
                style_function=lambda feature: {
                    "color": "red",
                    "weight": 5,
                    "opacity": 0.5,
                },
            ).add_to(m)

        elif color == "green" and show_green:
            folium.GeoJson(
                street,
                style_function=lambda feature: {
                    "color": "green",
                    "weight": 5,
                    "opacity": 0.5,
                },
            ).add_to(m)

    if len(benches)>0 and show_benches:
        for i, bench in benches.iterrows():
            icon = folium.features.CustomIcon(
                "https://cdn-icons-png.flaticon.com/256/2256/2256995.png",
                icon_size=(15, 15),
            )
            folium.Marker(
                location=[bench.geometry.y, bench.geometry.x],
                icon=icon,
                popup=f"<b>{benches.index.get_loc(i)+1}/{len(benches)}</b><br>belongs to <i>{street_name}</i>",
            ).add_to(m)



st.set_page_config(layout="wide", page_title="Street Highlighter", page_icon="🗺️")

geolocator = Nominatim(user_agent="street-highlighter")
location = location = geolocator.geocode(f"Półwiejska, Poznań")


with st.sidebar:
    city = st.text_input("Enter a city:", "Poznań").title()
    street_name = st.text_input("Enter a street:", "Półwiejska").title()
    street_length = st.slider(
        "Street length *m* (only change for large streets):", 0, 10000, 1000
    )
    st.markdown("---")
    show_benches = st.checkbox("Show benches", value=True)
    show_without_benches = st.checkbox("Show streets without benches", value=True)
    show_red = st.checkbox("Show red streets", value=True)
    show_green = st.checkbox("Show green streets", value=True)
    show_yellow = st.checkbox("Show distances", value=True)
    st.markdown("---")
    if st.button("Show"):
        location = geolocator.geocode(f"{street_name}, {city}")


if location:
    m = folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=15,
        max_zoom=20,
        tiles="cartodbpositron",
    )

    geo_data = ox.features_from_address(
        f"{street_name}, {city}",
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
            ],
            "amenity": "bench",
        },
    )
    geo_data["name"].fillna("", inplace=True)

    if street_name:
        draw_street(street_name)
    else:        
        for street_name in geo_data[geo_data["amenity"] != "bench"]["name"].unique():
            if street_name not in ["", "Stanisława Taczaka", "Forum Academicum"]:
                draw_street(street_name)

    st.components.v1.html(m._repr_html_(), height=800)