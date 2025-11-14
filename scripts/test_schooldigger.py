#!/usr/bin/env python3
"""
Quick test to see what SchoolDigger API actually returns
"""

import os
import requests
import json

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "YOUR_KEY_HERE")
RAPIDAPI_HOST = "schooldigger-k-12-school-data-api.p.rapidapi.com"

def test_api():
    url = "https://schooldigger-k-12-school-data-api.p.rapidapi.com/v2.0/schools"

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    # Test 1: Just state
    print("TEST 1: Just state parameter")
    params = {"st": "IN", "perPage": 5}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Full response:\n{json.dumps(data, indent=2)[:1000]}")
    else:
        print(f"Error: {r.text[:500]}")

    print("\n" + "="*70 + "\n")

    # Test 2: State + ZIP
    print("TEST 2: State + ZIP parameter")
    params = {"st": "IN", "zip": "46220", "perPage": 5}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Full response:\n{json.dumps(data, indent=2)[:1000]}")
    else:
        print(f"Error: {r.text[:500]}")

if __name__ == "__main__":
    test_api()
