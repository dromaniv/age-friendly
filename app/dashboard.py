import os
import math
import folium
import locale
import requests
import numpy as np
import osmnx as ox
import pandas as pd
import streamlit as st
import geopandas as gpd
from geopy.geocoders import Nominatim
from shapely.ops import nearest_points
from shapely.geometry import Point, LineString, Polygon


# Caching functions for faster loading
@st.cache_data
def get_sidewalks(location_name):
    # Find streets inside the district
    sidewalks_gdf = ox.features_from_place(location_name, tags={"highway": ["footway", "residential","tertiary", "unclassified", "secondary", "primary"]})
    # Data preprocessing:
    # Remove polygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "Polygon"]
    # Remove multipolygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "MultiPolygon"]
    # Remove crossings only if there are footways in the street
    if 'footway' in sidewalks_gdf.columns:
        if sidewalks_gdf[sidewalks_gdf["footway"] == "crossing"].shape[0] > 0:
            sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["footway"] != "crossing"]
    # Calculate the length of each sidewalk
    sidewalks_gdf["length"] = sidewalks_gdf.geometry.length
    # Remove short sidewalks from the original GeoDataFrame
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["length"] >= 0.0005]
    return sidewalks_gdf

@st.cache_data
def get_benches(location_name, _district, benches_file=None):
    # Find benches inside the district
    benches_gdf = ox.features_from_place(location_name, tags={"amenity": "bench"})

    # Parse benches file
    if benches_file is not None:
        if benches_file.name.endswith(".csv"):
            imported_benches = pd.read_csv(benches_file, sep=";")
        elif benches_file.name.endswith(".xlsx"):
            imported_benches = pd.read_excel(benches_file)
        else:
            st.warning("Invalid file format. Only CSV and XLSX files are supported.")
            return benches_gdf
        if "lon" in imported_benches.columns and "lat" in imported_benches.columns:
            imported_benches["geometry"] = imported_benches.apply(
                lambda row: Point(row["lon"], row["lat"]), axis=1
            )
            benches_gdf = pd.concat([benches_gdf, imported_benches])
            benches_gdf = benches_gdf[benches_gdf.within(district.geometry[0])]
        else:
            st.warning(
                "The uploaded file does not contain `lon` and `lat` columns. Ignoring..."
            )
    return benches_gdf

def segment_streets(streets_gdf, max_length):
    new_geometries = []
    expanded_data = {column: [] for column in streets_gdf.columns if column != 'geometry'}
    
    for _, row in streets_gdf.iterrows():
        segments = segment_line(row.geometry, max_length)
        new_geometries.extend(segments)
        for column in expanded_data:
            expanded_data[column].extend([row[column]] * len(segments))

    new_streets_gdf = gpd.GeoDataFrame(expanded_data, geometry=new_geometries, crs=streets_gdf.crs)
    return new_streets_gdf


def segment_line(line, max_length):
    num_segments = math.ceil(line.length / max_length)
    segments = []

    for i in range(num_segments):
        start_dist = i * max_length
        end_dist = min(start_dist + max_length, line.length)
        if end_dist < line.length:
            segment = LineString([line.interpolate(start_dist), line.interpolate(end_dist)])
        else:
            segment = LineString([line.interpolate(start_dist), line.coords[-1]])
        segments.append(segment)

    return segments

def classify_sidewalks(sidewalks_gdf, benches_gdf, good_street_value, okay_street_value):
    # Assign benches geometry list to each sidewalk
    buffer_sidewalks = sidewalks_gdf.geometry.buffer(0.00007)
    sidewalks_gdf["benches"] = buffer_sidewalks.apply(
        lambda x: benches_gdf[benches_gdf.within(x)].geometry.tolist()
    )

    # Function to check if there is a bench every meters along the sidewalk
    def is_benched_every_x_meters(sidewalk, meters):
        geometry = sidewalk.geometry
        benches = sidewalk.benches
        length = geometry.length
        num_segments = int(np.ceil(length / meters))

        for i in range(num_segments):
            try:
                segment_point = geometry.interpolate(i * meters)
                close_bench = any([segment_point.distance(bench) <= meters for bench in benches])
                if not close_bench:
                    return False
            except:
                st.error(geometry)
        return True
    
    # Classify sidewalks
    sidewalks_gdf["good"] = sidewalks_gdf.apply(
        lambda x: is_benched_every_x_meters(x, good_street_value), axis=1
    )
    sidewalks_gdf["okay"] = sidewalks_gdf.apply(
        lambda x: is_benched_every_x_meters(x, okay_street_value), axis=1
    )
    sidewalks_gdf["bad"] = sidewalks_gdf.apply(
        lambda x: not is_benched_every_x_meters(x, okay_street_value), axis=1
    )
    return sidewalks_gdf


