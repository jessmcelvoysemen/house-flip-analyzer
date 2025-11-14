#!/usr/bin/env python3
"""
One-time script to fetch school ratings for Indianapolis neighborhoods.
Cost: FREE (2,000 calls/month with SchoolDigger via RapidAPI)

School ratings are HUGE for resale value - especially for families.

API: SchoolDigger via RapidAPI
Sign up: https://rapidapi.com/schooldigger-schooldigger-default/api/schooldigger-k-12-school-data-api

Usage:
1. Get RapidAPI key (you already have one from Realtor.com!)
2. Set RAPIDAPI_KEY environment variable
3. Run: python3 scripts/03_school_ratings_mapper.py
4. Copy output into function_app.py as scoring bonus
"""

import os
import requests
import time
import statistics

# Use the same RapidAPI key as your Realtor.com API
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "YOUR_KEY_HERE")
RAPIDAPI_HOST = "schooldigger-k-12-school-data-api.p.rapidapi.com"

# ZIP codes for Indianapolis metro area neighborhoods and suburbs
# Covers all 9 counties in your census data: Marion, Hamilton, Hendricks,
# Johnson, Boone, Hancock, Madison, Morgan, Shelby
NEIGHBORHOOD_ZIPS = {
    # ===== MARION COUNTY (Indianapolis) =====

    # Downtown/Central
    "Downtown": "46204",
    "Mass Ave": "46204",
    "Lockerbie Square": "46202",

    # Near Eastside/Southeast
    "Fountain Square": "46203",
    "Fletcher Place": "46225",
    "Bates-Hendricks": "46203",
    "Irvington": "46219",
    "Near Eastside": "46201",
    "Fall Creek Place": "46205",
    "Near Southeast": "46203",

    # North Indianapolis
    "Broad Ripple": "46220",
    "Meridian-Kessler": "46208",
    "Butler-Tarkington": "46208",
    "Crown Hill": "46208",

    # Northeast/Lawrence/Castleton
    "Lawrence": "46226",
    "Castleton": "46250",
    "Geist": "46236",
    "Fort Ben Harrison": "46216",

    # West/Southwest Indianapolis
    "Speedway": "46224",
    "Near Westside": "46222",
    "West Indianapolis": "46221",
    "Pike Township": "46254",

    # South Indianapolis
    "Beech Grove": "46107",
    "Garfield Park": "46225",
    "Southport": "46227",
    "Perry Township": "46217",

    # ===== HAMILTON COUNTY (Wealthy Northern Suburbs) =====
    "Carmel": "46032",
    "Carmel - North": "46033",
    "Fishers": "46037",
    "Fishers - North": "46038",
    "Westfield": "46074",
    "Noblesville": "46060",
    "Cicero": "46034",

    # ===== BOONE COUNTY (Northwest Suburbs) =====
    "Zionsville": "46077",
    "Lebanon": "46052",
    "Whitestown": "46075",

    # ===== HENDRICKS COUNTY (West Suburbs) =====
    "Plainfield": "46168",
    "Avon": "46123",
    "Brownsburg": "46112",
    "Danville": "46122",

    # ===== JOHNSON COUNTY (South Suburbs) =====
    "Greenwood": "46143",
    "Franklin": "46131",
    "Whiteland": "46184",
    "New Whiteland": "46184",
    "Bargersville": "46106",

    # ===== HANCOCK COUNTY (East Suburbs) =====
    "Greenfield": "46140",
    "New Palestine": "46163",
    "McCordsville": "46055",

    # ===== MADISON COUNTY (Northeast - Anderson Area) =====
    "Anderson": "46016",
    "Anderson - East": "46012",
    "Anderson - South": "46013",
    "Pendleton": "46064",
    "Chesterfield": "46017",

    # ===== MORGAN COUNTY (Southwest) =====
    "Martinsville": "46151",
    "Mooresville": "46158",

    # ===== SHELBY COUNTY (Southeast) =====
    "Shelbyville": "46176",
}

def get_schools_in_zip(zip_code):
    """Fetch all schools in a ZIP code via SchoolDigger API"""
    # SchoolDigger API endpoint v2.0 (via RapidAPI)
    url = "https://schooldigger-k-12-school-data-api.p.rapidapi.com/v2.0/schools"

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    params = {
        "st": "IN",  # State code (required)
        "zip": zip_code,
        "perPage": 50  # Get more schools to ensure we cover the area
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)

        if r.status_code == 200:
            data = r.json()
            schools = []

            # SchoolDigger v2.0 returns a list of school objects
            # Try different possible keys for the school list
            school_list = data.get("schoolList", data.get("schools", []))

            for school in school_list:
                # SchoolDigger uses "rankingstatewide" or "rankingStatewide" as the rating metric
                # It's a percentile rank (1-100), we'll convert to 1-10 scale
                rank = school.get("rankingstatewide") or school.get("rankingStatewide")
                name = school.get("schoolName", school.get("name", "Unknown"))
                level = school.get("schoolLevel", school.get("level", "Unknown"))

                if rank is not None:
                    # Convert percentile rank to 1-10 rating
                    # Top 10% = 10, 10-20% = 9, etc.
                    rating = max(1, min(10, 11 - (rank // 10)))

                    schools.append({
                        "name": name,
                        "rating": rating,
                        "type": level,
                        "rank_percentile": rank
                    })

            return schools
        elif r.status_code == 429:
            print(f"    Rate limit hit!")
            return None
        else:
            print(f"    API error: {r.status_code} - {r.text[:200]}")
            return None

    except Exception as e:
        print(f"    Error: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("SCHOOL RATINGS MAPPER - One-Time Data Collection")
    print("="*70)

    if RAPIDAPI_KEY == "YOUR_KEY_HERE":
        print("\n❌ ERROR: Set RAPIDAPI_KEY first!")
        print("   Use the same RapidAPI key from your Realtor.com setup")
        print("   export RAPIDAPI_KEY='your-rapidapi-key-here'")
        return

    print(f"\nFetching school ratings for {len(NEIGHBORHOOD_ZIPS)} neighborhoods...")
    print("(SchoolDigger via RapidAPI - 2,000 free calls/month)\n")

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
    total_calls = sum(r["num_schools"] for r in ratings.values())
    print(f"\n✅ Done! Average school rating: {avg:.1f}/10")
    print(f"📊 API calls used: {total_calls} / 2,000 free monthly limit")
    print("💰 Cost: $0 (FREE - well under monthly limit!)")

if __name__ == "__main__":
    main()
