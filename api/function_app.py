import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import azure.functions as func
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Config
ACS_YEAR = "2023"
ACS_BASE = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "realty-in-us.p.rapidapi.com")
RAPIDAPI_TEST_URL = os.environ.get(
    "RAPIDAPI_TEST_URL",
    "https://realty-in-us.p.rapidapi.com/properties/v3/list"
)

DEFAULT_PRICE_MIN = int(os.environ.get("PRICE_MIN", "200000"))
DEFAULT_PRICE_MAX = int(os.environ.get("PRICE_MAX", "225000"))

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
REQUEST_TIMEOUT = 30

_dom_cache: Dict[str, Optional[int]] = {}

def safe_int(x: Any) -> Optional[int]:
    try:
        return int(float(x))
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
    t = (tract or "").zfill(6)
    head = int(t[:2]) if t.isdigit() else 0
    
    if county_name == "Marion":
        if head <= 10:
            return "Indianapolis – Eastside"
        elif head <= 20:
            return "Indianapolis – South/Southeast"
        elif head <= 30:
            return "Indianapolis – Far Eastside"
        elif head <= 40:
            return "Indianapolis – Near Eastside/Downtown"
        else:
            return "Indianapolis – Outlying Areas"
    
    if county_name == "Madison":
        if head <= 10:
            return "Anderson – Far West"
        elif head <= 20:
            return "Anderson – East Side (North)"
        else:
            return "Anderson – East Side (Central)"
    
    return f"{county_name} County – Outlying Areas Subarea"

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
        logging.warning("Market data lookup failed for zip %s: %s", zip_code, e)
        _dom_cache[zip_code] = None
        return {"median_days_on_market": None}

def get_zip_for_tract(county_fips: str, tract: str) -> Optional[str]:
    if county_fips == "097":
        head = int((tract or "000000").zfill(6)[:2])
        if head <= 15:
            return "46219"
        elif head <= 25:
            return "46227"
        else:
            return "46218"
    if county_fips == "095":
        return "46016"
    if county_fips == "145":
        return "46176"
    return None

def score_tract_flip_potential(tract: Dict[str, Any], price_min: int, price_max: int) -> Dict[str, Any]:
    mhv = tract.get("median_home_value") or 0
    income = tract.get("median_income") or 0
    vacancy_pct = tract.get("vacancy_pct") or 0.0
    dom = tract.get("days_on_market")
    
    if mhv <= 0:
        gap_score = 0.0
        gap_ratio = 0.0
    else:
        gap_ratio = mhv / price_max if price_max > 0 else 0
        
        if gap_ratio < 1.1:
            gap_score = 0.0
        elif 1.1 <= gap_ratio <= 1.6:
            ideal_ratio = 1.35
            distance_from_ideal = abs(gap_ratio - ideal_ratio)
            gap_score = clamp01(1.0 - (distance_from_ideal / 0.25))
        else:
            gap_score = clamp01(max(0.0, 1.0 - (gap_ratio - 1.6) * 0.5))
    
    if 8.0 <= vacancy_pct <= 15.0:
        vacancy_score = 1.0
    else:
        distance = min(abs(vacancy_pct - 8.0), abs(vacancy_pct - 15.0))
        vacancy_score = clamp01(1.0 - (distance / 15.0))
    
    if mhv > 0:
        ideal_income = mhv / 3.5
        income_ratio = income / ideal_income if ideal_income > 0 else 0
        if 0.8 <= income_ratio <= 1.2:
            income_score = 1.0
        else:
            income_score = clamp01(income_ratio) if income_ratio < 0.8 else clamp01(2.0 - income_ratio)
    else:
        income_score = 0.0
    
    if dom is not None and dom > 0:
        if dom < 30:
            velocity_score = 1.0
        elif dom <= 60:
            velocity_score = 0.7
        elif dom <= 90:
            velocity_score = 0.4
        else:
            velocity_score = 0.2
    else:
        velocity_score = 0.5
    
    W_GAP = 0.40
    W_VAC = 0.25
    W_INC = 0.25
    W_VEL = 0.10
    
    total = (
        W_GAP * gap_score +
        W_VAC * vacancy_score +
        W_INC * income_score +
        W_VEL * velocity_score
    )
    
    total_score = round(total * 100, 1)
    
    insights = []
    warnings = []
    
    if gap_ratio >= 1.3 and gap_ratio <= 1.4:
        insights.append("Perfect buy-sell gap for profitable flips")
    elif gap_ratio < 1.1:
        warnings.append("Limited profit potential - median too close to budget")
    elif gap_ratio > 1.7:
        warnings.append("Median significantly above budget - verify distressed inventory exists")
    
    if 10 <= vacancy_pct <= 13:
        insights.append("Healthy inventory levels")
    elif vacancy_pct < 5:
        warnings.append("Very low vacancy - limited deal flow")
    elif vacancy_pct > 20:
        warnings.append("High vacancy may indicate declining area")
    
    if income >= mhv / 3.5:
        insights.append("Strong buyer income for resale")
    elif income < mhv / 4.5:
        warnings.append("Buyer income may limit resale market")
    
    if dom and dom < 40:
        insights.append(f"Fast-moving market ({dom} days)")
    elif dom and dom > 90:
        warnings.append(f"Slower market ({dom} days to sell)")
    
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

