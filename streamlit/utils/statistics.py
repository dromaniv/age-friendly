import pandas as pd
import numpy as np
import geopandas as gpd
import os
from shapely.geometry import MultiLineString, LineString


def calculate_single_street_friendliness(sidewalk):
    current_benches = len(sidewalk["benches"])
    needed_benches = sidewalk["benches_to_good"]
    if current_benches + needed_benches > 0:
        return current_benches / (current_benches + needed_benches)
    else:
        return 0


def calculate_average_nearest_bench_distance(sidewalks_gdf):

    if sidewalks_gdf.crs.to_epsg() != 3857:
        sidewalks_gdf = sidewalks_gdf.to_crs(epsg=3857)

    nearest_distances = []  # Collect all minimum distances across all benches
    avg_distances = []  # Collect per-sidewalk average distances
    max_distances = []  # Collect per-sidewalk maximum distances

    for _, sidewalk in sidewalks_gdf.iterrows():
        benches = sidewalk.benches
        if len(benches) < 2:
            continue

        sidewalk_distances = []
        for i, bench in enumerate(benches):
            distances = [
                bench.distance(other_bench)
                for j, other_bench in enumerate(benches)
                if i != j
            ]
            if distances:
                min_distance = min(distances) * 111320  # Convert to meters
                sidewalk_distances.append(min_distance)
                nearest_distances.append(
                    min_distance
                )  # Collecting all minimum distances

        # Compute sidewalk-specific statistics if distances were found
        if sidewalk_distances:
            avg_distances.append(
                np.mean(sidewalk_distances)
            )  # Average for each sidewalk
            max_distances.append(
                np.max(sidewalk_distances)
            )  # Maximum for each sidewalk

    avg_of_nearest_distances = np.mean(nearest_distances) if nearest_distances else 0
    avg_of_avg_distances = np.mean(avg_distances) if avg_distances else 0
    avg_of_max_distances = np.mean(max_distances) if max_distances else 0

    return avg_of_nearest_distances, avg_of_max_distances, avg_of_avg_distances


def parse_multilinestring(multilinestring_str):
    # Remove the 'MultiLineString ((' and '))' from the string
    multilinestring_str = multilinestring_str.replace("MultiLineString ((", "").replace(
        "))", ""
    )
    linestrings = multilinestring_str.split("), (")
    line_coords = []
    for line in linestrings:
        coords = []
        for coord in line.split(", "):
            try:
                # Split coordinate into x and y
                x_str, y_str = coord.strip().split()
                x = float(x_str)
                y = float(y_str)
                coords.append((x, y))
            except ValueError:
                # Skip invalid coordinate pairs
                continue
        # Only add lines with at least two valid coordinates
        if len(coords) >= 2:
            line_coords.append(coords)
    # Check if we have at least one valid linestring
    if line_coords:
        try:
            return MultiLineString([LineString(coords) for coords in line_coords])
        except ValueError as e:
            print(f"Error creating MultiLineString: {e}")
            return None
    else:
        return None  # Return None if no valid lines found


