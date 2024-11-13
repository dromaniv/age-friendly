import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from utils.classification import classify_sidewalks


def add_optimized_benches(
    benches_gdf, sidewalks_gdf, num_benches, good_street_value, tolerance_factor=2
):

    # Generate candidate places for each street
    def generate_candidate_bench_placements(street):
        street_geometry = street["geometry"]
        street_length = street_geometry.length
        # Double the number of candidate points
        num_candidates = int(street_length // good_street_value) * tolerance_factor

        # Generate candidate points at intervals along the street geometry
        candidate_points = [
            street_geometry.interpolate(i * (street_length / num_candidates))
            for i in range(1, num_candidates + 1)
        ]

        # Calculate initial distances for each candidate
        distances = []
        for candidate in candidate_points:
            if street["benches"]:
                # Distance to nearest bench on the same street
                min_distance = min(
                    candidate.distance(bench) for bench in street["benches"]
                )
            else:
                # If no benches on the street, use the distance to the nearest bench in general
                min_distance = min(
                    candidate.distance(bench) for bench in benches_gdf.geometry
                )
            distances.append((candidate, min_distance))

        return distances

    # Precompute all candidate points and distances for each street
    street_candidates = {}
    for _, street in sidewalks_gdf.iterrows():
        street_candidates[street.name] = generate_candidate_bench_placements(street)

    benches_to_add = []
    while num_benches > 0 and any(street_candidates.values()):
        # Find the candidate with the maximum distance to the nearest existing bench on the same street
        max_distance = 0
        best_candidate = None
        best_street = None

        for street_id, candidates in street_candidates.items():
            if not candidates:
                continue
            candidate, distance = max(candidates, key=lambda x: x[1])
            if distance > max_distance:
                max_distance = distance
                best_candidate = candidate
                best_street = street_id

        if best_candidate is None:
            break  # No more valid candidates

        # Place the selected bench
        benches_to_add.append(best_candidate)
        num_benches -= 1

        # Update the street's list of benches
        sidewalks_gdf.at[best_street, "benches"].append(best_candidate)

        # Reclassify only the affected street to check if it meets the "good" status
        affected_street = sidewalks_gdf.loc[[best_street]]
        sidewalks_gdf.update(
            classify_sidewalks(affected_street, good_street_value, good_street_value)
        )

        # Update only the distances for candidates on this street
        updated_candidates = []
        for candidate, _ in street_candidates[best_street]:
            # Calculate distance to the nearest bench on the same street
            distance = min(
                candidate.distance(bench)
                for bench in sidewalks_gdf.at[best_street, "benches"]
            )
            updated_candidates.append((candidate, distance))

        # Only keep candidates with a positive distance
        street_candidates[best_street] = [c for c in updated_candidates if c[1] > 0]

    # Convert the added benches to a GeoDataFrame and merge with existing benches
    if benches_to_add:
        new_benches_gdf = gpd.GeoDataFrame(
            geometry=benches_to_add, crs=sidewalks_gdf.crs
        )
        benches_gdf = pd.concat([benches_gdf, new_benches_gdf], ignore_index=True)
        benches_gdf = benches_gdf.drop_duplicates(subset=['geometry'])

    return benches_gdf
