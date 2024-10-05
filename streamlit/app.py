import os
import osmnx as ox
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# Set page configuration
st.set_page_config(layout="wide", page_title="Age Friendly", page_icon="🗺️")

# Import utilities
from utils.districts import get_districts, get_district_geodataframe
from utils.heatmap import generate_heatmap
from utils.map_utils import initialize_map, add_district_boundaries
from utils.benches_sidewalks import (
    calculate_benches,
    get_sidewalks,
    get_benches,
    assign_benches_to_sidewalks,
)
from utils.drawing import draw_benches, draw_sidewalks
from utils.classification import classify_sidewalks
from utils.simulation import add_optimized_benches
from utils.statistics import get_basic_statistics

# Initialize session state for simulation status
if "simulate_status" not in st.session_state:
    st.session_state.simulate_status = False

# Get geolocator
geolocator = Nominatim(user_agent="street-highlighter")

# Sidebar for user input
with st.sidebar:
    admin_level = st.slider(
        "Admin Level",
        min_value=7,
        max_value=11,
        value=9,
        help="Select the administrative level for what constitutes a district. Lower values are more general (e.g. city), higher values are more specific (e.g. neighborhood).",
    )
    city = st.text_input("City:", value="Poznań", help="ℹ️ Enter the name of the city.")
    districts = get_districts(city, admin_level)
    district_name = st.selectbox(
        "District:",
        [""] + districts,
        help="ℹ️ Select the district to highlight on the map.",
    )
    if os.path.exists("streamlit/static/heatmaps") and f"{city}.xlsx" in os.listdir(
        "streamlit/static/heatmaps"
    ):
        heatmap_file = f"streamlit/static/heatmaps/{city}.xlsx"
        st.write("###### Heatmap file found.")
    elif os.path.exists("/streamlit/static/heatmaps") and f"{city}.xlsx" in os.listdir(
        "/streamlit/static/heatmaps"
    ):
        heatmap_file = f"/streamlit/static/heatmaps/{city}.xlsx"
        st.write("###### Heatmap file found.")
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

        if os.path.exists(
            "streamlit/static/benches"
        ) and f"{district_name}.xlsx" in os.listdir("streamlit/static/benches"):
            benches_file = f"streamlit/static/benches/{district_name}.xlsx"
            # remove previous heatmap message:
            st.write("###### Benches file found.")
        elif os.path.exists(
            "/streamlit/static/benches"
        ) and f"{district_name}.xlsx" in os.listdir("/streamlit/static/benches"):
            benches_file = f"/streamlit/static/benches/{district_name}.xlsx"
            st.write("###### Benches file found.")
        else:
            benches_file = st.file_uploader(
                "Upload benches file",
                type=["xlsx"],
                help="The file should contain only `lat` and `lon` columns with coordinates of benches.",
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

    # Get district geodataframe
    district = get_district_geodataframe(location_name)

    # Find sidewalks inside the district
    progress_bar.progress(30)
    step_text.text("Finding sidewalks...")
    sidewalks_gdf = get_sidewalks(location_name)

    # Find benches inside the district
    progress_bar.progress(40)
    step_text.text("Finding benches...")
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
