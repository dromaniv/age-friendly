import os
import folium
import requests
import osmnx as ox
import pandas as pd
import streamlit as st
import geopandas as gpd
from geopy.geocoders import Nominatim
from shapely.geometry import Polygon
from utils.statistics import get_basic_statistics
from utils.benches_sidewalks import (
    calculate_benches,
    get_sidewalks,
    get_benches,
    assign_benches_to_sidewalks,
)
from utils.simulation import add_optimized_benches
from utils.drawing import draw_benches, draw_sidewalks
from utils.classification import classify_sidewalks
from streamlit_folium import st_folium

# Set page configuration
st.set_page_config(layout="wide", page_title="Age Friendly", page_icon="🗺️")


geolocator = Nominatim(user_agent="street-highlighter")

# Initialize session state for simulation status
if "simulate_status" not in st.session_state:
    st.session_state.simulate_status = False


# Function to generate heatmap
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


# Helper function for color calculation
def color_B_to_R(inhabitants, value):
    index = inhabitants.index(value)
    ratio = index / len(inhabitants)
    red_value = int((1 - ratio) * 255)  # More red when ratio is close to 0
    blue_value = int(ratio * 255)  # More blue when ratio is close to 1
    # create a color in RGB format
    color = f"#{blue_value:02X}00{red_value:02X}"
    return color


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


