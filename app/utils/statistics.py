import pandas as pd
import numpy as np

def calculate_single_street_friendliness(sidewalk):
    current_benches = len(sidewalk["benches"])
    needed_benches = sidewalk["benches_to_good"]
    if current_benches + needed_benches > 0:
        return current_benches / (current_benches + needed_benches)
    else:
        return 0


def get_basic_statistics(sidewalks_gdf):
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
            ],
            "Value": [
                f"{total_length:.2f}",
                f"{current_benches}",
                f"{overall_friendliness:.2f}%",
            ],
        }
    )
    return street_stats, general_stats
