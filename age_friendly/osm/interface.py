import os
import folium
import numpy as np
import osmnx as ox
import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
from shapely.geometry import Point, Polygon
from django.conf import settings



# Initialize geolocator
geolocator = Nominatim(user_agent="age_friendly")


def get_sidewalks(location_name):
    # Find streets inside the district
    sidewalks_gdf = ox.features_from_place(location_name, tags={"highway": ["footway"]})
    # Data preprocessing:
    # Remove polygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "Polygon"]
    # Remove multipolygons
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf.geometry.type != "MultiPolygon"]
    # Remove crossings
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["footway"] != "crossing"]
    # Calculate the length of each sidewalk
    sidewalks_gdf["length"] = sidewalks_gdf.geometry.length
    # Remove short sidewalks from the original GeoDataFrame
    sidewalks_gdf = sidewalks_gdf[sidewalks_gdf["length"] >= 0.0005]
    return sidewalks_gdf


def get_benches(location_name, district, benches_file=None):
    # Find benches inside the district
    benches_gdf = ox.features_from_place(location_name, tags={"amenity": "bench"})

    # Parse benches file
    if benches_file is not None:
        if benches_file.name.endswith(".csv"):
            imported_benches = pd.read_csv(benches_file, sep=";")
        elif benches_file.name.endswith(".xlsx"):
            imported_benches = pd.read_excel(benches_file)
        else:
            print("Invalid file format. Only CSV and XLSX files are supported.")
            return benches_gdf
        if "lon" in imported_benches.columns and "lat" in imported_benches.columns:
            imported_benches["geometry"] = imported_benches.apply(
                lambda row: Point(row["lon"], row["lat"]), axis=1
            )
            benches_gdf = pd.concat([benches_gdf, imported_benches])
            benches_gdf = benches_gdf[benches_gdf.within(district.geometry[0])]
        else:
            print(
                "The uploaded file does not contain `lon` and `lat` columns. Ignoring..."
            )
    return benches_gdf


def classify_sidewalks(
    sidewalks_gdf, benches_gdf, good_street_value, okay_street_value
):
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
                close_bench = any(
                    [segment_point.distance(bench) <= meters for bench in benches]
                )
                if not close_bench:
                    return False
            except:
                print("Error", geometry)
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


def get_map(
    location_name,
    show_benches,
    show_good,
    show_okay,
    show_bad,
    show_empty,
    good_color,
    okay_color,
    bad_color,
    empty_color,
    good_distance,
    okay_distance,
    benches_file=None,
):

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

    if show_benches:
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
                location=[bench_coords[1], bench_coords[0]],
                icon=icon,
                tooltip=tooltip,
            ).add_to(m)

    sidewalks_class = classify_sidewalks(
        sidewalks_gdf, benches_gdf, good_distance, okay_distance
    )

    def add_sidewalk_to_map(sidewalk, color, m):
        folium.GeoJson(
            sidewalk.geometry,
            style_function=lambda x: {
                "color": color,
                "weight": 5,
                "opacity": 0.8,
            },
            tooltip=f"Benches: {len(sidewalk.benches)}, Length: {sidewalk.length * 111320:.2f} m",
        ).add_to(m)

    for index, sidewalk in enumerate(sidewalks_class.iterrows()):
        if sidewalk[1]["good"] and show_good:
            add_sidewalk_to_map(sidewalk[1], good_color, m)
        elif sidewalk[1]["okay"] and show_okay:
            add_sidewalk_to_map(sidewalk[1], okay_color, m)
        elif sidewalk[1]["bad"] and show_bad:
            add_sidewalk_to_map(sidewalk[1], bad_color, m)
        if len(sidewalk[1].benches) == 0 and show_empty:
            add_sidewalk_to_map(sidewalk[1], empty_color, m)

    return m


def get_heatmap(location_name):
    location = geolocator.geocode(location_name)

    # read file in the static folder
    df = pd.read_excel(os.path.join(settings.STATICFILES_DIRS[0], "poprodukcyjny.xlsx"))

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

    return m


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