import folium
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import streamlit as st
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="age_friendly")


@st.cache_data
def generate_heatmap(location_name, heatmap_file_path):
    location = geolocator.geocode(location_name)

    # Read data from Excel file
    df = pd.read_excel(heatmap_file_path)

    inhabitants = sorted(set(df["LICZBA"].tolist()))

    # Clean up 'boundaries' column in df
    df["boundaries"] = df["boundaries"].str.replace(
        r"^MultiLineString \(\(", "", regex=True
    )
    df["boundaries"] = df["boundaries"].str.replace(r"\)\)$", "", regex=True)

    problematic_ids = [
        2503,
        2760,
        3255,
        3535,
        3546,
        3564,
        3565,
        3566,
        3576,
        3579,
        3583,
        3601,
        3645,
    ]
    df_filtered = df[~df["OBJECTID"].isin(problematic_ids)]

    # Create a Folium map centered at the location
    m = folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=13,
        max_zoom=20,
        tiles="cartodbpositron",
        control_scale=True,
    )

    for _, row in df_filtered.iterrows():
        # Split the string into individual coordinate pairs
        coordinate_pairs = row["boundaries"].split(", ")

        # Calculate the color based on the value of inhabitants
        color = color_B_to_R(inhabitants, row["LICZBA"])

        # Convert each coordinate pair into a tuple of floats
        points = [tuple(map(float, pair.split())) for pair in coordinate_pairs]

        # Create a Shapely Polygon from the list of points
        polygon = Polygon(points)

        # Convert the Polygon to a GeoJSON feature
        feature = gpd.GeoSeries([polygon]).__geo_interface__

        # Add the GeoJSON feature to the Folium map
        folium.GeoJson(
            feature,
            style_function=lambda x, color=color: {
                "fillColor": color,
                "color": color,
                "weight": 2.5,
                "fillOpacity": 0.3,
            },
            tooltip=f"{row['LICZBA']} people",
        ).add_to(m)

    return m._repr_html_()


def generate_heatmap_layer(m, heatmap_file_path, district_gdf, opacity):
    # Read data from Excel file
    df = pd.read_excel(heatmap_file_path)

    # Clean up 'boundaries' column in df
    df["boundaries"] = df["boundaries"].str.replace(
        r"^MultiLineString \(\(", "", regex=True
    )
    df["boundaries"] = df["boundaries"].str.replace(r"\)\)$", "", regex=True)

    problematic_ids = [
        2503,
        2760,
        3255,
        3535,
        3546,
        3564,
        3565,
        3566,
        3576,
        3579,
        3583,
        3601,
        3645,
    ]
    df_filtered = df[~df["OBJECTID"].isin(problematic_ids)]

    # Create geometry from 'boundaries' column
    def boundary_to_polygon(boundary_str):
        coordinate_pairs = boundary_str.split(", ")
        points = [tuple(map(float, pair.split())) for pair in coordinate_pairs]
        polygon = Polygon(points)
        return polygon

    df_filtered["geometry"] = df_filtered["boundaries"].apply(boundary_to_polygon)
    gdf = gpd.GeoDataFrame(df_filtered, geometry="geometry")
    gdf.set_crs(epsg=4326, inplace=True)
    district_gdf = district_gdf.to_crs(epsg=4326)

    # Get polygons within the district
    gdf_in_district = gpd.overlay(gdf, district_gdf, how="intersection")
    inhabitants = sorted(set(df["LICZBA"].tolist()))

    # Add polygons to the map
    for _, row in gdf_in_district.iterrows():
        color = color_B_to_R(inhabitants, row["LICZBA"])
        feature = folium.GeoJson(
            row["geometry"],
            style_function=lambda x, color=color: {
                "fillColor": color,
                "color": color,
                "weight": 2.5,
                "fillOpacity": opacity,
            },
            tooltip=f"{row['LICZBA']} people",
        )
        feature.add_to(m)

    return m


def color_B_to_R(inhabitants, value):
    index = inhabitants.index(value)
    ratio = index / len(inhabitants)
    red_value = int((1 - ratio) * 255)  # More red when ratio is close to 0
    blue_value = int(ratio * 255)  # More blue when ratio is close to 1
    # create a color in RGB format
    color = f"#{blue_value:02X}00{red_value:02X}"
    return color
