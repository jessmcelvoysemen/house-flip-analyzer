#!/usr/bin/env python3
"""
One-time script to fetch accurate ZIP codes for all Indianapolis-area census tracts using Google Maps.
Cost: ~$1-2 (all Central Indiana tracts * $5 per 1000 requests)

This fixes the listings bug where tracts were getting mapped to wrong ZIP codes based on crude ranges.

Usage:
1. Set GOOGLE_MAPS_API_KEY environment variable (same key as before)
2. Run: python3 scripts/06_google_maps_zip_codes.py
3. Copy the output and paste into function_app.py to replace get_zip_for_tract()
4. Delete this script!
"""

import os
import requests
import json
import time

# Set your Google Maps API key here or via environment variable
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_KEY_HERE")

# Census API
ACS_YEAR = "2023"
ACS_BASE = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

# Counties to process (same as your app)
COUNTIES = {
    "097": "Marion",      # Indianapolis
    "057": "Hamilton",    # Carmel, Fishers, Noblesville, Westfield
    "063": "Hendricks",   # Avon, Plainfield, Brownsburg
    "081": "Johnson",     # Greenwood, Franklin, Whiteland
    "011": "Boone",       # Zionsville, Lebanon
    "095": "Madison",     # Anderson
    "145": "Shelby",      # Shelbyville
    "109": "Morgan",      # Martinsville
    "059": "Hancock",     # Greenfield
}

def get_tract_center(geoid):
    """Get center lat/lng from Census tract GEOID using TIGER/Line API"""
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

    return None, None

def get_zip_from_google(lat, lng):
    """Call Google Maps Geocoding API to get ZIP code"""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if data["status"] == "OK" and data["results"]:
            # Extract postal_code from address_components
            for result in data["results"]:
                for component in result["address_components"]:
                    if "postal_code" in component["types"]:
                        return component["long_name"]

        return None
    except Exception as e:
        print(f"  Error calling Google Maps API: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("GOOGLE MAPS ZIP CODE MAPPER")
    print("="*70)
    print(f"\nFetching census tracts for Central Indiana counties...")

    if GOOGLE_MAPS_API_KEY == "YOUR_KEY_HERE":
        print("\n❌ ERROR: Set GOOGLE_MAPS_API_KEY environment variable first!")
        print("   export GOOGLE_MAPS_API_KEY='your-api-key-here'")
        return

    all_tracts = []

    # Fetch tracts for each county
    for county_fips, county_name in COUNTIES.items():
        print(f"  Fetching {county_name} County (FIPS {county_fips})...", end=" ")

        params = {
            "get": "NAME",
            "for": "tract:*",
            "in": f"state:18 county:{county_fips}"
        }

        try:
            r = requests.get(ACS_BASE, params=params, timeout=30)
            data = r.json()

            county_tracts = []
            for row in data[1:]:  # Skip header
                tract = row[-1]  # Last column is tract code
                geoid = f"18{county_fips}{tract}"
                county_tracts.append((county_fips, tract, geoid, county_name))

            all_tracts.extend(county_tracts)
            print(f"✓ {len(county_tracts)} tracts")
        except Exception as e:
            print(f"✗ Error: {e}")

    print(f"\n📊 Total: {len(all_tracts)} census tracts across {len(COUNTIES)} counties")
    print(f"💰 Estimated cost: ${len(all_tracts) * 0.005:.2f}")
    print("\nStarting ZIP code lookup (this will take a few minutes)...\n")

    mapping = {}  # { county_fips: { tract: zip } }
    errors = []

    for i, (county_fips, tract, geoid, county_name) in enumerate(all_tracts, 1):
        print(f"[{i}/{len(all_tracts)}] {county_name} tract {tract}...", end=" ")

        # Get tract center coordinates
        lat, lng = get_tract_center(geoid)

        if lat is None or lng is None:
            print(f"✗ No coordinates")
            errors.append(f"{county_name}-{tract}")
            continue

        # Call Google Maps
        zip_code = get_zip_from_google(lat, lng)

        if zip_code:
            if county_fips not in mapping:
                mapping[county_fips] = {}
            mapping[county_fips][tract] = zip_code
            print(f"✓ {zip_code}")
        else:
            errors.append(f"{county_name}-{tract}")
            print(f"✗ No ZIP found")

        # Rate limiting - be nice to Google's API
        time.sleep(0.2)  # 5 requests per second max

    # Generate Python code
    print("\n" + "="*70)
    print("RESULTS - Copy this into function_app.py:")
    print("="*70)
    print()
    print("# Google Maps ZIP code mapping (generated " + time.strftime("%Y-%m-%d") + ")")
    print("# Maps census tracts to accurate ZIP codes for listings lookups")
    print("TRACT_TO_ZIP_MAPPING = {")

    for county_fips in sorted(mapping.keys()):
        county_name = COUNTIES.get(county_fips, county_fips)
        print(f"    # {county_name} County (FIPS {county_fips})")
        print(f'    "{county_fips}": {{')
        for tract in sorted(mapping[county_fips].keys(), key=lambda x: int(x)):
            zip_code = mapping[county_fips][tract]
            print(f'        "{tract}": "{zip_code}",')
        print("    },")

    print("}")
    print()
    print("# Updated function to use the mapping:")
    print("def get_zip_for_tract(county_fips: str, tract: str) -> Optional[str]:")
    print('    """Map census tracts to ZIP codes using Google Maps data"""')
    print("    t = (tract or '').zfill(6)")
    print("    county_map = TRACT_TO_ZIP_MAPPING.get(county_fips, {})")
    print("    return county_map.get(t)")
    print()

    if errors:
        print(f"\n⚠️  {len(errors)} tracts had no ZIP code data:")
        for err in errors[:10]:  # Show first 10
            print(f"   {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more")

    total_mapped = sum(len(v) for v in mapping.values())
    print(f"\n✅ Done! Successfully mapped {total_mapped}/{len(all_tracts)} tracts")
    print(f"💰 Actual cost: ${len(all_tracts) * 0.005:.2f}")
    print("\n🔧 Next steps:")
    print("1. Copy the TRACT_TO_ZIP_MAPPING dictionary above")
    print("2. Paste it into api/function_app.py (after GOOGLE_MAPS_NEIGHBORHOODS)")
    print("3. Replace the get_zip_for_tract() function with the new version")
    print("4. Test with http://localhost:5001 to verify listings are accurate")
    print("5. Delete this script!")

if __name__ == "__main__":
    main()