def draw_and_simulate_map(
    location_name,
    benches_file,
    show_benches,
    show_good_streets,
    good_street_color,
    show_okay_streets,
    okay_street_color,
    show_bad_streets,
    bad_street_color,
    show_one_streets,
    one_street_color,
    show_zero_streets,
    zero_street_color,
    good_street_value,
    okay_street_value,
    budget=None,
    bench_cost=None,
):
    # Initialize progress bar
    step_text = st.empty()
    progress_bar = st.progress(0)
    step_text.text("Finding location...")

    # Find location
    location = geolocator.geocode(location_name)

    # Create Folium map
    progress_bar.progress(10)
    step_text.text("Creating map...")
    m = initialize_map(location)

    # Add district boundaries
    progress_bar.progress(20)
    step_text.text("Adding district boundaries...")
    m = add_district_boundaries(m, location_name)

    # Find sidewalks inside the district
    progress_bar.progress(30)
    step_text.text("Finding sidewalks...")
    sidewalks_gdf = get_sidewalks(location_name)

    # Find benches inside the district
    progress_bar.progress(40)
    step_text.text("Finding benches...")
    district = ox.geocode_to_gdf(location_name)  # Fetch the district data
    benches_gdf = get_benches(location_name, district, benches_file)

    progress_bar.progress(50)
    step_text.text("Assigning benches to sidewalks...")
    sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    # If simulation is activated
    if (
        st.session_state.simulate_status
        and budget is not None
        and bench_cost is not None
    ):
        num_benches = calculate_benches(budget, bench_cost)
        benches_gdf = add_optimized_benches(
            benches_gdf, sidewalks_gdf, num_benches, good_street_value
        )
        sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    progress_bar.progress(60)
    step_text.text("Drawing benches...")
    if show_benches:
        m = draw_benches(m, benches_gdf)

    progress_bar.progress(70)
    step_text.text("Classifying sidewalks...")
    sidewalks_class = classify_sidewalks(
        sidewalks_gdf, good_street_value, okay_street_value
    )

    progress_bar.progress(80)
    step_text.text("Drawing sidewalks...")
    show_options = {
        "good_streets": show_good_streets,
        "okay_streets": show_okay_streets,
        "bad_streets": show_bad_streets,
        "one_streets": show_one_streets,
        "zero_streets": show_zero_streets,
    }
    colors = {
        "good_street_color": good_street_color,
        "okay_street_color": okay_street_color,
        "bad_street_color": bad_street_color,
        "one_street_color": one_street_color,
        "zero_street_color": zero_street_color,
    }
    m = draw_sidewalks(m, sidewalks_class, show_options, colors)

    # Calculate statistics
    progress_bar.progress(90)
    step_text.text("Calculating statistics...")
    street_stats, general_stats = get_basic_statistics(
        sidewalks_class, district, heatmap_file
    )

    # Generate statistics HTML
    stats_html = street_stats.to_html(classes="table-style", index=False)
    stats_html += general_stats.to_html(classes="table-style", index=False)

    # Display the map using st_folium for better responsiveness
    progress_bar.progress(99)
    step_text.text("Loading map...")
    st_folium(m, width="100%", returned_objects=[])

    # Custom CSS for table styling
    st.markdown(
        """
        <style>
        .table-style {
            border-collapse: collapse;
            width: 100%;
            font-size: 14px;
        }
        .table-style td, .table-style th {
            border: 1px solid #ddd;
            padding: 8px;
        }
        .table-style tr:nth-child(even){background-color: #5D8AA8;}  /* Light blue */
        .table-style tr:hover {background-color: #ADD8E6;}
        .table-style th {
            padding-top: 12px;
            padding-bottom: 12px;
            text-align: left;
            background-color: #00008B;
            color: white;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Display the statistics
    st.markdown(stats_html, unsafe_allow_html=True)

    # Reset progress bar
    progress_bar.empty()
    step_text.empty()


# Sidebar for user input
with st.sidebar:
    admin_level = st.slider(
        "Admin Level",
        min_value=7,
        max_value=11,
        value=9,
        help="Select the administrative level for what constitutes a district. Lower values are more general (e.g. city), higher values are more specific (e.g. neighborhood).",
    )
    city = st.text_input("City:", value="Poznań", help="ℹEnter the name of the city.")
    districts = get_districts(city, admin_level)
    district_name = st.selectbox(
        "District:",
        [""] + districts,
        help="ℹSelect the district to highlight on the map.",
    )
    if f"{city}.xlsx" in os.listdir(os.path.join(os.getcwd(), "static")):
        heatmap_file = os.path.join(os.getcwd(), "static", f"{city}.xlsx")
    else:
        heatmap_file = st.file_uploader(
            "Upload heatmap file",
            type=["xlsx"],
            help="The file should contain `LICZBA` and `boundaries` columns with population and boundaries data.",
        )

    if heatmap_file is None and district_name == "":
        st.error(
            "Please upload a heatmap file or select a district. Without the heatmap file, some functionalities will be disabled."
        )
        st.stop()

    if district_name == "":
        # Handle heatmap
        st.warning("You can select a district or see the heatmap.")
        heatmap_map = generate_heatmap(city, heatmap_file)
    else:
        # Handle districts and main functionality
        if district_name == "ALL":
            location_name = f"{city}"
        else:
            location_name = f"{district_name}, {city}"

        benches_file = st.file_uploader(
            "Upload benches file",
            type=["csv", "xlsx"],
            help="The file should contain `lon` and `lat` columns with coordinates of benches.",
        )

        # Simulation checkbox
        simulate_flag = st.checkbox("Enable Simulation")
        if simulate_flag:
            budget = float(st.text_input("Enter your budget:", value="1000"))
            bench_cost = float(st.text_input("Cost of one bench:", value="10"))
            st.session_state.simulate_status = True
        else:
            st.session_state.simulate_status = False

        with st.expander("Map Options"):
            show_benches = st.checkbox("Show benches", value=True)
            st.write("Street display options:")
            col1, col2 = st.columns(2)
            with col1:
                show_good_streets = st.checkbox("Age-friendly (optimal)", value=True)
            with col2:
                good_street_color = st.color_picker(
                    "Optimal street color",
                    value="#24693D",
                    label_visibility="collapsed",
                )
            col3, col4 = st.columns(2)
            with col3:
                show_okay_streets = st.checkbox("Age-friendly (convenient)", value=True)
            with col4:
                okay_street_color = st.color_picker(
                    "Convenient street color",
                    value="#6DB463",
                    label_visibility="collapsed",
                )
            col5, col6 = st.columns(2)
            with col5:
                show_bad_streets = st.checkbox(
                    "Insufficiently age-friendly (moderate)", value=True
                )
            with col6:
                bad_street_color = st.color_picker(
                    "Moderate street color",
                    value="#F57965",
                    label_visibility="collapsed",
                )
            col9, col10 = st.columns(2)
            with col9:
                show_one_streets = st.checkbox(
                    "Insufficiently age-friendly (minimal)", value=True
                )
            with col10:
                one_street_color = st.color_picker(
                    "Minimal street color",
                    value="#E64E4B",
                    label_visibility="collapsed",
                )
            col11, col12 = st.columns(2)
            with col11:
                show_zero_streets = st.checkbox("Non-age-friendly", value=True)
            with col12:
                zero_street_color = st.color_picker(
                    "Non-age-friendly color",
                    value="#A3123A",
                    label_visibility="collapsed",
                )
            col7, col8 = st.columns(2)
            with col7:
                good_street_value = (
                    st.slider("Optimal distance", min_value=0, max_value=300, value=50)
                    / 111320
                )
            with col8:
                okay_street_value = (
                    st.slider(
                        "Convenient distance", min_value=0, max_value=300, value=150
                    )
                    / 111320
                )


# Main execution
if district_name == "":
    # Display heatmap when no district is selected
    st.components.v1.html(heatmap_map, height=1000)
else:
    draw_and_simulate_map(
        location_name,
        benches_file,
        show_benches,
        show_good_streets,
        good_street_color,
        show_okay_streets,
        okay_street_color,
        show_bad_streets,
        bad_street_color,
        show_one_streets,
        one_street_color,
        show_zero_streets,
        zero_street_color,
        good_street_value,
        okay_street_value,
        budget if st.session_state.simulate_status else None,
        bench_cost if st.session_state.simulate_status else None,
    )
