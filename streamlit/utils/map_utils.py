import folium
import streamlit as st
import osmnx as ox

def initialize_map(location):
    return folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=15,
        max_zoom=20,
        tiles="cartodbpositron",
        control_scale=True,
    )

def add_district_boundaries(map_object, location_name):
    district = ox.geocode_to_gdf(location_name)
    folium.GeoJson(district).add_to(map_object)
    return map_object
