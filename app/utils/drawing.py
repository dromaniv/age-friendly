import folium


def draw_benches(map_object, benches_gdf):
    for bench in benches_gdf.iterrows():
        icon = folium.features.CustomIcon(
            "https://cdn-icons-png.flaticon.com/256/2256/2256995.png",
            icon_size=(15, 15),
        )
        bench_coords = bench[1].geometry.centroid.coords[0]
        tooltip = "Imported/simulated bench" if bench[1]["amenity"] != "bench" else None
        folium.Marker(
            location=[bench_coords[1], bench_coords[0]], icon=icon, tooltip=tooltip
        ).add_to(map_object)
    return map_object


def draw_sidewalks(map_object, sidewalks_class, show_options, colors):
    for index, sidewalk in enumerate(sidewalks_class.iterrows()):
        # Tooltip text initialization
        tooltip_text = f"Current Benches: {len(sidewalk[1].benches)} | "

        if sidewalk[1]["good"]:
            tooltip_text += f"Status: Optimal"
        elif sidewalk[1]["okay"]:
            tooltip_text += f"Status: Convenient | "
        elif sidewalk[1]["bad"]:
            tooltip_text += f"Status: Insufficient | "

        # Add additional benches needed for okay and good classification
        if sidewalk[1]["bad"]:
            tooltip_text += (
                f"\nBenches to Convenient: {sidewalk[1]['benches_to_okay']} | "
            )
        if sidewalk[1]["okay"] or sidewalk[1]["bad"]:
            tooltip_text += f"\nBenches to Optimal: {sidewalk[1]['benches_to_good']}"

        # Determine the street color and draw the GeoJson
        if sidewalk[1]["good"] and show_options["good_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {
                    "color": colors["good_street_color"],
                    "weight": 5,
                    "opacity": 0.8,
                },
                tooltip=tooltip_text,
            ).add_to(map_object)
        elif sidewalk[1]["okay"] and show_options["okay_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {
                    "color": colors["okay_street_color"],
                    "weight": 5,
                    "opacity": 0.8,
                },
                tooltip=tooltip_text,
            ).add_to(map_object)
        elif sidewalk[1]["bad"] and show_options["bad_streets"]:
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {
                    "color": colors["bad_street_color"],
                    "weight": 5,
                    "opacity": 0.8,
                },
                tooltip=tooltip_text,
            ).add_to(map_object)
        if (
            sidewalk[1]["bad"]
            and len(sidewalk[1].benches) == 1
            and show_options["one_streets"]
        ):
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {
                    "color": colors["one_street_color"],
                    "weight": 5,
                    "opacity": 0.8,
                },
                tooltip=tooltip_text,
            ).add_to(map_object)
        elif (
            sidewalk[1]["bad"]
            and len(sidewalk[1].benches) == 0
            and show_options["zero_streets"]
        ):
            folium.GeoJson(
                sidewalk[1].geometry,
                style_function=lambda x: {
                    "color": colors["zero_street_color"],
                    "weight": 5,
                    "opacity": 0.8,
                },
                tooltip=tooltip_text,
            ).add_to(map_object)

    return map_object


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
