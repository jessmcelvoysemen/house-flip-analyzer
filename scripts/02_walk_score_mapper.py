#!/usr/bin/env python3
"""
One-time script to fetch Walk Scores for Indianapolis neighborhoods.
Cost: FREE (limited to 5000 requests/day on free tier)

Walk Score = how walkable is the neighborhood (0-100)
- 90-100: Walker's Paradise
- 70-89: Very Walkable
- 50-69: Somewhat Walkable
- 25-49: Car-Dependent
- 0-24: Car-Dependent (Driving Only)

Higher scores = more attractive to buyers, especially millennials/young families.

API: https://www.walkscore.com/professional/api.php
Sign up for free API key at: https://www.walkscore.com/professional/walk-score-apis.php

Usage:
1. Get free API key from Walk Score
2. Set WALK_SCORE_API_KEY environment variable
3. Run: python3 scripts/02_walk_score_mapper.py
4. Copy output into function_app.py
"""

import os
import requests
import time

WALK_SCORE_API_KEY = os.environ.get("WALK_SCORE_API_KEY", "YOUR_KEY_HERE")

# Representative coordinates for each Indianapolis neighborhood
# (You'd get these from the Google Maps script or manually)
NEIGHBORHOODS = {
    "Broad Ripple": (39.8686, -86.1431),
    "Fountain Square": (39.7473, -86.1472),
    "Downtown": (39.7684, -86.1581),
    "Irvington": (39.7834, -86.1047),
    "Mass Ave": (39.7736, -86.1528),
    "Fletcher Place": (39.7575, -86.1475),
    "Meridian-Kessler": (39.8186, -86.1581),
    "Butler-Tarkington": (39.8364, -86.1636),
    "Sobro": (39.7900, -86.1581),
    "Near Eastside": (39.7762, -86.1386),
    "Near Westside": (39.7762, -86.1775),
    "Garfield Park": (39.7356, -86.1472),
    "Beech Grove": (39.7212, -86.0886),
    "Lawrence": (39.8392, -86.0252),
}

def get_walk_score(lat, lng, address_label):
    """Fetch Walk Score for a location"""
    url = "https://api.walkscore.com/score"
    params = {
        "format": "json",
        "lat": lat,
        "lon": lng,
        "address": address_label,
        "wsapikey": WALK_SCORE_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if data.get("status") == 1:  # Success
            return data.get("walkscore"), data.get("description")
        else:
            return None, data.get("status")
    except Exception as e:
        return None, str(e)

def main():
    print("\n" + "="*70)
    print("WALK SCORE MAPPER - One-Time Neighborhood Scoring")
    print("="*70)

    if WALK_SCORE_API_KEY == "YOUR_KEY_HERE":
        print("\n❌ ERROR: Set WALK_SCORE_API_KEY first!")
        print("   Get free API key: https://www.walkscore.com/professional/api.php")
        print("   export WALK_SCORE_API_KEY='your-key-here'")
        return

    print(f"\nFetching Walk Scores for {len(NEIGHBORHOODS)} neighborhoods...")
    print("(FREE - no cost!)\n")

    scores = {}

    for neighborhood, (lat, lng) in NEIGHBORHOODS.items():
        print(f"Checking {neighborhood}...", end=" ")

        score, desc = get_walk_score(lat, lng, neighborhood)

        if score is not None:
            scores[neighborhood] = score
            print(f"✓ {score}/100 ({desc})")
        else:
            print(f"✗ Error: {desc}")

        time.sleep(1)  # Be nice to the API

    # Generate Python code
    print("\n" + "="*70)
    print("RESULTS - Add this to function_app.py for scoring bonus:")
    print("="*70)
    print()
    print("# Walk Score mapping (higher = more walkable = bonus points)")
    print("NEIGHBORHOOD_WALK_SCORES = {")
    for neighborhood in sorted(scores.keys()):
        print(f'    "{neighborhood}": {scores[neighborhood]},')
    print("}")
    print()
    print("# Scoring logic to add:")
    print("# if walk_score >= 70: bonus += 2  # Very walkable")
    print("# elif walk_score >= 50: bonus += 1  # Somewhat walkable")
    print()

    avg_score = sum(scores.values()) / len(scores) if scores else 0
    print(f"\n✅ Done! Average Walk Score: {avg_score:.1f}")
    print("💰 Cost: $0 (FREE!)")

if __name__ == "__main__":
    main()
