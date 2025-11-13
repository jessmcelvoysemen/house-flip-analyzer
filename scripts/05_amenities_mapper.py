#!/usr/bin/env python3
"""
One-time script to count amenities near each Indianapolis neighborhood.
Cost: FREE (using OpenStreetMap Overpass API)

Amenities = parks, grocery stores, restaurants, gyms, coffee shops, etc.
More amenities = more attractive neighborhood = higher resale value.

Data Source: OpenStreetMap (free, open data)
API: Overpass API (no key needed!)

Usage:
1. No API key needed!
2. Run: python3 scripts/05_amenities_mapper.py
3. Copy output into function_app.py
"""

import requests
import time

# Neighborhoods with center coordinates (from Google Maps script)
NEIGHBORHOODS = {
    "Broad Ripple": (39.8686, -86.1431),
    "Fountain Square": (39.7473, -86.1472),
    "Downtown": (39.7684, -86.1581),
    "Irvington": (39.7834, -86.1047),
    "Mass Ave": (39.7736, -86.1528),
    "Fletcher Place": (39.7575, -86.1475),
    "Meridian-Kessler": (39.8186, -86.1581),
    "Butler-Tarkington": (39.8364, -86.1636),
    "Near Eastside": (39.7762, -86.1386),
    "Near Westside": (39.7762, -86.1775),
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def count_amenities(lat, lng, radius=800):
    """
    Count amenities within radius (meters) of a point using OpenStreetMap.
    radius=800 = ~0.5 miles = walkable distance
    """
    # Overpass QL query to find amenities
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"](around:{radius},{lat},{lng});
      node["shop"](around:{radius},{lat},{lng});
      node["leisure"="park"](around:{radius},{lat},{lng});
      way["leisure"="park"](around:{radius},{lat},{lng});
    );
    out count;
    """

    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
        if r.status_code == 200:
            data = r.json()

            # Count different types
            amenities = {"restaurants": 0, "shops": 0, "parks": 0, "total": 0}

            for element in data.get("elements", []):
                tags = element.get("tags", {})
                amenity_type = tags.get("amenity", "")
                shop_type = tags.get("shop", "")
                leisure_type = tags.get("leisure", "")

                amenities["total"] += 1

                if amenity_type in ["restaurant", "cafe", "fast_food", "bar"]:
                    amenities["restaurants"] += 1
                if shop_type or amenity_type in ["marketplace"]:
                    amenities["shops"] += 1
                if leisure_type == "park":
                    amenities["parks"] += 1

            return amenities
        else:
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("AMENITIES MAPPER - Walkable Neighborhood Features")
    print("="*70)
    print("\nUsing OpenStreetMap Overpass API (FREE!)")
    print("Counting amenities within 0.5 mile radius of each neighborhood\n")

    scores = {}

    for neighborhood, (lat, lng) in NEIGHBORHOODS.items():
        print(f"Checking {neighborhood}...", end=" ")

        amenities = count_amenities(lat, lng)

        if amenities:
            # Calculate amenity score (0-100)
            # More amenities = higher score
            total = amenities["total"]
            amenity_score = min(100, total * 2)  # Cap at 100

            scores[neighborhood] = {
                "score": round(amenity_score, 1),
                "total": total,
                "restaurants": amenities["restaurants"],
                "shops": amenities["shops"],
                "parks": amenities["parks"]
            }

            print(f"✓ {total} amenities (Score: {amenity_score:.1f}/100)")
        else:
            print("✗ Failed")

        # Be nice to the free API
        time.sleep(2)

    # Generate Python code
    print("\n" + "="*70)
    print("RESULTS - Add this to function_app.py:")
    print("="*70)
    print()
    print("# Amenity scores (higher = more walkable amenities nearby)")
    print("NEIGHBORHOOD_AMENITY_SCORES = {")
    for neighborhood in sorted(scores.keys()):
        data = scores[neighborhood]
        print(f'    "{neighborhood}": {data["score"]},  # {data["total"]} amenities ({data["restaurants"]} dining, {data["shops"]} shops, {data["parks"]} parks)')
    print("}")
    print()
    print("# Scoring logic to add:")
    print("# if amenity_score >= 70: bonus += 2  # Great walkability")
    print("# elif amenity_score >= 40: bonus += 1  # Good amenities")
    print()

    avg_score = sum(s["score"] for s in scores.values()) / len(scores) if scores else 0
    print(f"\n✅ Done! Average amenity score: {avg_score:.1f}/100")
    print("💰 Cost: $0 (FREE - OpenStreetMap!)")

if __name__ == "__main__":
    main()
