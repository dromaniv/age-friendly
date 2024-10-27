import requests
import osmnx as ox
import streamlit as st


@st.cache_data
def get_districts(city_name, admin_level=9):
    # Overpass API Query
    query = f"""
    [out:json];
    area[name="{city_name}"]->.searchArea;
    (
      rel(area.searchArea)["admin_level"="{admin_level}"];
    );
    out body;
    """

    # URL of the Overpass API
    url = "http://overpass-api.de/api/interpreter"

    # Send request to Overpass API
    response = requests.get(url, params={"data": query})
    data = response.json()

    # Extract district names
    districts = [
        element["tags"]["name"]
        for element in data["elements"]
        if "name" in element["tags"]
    ]

    # Sort districts alphabetically
    districts.sort()

    return districts


@st.cache_data
def get_district_geodataframe(location_name):
    return ox.geocode_to_gdf(location_name)
