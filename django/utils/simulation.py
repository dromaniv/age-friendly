import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, MultiPoint, Point


def add_simulated_benches(benches_gdf, sidewalks_gdf, longest_bad_streets, num_benches):
    benches_to_add = []
    for _, street in longest_bad_streets.iterrows():
        # Calculate the position to place the bench (in the middle of the street)
        bench_point = street.geometry.interpolate(0.5, normalized=True)
        bench = gpd.GeoDataFrame(
            index=[0], crs=sidewalks_gdf.crs, geometry=[bench_point]
        )

        # Collect the bench in a list
        benches_to_add.append(bench)

    # Concatenate the new benches to the existing benches GeoDataFrame
    if benches_to_add:
        benches_gdf = pd.concat([benches_gdf] + benches_to_add, ignore_index=True)

    return benches_gdf


def add_optimized_benches(benches_gdf, sidewalks_gdf, num_benches, good_street_value):
    # Function to find the optimal bench placement point on a street
    def find_optimal_bench_placement(street):
        # Split the street into segments between existing benches
        segments = split_street_by_benches(street["geometry"], street["benches"])

        # Find the longest segment
        longest_segment = max(segments, key=lambda seg: seg.length)

        # Place the bench at the midpoint of the longest segment
        bench_point = longest_segment.interpolate(0.5, normalized=True)
        return gpd.GeoDataFrame(
            index=[0], crs=sidewalks_gdf.crs, geometry=[bench_point]
        )

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
            return [
                LineString([all_points[i], all_points[i + 1]])
                for i in range(len(all_points) - 1)
            ]
        else:
            # If street_geometry is not a LineString, return an empty list
            return []

    # Identify streets that need benches
    sidewalks_gdf["benches_needed_for_okay"] = sidewalks_gdf.apply(
        lambda x: max(
            0, int(np.ceil(x["length"] / good_street_value)) - len(x["benches"])
        ),
        axis=1,
    )
    streets_needing_benches = sidewalks_gdf[sidewalks_gdf.benches_needed_for_okay > 0]

    # Sort these streets by the number of benches needed
    prioritized_streets = streets_needing_benches.sort_values(
        "benches_needed_for_okay", ascending=False
    )

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