def pop_weighted_avg(values: List[Tuple[Optional[float], int]]) -> Optional[float]:
    num = 0.0
    den = 0
    for v, w in values:
        if v is None:
            continue
        num += float(v) * int(w or 0)
        den += int(w or 0)
    if den == 0:
        return None
    return num / den

def aggregate_group(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_pop = sum(int(r.get("total_pop") or 0) for r in rows)
    med_home_val = pop_weighted_avg([(r.get("median_home_value"), r.get("total_pop") or 0) for r in rows])
    med_income   = pop_weighted_avg([(r.get("median_income"), r.get("total_pop") or 0) for r in rows])
    vac_pct      = pop_weighted_avg([(r.get("vacancy_pct"), r.get("total_pop") or 0) for r in rows])
    dom          = pop_weighted_avg([(r.get("days_on_market"), r.get("total_pop") or 0) for r in rows])
    gap_ratio    = pop_weighted_avg([(r.get("gap_ratio"), r.get("total_pop") or 0) for r in rows])
    
    area_score = pop_weighted_avg([(r.get("score"), r.get("total_pop") or 0) for r in rows])
    
    all_insights = []
    all_warnings = []
    for r in rows:
        all_insights.extend(r.get("insights", []))
        all_warnings.extend(r.get("warnings", []))
    
    unique_insights = list(set(all_insights))[:3]
    unique_warnings = list(set(all_warnings))[:3]
    
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
        "insights": unique_insights,
        "warnings": unique_warnings,
        "member_tracts": members,
        "tracts_count": len(rows),
    }

# CORS headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "ok", "ts": datetime.utcnow().isoformat()}),
        mimetype="application/json",
        headers=CORS_HEADERS
    )

