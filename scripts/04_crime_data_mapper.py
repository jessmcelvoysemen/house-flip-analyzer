#!/usr/bin/env python3
"""
One-time script to fetch crime statistics for Indianapolis neighborhoods.
Cost: FREE (using Indianapolis Open Data Portal)

Low crime = higher property values and easier resales.

Data Source: Indianapolis Open Data Portal
URL: https://data.indy.gov/

Usage:
1. No API key needed - it's public data!
2. Run: python3 scripts/04_crime_data_mapper.py
3. Copy output into function_app.py
"""

import requests
import time
from collections import defaultdict

# Socrata API endpoint for Indianapolis crime data (last 90 days)
CRIME_DATA_URL = "https://data.indy.gov/resource/crime-incidents.json"

# Neighborhood name mappings to match your app
NEIGHBORHOOD_BOUNDS = {
    # Format: "Name": (min_lat, max_lat, min_lng, max_lng)
    "Broad Ripple": (39.85, 39.88, -86.16, -86.13),
    "Downtown": (39.76, 39.78, -86.17, -86.15),
    "Fountain Square": (39.74, 39.76, -86.16, -86.14),
    "Irvington": (39.77, 39.79, -86.12, -86.09),
    "Mass Ave": (39.77, 39.78, -86.16, -86.14),
    "Near Eastside": (39.77, 39.78, -86.15, -86.13),
    "Fletcher Place": (39.75, 39.77, -86.16, -86.14),
    "Meridian-Kessler": (39.81, 39.83, -86.17, -86.15),
}

def fetch_recent_crimes():
    """Fetch recent crime data from Indianapolis Open Data"""
    try:
        # Limit to last 90 days, only get location data
        params = {
            "$limit": 50000,
            "$select": "latitude,longitude,ucr_hierarchy",
            "$where": "date > '2024-08-01T00:00:00.000'"  # Adjust date as needed
        }

        print("Fetching crime data from Indianapolis Open Data Portal...")
        r = requests.get(CRIME_DATA_URL, params=params, timeout=30)

        if r.status_code == 200:
            return r.json()
        else:
            print(f"Error: HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching crime data: {e}")
        return None

def categorize_crime(ucr_code):
    """Categorize crime by severity (property crimes matter most for home values)"""
    violent = ["HOMICIDE", "ROBBERY", "ASSAULT", "RAPE"]
    property_crime = ["BURGLARY", "THEFT", "AUTO THEFT", "VANDALISM"]

    if any(v in ucr_code.upper() for v in violent):
        return "violent"
    elif any(p in ucr_code.upper() for p in property_crime):
        return "property"
    else:
        return "other"

def count_crimes_by_neighborhood(crimes):
    """Count crimes in each neighborhood boundary"""
    counts = defaultdict(lambda: {"violent": 0, "property": 0, "other": 0, "total": 0})

    for crime in crimes:
        try:
            lat = float(crime.get("latitude", 0))
            lng = float(crime.get("longitude", 0))
            crime_type = categorize_crime(crime.get("ucr_hierarchy", ""))

            # Check which neighborhood this falls in
            for neighborhood, (min_lat, max_lat, min_lng, max_lng) in NEIGHBORHOOD_BOUNDS.items():
                if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                    counts[neighborhood][crime_type] += 1
                    counts[neighborhood]["total"] += 1
                    break
        except:
            continue

    return counts

def main():
    print("\n" + "="*70)
    print("CRIME DATA MAPPER - Indianapolis Neighborhoods")
    print("="*70)
    print("\nUsing Indianapolis Open Data Portal (FREE!)")
    print()

    crimes = fetch_recent_crimes()

    if not crimes:
        print("\n❌ Failed to fetch crime data")
        return

    print(f"✓ Fetched {len(crimes)} crime incidents")
    print("\nAnalyzing by neighborhood...\n")

    crime_counts = count_crimes_by_neighborhood(crimes)

    # Calculate crime scores (lower crime = higher score)
    scores = {}

    for neighborhood, counts in crime_counts.items():
        # Weight violent crimes more heavily
        weighted_crime = counts["violent"] * 3 + counts["property"] * 2 + counts["other"]

        # Convert to 0-100 scale (inverted - lower crime = higher score)
        # Assuming max ~500 weighted crimes in worst neighborhood
        safety_score = max(0, 100 - (weighted_crime / 5))

        scores[neighborhood] = round(safety_score, 1)

        print(f"{neighborhood}:")
        print(f"  Total incidents: {counts['total']}")
        print(f"  Violent: {counts['violent']}, Property: {counts['property']}")
        print(f"  Safety Score: {safety_score:.1f}/100")
        print()

    # Generate Python code
    print("="*70)
    print("RESULTS - Add this to function_app.py:")
    print("="*70)
    print()
    print("# Crime/Safety scores (higher = safer neighborhood)")
    print("NEIGHBORHOOD_SAFETY_SCORES = {")
    for neighborhood in sorted(scores.keys()):
        print(f'    "{neighborhood}": {scores[neighborhood]},')
    print("}")
    print()
    print("# Scoring logic to add:")
    print("# if safety_score >= 80: bonus += 2  # Very safe")
    print("# elif safety_score >= 60: bonus += 1  # Relatively safe")
    print("# elif safety_score < 40: penalty -= 2  # Higher crime")
    print()

    avg_safety = sum(scores.values()) / len(scores) if scores else 0
    print(f"\n✅ Done! Average safety score: {avg_safety:.1f}/100")
    print("💰 Cost: $0 (FREE - public data!)")
    print("\n💡 TIP: Re-run quarterly to keep data fresh")

if __name__ == "__main__":
    main()