def get_basic_statistics(sidewalks_gdf, benches_gdf, district, heatmap_file):
    # Reproject to a suitable projected CRS for accurate length and area calculations
    sidewalks_gdf = sidewalks_gdf.to_crs(epsg=3857)
    district = district.to_crs(epsg=3857)

    avg_nearest_bench_distance, avg_max_nearest_bench_distance, avg_of_all_averages = (
        calculate_average_nearest_bench_distance(sidewalks_gdf)
    )

    # Classify sidewalks by friendliness and bench count
    good_streets = sidewalks_gdf[sidewalks_gdf["good"]]
    okay_streets = sidewalks_gdf[sidewalks_gdf["okay"]]
    insufficient_streets = sidewalks_gdf[
        (sidewalks_gdf["bad"]) & (sidewalks_gdf["benches"].apply(len) > 1)
    ]
    insufficient_minimal_streets = sidewalks_gdf[
        (sidewalks_gdf["bad"]) & (sidewalks_gdf["benches"].apply(len) == 1)
    ]
    non_age_friendly_streets = sidewalks_gdf[
        (sidewalks_gdf["bad"]) & (sidewalks_gdf["benches"].apply(len) == 0)
    ]

    # Calculate length and percentage statistics
    total_length = sidewalks_gdf["length"].sum() * 111320 / 1000
    good_length = good_streets["length"].sum() * 111320 / 1000
    okay_length = okay_streets["length"].sum() * 111320 / 1000
    insufficient_length = insufficient_streets["length"].sum() * 111320 / 1000
    insufficient_minimal_length = (
        insufficient_minimal_streets["length"].sum() * 111320 / 1000
    )
    non_age_friendly_length = non_age_friendly_streets["length"].sum() * 111320 / 1000

    percent_good = (good_length / total_length) * 100
    percent_okay = (okay_length / total_length) * 100
    percent_insufficient = (insufficient_length / total_length) * 100
    percent_insufficient_minimal = (insufficient_minimal_length / total_length) * 100
    percent_non_age_friendly = (non_age_friendly_length / total_length) * 100

    current_benches = len(benches_gdf)
    benches_needed_for_okay = sidewalks_gdf["benches_to_okay"].sum()
    benches_needed_for_good = sidewalks_gdf["benches_to_good"].sum()

    sidewalks_gdf["friendliness"] = sidewalks_gdf.apply(
        calculate_single_street_friendliness, axis=1
    )
    overall_friendliness = (
        sidewalks_gdf.apply(calculate_single_street_friendliness, axis=1)
        * (sidewalks_gdf["length"] / sidewalks_gdf["length"].sum())
    ).sum() * 100

    number_of_street_segments = len(sidewalks_gdf)

    if not heatmap_file:
        density = 0
    else:
        # Load density information from the static file
        density_df = pd.read_excel(heatmap_file)
        # Ensure the density_df has the correct columns
        if not {"OBJECTID", "LICZBA", "boundaries"}.issubset(density_df.columns):
            raise KeyError(
                "The 'heatmap.xlsx' file is missing required columns: 'OBJECTID', 'LICZBA', 'boundaries'."
            )

        # Create geometries from the 'boundaries' column
        density_df["geometry"] = density_df["boundaries"].apply(parse_multilinestring)
        density_gdf = gpd.GeoDataFrame(density_df, geometry="geometry", crs="EPSG:4326")

        # Reproject to match the district CRS
        density_gdf = density_gdf.to_crs(epsg=3857)

        # Calculate total seniors within the district
        district_seniors = density_gdf[density_gdf.within(district.geometry.iloc[0])]
        total_seniors = district_seniors["LICZBA"].sum()

        # Calculate total area of the district in square meters
        total_area = district.geometry.area.sum()  # in square meters

        # Convert total area to square kilometers
        total_area_km2 = total_area / 1e6  # Convert area to km²

        # Calculate density in seniors per km²
        density = total_seniors / total_area_km2 if total_area_km2 > 0 else 0

    # Creating DataFrames for the tables
    street_stats = pd.DataFrame(
        {
            "Type of Street": [
                "Optimal",
                "Convenient",
                "Insufficiently age-friendly (moderate)",
                "Insufficiently age-friendly (minimal)",
                "Non-age friendly",
            ],
            "Number of Streets": [
                len(good_streets),
                len(okay_streets),
                len(insufficient_streets),
                len(insufficient_minimal_streets),
                len(non_age_friendly_streets),
            ],
            "Total Length (km)": [
                f"{good_length:.2f}",
                f"{okay_length:.2f}",
                f"{insufficient_length:.2f}",
                f"{insufficient_minimal_length:.2f}",
                f"{non_age_friendly_length:.2f}",
            ],
            "Percentage of Total Length": [
                f"{percent_good:.2f}%",
                f"{percent_okay:.2f}%",
                f"{percent_insufficient:.2f}%",
                f"{percent_insufficient_minimal:.2f}%",
                f"{percent_non_age_friendly:.2f}%",
            ],
            "Benches Needed": [
                benches_needed_for_good,
                benches_needed_for_okay,
                "N/A",
                "N/A",
                "N/A",
            ],
        }
    )

    general_stats = pd.DataFrame(
        {
            "Statistic": [
                "Total Length (km)",
                "Current Benches",
                "Overall Friendliness",
                "Number of Street Segments",
                "Average of Distance to the Nearest Bench (m)",
            ],
            "Value": [
                f"{total_length:.2f}",
                f"{current_benches}",
                f"{overall_friendliness:.2f}%",
                f"{number_of_street_segments}",
                f"{avg_nearest_bench_distance:.2f}",
            ],
        }
    )
    return street_stats, general_stats
