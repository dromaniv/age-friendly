import pandas as pd
import numpy as np
import geopandas as gpd
import os
from django.conf import settings
from shapely.geometry import MultiLineString, LineString

def calculate_single_street_friendliness(sidewalk):
    current_benches = len(sidewalk["benches"])
    needed_benches = sidewalk["benches_to_good"]
    if current_benches + needed_benches > 0:
        return current_benches / (current_benches + needed_benches)
    else:
        return 0

def parse_multilinestring(multilinestring_str):
    # Remove the 'MultiLineString ((' and '))' from the string
    multilinestring_str = multilinestring_str.replace('MultiLineString ((', '').replace('))', '')
    linestrings = multilinestring_str.split('), (')
    line_coords = [
        [tuple(map(float, coord.split())) for coord in line.split(', ')]
        for line in linestrings
    ]
    return MultiLineString([LineString(coords) for coords in line_coords])

def get_basic_statistics(sidewalks_gdf, district):

    # Reproject to a suitable projected CRS for accurate length and area calculations
    sidewalks_gdf = sidewalks_gdf.to_crs(epsg=3857)
    district = district.to_crs(epsg=3857)
    
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
    benches_needed_for_okay = sidewalks_gdf["benches_to_okay"].sum()
    benches_needed_for_good = sidewalks_gdf["benches_to_good"].sum()

    sidewalks_gdf["friendliness"] = sidewalks_gdf.apply(
        calculate_single_street_friendliness, axis=1
    )
    overall_friendliness = (
        sidewalks_gdf.apply(calculate_single_street_friendliness, axis=1)
        * (sidewalks_gdf["length"] / raw_total_length)
    ).sum() * 100

    number_of_street_segments = len(sidewalks_gdf)

    # Load density information from the static file
    density_file_path = os.path.join(settings.STATICFILES_DIRS[0], 'heatmap.xlsx')
    density_df = pd.read_excel(density_file_path)

    print("Columns in density_df:", density_df.columns)

    # Ensure the density_df has the correct columns
    if not {'OBJECTID', 'LICZBA', 'boundaries'}.issubset(density_df.columns):
        raise KeyError("The 'heatmap.xlsx' file is missing required columns: 'OBJECTID', 'LICZBA', 'boundaries'.")

    # Create geometries from the 'boundaries' column
    density_df['geometry'] = density_df['boundaries'].apply(parse_multilinestring)
    density_gdf = gpd.GeoDataFrame(density_df, geometry='geometry', crs='EPSG:4326')

    # Reproject to match the district CRS
    density_gdf = density_gdf.to_crs(epsg=3857)

    # Calculate total seniors within the district
    district_seniors = density_gdf[density_gdf.within(district.geometry.iloc[0])]
    total_seniors = district_seniors['Liczba'].sum()

    # Calculate total area of the district
    total_area = district.geometry.area.sum()  # in square meters
    density = total_seniors / total_area if total_area > 0 else 0

    # Creating DataFrames for the tables
    street_stats = pd.DataFrame(
        {
            "Type of Street": ["Good", "Okay", "Bad"],
            "Number of Streets": [
                len(good_streets),
                len(okay_streets),
                len(bad_streets),
            ],
            "Total Length (km)": [
                f"{good_length:.2f}",
                f"{okay_length:.2f}",
                f"{bad_length:.2f}",
            ],
            "Percentage of Total Length": [
                f"{percent_good:.2f}%",
                f"{percent_okay:.2f}%",
                f"{percent_bad:.2f}%",
            ],
            "Benches Needed": [benches_needed_for_good, benches_needed_for_okay, "N/A"],
        }
    )

    general_stats = pd.DataFrame(
        {
            "Statistic": [
                "Total Length (km)",
                "Current Benches",
                "Overall Friendliness",
                "Number of Street Segments",
                "Density (seniors/m²)",
            ],
            "Value": [
                f"{total_length:.2f}",
                f"{current_benches}",
                f"{overall_friendliness:.2f}%",
                f"{number_of_street_segments}",
                f"{density:.6f}",
            ],
        }
    )
    return street_stats, general_stats