@st.cache_data
def generate_heatmap(location_name):
    location = geolocator.geocode(location_name)

    # read file in the same directory as the script
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), "poprodukcyjny.xlsx"))

    inhabitants = df["LICZBA"].tolist()
    inhabitants = list(dict.fromkeys(inhabitants))  # delete duplicate values
    inhabitants.sort()

    # slice 'MultiLineString ((' and ')' from the rows of df['boundaries']
    df["boundaries"] = df["boundaries"].str.replace(
        r"^MultiLineString \(\(", "", regex=True
    )
    df["boundaries"] = df["boundaries"].str.replace(r"\)\)$", "", regex=True)

    problematic_ids = [2503, 2760, 3255, 3535, 3546, 3564, 3565, 3566, 3576, 3579, 3583, 3601, 3645] # these aint right, just omit them

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

    return m._repr_html_()


# Calculate the color based on the value of inhabitants
def color_B_to_R(inhabitants, value):
    min_ratio = 0
    max_ratio = (len(inhabitants) - 1) / len(inhabitants)
    index = inhabitants.index(value)

    # calculate the ratio based on the index
    ratio = index / len(inhabitants)

    # interpolate between blue and red based on the ratio
    red_value = int((1 - ratio) * 255)  # More red when ratio is close to 0
    blue_value = int(ratio * 255)  # More blue when ratio is close to 1

    # create a color in RGB format
    color = f"#{blue_value:02X}00{red_value:02X}"

    return color

def get_districts(city_name):
    # Doesn't even work that well (e.g. no Łacina)
    # Overpass API Query
    # This query looks for nodes tagged as 'place=suburb' within the city
    query = f"""
    [out:json];
    area[name="{city_name}"]->.searchArea;
    (
      rel(area.searchArea)["admin_level"="9"];
    );
    out body;
    """

    # URL of the Overpass API
    url = "http://overpass-api.de/api/interpreter"

    # Send request to Overpass API
    response = requests.get(url, params={"data": query})
    data = response.json()

    # Extract district names
    districts = [element["tags"]["name"] for element in data["elements"]]

    # Sort districts alphabetically
    districts.sort(key=locale.strxfrm)

    return districts


# Set page configuration
st.set_page_config(layout="wide", page_title="Street Highlighter", page_icon="🗺️")
st.markdown(  # hardcoded style for the sidebar and the map
    """<style>
        .st-emotion-cache-10oheav.eczjsme4 {
            padding-top: 16px;
        }
        .st-emotion-cache-z5fcl4.ea3mdgi4 {
            padding-top: 32px;
        }
        </style>
        """,
    unsafe_allow_html=True,
)
locale.setlocale(locale.LC_COLLATE, "pl_PL.UTF-8")
geolocator = Nominatim(user_agent="street-highlighter")


# Sidebar for user input
with st.sidebar:
    city = st.selectbox("Select a city:", ["Poznań", "Hasselt", "Żnin"])
    districts = get_districts(city)
    district_name = st.selectbox(
        "Select a district:",
        [""] + districts, # + ["ALL"]
    )
    if district_name == "":
        # Handle heatmap
        st.warning("You can select a district or see the heatmap.")
        heatmap = generate_heatmap(city)
    else:
        # Handle districts and main functionality
        if district_name == "ALL":
            location_name = f"{city}"
        else:
            location_name = f"{district_name}, {city}"

        st.write("# Map options:")
        show_benches = st.checkbox("Show benches", value=True)
        st.write("\n")

        col1, col2 = st.columns(2)
        with col1:
            show_good_streets = st.checkbox("Show good streets", value=True)
        with col2:
            good_street_color = st.color_picker("Good street color", value="#009900")
        col3, col4 = st.columns(2)
        with col3:
            show_okay_streets = st.checkbox("Show okay streets", value=True)
        with col4:
            okay_street_color = st.color_picker("Okay street color", value="#FFA500")
        col5, col6 = st.columns(2)
        with col5:
            show_bad_streets = st.checkbox("Show bad streets", value=True)
        with col6:
            bad_street_color = st.color_picker("Bad street color", value="#FF0000")
        col7, col8 = st.columns(2)
        with col7:
            good_street_value = st.slider(
                "Good street distance", min_value=0, max_value=300, value=50
            ) / 111320
        with col8:
            okay_street_value = st.slider(
                "Okay street distance", min_value=0, max_value=300, value=150
            ) / 111320
        col9, col10 = st.columns(2)
        with col9:
            show_one_streets = st.checkbox("Show streets with 1 bench", value=True)
        with col10:
            one_street_color = st.color_picker("1 bench street color", value="#0000FF")
        col11, col12 = st.columns(2)
        with col11:
            show_zero_streets = st.checkbox("Show streets with 0 benches", value=True)
        with col12:
            zero_street_color = st.color_picker("0 bench street color", value="#000000")

        st.write("\n")
        benches_file = st.file_uploader("Upload benches file", type=["csv", "xlsx"])
        st.write(
            "ℹ️ The file should contain `lon` and `lat` columns with coordinates of benches."
        )

