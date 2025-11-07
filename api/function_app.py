import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import azure.functions as func
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- Config ---
ACS_YEAR = "2023"
ACS_BASE = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "realty-in-us.p.rapidapi.com")
RAPIDAPI_TEST_URL = os.environ.get(
    "RAPIDAPI_TEST_URL",
    "https://realty-in-us.p.rapidapi.com/properties/v3/list"
)

DEFAULT_PRICE_MIN = int(os.environ.get("PRICE_MIN", "150000"))
DEFAULT_PRICE_MAX = int(os.environ.get("PRICE_MAX", "250000"))

CENTRAL_IN_COUNTIES = {
    "Boone": "011",
    "Hamilton": "057",
    "Hancock": "059",
    "Hendricks": "063",
    "Johnson": "081",
    "Madison": "095",
    "Marion": "097",
    "Morgan": "109",
    "Shelby": "145",
}

ACS_VARS = {
    "B01003_001E": "total_pop",
    "B25001_001E": "housing_units",
    "B25002_003E": "housing_vacant",
    "B25077_001E": "median_home_value",
    "B19013_001E": "median_income",
    "B25064_001E": "median_gross_rent",
}

MAX_MARKET_LOOKUPS_DEFAULT = 10
REQUEST_TIMEOUT = 60

# --- Simple in-memory caches ---
_census_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_HOURS = 24
_dom_cache: Dict[str, Optional[int]] = {}

def safe_int(x: Any) -> Optional[int]:
    """Convert to int, treating Census sentinel values (negatives) as None"""
    try:
        val = int(float(x))
        # Census API uses large negative numbers as sentinel "N/A" values
        # Common ones: -666666666, -222222222, -999999999, -888888888
        # Treat any negative as missing data
        if val < 0:
            return None
        return val
    except Exception:
        return None

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def tract_id_human(tract_str: str) -> str:
    if not tract_str:
        return ""
    t = tract_str.zfill(6)
    return f"{t[:4]}.{t[4:]}"

def neighborhood_label(county_name: str, tract: str) -> str:
    """Map census tracts to recognizable neighborhoods/cities"""
    t = (tract or "").zfill(6)

    # For Marion County, use 4-digit tract codes since they only span 31xx-39xx
    if county_name == "Marion":
        try:
            code = int(t[:4]) if len(t) >= 4 else 0
        except:
            code = 0

        # Split Marion County (Indianapolis) into ~15 neighborhoods using 4-digit codes
        if code < 3120:  return "Indianapolis — Near Eastside"
        if code < 3140:  return "Indianapolis — Eastside"
        if code < 3160:  return "Indianapolis — Far Eastside"
        if code < 3180:  return "Indianapolis — Lawrence/Castleton"
        if code < 3200:  return "Indianapolis — Northeast"
        if code < 3220:  return "Indianapolis — Broad Ripple/Butler-Tarkington"
        if code < 3240:  return "Indianapolis — Meridian-Kessler/SoBro"
        if code < 3260:  return "Indianapolis — Downtown/Mass Ave"
        if code < 3280:  return "Indianapolis — Near Westside/Haughville"
        if code < 3300:  return "Indianapolis — Fountain Square/Fletcher Place"
        if code < 3330:  return "Indianapolis — Irvington/Warren Park"
        if code < 3360:  return "Indianapolis — Near Southside/Garfield Park"
        if code < 3400:  return "Indianapolis — Southport/Beech Grove"
        if code < 3450:  return "Indianapolis — Perry Township"
        if code < 3500:  return "Indianapolis — Greenwood Area/Center Grove"
        if code < 3550:  return "Indianapolis — Decatur/Southwest"
        if code < 3650:  return "Indianapolis — Pike Township/Northwest"
        if code < 3750:  return "Indianapolis — Washington Township/North"
        if code < 3850:  return "Indianapolis — Lawrence Township/Northeast"
        return "Indianapolis — Wayne Township/Southwest"

    # For other counties, use 2-digit codes as before
    head = int(t[:2]) if t[:2].isdigit() else 0

    if county_name == "Hamilton":
        # Wealthy suburbs - break into cities
        if head <= 8:  return "Noblesville"
        if head <= 15:  return "Westfield"
        if head <= 25:  return "Carmel — North"
        if head <= 35:  return "Carmel — South/Keystone"
        if head <= 50:  return "Fishers — North"
        if head <= 70:  return "Fishers — South/Geist"
        return "Hamilton County — North suburbs"

    if county_name == "Hendricks":
        if head <= 15:  return "Avon"
        if head <= 35:  return "Plainfield"
        if head <= 50:  return "Brownsburg"
        return "Danville/Hendricks County"

    if county_name == "Johnson":
        if head <= 20:  return "Greenwood"
        if head <= 40:  return "Franklin"
        if head <= 60:  return "Whiteland/New Whiteland"
        return "Johnson County — South suburbs"

    if county_name == "Boone":
        if head <= 20:  return "Zionsville"
        if head <= 50:  return "Lebanon"
        return "Boone County — Whitestown area"

    if county_name == "Madison":
        if head <= 10:  return "Anderson — West Side"
        if head <= 20:  return "Anderson — Downtown/Central"
        if head <= 35:  return "Anderson — East Side"
        if head <= 50:  return "Anderson — South"
        return "Madison County — Pendleton/Chesterfield"

    if county_name == "Shelby":
        if head <= 30:  return "Shelbyville — Central"
        return "Shelby County — Outlying"

    if county_name == "Morgan":
        if head <= 30:  return "Martinsville"
        return "Morgan County — Outlying"

    if county_name == "Hancock":
        if head <= 30:  return "Greenfield"
        return "Hancock County — Outlying"

    return f"{county_name} County"

