# views.py
import locale
import requests
from .models import AppSettings
from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout

from osm.interface import get_map, get_heatmap


locale.setlocale(locale.LC_COLLATE, "pl_PL.UTF-8")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")
    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def index(request):
    return render(request, "index.html")


@login_required
def settings(request):
    if request.method == "POST":
        # Save the settings in the database
        settings = AppSettings.objects.get(user=request.user)

        settings.admin_level = request.POST.get("admin_level")
        settings.heatmap_file = request.FILES.get("heatmap_file")

        settings.save()
        messages.success(request, "Settings updated successfully!")
        return redirect("settings")

    else:
        if not request.user.is_authenticated:
            return redirect("login")

        # Load the settings from the database
        settings = AppSettings.objects.get(user=request.user)

        admin_level = settings.admin_level
        heatmap_file = settings.heatmap_file

        # Pass the settings to the template
        context = {"admin_level": admin_level, "heatmap_file": heatmap_file}

        return render(request, "settings.html", context)


@login_required
def show_heatmap(request):
    if request.method == "POST":
        # Get form data
        city = request.POST.get("city")

        # Check if valid
        if city is None:
            return JsonResponse({"heatmap_html": "Error: Please select a city."})

        # Generate the heatmap
        heatmap = get_heatmap(city)

        return JsonResponse({"heatmap_html": heatmap._repr_html_()})


@login_required
def get_districts(request):
    # Doesn't even work that well (e.g. no Łacina)
    # Overpass API Query
    # This query looks for nodes tagged as 'place=suburb' within the city
    city_name = request.GET.get("city")

    settings = AppSettings.objects.get(user=request.user)
    admin_level = settings.admin_level

    query = f"""
    [out:json];
    area[name="{city_name}"]->.searchArea;
    (
      rel(area.searchArea)["admin_level"="{admin_level}"];
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

    return JsonResponse({"districts": districts})


@login_required
def show_map(request):
    if request.method == "POST":
        # Get form data
        city = request.POST.get("city")
        district = request.POST.get("district")

        # Check if valid
        if city is None or district is None:
            return JsonResponse({"map_html": "Error: City or district not specified."})
        
        map = get_map(
                location_name = f"{city}, {district}",
                show_benches = "show_benches" in request.POST,
                show_good = "show_good" in request.POST,
                show_okay = "show_okay" in request.POST,
                show_bad = "show_bad" in request.POST,
                show_empty = "show_empty" in request.POST,
                good_color = request.POST.get("good_color", "#009900"),
                okay_color = request.POST.get("okay_color", "#FFA500"),
                bad_color = request.POST.get("bad_color", "#FF0000"),
                empty_color = request.POST.get("no_color", "#000000"),
                good_distance = int(request.POST.get("good_distance", "50")) / 111320,
                okay_distance = int(request.POST.get("okay_distance", "150")) / 111320,
                benches_file = request.FILES.get("benches_file"),
            )

        return JsonResponse({"map_html": map._repr_html_()})
