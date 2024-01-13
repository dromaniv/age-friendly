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
from shapely.geometry import Point, LineString, Polygon, MultiPoint


# Caching functions for faster loading
@st.cache_data
def get_sidewalks(location_name):
    # Find streets inside the district
    sidewalks_gdf = ox.features_from_place(location_name, tags={"highway": ["footway"]})
    # sidewalks_gdf = ox.features_from_place(location_name, tags={"highway": ["footway", "residential","tertiary", "unclassified", "secondary", "primary"]})

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
    print(benches_gdf)
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

def assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf):
    # Buffer sidewalks slightly to include nearby benches
    buffer_sidewalks = sidewalks_gdf.geometry.buffer(0.00007)  # Adjust buffer size as needed
    sidewalks_gdf["benches"] = buffer_sidewalks.apply(
        lambda x: benches_gdf[benches_gdf.within(x)].geometry.tolist()
    )
    return sidewalks_gdf

def classify_sidewalks(sidewalks_gdf, benches_gdf, good_street_value, okay_street_value):
    
    #sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

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

    def additional_benches_needed(sidewalk, target_distance):
        length = sidewalk.geometry.length
        existing_benches = len(sidewalk.benches)
        required_benches = int(np.ceil(length / target_distance)) - existing_benches
        return max(0, required_benches)

    sidewalks_gdf["benches_to_okay"] = sidewalks_gdf.apply(
        lambda x: additional_benches_needed(x, okay_street_value), axis=1
    )
    sidewalks_gdf["benches_to_good"] = sidewalks_gdf.apply(
        lambda x: additional_benches_needed(x, good_street_value), axis=1
    )

    sidewalks_gdf["good"] = sidewalks_gdf["benches_to_good"] == 0
    sidewalks_gdf["okay"] = (sidewalks_gdf["benches_to_okay"] == 0) & ~sidewalks_gdf["good"]
    sidewalks_gdf["bad"] = ~sidewalks_gdf["good"] & ~sidewalks_gdf["okay"]

    return sidewalks_gdf


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
if 'simulate_status' not in st.session_state:
    st.session_state.simulate_status = False


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

        budget = float(st.text_input("Enter your budget:", value="1000"))
        bench_cost = float(st.text_input("Cost of one bench:", value="10"))
        simulate_button = st.button("Simulate")
        if simulate_button:
            st.session_state.simulate_status = True


        st.write("# Map options:")
        show_benches = st.checkbox("Show benches", value=True)
        st.write("\n")

        col1, col2 = st.columns(2)
        with col1:
            show_good_streets = st.checkbox("Show good streets", value=True)
        with col2:
            good_street_color = st.color_picker("Good street color", value="#24693D")
        col3, col4 = st.columns(2)
        with col3:
            show_okay_streets = st.checkbox("Show okay streets", value=True)
        with col4:
            okay_street_color = st.color_picker("Okay street color", value="#6DB463")
        col5, col6 = st.columns(2)
        with col5:
            show_bad_streets = st.checkbox("Show bad streets (multiple benches)", value=True)
        with col6:
            bad_street_color = st.color_picker("Bad street color (multiple benches)", value="#F57965")
        col9, col10 = st.columns(2)
        with col9:
            show_one_streets = st.checkbox("Show bad streets (one bench)", value=True)
        with col10:
            one_street_color = st.color_picker("Bad street color (one bench)", value="#E64E4B")
        col11, col12 = st.columns(2)
        with col11:
            show_zero_streets = st.checkbox("Show bad streets (zero benches)", value=True)
        with col12:
            zero_street_color = st.color_picker("Bad street color (zero benches)", value="#A3123A")
        col7, col8 = st.columns(2)
        with col7:
            good_street_value = st.slider(
                "Good street distance", min_value=0, max_value=300, value=50
            ) / 111320
        with col8:
            okay_street_value = st.slider(
                "Okay street distance", min_value=0, max_value=300, value=150
            ) / 111320

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

# Drawing and simulating

def initialize_map(location):
    return folium.Map(
        location=[location.latitude, location.longitude],
        zoom_start=15,
        max_zoom=20,
        tiles="cartodbpositron",
        use_container_width=True,
    )

def add_district_boundaries(map_object, location_name):
    district = ox.geocode_to_gdf(location_name)
    folium.GeoJson(district).add_to(map_object)
    return map_object

