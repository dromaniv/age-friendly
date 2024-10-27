from geopy.geocoders import Nominatim
import osmnx as ox
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import streamlit as st

geolocator = Nominatim(user_agent="age_friendly")


def get_location(location_name):
    return geolocator.geocode(location_name)


@st.cache_data
def get_sidewalks(location_name):
    # Find streets inside the district
    sidewalks_gdf = ox.features_from_place(location_name, tags={"highway": ["footway"]})
    # Data preprocessing:
    # Remove polygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "Polygon"]
    # Remove multipolygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "MultiPolygon"]
    # Remove crossings only if there are footways in the street
    if "footway" in sidewalks_gdf.columns:
        if sidewalks_gdf[sidewalks_gdf["footway"] == "crossing"].shape[0] > 0:
            sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["footway"] != "crossing"]
    # Calculate the length of each sidewalk
    sidewalks_gdf["length"] = sidewalks_gdf.geometry.length
    # Remove short sidewalks from the original GeoDataFrame
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["length"] >= 0.0005]
    return sidewalks_gdf


def get_benches(location_name, district, benches_file=None):
    # Find benches inside the district
    try:
        benches_gdf = ox.features_from_place(location_name, tags={"amenity": "bench"})
    except:
        st.error("We don't have data for this location :(")
        st.stop()
    # Parse benches file
    if benches_file is not None:
        imported_benches = pd.read_excel(benches_file)
        if "lon" in imported_benches.columns and "lat" in imported_benches.columns:
            imported_benches["geometry"] = imported_benches.apply(
                lambda row: Point(row["lon"], row["lat"]), axis=1
            )
            imported_benches["amenity"] = "import"
            benches_gdf = pd.concat([benches_gdf, imported_benches])
            benches_gdf = benches_gdf[benches_gdf.within(district.geometry[0])]
        else:
            print(
                "The uploaded file does not contain `lat` and `lon` columns. Ignoring..."
            )
    # Get rid of benches without geometry
    benches_gdf = benches_gdf[benches_gdf.geometry.notnull()]
    # Get rid of duplicates
    benches_gdf = benches_gdf.drop_duplicates(subset="geometry")
    return benches_gdf


def assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf):
    # Buffer sidewalks slightly to include nearby benches
    buffer_sidewalks = sidewalks_gdf.geometry.buffer(
        0.0001
    )  # Adjust buffer size as needed
    sidewalks_gdf["benches"] = buffer_sidewalks.apply(
        lambda x: benches_gdf[benches_gdf.within(x)].geometry.tolist()
    )
    return sidewalks_gdf


def calculate_benches(budget, bench_cost):
    return int(budget // bench_cost)
