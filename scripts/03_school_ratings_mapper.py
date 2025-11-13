#!/usr/bin/env python3
"""
One-time script to fetch school ratings for Indianapolis neighborhoods.
Cost: FREE (GreatSchools API is free for non-commercial use)

School ratings are HUGE for resale value - especially for families.

API: https://www.greatschools.org/api/
Sign up: https://www.greatschools.org/api-request/

Usage:
1. Request free API key from GreatSchools
2. Set GREATSCHOOLS_API_KEY environment variable
3. Run: python3 scripts/03_school_ratings_mapper.py
4. Copy output into function_app.py as scoring bonus
"""

import os
import requests
import time

GREATSCHOOLS_API_KEY = os.environ.get("GREATSCHOOLS_API_KEY", "YOUR_KEY_HERE")

# ZIP codes for each major Indianapolis neighborhood
NEIGHBORHOOD_ZIPS = {
    "Broad Ripple": "46220",
    "Fountain Square": "46203",
    "Downtown": "46204",
    "Irvington": "46219",
    "Mass Ave": "46204",
    "Fletcher Place": "46203",
    "Meridian-Kessler": "46208",
    "Butler-Tarkington": "46208",
    "Near Eastside": "46201",
    "Lawrence": "46226",
    "Carmel": "46032",
    "Fishers": "46037",
    "Zionsville": "46077",
    "Greenwood": "46143",
    "Westfield": "46074",
}

def get_schools_in_zip(zip_code):
    """Fetch all schools in a ZIP code"""
    url = f"https://api.greatschools.org/schools"
    params = {
        "state": "IN",
        "zip": zip_code,
        "key": GREATSCHOOLS_API_KEY,
        "limit": 20
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            # Parse XML response (GreatSchools API returns XML)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)

            schools = []
            for school in root.findall(".//school"):
                rating = school.find("gsRating")
                school_type = school.find("type")
                name = school.find("name")

                if rating is not None and rating.text:
                    schools.append({
                        "name": name.text if name is not None else "Unknown",
                        "rating": int(rating.text),
                        "type": school_type.text if school_type is not None else "Unknown"
                    })

            return schools
        else:
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("SCHOOL RATINGS MAPPER - One-Time Data Collection")
    print("="*70)

    if GREATSCHOOLS_API_KEY == "YOUR_KEY_HERE":
        print("\n❌ ERROR: Set GREATSCHOOLS_API_KEY first!")
        print("   Request free API key: https://www.greatschools.org/api-request/")
        print("   export GREATSCHOOLS_API_KEY='your-key-here'")
        return

    print(f"\nFetching school ratings for {len(NEIGHBORHOOD_ZIPS)} neighborhoods...")
    print("(FREE API - may take a minute)\n")

    ratings = {}

    for neighborhood, zip_code in NEIGHBORHOOD_ZIPS.items():
        print(f"Checking {neighborhood} (ZIP {zip_code})...", end=" ")

        schools = get_schools_in_zip(zip_code)

        if schools:
            # Calculate average rating for the neighborhood
            avg_rating = sum(s["rating"] for s in schools) / len(schools) if schools else 0
            ratings[neighborhood] = {
                "avg_rating": round(avg_rating, 1),
                "num_schools": len(schools),
                "top_school": max(schools, key=lambda x: x["rating"])["rating"] if schools else 0
            }
            print(f"✓ Avg: {avg_rating:.1f}/10 ({len(schools)} schools)")
        else:
            print(f"✗ No data")

        time.sleep(1)  # Rate limiting

    # Generate Python code
    print("\n" + "="*70)
    print("RESULTS - Add this to function_app.py:")
    print("="*70)
    print()
    print("# School ratings mapping (higher = better schools = bonus points)")
    print("NEIGHBORHOOD_SCHOOL_RATINGS = {")
    for neighborhood in sorted(ratings.keys()):
        data = ratings[neighborhood]
        print(f'    "{neighborhood}": {data["avg_rating"]},  # {data["num_schools"]} schools, top: {data["top_school"]}/10')
    print("}")
    print()
    print("# Scoring logic to add:")
    print("# if school_rating >= 7: bonus += 3  # Great schools")
    print("# elif school_rating >= 5: bonus += 1  # Good schools")
    print()

    avg = sum(r["avg_rating"] for r in ratings.values()) / len(ratings) if ratings else 0
    print(f"\n✅ Done! Average school rating: {avg:.1f}/10")
    print("💰 Cost: $0 (FREE!)")

if __name__ == "__main__":
    main()