def draw_benches(map_object, benches_gdf):
    for bench in benches_gdf.iterrows():
        icon = folium.features.CustomIcon(
            "https://cdn-icons-png.flaticon.com/256/2256/2256995.png",
            icon_size=(15, 15),
        )
        bench_coords = bench[1].geometry.centroid.coords[0]
        tooltip = "Imported bench" if bench[1]["amenity"] != "bench" else None
        folium.Marker(
            location=[bench_coords[1], bench_coords[0]], icon=icon, tooltip=tooltip
        ).add_to(map_object)
    return map_object


def draw_sidewalks(map_object, sidewalks_class, show_options, colors):
    for index, sidewalk in enumerate(sidewalks_class.iterrows()):
        # Tooltip text initialization
        tooltip_text = f"Current Benches: {len(sidewalk[1].benches)} | "

        if sidewalk[1]["good"]:
            tooltip_text += f"Status: Good"
        elif sidewalk[1]["okay"]:
            tooltip_text += f"Status: Okay | "
        elif sidewalk[1]["bad"]:
            tooltip_text += f"Status: Bad | "

        # Add additional benches needed for okay and good classification
        if sidewalk[1]["bad"]:
            tooltip_text += f"\nBenches to Okay: {sidewalk[1]['benches_to_okay']} | "
        if sidewalk[1]["okay"] or sidewalk[1]["bad"]:
            tooltip_text += f"\nBenches to Good: {sidewalk[1]['benches_to_good']}"

        # Determine the street color and draw the GeoJson
        if sidewalk[1]["good"] and show_options["good_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {"color": colors["good_street_color"], "weight": 5, "opacity": 0.8},
                tooltip=tooltip_text
            ).add_to(map_object)
        elif sidewalk[1]["okay"] and show_options["okay_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {"color": colors["okay_street_color"], "weight": 5, "opacity": 0.8},
                tooltip=tooltip_text
            ).add_to(map_object)
        elif sidewalk[1]["bad"] and show_options["bad_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {"color": colors["bad_street_color"], "weight": 5, "opacity": 0.8},
                tooltip=tooltip_text
            ).add_to(map_object)
        if sidewalk[1]["bad"] and len(sidewalk[1].benches) == 1 and show_options["one_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {"color": colors["one_street_color"], "weight": 5, "opacity": 0.8},
                tooltip=tooltip_text
            ).add_to(map_object)
        elif sidewalk[1]["bad"] and len(sidewalk[1].benches) == 0 and show_options["zero_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {"color": colors["zero_street_color"], "weight": 5, "opacity": 0.8},
                tooltip=tooltip_text
            ).add_to(map_object)

    return map_object