@app.route(route="analyze", methods=["GET", "POST", "OPTIONS"])
def analyze_neighborhoods(req: func.HttpRequest) -> func.HttpResponse:
    # Handle OPTIONS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=CORS_HEADERS)
    
    logging.info("Starting neighborhood analysis")

    try:
        top_n = int(req.params.get("top", "999"))
        min_score = float(req.params.get("min_score", "0"))
        include_market_data = req.params.get("market_data", "false").lower() == "true"
        do_group = req.params.get("group", "").lower() == "neighborhood"
        
        price_min = int(req.params.get("price_min", DEFAULT_PRICE_MIN))
        price_max = int(req.params.get("price_max", DEFAULT_PRICE_MAX))
        if price_min > price_max:
            price_min, price_max = price_max, price_min
        
        max_market_lookups = min(int(req.params.get("max_market_lookups", MAX_MARKET_LOOKUPS_DEFAULT)), 50)
        
        all_tracts: List[Dict[str, Any]] = []
        errors: List[str] = []
        
        for county_name, county_fips in CENTRAL_IN_COUNTIES.items():
            try:
                params = {
                    "get": ",".join(ACS_VARS.keys()),
                    "for": "tract:*",
                    "in": f"state:18 county:{county_fips}",
                }
                r = requests.get(ACS_BASE, params=params, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                headers = data[0]
                rows = data[1:]
                
                for row in rows:
                    rec = dict(zip(headers, row))
                    
                    total_housing = safe_int(rec.get("B25001_001E"))
                    vacant = safe_int(rec.get("B25002_003E"))
                    vacancy_pct = 0.0
                    if total_housing and vacant is not None and total_housing > 0:
                        vacancy_pct = (vacant / total_housing) * 100.0
                    
                    tract = rec.get("tract")
                    tract_dict: Dict[str, Any] = {
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
                    
                    scoring = score_tract_flip_potential(tract_dict, price_min=price_min, price_max=price_max)
                    tract_dict.update(scoring)
                    
                    all_tracts.append(tract_dict)
            
            except Exception as e:
                err = f"Error fetching {county_name}: {e}"
                logging.error(err)
                errors.append(err)
        
        all_tracts.sort(key=lambda x: x["score"], reverse=True)
        filtered = [t for t in all_tracts if (t.get("score") or 0) >= min_score]
        
        if include_market_data and RAPIDAPI_KEY:
            looked = 0
            for t in filtered:
                if looked >= max_market_lookups:
                    break
                zip_guess = get_zip_for_tract(t.get("county"), t.get("tract"))
                if not zip_guess:
                    continue
                dom = get_market_stats_for_zip(zip_guess).get("median_days_on_market")
                if dom is not None:
                    t["days_on_market"] = int(dom)
                    t["zip_code"] = zip_guess
                    looked += 1
                time.sleep(0.15)
        
        if not do_group:
            top_opportunities = filtered[:top_n]
            result = {
                "status": "success",
                "total_tracts_analyzed": len(all_tracts),
                "opportunities": top_opportunities,
                "summary": {
                    "top_score": top_opportunities[0]["score"] if top_opportunities else 0,
                    "avg_score": round(sum(t["score"] for t in filtered) / len(filtered), 1) if filtered else 0,
                    "total_meeting_criteria": len(filtered),
                },
                "market_data_enabled": bool(include_market_data and RAPIDAPI_KEY),
                "price_band_used": {"min": price_min, "max": price_max},
                "errors": errors or None,
            }
            return func.HttpResponse(
                json.dumps(result, indent=2),
                mimetype="application/json",
                headers=CORS_HEADERS
            )
        
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for t in filtered:
            key = f"{t.get('county_name')}|{t.get('neighborhood')}"
            groups.setdefault(key, []).append(t)
        
        neighborhoods: List[Dict[str, Any]] = []
        for key, rows in groups.items():
            county_name, neigh = key.split("|", 1)
            agg = aggregate_group(rows)
            agg.update({
                "county_name": county_name,
                "neighborhood": neigh,
            })
            
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
            "neighborhoods": top_areas,
            "grouped_by_neighborhood": True,
            "summary": {
                "top_score": top_areas[0]["score"] if top_areas else 0,
                "avg_score": round(sum(a["score"] for a in neighborhoods) / len(neighborhoods), 1) if neighborhoods else 0,
                "total_meeting_criteria": len(neighborhoods),
            },
            "market_data_enabled": bool(include_market_data and RAPIDAPI_KEY),
            "price_band_used": {"min": price_min, "max": price_max},
            "errors": errors or None,
        }
        
        return func.HttpResponse(
            json.dumps(result, indent=2),
            mimetype="application/json",
            headers=CORS_HEADERS
        )
    
    except Exception as e:
        logging.exception("Analysis failed")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": str(e),
                "details": "Check Azure logs for full error details"
            }),
            status_code=500,
            mimetype="application/json",
            headers=CORS_HEADERS
        )