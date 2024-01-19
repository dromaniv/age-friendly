# views.py
import locale
import requests
from .models import AppSettings
from django.conf import settings
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
def settings_view(request):
    if request.method == "POST":
        # Save the settings in the database
        app_settings = AppSettings.objects.get(user=request.user)

        app_settings.admin_level = request.POST.get("admin_level")

        app_settings.heatmap_file = (
            request.FILES.get("heatmap_file")
            if request.FILES.get("heatmap_file")
            else app_settings.heatmap_file
        )
        delete_heatmap = request.POST.get("delete_heatmap")
        if delete_heatmap:
            app_settings.heatmap_file.delete(save=False)
            app_settings.heatmap_file.name = None

        app_settings.benches_file = (
            request.FILES.get("benches_file")
            if request.FILES.get("benches_file")
            else app_settings.benches_file
        )
        delete_benches = request.POST.get("delete_benches")
        if delete_benches:
            app_settings.benches_file.delete(save=False)
            app_settings.benches_file.name = None

        app_settings.good_color = request.POST.get("good_color")
        app_settings.okay_color = request.POST.get("okay_color")
        app_settings.bad_color = request.POST.get("bad_color")
        app_settings.one_color = request.POST.get("one_color")
        app_settings.empty_color = request.POST.get("empty_color")

        app_settings.save()
        messages.success(request, "Settings updated successfully!")
        return redirect("settings")

    else:
        if not request.user.is_authenticated:
            return redirect("login")

        # Load the settings from the database
        app_settings = AppSettings.objects.get(user=request.user)

        admin_level = app_settings.admin_level

        heatmap_file = app_settings.heatmap_file
        heatmap_file_name = heatmap_file.name.split("/")[-1] if heatmap_file else None
        heatmap_file_url = (
            settings.STATIC_URL + heatmap_file_name if heatmap_file else None
        )

        benches_file = app_settings.benches_file
        benches_file_name = benches_file.name.split("/")[-1] if benches_file else None
        benches_file_url = (
            settings.STATIC_URL + benches_file_name if benches_file else None
        )

        good_color = app_settings.good_color
        okay_color = app_settings.okay_color
        bad_color = app_settings.bad_color
        one_color = app_settings.one_color
        empty_color = app_settings.empty_color

        # Pass the settings to the template
        context = {
            "admin_level": admin_level,
            "heatmap_file": heatmap_file,
            "heatmap_file_name": heatmap_file_name,
            "heatmap_file_url": heatmap_file_url,
            "benches_file": benches_file,
            "benches_file_name": benches_file_name,
            "benches_file_url": benches_file_url,
            "good_color": good_color,
            "okay_color": okay_color,
            "bad_color": bad_color,
            "one_color": one_color,
            "empty_color": empty_color,
        }

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
        heatmap = get_heatmap(request.user, city)

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

        show_options = {
            "good_streets": "show_good" in request.POST,
            "okay_streets": "show_okay" in request.POST,
            "bad_streets": "show_bad" in request.POST,
            "one_streets": "show_one" in request.POST,
            "zero_streets": "show_empty" in request.POST,
        }

        map = get_map(
            request.user,
            location_name=f"{city}, {district}",
            show_benches="show_benches" in request.POST,
            show_options=show_options,
            good_distance=int(request.POST.get("good_distance", "50")) / 111320,
            okay_distance=int(request.POST.get("okay_distance", "150")) / 111320,
            simulation="simulation" in request.POST,
            budget=request.POST.get("budget", None),
            bench_cost=request.POST.get("bench_cost", None),
        )

        return JsonResponse({"map_html": map._repr_html_()})
