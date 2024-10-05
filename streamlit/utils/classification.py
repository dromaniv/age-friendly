import numpy as np
import streamlit as st


def classify_sidewalks(sidewalks_gdf, good_street_value, okay_street_value):
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
            except Exception as e:
                print(e)
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
    sidewalks_gdf["okay"] = (sidewalks_gdf["benches_to_okay"] == 0) & ~sidewalks_gdf[
        "good"
    ]
    sidewalks_gdf["bad"] = ~sidewalks_gdf["good"] & ~sidewalks_gdf["okay"]

    return sidewalks_gdf