# Heatmap
if district_name == "":
    st.components.v1.html(heatmap, height=4320, scrolling=False)
    st.markdown(
        """<style>
            .st-emotion-cache-z5fcl4.ea3mdgi4 {
                overflow: hidden;
            }
            """,
        unsafe_allow_html=True,
    )
    st.stop()

# Initialize progress bar
step_text = st.empty()
progress_bar = st.progress(0)
step_text.text("Finding location...")

# Find location
location = geolocator.geocode(location_name)

progress_bar.progress(5)
step_text.text("Creating map...")

# Create Folium map
m = folium.Map(
    location=[location.latitude, location.longitude],
    zoom_start=15,
    max_zoom=20,
    tiles="cartodbpositron",
    use_container_width=True,
)

progress_bar.progress(10)
step_text.text("Adding district boundaries...")

# Get the district boundaries and add to the map
district = ox.geocode_to_gdf(location_name)
folium.GeoJson(district).add_to(m)

progress_bar.progress(15)
step_text.text("Finding sidewalks...")

# Find streets inside the district
sidewalks_gdf = get_sidewalks(location_name)

progress_bar.progress(25)
step_text.text("Finding benches...")

# Find benches inside the district
benches_gdf = get_benches(location_name, district, benches_file)

progress_bar.progress(35)
if show_benches:
    step_text.text("Drawing benches...")

    # Draw benches on the map
    for bench in benches_gdf.iterrows():
        icon = folium.features.CustomIcon(
            "https://cdn-icons-png.flaticon.com/256/2256/2256995.png",
            icon_size=(15, 15),
        )
        bench_coords = bench[1].geometry.centroid.coords[0]
        if bench[1]["amenity"] != "bench":
            tooltip = "Imported bench"
        else:
            tooltip = None
        folium.Marker(
            location=[bench_coords[1], bench_coords[0]], icon=icon, tooltip=tooltip
        ).add_to(m)

progress_bar.progress(40)
step_text.text("Classifying sidewalks...")

sidewalks_class = classify_sidewalks(sidewalks_gdf, benches_gdf, good_street_value, okay_street_value)

progress_bar.progress(50)
step_text.text("Drawing sidewalks...")

for index, sidewalk in enumerate(sidewalks_class.iterrows()):
    if sidewalk[1]["good"] and show_good_streets:
        folium.GeoJson(
            sidewalk[1].geometry,
            style_function=lambda x: {
                "color": good_street_color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk[1].benches)}",
        ).add_to(m)
    elif sidewalk[1]["okay"] and show_okay_streets:
        folium.GeoJson(
            sidewalk[1].geometry,
            style_function=lambda x: {
                "color": okay_street_color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk[1].benches)}",
        ).add_to(m)
    elif sidewalk[1]["bad"] and show_bad_streets:
        folium.GeoJson(
            sidewalk[1].geometry,
            style_function=lambda x: {
                "color": bad_street_color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk[1].benches)}",
        ).add_to(m)
    if len(sidewalk[1].benches) == 1 and show_one_streets:
        folium.GeoJson(
            sidewalk[1].geometry,
            style_function=lambda x: {
                "color": one_street_color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk[1].benches)}",
        ).add_to(m)
    if len(sidewalk[1].benches) == 0 and show_zero_streets:
        folium.GeoJson(
            sidewalk[1].geometry,
            style_function=lambda x: {
                "color": zero_street_color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk[1].benches)}",
        ).add_to(m)
    progress_bar.progress(0.5 + (index + 1) / len(sidewalks_gdf) / 2)

# Reset progress bar
progress_bar.empty()
step_text.empty()

# Load and configure map
st.components.v1.html(m._repr_html_(), height=4320, scrolling=False)
st.markdown(
    """<style>
        .st-emotion-cache-z5fcl4.ea3mdgi4 {
            overflow: hidden;
        }
        """,
    unsafe_allow_html=True,
)