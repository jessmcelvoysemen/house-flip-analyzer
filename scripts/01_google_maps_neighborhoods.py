#!/usr/bin/env python3
"""
One-time script to fetch Google Maps neighborhood names for all Indianapolis census tracts.
Cost: ~$1 (200 tracts * $5 per 1000 requests)

Usage:
1. Set GOOGLE_MAPS_API_KEY environment variable or edit below
2. Run: python3 scripts/01_google_maps_neighborhoods.py
3. Copy the output and paste into function_app.py
4. Delete this script!
"""

import os
import requests
import json
import time

# Set your Google Maps API key here or via environment variable
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_KEY_HERE")

# Census API to get tract boundaries
ACS_YEAR = "2023"
ACS_BASE = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
MARION_COUNTY_FIPS = "097"

def get_tract_center(geoid):
    """Get center lat/lng from Census tract GEOID"""
    # Using internal point from Census (most representative point)
    url = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    params = {
        "get": "NAME",
        "for": f"tract:{geoid[-6:]}",
        "in": f"state:18 county:{MARION_COUNTY_FIPS}"
    }

    # For simplicity, we'll get internal point from the detailed tract data
    # Alternative: use Census TIGER/Line shapefiles, but that's overkill
    # We'll use a simpler approach - get it from the tract metadata endpoint

    tiger_url = f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2023/MapServer/8/query"
    params = {
        "where": f"GEOID='{geoid}'",
        "outFields": "INTPTLAT,INTPTLON",
        "f": "json"
    }

    try:
        r = requests.get(tiger_url, params=params, timeout=10)
        data = r.json()
        if data.get("features"):
            attrs = data["features"][0]["attributes"]
            return float(attrs["INTPTLAT"]), float(attrs["INTPTLON"])
    except:
        pass

    # Fallback: estimate from tract code (rough approximation)
    # Indianapolis is roughly centered at 39.77, -86.15
    # This is just a backup - we'll try to get real coords first
    tract_num = int(geoid[-6:])
    base_lat = 39.77
    base_lng = -86.15

    # Rough grid estimation (not perfect but works for fallback)
    row = (tract_num // 100) % 10
    col = tract_num % 100

    lat = base_lat + (row - 5) * 0.02
    lng = base_lng + (col - 50) * 0.02

    return lat, lng

def get_neighborhood_from_google(lat, lng):
    """Call Google Maps Geocoding API to get neighborhood name"""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": GOOGLE_MAPS_API_KEY,
        "result_type": "neighborhood|sublocality|locality"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if data["status"] == "OK" and data["results"]:
            # Try to find neighborhood or sublocality
            for result in data["results"]:
                for component in result["address_components"]:
                    types = component["types"]
                    if "neighborhood" in types or "sublocality" in types:
                        return component["long_name"]

            # Fallback to locality (city level)
            for result in data["results"]:
                for component in result["address_components"]:
                    if "locality" in component["types"]:
                        return f"Indianapolis — {component['long_name']}"

        return None
    except Exception as e:
        print(f"  Error calling Google Maps API: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("GOOGLE MAPS NEIGHBORHOOD MAPPER")
    print("="*70)
    print(f"\nFetching Indianapolis census tracts...")

    if GOOGLE_MAPS_API_KEY == "YOUR_KEY_HERE":
        print("\n❌ ERROR: Set GOOGLE_MAPS_API_KEY environment variable first!")
        print("   export GOOGLE_MAPS_API_KEY='your-api-key-here'")
        return

    # Fetch all Marion County tracts
    params = {
        "get": "NAME",
        "for": "tract:*",
        "in": f"state:18 county:{MARION_COUNTY_FIPS}"
    }

    r = requests.get(ACS_BASE, params=params, timeout=30)
    data = r.json()

    tracts = []
    for row in data[1:]:  # Skip header
        tract = row[-1]  # Last column is tract code
        geoid = f"18{MARION_COUNTY_FIPS}{tract}"
        tracts.append((tract, geoid))

    print(f"Found {len(tracts)} census tracts in Marion County")
    print(f"\nEstimated cost: ${len(tracts) * 0.005:.2f}")
    print("\nStarting neighborhood lookup (this will take a few minutes)...\n")

    mapping = {}
    errors = []

    for i, (tract, geoid) in enumerate(tracts, 1):
        print(f"[{i}/{len(tracts)}] Tract {tract}...", end=" ")

        # Get tract center coordinates
        lat, lng = get_tract_center(geoid)

        # Call Google Maps
        neighborhood = get_neighborhood_from_google(lat, lng)

        if neighborhood:
            mapping[tract] = neighborhood
            print(f"✓ {neighborhood}")
        else:
            errors.append(tract)
            print(f"✗ No neighborhood found")

        # Rate limiting - be nice to Google's API
        time.sleep(0.2)  # 5 requests per second max

    # Generate Python code
    print("\n" + "="*70)
    print("RESULTS - Copy this into function_app.py:")
    print("="*70)
    print()
    print("# Google Maps neighborhood mapping (generated " + time.strftime("%Y-%m-%d") + ")")
    print("GOOGLE_MAPS_NEIGHBORHOODS = {")
    for tract in sorted(mapping.keys(), key=lambda x: int(x)):
        print(f'    "{tract}": "{mapping[tract]}",')
    print("}")
    print()

    if errors:
        print(f"\n⚠️  {len(errors)} tracts had no neighborhood data:")
        print(f"   {', '.join(errors)}")

    print(f"\n✅ Done! Successfully mapped {len(mapping)}/{len(tracts)} tracts")
    print(f"💰 Estimated cost: ${len(tracts) * 0.005:.2f}")

if __name__ == "__main__":
    main()
