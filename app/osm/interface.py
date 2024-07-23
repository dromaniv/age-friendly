import os
import folium
import numpy as np
import osmnx as ox
import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
from dashboard.models import AppSettings
from shapely.geometry import Point, Polygon, MultiPoint, LineString
from django.conf import settings
from utils.statistics import *
from utils.benches_sidewalks import *
from utils.simulation import *
from utils.drawing import *
from utils.classification import *

def get_map(
    user,
    location_name,
    show_benches,
    show_options,
    good_distance,
    okay_distance,
    simulation,
    budget,
    bench_cost,
):
    budget = float(budget) if budget != "" else None
    bench_cost = float(bench_cost) if bench_cost != "" else None

    # Get settings
    app_settings = AppSettings.objects.get(user=user)
    benches_file = app_settings.benches_file if app_settings.benches_file else None

    # Find location
    location = geolocator.geocode(location_name)

    # Create Folium map
    m = folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=15,
        max_zoom=20,
        tiles="cartodbpositron",
        use_container_width=True,
    )

    # Get the district boundaries and add to the map
    district = ox.geocode_to_gdf(location_name)
    folium.GeoJson(district).add_to(m)

    # Find streets inside the district
    sidewalks_gdf = get_sidewalks(location_name)

    # Find benches inside the district
    benches_gdf = get_benches(location_name, district, benches_file)

    # Close bench file
    if benches_file is not None:
        benches_file.close()

    # Assign benches to sidewalks
    sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    # Simulate benches
    if simulation:
        num_benches = calculate_benches(budget, bench_cost)
        benches_gdf = add_optimized_benches(
            benches_gdf, sidewalks_gdf, num_benches, good_distance
        )
        sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    # Draw benches
    if show_benches:
        m = draw_benches(m, benches_gdf)

    # Classify sidewalks
    sidewalks_gdf = classify_sidewalks(sidewalks_gdf, good_distance, okay_distance)

    # Draw sidewalks
    colors = {
        "good_street_color": app_settings.good_color,
        "okay_street_color": app_settings.okay_color,
        "bad_street_color": app_settings.bad_color,
        "one_street_color": app_settings.one_color,
        "zero_street_color": app_settings.empty_color,
    }

    m = draw_sidewalks(m, sidewalks_gdf, show_options, colors)._repr_html_()

    # Calculate statistics
    street_stats, general_stats = get_basic_statistics(sidewalks_gdf)

    # Add statistics as HTML
    m += "<br><br>"
    m += street_stats.to_html(classes="table table-striped table-hover")
    m += general_stats.to_html(classes="table table-striped table-hover")

    return m


def get_heatmap(user, location_name):
    app_settings = AppSettings.objects.get(user=user)

    location = geolocator.geocode(location_name)

    # read file in the static folder
    df = pd.read_excel(
        os.path.join(settings.STATICFILES_DIRS[0], app_settings.heatmap_file.name)
    )

    inhabitants = df["LICZBA"].tolist()
    inhabitants = list(dict.fromkeys(inhabitants))  # delete duplicate values
    inhabitants.sort()

    # slice 'MultiLineString ((' and ')' from the rows of df['boundaries']
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
    ]  # these aint right, just omit them

    df_filtered = df[~df["OBJECTID"].isin(problematic_ids)]

    # Create a Folium map centered at Poznań
    m = folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=13,
        max_zoom=20,
        tiles="cartodbpositron",
        use_container_width=True,
    )

    for index, row in df_filtered.iterrows():
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
        # Pass the color as a default argument to the lambda function
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

    return m