# --- Listings cache (per ZIP) ---
_listings_cache = {}  # { zip: {"ts": ISO_UTC, "data": {...}} }
LISTINGS_CACHE_HOURS = 6

def _cache_get_listings(zip_code: str):
    entry = _listings_cache.get(zip_code)
    if not entry:
        return None
    try:
        ts = datetime.fromisoformat(entry["ts"])
        if datetime.utcnow() - ts > timedelta(hours=LISTINGS_CACHE_HOURS):
            del _listings_cache[zip_code]
            return None
    except Exception:
        del _listings_cache[zip_code]
        return None
    return entry["data"]

def _cache_set_listings(zip_code: str, data: dict) -> None:
    _listings_cache[zip_code] = {"ts": datetime.utcnow().isoformat(), "data": data}

# === CENSUS DATA WITH CACHE/RETRY ===

def get_cached_census_data(county_fips: str) -> Optional[List[List[str]]]:
    if county_fips not in _census_cache:
        return None
    cache_entry = _census_cache[county_fips]
    cache_time = datetime.fromisoformat(cache_entry["cached_at"])
    if datetime.utcnow() - cache_time > timedelta(hours=CACHE_DURATION_HOURS):
        del _census_cache[county_fips]
        return None
    return cache_entry["data"]

def cache_census_data(county_fips: str, data: List[List[str]]) -> None:
    _census_cache[county_fips] = {"data": data, "cached_at": datetime.utcnow().isoformat()}

def fetch_census_data_with_retry(county_name: str, county_fips: str, max_retries: int = 3) -> Optional[List[List[str]]]:
    cached = get_cached_census_data(county_fips)
    if cached is not None:
        logging.info("✅ Using cached ACS for %s", county_name)
        return cached

    params = {
        "get": ",".join(ACS_VARS.keys()),
        "for": "tract:*",
        "in": f"state:18 county:{county_fips}",
    }
    for attempt in range(max_retries):
        try:
            timeout = REQUEST_TIMEOUT * (attempt + 1)
            r = requests.get(ACS_BASE, params=params, timeout=timeout)
            if r.status_code == 503:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            r.raise_for_status()
            data = r.json()
            if not data or len(data) < 2:
                return None
            cache_census_data(county_fips, data)
            return data
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    return None

# === MARKET DATA (optional) ===

