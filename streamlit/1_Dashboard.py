import os
import osmnx as ox
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# Set page configuration for Dashboard
st.set_page_config(layout="wide", page_title="Dashboard", page_icon="🗺️")

# Import utilities
from utils.districts import get_districts, get_district_geodataframe
from utils.heatmap import generate_heatmap, generate_heatmap_layer
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
        min_value=1,
        max_value=5,
        value=3,
        help="Select the administrative level for what constitutes a district. Lower values are more general (e.g., city), higher values are more specific (e.g., neighborhood).",
    )


    city = (
        st.text_input("City:", value="Poznań", help="ℹ️ Enter the name of the city.")
        .capitalize()
        .strip()
    )
    districts = get_districts(city, admin_level + 6)
    district_name = st.selectbox(
        "Define area:",
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
        if district_name == city:
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
            show_heatmap_overlay = st.checkbox("Show heatmap overlay", value=False)
            if show_heatmap_overlay:
                heatmap_opacity = st.slider(
                    "Heatmap opacity", min_value=0.0, max_value=1.0, value=0.3
                )
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

    with st.expander("Advanced Road Options"):
        # Categorized lists of highway types
        recommended_types = ["footway", "pedestrian", "living_street"]
        optional_types = [
            "path", "steps", "bridleway", "cycleway", "corridor", "platform",
            "residential", "service", "unclassified", "road", "track"
        ]
        completeness_types = [
            "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
            "secondary", "secondary_link", "tertiary", "tertiary_link", "bus_guideway",
            "escape", "raceway", "construction", "proposed"
        ]

        possible_types = recommended_types + optional_types + completeness_types

        selected_highway_types = st.multiselect(
            "Select the highway types to consider:",
            possible_types,
            default=recommended_types,
            help=(
                "**What is this and why can you choose?**\n"
                "This section allows you to customize which OpenStreetMap 'highway' types "
                "are included in the analysis. By default, we focus on the most pedestrian-friendly "
                "environments—those safer and more comfortable for older adults. However, every region "
                "is different, and you may want to consider additional types of roads, paths, or "
                "infrastructure depending on local conditions, data availability, and specific goals. "
                "Giving you the flexibility to choose ensures that this tool can adapt to different "
                "urban landscapes and user needs.\n\n"
                
                "**Recommended Types (Default):**\n"
                "- **footway:** Sidewalks or paths mainly for pedestrians.\n"
                "- **pedestrian:** Streets or zones designed with priority for pedestrians.\n"
                "- **living_street:** Roads where pedestrians share space with vehicles but have priority.\n\n"
                "These are chosen by default because they represent environments that are typically "
                "safe and accessible for older adults.\n\n"
                
                "**Optional Types (Might or Might Not Be Helpful):**\n"
                "- **path, steps, bridleway:** Various pedestrian-friendly paths, trails, or stairs.\n"
                "- **cycleway, corridor, platform:** Specialized ways like bike paths, indoor passages, "
                "and transit platforms that might be relevant depending on local context.\n"
                "- **residential, service, unclassified, road, track:** Streets commonly found in neighborhoods "
                "or rural areas, potentially walkable but not always designed for pedestrians.\n\n"
                "Consider these if your region’s conditions or the scope of your analysis require a broader look "
                "at where older adults might walk.\n\n"
                
                "**For Completeness (Generally Not Recommended):**\n"
                "- **motorway, trunk, primary, secondary, tertiary (and _link variants):** Major roads or "
                "high-speed routes not meant for pedestrians.\n"
                "- **bus_guideway, escape, raceway:** Specialized, niche ways rarely relevant for pedestrian use.\n"
                "- **construction, proposed:** Roads in progress or planned, but not currently usable.\n\n"
                "These are rarely necessary for a pedestrian accessibility analysis and might not add much value "
                "unless you have very specific, edge-case reasons to include them."
            )
        )

# Main execution for Dashboard
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
    sidewalks_gdf = get_sidewalks(location_name, selected_highway_types)

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
    step_text.text("Drawing map...")
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

    # Add heatmap overlay if enabled
    if show_heatmap_overlay:
        m = generate_heatmap_layer(m, heatmap_file, district, heatmap_opacity)

    # Calculate statistics
    progress_bar.progress(90)
    step_text.text("Calculating statistics...")
    street_stats, general_stats = get_basic_statistics(
        sidewalks_class, benches_gdf, district, heatmap_file
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