def calculate_benches(budget, bench_cost):
    return int(budget // bench_cost)

def find_longest_streets(sidewalks_gdf, num_streets):

    # Sort the sidewalks by length in descending order
    sorted_sidewalks = sidewalks_gdf.sort_values(by='length', ascending=False)

    # Select the top 'num_streets' longest sidewalks
    longest_bad_streets = sorted_sidewalks.head(num_streets)

    return longest_bad_streets

def add_simulated_benches(benches_gdf, sidewalks_gdf, longest_bad_streets, num_benches):
    benches_to_add = []
    for _, street in longest_bad_streets.iterrows():
        # Calculate the position to place the bench (in the middle of the street)
        bench_point = street.geometry.interpolate(0.5, normalized=True)
        bench = gpd.GeoDataFrame(index=[0], crs=sidewalks_gdf.crs, geometry=[bench_point])

        # Collect the bench in a list
        benches_to_add.append(bench)

    # Concatenate the new benches to the existing benches GeoDataFrame
    if benches_to_add:
        benches_gdf = pd.concat([benches_gdf] + benches_to_add, ignore_index=True)

    return benches_gdf

def add_optimized_benches(benches_gdf, sidewalks_gdf, num_benches):
    # Function to find the optimal bench placement point on a street
    def find_optimal_bench_placement(street):
        # Split the street into segments between existing benches
        segments = split_street_by_benches(street['geometry'], street['benches'])
        
        # Find the longest segment
        longest_segment = max(segments, key=lambda seg: seg.length)
        
        # Place the bench at the midpoint of the longest segment
        bench_point = longest_segment.interpolate(0.5, normalized=True)
        return gpd.GeoDataFrame(index=[0], crs=sidewalks_gdf.crs, geometry=[bench_point])

    def split_street_by_benches(street_geometry, benches):
        # Ensure that the geometry is LineString and get boundary points
        if isinstance(street_geometry, LineString):
            coords = list(street_geometry.coords)
            start_point = Point(coords[0])
            end_point = Point(coords[-1])

            # Ensure benches are in a list of Point objects
            bench_points = []
            if isinstance(benches, MultiPoint):
                bench_points = list(benches.geoms)
            elif isinstance(benches, Point):
                bench_points = [benches]
            elif isinstance(benches, list):
                bench_points = [b for b in benches if isinstance(b, Point)]

            # Combine and sort points along the street geometry
            all_points = [start_point] + bench_points + [end_point]
            all_points.sort(key=lambda point: street_geometry.project(point))

            # Create segments between each pair of points
            return [LineString([all_points[i], all_points[i+1]]) for i in range(len(all_points)-1)]
        else:
            # If street_geometry is not a LineString, return an empty list
            return []




    # Identify streets that need benches
    sidewalks_gdf["benches_needed_for_okay"] = sidewalks_gdf.apply(
        lambda x: max(0, int(np.ceil(x['length'] / good_street_value)) - len(x['benches'])), axis=1
    )
    streets_needing_benches = sidewalks_gdf[sidewalks_gdf.benches_needed_for_okay > 0]

    # Sort these streets by the number of benches needed
    prioritized_streets = streets_needing_benches.sort_values('benches_needed_for_okay', ascending=False)

    # Add benches to the streets with the highest priority first
    benches_to_add = []
    for _, street in prioritized_streets.iterrows():
        if num_benches <= 0:
            break
        bench = find_optimal_bench_placement(street)
        benches_to_add.append(bench)
        num_benches -= 1

    # Concatenate the new benches to the existing benches GeoDataFrame
    if benches_to_add:
        benches_gdf = pd.concat([benches_gdf] + benches_to_add, ignore_index=True)

    return benches_gdf

def calculate_single_street_friendliness(sidewalk):
    current_benches = len(sidewalk['benches'])
    needed_benches = sidewalk['benches_to_good']
    if current_benches + needed_benches > 0:
        return current_benches / (current_benches + needed_benches)
    else:
        return 0

def display_basic_statistics(sidewalks_gdf):
    good_streets = sidewalks_gdf[sidewalks_gdf["good"]]
    okay_streets = sidewalks_gdf[sidewalks_gdf["okay"]]
    bad_streets = sidewalks_gdf[sidewalks_gdf["bad"]]

    raw_total_length = sidewalks_gdf["length"].sum() 
    total_length = raw_total_length * 111320 / 1000
    good_length = good_streets["length"].sum() * 111320 / 1000
    okay_length = okay_streets["length"].sum() * 111320 / 1000
    bad_length = bad_streets["length"].sum() * 111320 / 1000 

    percent_good = (good_length / total_length) * 100
    percent_okay = (okay_length / total_length) * 100
    percent_bad = (bad_length / total_length) * 100

    current_benches = sidewalks_gdf["benches"].apply(len).sum()
    benches_needed_for_okay = sidewalks_gdf['benches_to_okay'].sum()
    benches_needed_for_good = sidewalks_gdf['benches_to_good'].sum()

    sidewalks_gdf['friendliness'] = sidewalks_gdf.apply(calculate_single_street_friendliness, axis=1)
    overall_friendliness = (sidewalks_gdf.apply(calculate_single_street_friendliness, axis=1) * (sidewalks_gdf['length'] / raw_total_length)).sum() * 100

    # Creating DataFrames for the tables
    street_stats = pd.DataFrame({
        "Type of Street": ["Good", "Okay", "Bad"],
        "Number of Streets": [len(good_streets), len(okay_streets), len(bad_streets)],
        "Total Length (km)": [f"{good_length:.2f}", f"{okay_length:.2f}", f"{bad_length:.2f}"],
        "Percentage of Total Length": [f"{percent_good:.2f}%", f"{percent_okay:.2f}%", f"{percent_bad:.2f}%"],
        "Benches Needed": [benches_needed_for_good, benches_needed_for_okay, "N/A"]
    })

    general_stats = pd.DataFrame({
        "Statistic": ["Total Length (km)", "Current Benches", "Overall Friendliness"],
        "Value": [f"{total_length:.2f}", f"{current_benches}", f"{overall_friendliness:.2f}%"]
    })

    # Displaying the tables side by side with custom styling
    col1, col2 = st.columns(2)
    with col1:
        #st.write("### Street Type Statistics")
        st.markdown(street_stats.to_html(index=False, classes="table-style"), unsafe_allow_html=True)
    with col2:
        #st.write("### General Statistics")
        st.markdown(general_stats.to_html(index=False, classes="table-style"), unsafe_allow_html=True)

    # Optional: Adding custom CSS for table styling
    st.markdown("""
        <style>
        .table-style {
            border-collapse: collapse;
            width: 100%;
            font-size: 10px;
        }
        .table-style td, .table-style th {
            border: 1px solid #ddd;
            padding: 4px;
        }
        .table-style tr:nth-child(even){background-color: #f2f2f2;}
        .table-style tr:hover {background-color: #ddd;}
        .table-style th {
            padding-bottom: 6px;
            text-align: left;
            background-color: #04AA6D;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

def draw_and_simulate_map(simulate):
    # Initialize progress bar
    step_text = st.empty()
    progress_bar = st.progress(0)
    step_text.text("Finding location...")

    # Find location
    location = geolocator.geocode(location_name)

    # Create Folium map
    progress_bar.progress(5)
    step_text.text("Creating map...")
    m = initialize_map(location)

    # Find district
    progress_bar.progress(10)
    step_text.text("Adding district boundaries...")
    district = ox.geocode_to_gdf(location_name)  # Fetch the district data
    m = add_district_boundaries(m, location_name)

    # Find streets inside the district
    progress_bar.progress(15)
    step_text.text("Finding sidewalks...")
    sidewalks_gdf = get_sidewalks(location_name)

    # Find benches inside the district
    progress_bar.progress(25)
    step_text.text("Finding benches...")
    benches_gdf = get_benches(location_name, district, benches_file)

    progress_bar.progress(30)
    step_text.text("Assigning benches to sidewalks...")
    sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    # bench_count_before = len(benches_gdf)

    # If simulation is activated
    if st.session_state.simulate_status:
        # st.write(f"Drawing with budget: {budget} and bench cost: {bench_cost}")
        num_benches = calculate_benches(budget, bench_cost)
        #benches_gdf = add_simulated_benches(benches_gdf, sidewalks_gdf, longest_streets, num_benches)
        benches_gdf = add_optimized_benches(benches_gdf, sidewalks_gdf, num_benches)
        sidewalks_gdf = assign_benches_to_sidewalks(sidewalks_gdf, benches_gdf)

    # else:
        # st.write(f"Drawing without simulation")

    # # Count the number of benches after simulation
    # bench_count_after = len(benches_gdf)

    # # Display the bench count
    # st.write(f"Number of benches before simulation: {bench_count_before}")
    # st.write(f"Number of benches after simulation: {bench_count_after}")

    progress_bar.progress(35)
    step_text.text("Drawing benches...")
    m = draw_benches(m, benches_gdf)

    progress_bar.progress(40)
    step_text.text("Classifying sidewalks...")
    sidewalks_class = classify_sidewalks(sidewalks_gdf, benches_gdf, good_street_value, okay_street_value)

    progress_bar.progress(50)
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

    display_basic_statistics(sidewalks_class)

    # Reset progress bar
    progress_bar.empty()
    step_text.empty()

     # Generate the HTML representation of the Folium map
    map_html = m._repr_html_()

    # Clear the existing map placeholder before redrawing the map
    st.empty()

    # Display the map using markdown in Streamlit
    st.components.v1.html(map_html, height=400, scrolling=False)

    st.markdown(
        """<style>
            .st-emotion-cache-z5fcl4.ea3mdgi4 {
                overflow: hidden;
            }
            """,
        unsafe_allow_html=True,
    )

# Heatmap view
if district_name == "":
    heatmap = generate_heatmap(city)
    st.components.v1.html(heatmap, height=4320, scrolling=False)
    st.stop()

draw_and_simulate_map(simulate_button)