def get_market_stats_for_zip(zip_code: str) -> Dict[str, Optional[int]]:
    if not zip_code:
        return {"median_days_on_market": None}
    if zip_code in _dom_cache:
        return {"median_days_on_market": _dom_cache[zip_code]}
    if not (RAPIDAPI_KEY and RAPIDAPI_HOST and RAPIDAPI_TEST_URL):
        _dom_cache[zip_code] = None
        return {"median_days_on_market": None}

    try:
        payload = {
            "limit": 25,
            "offset": 0,
            "postal_code": zip_code,
            "status": ["for_sale", "under_contract"],
            "sort": {"direction": "desc", "field": "list_date"},
        }
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }
        resp = requests.post(RAPIDAPI_TEST_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            _dom_cache[zip_code] = None
            return {"median_days_on_market": None}
        resp.raise_for_status()
        data = resp.json()

        days = []
        props = (data or {}).get("data", {}).get("home_search", {}).get("results", []) or []
        for p in props:
            dom = (p.get("days_on_market") or p.get("list_days_on_market") or p.get("dom"))
            if isinstance(dom, int) and dom >= 0:
                days.append(dom)

        if not days:
            _dom_cache[zip_code] = None
            return {"median_days_on_market": None}

        days.sort()
        median_dom = days[len(days)//2]
        _dom_cache[zip_code] = int(median_dom)
        return {"median_days_on_market": int(median_dom)}
    except Exception as e:
        logging.warning("Market data lookup failed for %s: %s", zip_code, e)
        _dom_cache[zip_code] = None
        return {"median_days_on_market": None}

def get_zip_for_tract(county_fips: str, tract: str) -> Optional[str]:
    """Map census tracts to ZIP codes for market data lookups"""
    t2 = int((tract or "000000").zfill(6)[:2])

    if county_fips == "097":  # Marion (Indianapolis)
        if t2 <= 5: return "46239"      # Far Eastside
        if t2 <= 12: return "46226"     # Lawrence/Castleton
        if t2 <= 18: return "46220"     # Broad Ripple
        if t2 <= 25: return "46202"     # Downtown
        if t2 <= 32: return "46203"     # Fountain Square
        if t2 <= 38: return "46219"     # Irvington
        if t2 <= 45: return "46227"     # Southport
        if t2 <= 52: return "46254"     # Pike
        if t2 <= 65: return "46241"     # Decatur
        if t2 <= 75: return "46237"     # Franklin Township
        return "46217"                  # Perry Township

    if county_fips == "057":  # Hamilton
        if t2 <= 8: return "46060"      # Noblesville
        if t2 <= 15: return "46074"     # Westfield
        if t2 <= 25: return "46032"     # Carmel North
        if t2 <= 35: return "46033"     # Carmel South
        if t2 <= 50: return "46038"     # Fishers North
        return "46037"                  # Fishers South/Geist

    if county_fips == "063":  # Hendricks
        if t2 <= 15: return "46123"     # Avon
        if t2 <= 35: return "46168"     # Plainfield
        return "46112"                  # Brownsburg

    if county_fips == "081":  # Johnson
        if t2 <= 20: return "46143"     # Greenwood
        if t2 <= 40: return "46131"     # Franklin
        return "46184"                  # Whiteland

    if county_fips == "011":  # Boone
        if t2 <= 20: return "46077"     # Zionsville
        return "46052"                  # Lebanon

    if county_fips == "095":  # Madison
        if t2 <= 10: return "46011"     # Anderson West
        if t2 <= 20: return "46016"     # Anderson Downtown
        if t2 <= 35: return "46013"     # Anderson East
        return "46017"                  # Anderson South

    if county_fips == "145":  # Shelby
        return "46176"                  # Shelbyville

    if county_fips == "109":  # Morgan
        return "46151"                  # Martinsville

    if county_fips == "059":  # Hancock
        return "46140"                  # Greenfield

    return None

# === SCORING ===

def score_tract_flip_potential(tract: Dict[str, Any], price_min: int, price_max: int) -> Dict[str, Any]:
    mhv = tract.get("median_home_value") or 0
    income = tract.get("median_income") or 0
    vacancy_pct = tract.get("vacancy_pct") or 0.0
    dom = tract.get("days_on_market")

    # Gap score
    gap_ratio = (mhv / price_max) if price_max > 0 else 0
    if mhv <= 0: gap_score = 0.0; gap_ratio = 0.0
    elif gap_ratio < 1.1: gap_score = 0.0
    elif 1.1 <= gap_ratio <= 1.6:
        ideal = 1.35
        gap_score = clamp01(1.0 - (abs(gap_ratio - ideal) / 0.25))
    else:
        gap_score = clamp01(max(0.0, 1.0 - (gap_ratio - 1.6) * 0.5))

    # Vacancy score
    if 8.0 <= vacancy_pct <= 15.0: vacancy_score = 1.0
    else: vacancy_score = clamp01(1.0 - (min(abs(vacancy_pct-8.0), abs(vacancy_pct-15.0)) / 15.0))

    # Income score
    if mhv > 0:
        ideal_income = mhv / 3.5
        r = income / ideal_income if ideal_income > 0 else 0
        income_score = 1.0 if 0.8 <= r <= 1.2 else (clamp01(r) if r < 0.8 else clamp01(2.0 - r))
    else:
        income_score = 0.0

    # Velocity score
    if dom is not None and dom > 0:
        if dom < 30: velocity_score = 1.0
        elif dom <= 60: velocity_score = 0.7
        elif dom <= 90: velocity_score = 0.4
        else: velocity_score = 0.2
    else:
        velocity_score = 0.5

    total = 0.50*gap_score + 0.20*vacancy_score + 0.20*income_score + 0.10*velocity_score
    total_score = round(total * 100, 1)

    insights, warnings = [], []
    if 1.3 <= gap_ratio <= 1.4: insights.append("💰 Strong profit potential in this price range")
    elif gap_ratio < 1.1: warnings.append("⚠️ Limited profit margin")
    elif gap_ratio > 1.7: warnings.append("⚠️ Median value significantly above budget")
    if 10 <= vacancy_pct <= 13: insights.append("✓ Healthy inventory levels")
    elif vacancy_pct < 5: warnings.append("⚠️ Limited inventory availability")
    elif vacancy_pct > 20: warnings.append("⚠️ High vacancy may indicate market weakness")
    if income >= mhv/3.5: insights.append("✓ Strong buyer income for resale")
    elif income < mhv/4.5: warnings.append("⚠️ Income levels may limit buyer pool")
    if dom and dom < 40: insights.append(f"⚡ Fast-moving market (~{dom} days)")
    elif dom and dom > 90: warnings.append(f"⚠️ Slower market (~{dom} days to sell)")

    return {
        "score": total_score,
        "gap_ratio": round(gap_ratio, 2),
        "gap_score": round(gap_score * 100, 1),
        "vacancy_score": round(vacancy_score * 100, 1),
        "income_score": round(income_score * 100, 1),
        "velocity_score": round(velocity_score * 100, 1),
        "insights": insights,
        "warnings": warnings,
    }

# === GROUP AGGREGATION ===

def pop_weighted_avg(values: List[Tuple[Optional[float], int]]) -> Optional[float]:
    num = 0.0
    den = 0
    for v, w in values:
        if v is None: continue
        num += float(v) * int(w or 0)
        den += int(w or 0)
    if den == 0: return None
    return num / den

def aggregate_group(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_pop = sum(int(r.get("total_pop") or 0) for r in rows)
    med_home_val = pop_weighted_avg([(r.get("median_home_value"), r.get("total_pop") or 0) for r in rows])
    med_income   = pop_weighted_avg([(r.get("median_income"), r.get("total_pop") or 0) for r in rows])
    vac_pct      = pop_weighted_avg([(r.get("vacancy_pct"), r.get("total_pop") or 0) for r in rows])

    # Only aggregate DOM if at least one tract in group has it
    dom_values = [(r.get("days_on_market"), r.get("total_pop") or 0) for r in rows if r.get("days_on_market") is not None]
    dom = pop_weighted_avg(dom_values) if dom_values else None

    gap_ratio    = pop_weighted_avg([(r.get("gap_ratio"), r.get("total_pop") or 0) for r in rows])
    area_score   = pop_weighted_avg([(r.get("score"), r.get("total_pop") or 0) for r in rows])

    # 👉 Derive messages from the aggregated metrics (not by unioning tract messages)
    insights: List[str] = []
    warnings: List[str] = []

    if gap_ratio is not None:
        if 1.3 <= gap_ratio <= 1.4:
            insights.append("💰 Strong profit potential in this price range")
        elif gap_ratio < 1.1:
            warnings.append("⚠️ Limited profit margin")
        elif gap_ratio > 1.7:
            warnings.append("⚠️ Median value significantly above budget")

    if vac_pct is not None:
        if 8.0 <= vac_pct <= 15.0:
            insights.append("✓ Healthy inventory levels")
        elif vac_pct < 5.0:
            warnings.append("⚠️ Limited inventory availability")
        elif vac_pct > 20.0:
            warnings.append("⚠️ High vacancy may indicate market weakness")

    if med_home_val and med_income:
        ideal_income = med_home_val / 3.5
        ratio = (med_income / ideal_income) if ideal_income else 0
        if ratio >= 1.0:
            insights.append("✓ Strong buyer income for resale")
        elif ratio < 0.8:
            warnings.append("⚠️ Income levels may limit buyer pool")

    if dom is not None:
        if dom < 40:
            insights.append(f"⚡ Fast-moving market (~{int(dom)} days)")
        elif dom > 90:
            warnings.append(f"⚠️ Slower market (~{int(dom)} days to sell)")

    # Keep cards concise
    insights = insights[:3]
    warnings = warnings[:3]

    members = [{
        "tract_id": r.get("tract_id"),
        "zip_code": r.get("zip_code"),
        "score": r.get("score")
    } for r in rows]

    return {
        "median_home_value": round(med_home_val, 1) if med_home_val is not None else None,
        "median_income": round(med_income, 1) if med_income is not None else None,
        "vacancy_pct": round(vac_pct, 1) if vac_pct is not None else None,
        "days_on_market": int(dom) if dom is not None else None,
        "gap_ratio": round(gap_ratio, 2) if gap_ratio is not None else None,
        "total_pop": total_pop,
        "score": round(area_score, 1) if area_score is not None else 0.0,
        "insights": insights,
        "warnings": warnings,
        "member_tracts": members,
        "tracts_count": len(rows),
    }

# === HTTP ===

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def _to_bool(v: Optional[str], default: bool=False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1","true","yes","y","on")

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({
            "status": "ok",
            "ts": datetime.utcnow().isoformat(),
            "cache": {"census_counties_cached": len(_census_cache), "dom_zips_cached": len(_dom_cache)}
        }),
        mimetype="application/json",
        headers=CORS_HEADERS
    )

@app.route(route="analyze", methods=["GET", "POST", "OPTIONS"])
def analyze_neighborhoods(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=CORS_HEADERS)
    logging.info("🚀 Starting neighborhood analysis")

    try:
        # ---- inputs (robust) ----
        top_n = max(1, min(int(req.params.get("top", "50")), 50))
        price_min = int(req.params.get("price_min", DEFAULT_PRICE_MIN))
        price_max = int(req.params.get("price_max", DEFAULT_PRICE_MAX))
        if price_min > price_max:
            price_min, price_max = price_max, price_min
        min_score = float(req.params.get("min_score", "0"))

        include_market_data = _to_bool(
            req.params.get("marketdata")
            or req.params.get("market_data")
            or req.params.get("include_market_data")
            or req.params.get("use_market_data"),
            False
        )
        if top_n > 50:
            include_market_data = False  # throttle to avoid timeouts

        do_group = _to_bool(
            req.params.get("groupneighborhood")
            or req.params.get("group_neighborhood")
            or req.params.get("groupNeighborhood"),
            True
        )
        if req.params.get("group", "").lower() == "neighborhood":
            do_group = True

        try:
            rehab_budget = int(req.params.get("rehab_budget", "40000"))
        except Exception:
            rehab_budget = 40000

        max_market_lookups = min(int(req.params.get("max_market_lookups", MAX_MARKET_LOOKUPS_DEFAULT)), 50)

        # ---- fetch ACS across counties ----
        all_tracts: List[Dict[str, Any]] = []
        errors: List[str] = []
        for county_name, county_fips in CENTRAL_IN_COUNTIES.items():
            data = fetch_census_data_with_retry(county_name, county_fips)
            if data is None:
                errors.append(f"Failed to fetch {county_name} after retries")
                continue

            headers = data[0]; rows = data[1:]
            for row in rows:
                rec = dict(zip(headers, row))
                total_housing = safe_int(rec.get("B25001_001E"))
                vacant = safe_int(rec.get("B25002_003E"))
                vacancy_pct = 0.0
                if total_housing and vacant is not None and total_housing > 0:
                    vacancy_pct = (vacant / total_housing) * 100.0

                tract = rec.get("tract")
                item: Dict[str, Any] = {
                    "state": rec.get("state"),
                    "county": rec.get("county"),
                    "tract": tract,
                    "county_name": county_name,
                    "neighborhood": neighborhood_label(county_name, tract),
                    "tract_id": tract_id_human(tract or ""),
                    "total_pop": safe_int(rec.get("B01003_001E")),
                    "housing_units": total_housing,
                    "housing_vacant": vacant,
                    "vacancy_pct": round(vacancy_pct, 1),
                    "median_home_value": safe_int(rec.get("B25077_001E")),
                    "median_income": safe_int(rec.get("B19013_001E")),
                    "median_gross_rent": safe_int(rec.get("B25064_001E")),
                }
                item.update(score_tract_flip_potential(item, price_min=price_min, price_max=price_max))
                all_tracts.append(item)

        all_tracts.sort(key=lambda x: x["score"], reverse=True)
        filtered = [t for t in all_tracts if (t.get("score") or 0) >= min_score]

        # optional market data
        if include_market_data and RAPIDAPI_KEY:
            logging.info(f"🔍 Fetching market data for up to {max_market_lookups} areas...")
            looked = 0
            for t in filtered:
                if looked >= max_market_lookups: break
                try:
                    zip_guess = get_zip_for_tract(t.get("county"), t.get("tract"))
                    if not zip_guess: continue
                    market_stats = get_market_stats_for_zip(zip_guess)
                    dom = market_stats.get("median_days_on_market") if market_stats else None
                    if dom is not None:
                        t["days_on_market"] = int(dom)
                        t["zip_code"] = zip_guess
                        looked += 1
                        logging.info(f"  ✓ ZIP {zip_guess}: {dom} days on market")
                    time.sleep(0.15)
                except Exception as e:
                    logging.warning(f"  ✗ Failed to fetch market data for tract: {e}")
                    continue
            logging.info(f"✅ Market data fetched for {looked} areas")

        if not do_group:
            top_ops = filtered[:top_n]
            return func.HttpResponse(json.dumps({
                "status": "success",
                "total_tracts_analyzed": len(all_tracts),
                "rehab_budget_used": rehab_budget,
                "opportunities": top_ops,
                "summary": {
                    "top_score": top_ops[0]["score"] if top_ops else 0,
                    "avg_score": round(sum(t["score"] for t in filtered)/len(filtered), 1) if filtered else 0,
                    "total_meeting_criteria": len(filtered),
                },
                "market_data_enabled": bool(include_market_data and RAPIDAPI_KEY),
                "price_band_used": {"min": price_min, "max": price_max},
                "errors": errors or None,
            }, indent=2), mimetype="application/json", headers=CORS_HEADERS)

        # group by neighborhood
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for t in filtered:
            key = f"{t.get('county_name')}|{t.get('neighborhood')}"
            groups.setdefault(key, []).append(t)

        print("\n" + "="*70)
        print(f"📊 NEIGHBORHOOD GROUPING BREAKDOWN")
        print("="*70)
        print(f"Total tracts analyzed: {len(all_tracts)}")
        print(f"Tracts after filtering: {len(filtered)}")
        print(f"Number of neighborhood groups created: {len(groups)}")

        # Show tract code distribution for Marion County to help debug
        marion_tracts = [t for t in filtered if t.get('county_name') == 'Marion']
        if marion_tracts:
            tract_codes = sorted([int(t.get('tract', '0').zfill(6)[:2]) for t in marion_tracts if t.get('tract')])
            print(f"\nMarion County tract code distribution ({len(marion_tracts)} tracts):")
            print(f"  Min tract code: {min(tract_codes) if tract_codes else 'N/A'}")
            print(f"  Max tract code: {max(tract_codes) if tract_codes else 'N/A'}")
            from collections import Counter
            code_counts = Counter(tract_codes)
            print(f"  Tract codes present: {sorted(code_counts.keys())}")

        print("\nNeighborhoods found:")
        for key in sorted(groups.keys()):
            county, neigh = key.split("|", 1)
            tract_count = len(groups[key])
            avg_score = sum(t.get('score', 0) for t in groups[key]) / tract_count if tract_count > 0 else 0
            print(f"  • {neigh} ({county}): {tract_count} tracts, avg score: {avg_score:.1f}")
        print("="*70 + "\n")

        logging.info(f"📊 Grouped {len(filtered)} tracts into {len(groups)} neighborhoods:")
        for key in sorted(groups.keys()):
            county, neigh = key.split("|", 1)
            logging.info(f"  • {neigh} ({county}): {len(groups[key])} tracts")

        neighborhoods: List[Dict[str, Any]] = []
        for key, rows in groups.items():
            county_name, neigh = key.split("|", 1)
            agg = aggregate_group(rows)
            agg.update({"county_name": county_name, "neighborhood": neigh})

            if "Subarea" in neigh and not any(r.get("zip_code") for r in rows):
                ids = sorted([r.get("tract_id", "") for r in rows if r.get("tract_id")])
                if ids:
                    agg["label_hint"] = f"Tracts {ids[0].split('.')[0]}xx–{ids[-1].split('.')[0]}xx"

            zips = [r.get("zip_code") for r in rows if r.get("zip_code")]
            if not zips:
                guesses = [get_zip_for_tract(r.get("county"), r.get("tract")) for r in rows]
                guesses = [g for g in guesses if g]
                if guesses:
                    guess = max(set(guesses), key=guesses.count)
                    conf = guesses.count(guess) / max(1, len(guesses))
                    agg["zip_guess"] = guess
                    agg["zip_confidence"] = round(conf, 3)
            neighborhoods.append(agg)

        neighborhoods.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_areas = neighborhoods[:top_n]

        result = {
            "status": "success",
            "total_tracts_analyzed": len(all_tracts),
            "rehab_budget_used": rehab_budget,
            "neighborhoods": top_areas,
            "grouped_by_neighborhood": True,
            "summary": {
                "top_score": top_areas[0]["score"] if top_areas else 0,
                "avg_score": round(sum(a["score"] for a in neighborhoods)/len(neighborhoods), 1) if neighborhoods else 0,
                "total_meeting_criteria": len(neighborhoods),
            },
            "market_data_enabled": bool(include_market_data and RAPIDAPI_KEY),
            "price_band_used": {"min": price_min, "max": price_max},
            "errors": errors or None,
        }
        logging.info("✅ Analysis complete, returning %d neighborhoods", len(top_areas))
        return func.HttpResponse(json.dumps(result, indent=2), mimetype="application/json", headers=CORS_HEADERS)

    except Exception as e:
        logging.exception("❌ Analysis failed")
        return func.HttpResponse(
            json.dumps({"status": "error","message": str(e),"details": "Check Azure logs for full error details"}),
            status_code=500, mimetype="application/json", headers=CORS_HEADERS
        )
        
@app.route(route="listings", methods=["GET"])
def listings_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns active listings for a ZIP using the same RapidAPI provider you already use.
    Query params:
      zip          (required)
      limit        default 12
      price_max    optional: user's max purchase price (for "under budget" count)
      arv          optional: ARV/median value, used with 'discount' to count the target band
      discount     optional: default 0.77 (i.e., <= 77% of ARV is "target band")
    """
    if not (RAPIDAPI_KEY and RAPIDAPI_HOST and RAPIDAPI_TEST_URL):
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Market/listings API not configured"}),
            status_code=400, mimetype="application/json", headers=CORS_HEADERS
        )

    zip_code = (req.params.get("zip") or "").strip()
    if not zip_code:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "zip is required"}),
            status_code=400, mimetype="application/json", headers=CORS_HEADERS
        )

    try:
        limit = max(1, min(int(req.params.get("limit", "12")), 50))
    except Exception:
        limit = 12

    # Optional thresholds for counts
    try:
        price_max = int(req.params.get("price_max")) if req.params.get("price_max") else None
    except Exception:
        price_max = None

    try:
        arv = int(float(req.params.get("arv"))) if req.params.get("arv") else None
    except Exception:
        arv = None

    try:
        discount = float(req.params.get("discount", "0.77"))
    except Exception:
        discount = 0.77

    # Cache hit?
    cached = _cache_get_listings(zip_code)
    if cached is not None:
        data = cached
    else:
        # Call RapidAPI provider (same as DOM provider; different payload intent)
        payload = {
            "limit": max(25, limit),   # fetch a few more so counts are meaningful
            "offset": 0,
            "postal_code": zip_code,
            "status": ["for_sale", "under_contract"],
            "sort": {"direction": "desc", "field": "list_date"},
        }
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }
        try:
            r = requests.post(RAPIDAPI_TEST_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                data = {"results": [], "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}}
            else:
                r.raise_for_status()
                raw = r.json()
                props = (raw or {}).get("data", {}).get("home_search", {}).get("results", []) or []

                items = []
                under_budget = 0
                in_target = 0
                target_price = None
                if arv and discount:
                    target_price = int(arv * discount)

                for p in props:
                    # Normalize a handful of fields (many feeds use similar names)
                    price = (
                        p.get("list_price") or p.get("price") or
                        (p.get("location") or {}).get("address", {}).get("coordinate", {}).get("price")
                    )
                    if not isinstance(price, (int, float)):
                        continue

                    addr = (p.get("location") or {}).get("address", {}) or {}
                    line = addr.get("line") or ""
                    city = addr.get("city") or ""
                    state = addr.get("state_code") or addr.get("state") or ""
                    postal = addr.get("postal_code") or zip_code

                    beds = p.get("description", {}).get("beds") or p.get("beds")
                    baths = p.get("description", {}).get("baths") or p.get("baths")
                    dom = p.get("days_on_market") or p.get("list_days_on_market") or p.get("dom")

                    # Link & photo if present
                    href = (p.get("href") or p.get("permalink") or p.get("rdc_web_url") or "")
                    photo = ""
                    photos = p.get("photos") or []
                    if isinstance(photos, list) and photos:
                        first = photos[0]
                        photo = first.get("href") or first.get("url") or ""

                    items.append({
                        "price": int(price),
                        "address": ", ".join([s for s in [line, city, state] if s]),
                        "zip": postal,
                        "beds": beds,
                        "baths": baths,
                        "dom": dom if isinstance(dom, int) else None,
                        "url": href,
                        "photo": photo
                    })

                    if price_max and price <= price_max:
                        under_budget += 1
                    if target_price and price <= target_price:
                        in_target += 1

                data = {
                    "results": sorted(items, key=lambda x: x["price"])[:limit],
                    "counts": {
                        "active_total": len(items),
                        "under_budget": under_budget,
                        "in_target_band": in_target
                    }
                }

            _cache_set_listings(zip_code, data)

        except Exception as e:
            logging.warning("Listings fetch failed for %s: %s", zip_code, e)
            data = {"results": [], "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}}

    return func.HttpResponse(json.dumps({
        "status": "success",
        "zip": zip_code,
        "discount_used": discount,
        "counts": data.get("counts", {}),
        "results": data.get("results", [])
    }, indent=2), mimetype="application/json", headers=CORS_HEADERS)
