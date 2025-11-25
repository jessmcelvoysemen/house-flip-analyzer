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
RAPIDAPI_AUTOCOMPLETE_URL = "https://realty-in-us.p.rapidapi.com/locations/v2/auto-complete"

# School ratings by neighborhood/city (1-10 scale)
# Based on district performance, test scores, and school quality metrics
# Source: Compiled from GreatSchools, Niche, Indiana DOE data (2024-2025)
NEIGHBORHOOD_SCHOOL_RATINGS = {
    # ===== HAMILTON COUNTY (Top-rated schools in Indiana) =====
    "Carmel": 9.5,
    "Carmel — North": 9.5,
    "Carmel — South/Keystone": 9.5,
    "Fishers": 9.0,
    "Fishers — North": 9.0,
    "Fishers — South/Geist": 9.0,
    "Westfield": 8.5,
    "Noblesville": 8.5,
    "Cicero": 8.0,

    # ===== BOONE COUNTY (Excellent schools) =====
    "Zionsville": 9.0,
    "Lebanon": 7.0,
    "Whitestown": 7.5,
    "Boone County — Whitestown area": 7.5,

    # ===== HENDRICKS COUNTY (Strong suburban schools) =====
    "Avon": 8.0,
    "Plainfield": 7.5,
    "Brownsburg": 7.5,
    "Danville": 7.0,
    "Danville/Hendricks County": 7.0,

    # ===== JOHNSON COUNTY (Good suburban schools) =====
    "Greenwood": 7.0,
    "Franklin": 6.5,
    "Whiteland": 6.5,
    "Whiteland/New Whiteland": 6.5,
    "New Whiteland": 6.5,
    "Bargersville": 7.0,
    "Johnson County — South suburbs": 6.5,

    # ===== HANCOCK COUNTY (Mixed quality) =====
    "Greenfield": 6.5,
    "New Palestine": 7.0,
    "McCordsville": 7.5,  # Part of Mt. Vernon schools
    "Hancock County — Outlying": 6.5,

    # ===== MARION COUNTY - NORTH (Better IPS/Township schools) =====
    "Broad Ripple": 6.5,
    "Meridian-Kessler": 7.0,
    "Butler-Tarkington": 6.5,
    "Crown Hill": 6.0,
    "Highland-Kessler": 6.5,
    "North Central": 8.0,  # Strong township schools
    "Meridian Hills/Williams Creek": 8.5,

    # ===== MARION COUNTY - NORTHEAST (Lawrence Township) =====
    "Lawrence": 6.5,
    "Lawrence-Fort Ben-Oaklandon": 6.5,
    "Lawrence Woods": 6.5,
    "Castleton": 7.0,
    "Geist": 8.0,  # HSE schools
    "I-69/Fall Creek": 6.0,
    "Allisonville": 7.0,
    "Bay Ridge": 7.0,
    "Oakland Hills at Geist": 8.0,
    "Lawrence Township": 6.5,

    # ===== MARION COUNTY - EAST =====
    "Irvington": 5.5,
    "Irvington Historic District": 5.5,
    "Warren": 5.5,
    "East Gate": 5.5,
    "Community Heights": 5.5,
    "Arlington Woods": 5.0,
    "Far Eastside": 5.0,
    "East Warren": 5.0,
    "Southeast Warren": 5.0,
    "Eastside": 5.0,

    # ===== MARION COUNTY - DOWNTOWN/CENTRAL =====
    "Downtown": 5.0,
    "Mile Square": 5.0,
    "Mass Ave": 5.0,
    "Lockerbie Square": 6.0,  # Diverse schools, some choice
    "Chatham-Arch": 6.0,
    "Fall Creek Place": 6.0,  # Improving area
    "Near Northside": 5.5,

    # ===== MARION COUNTY - NEAR EASTSIDE/SOUTHEAST =====
    "Near Eastside": 5.0,
    "Fountain Square": 5.5,
    "Fletcher Place": 6.0,  # Gentrifying, school choice
    "Bates-Hendricks": 5.5,
    "Near Southeast": 5.0,
    "Holy Cross": 5.5,
    "Englewood": 5.0,
    "Tuxedo Park": 5.0,
    "Bean Creek": 5.0,
    "Christian Park": 5.0,

    # ===== MARION COUNTY - WEST/NORTHWEST =====
    "Speedway": 6.0,
    "Pike Township": 6.0,
    "Pike Township/Northwest": 6.0,
    "Eagle Creek": 6.5,
    "Traders Point": 7.0,
    "Near Westside": 5.0,
    "West Side": 5.0,
    "West Indianapolis": 5.0,
    "Haughville": 4.5,
    "Eagledale": 5.5,
    "Garden City": 5.5,
    "Park Fletcher": 5.5,
    "Mars Hill": 5.5,
    "Stout Field": 5.5,
    "Riverside": 5.5,
    "Near NW - Riverside": 5.5,
    "Crooked Creek": 6.0,
    "Crooked Creek Civic League": 6.0,
    "Chapel Hill / Ben Davis": 6.0,
    "Chapel Glen": 6.0,
    "Chapel Hill Village": 6.0,
    "Park 100": 6.0,
    "Westchester Estates": 6.5,
    "New Augusta": 6.5,
    "Augusta / New Augusta": 6.5,
    "Fieldstone and Brookstone": 6.5,
    "Northwest High School": 6.0,
    "International Marketplace": 6.0,
    "Guion Lakes": 6.0,
    "Snacks / Guion Creek": 6.0,
    "Liberty Creek North": 6.5,
    "Deer Creek": 6.5,

    # ===== MARION COUNTY - NORTH CENTRAL (Township schools) =====
    "Keystone at the Crossing": 7.5,
    "College Commons": 7.5,
    "St Vincent / Greenbriar": 7.5,
    "Misty Lake": 7.0,
    "Driftwood Hills": 7.5,
    "Clearwater": 7.5,
    "Ivy Hills": 7.5,
    "Glendale": 7.0,
    "Ravenswood": 7.0,
    "Warfleigh": 7.0,
    "Sherwood Forest": 7.5,
    "Devon": 7.0,
    "Canterbury-Chatard": 7.5,
    "Oliver Johnson's Woods": 7.0,
    "Millersville": 6.5,
    "Delaware Trails": 6.5,
    "Devonshire": 7.0,
    "Devington": 6.5,

    # ===== MARION COUNTY - NORTHEAST AREAS =====
    "Fairgrounds": 6.0,
    "Meadows": 6.0,
    "Forest Manor": 5.0,
    "Martindale - Brightwood": 5.0,
    "Mapleton - Fall Creek": 5.5,
    "Highland Vicinity": 5.5,
    "Reagan Park": 5.5,

    # ===== MARION COUNTY - SOUTH =====
    "Beech Grove": 6.0,
    "Southport": 6.5,
    "Garfield Park": 5.0,
    "Garfield Park-South Neighborhood": 5.0,
    "Old Southside": 5.5,
    "Near Southside": 5.5,
    "Perry Township": 6.0,
    "Perry Manor": 6.0,
    "South Perry": 6.0,
    "North Perry": 6.0,
    "University Heights": 6.0,
    "University Heights and Rosedale Hills": 6.0,
    "Carson Heights": 6.0,
    "Southdale": 6.0,
    "Edgewood": 6.0,
    "Homecroft": 6.5,
    "I-65 / South Emerson": 6.0,
    "Richling Acres": 6.0,
    "Linden Wood": 6.0,
    "Winchester Village": 6.0,
    "Richmond Hill": 6.0,
    "Hill Valley Estates": 6.0,
    "Poplar Grove": 6.0,
    "Five Points": 6.0,
    "Glenns Valley": 6.0,
    "Sunshine Gardens": 6.0,
    "New Bethel": 5.5,
    "Acton": 5.5,
    "South Franklin": 5.5,
    "Galludet": 5.5,
    "Brendonwood": 6.5,

    # ===== MARION COUNTY - SOUTHWEST =====
    "Camby": 6.0,
    "West Newton": 6.0,
    "Valley Mills": 6.0,

    # ===== MARION COUNTY - SPECIAL AREAS =====
    "Airport": 5.5,
    "Kennedy King": 5.0,
    "Hawthorne": 5.5,

    # ===== MADISON COUNTY (Below average) =====
    "Anderson": 5.0,
    "Anderson — West Side": 5.0,
    "Anderson — Downtown/Central": 5.0,
    "Anderson — East Side": 5.0,
    "Anderson — South": 5.0,
    "Pendleton": 6.0,
    "Chesterfield": 5.5,
    "Madison County — Pendleton/Chesterfield": 5.5,

    # ===== MORGAN COUNTY (Mixed rural) =====
    "Martinsville": 6.0,
    "Mooresville": 6.5,
    "Morgan County — Outlying": 6.0,

    # ===== SHELBY COUNTY (Small city schools) =====
    "Shelbyville": 6.0,
    "Shelbyville — Central": 6.0,
    "Shelby County — Outlying": 6.0,
}

# Recent Starbucks openings in Central Indiana (2024-2025)
# Used as a positive indicator for neighborhood growth and retail investment
STARBUCKS_RECENT_OPENINGS = {
    "Mooresville",
    "Noblesville",
    "Westfield",
    "Zionsville",
    "Greenfield",
    "New Palestine",
    "Brownsburg",
    "Pendleton",
    "Greenwood",
    "Anderson",
    # Indianapolis locations - mapping to specific neighborhoods
    "Broad Ripple",  # 62nd & Keystone
    "Beech Grove",  # Southport & Franklin Rd
}

# Google Maps neighborhood mapping (generated 2025-11-13)
# Official neighborhood names from Google Maps Geocoding API
GOOGLE_MAPS_NEIGHBORHOODS = {
    "310104": "Park 100",
    "310105": "Park 100",
    "310106": "Westchester Estates",
    "310108": "Eagle Creek",
    "310110": "Eagle Creek",
    "310111": "Eagle Creek",
    "310112": "Traders Point",
    "310113": "Eagle Creek",
    "310201": "New Augusta",
    "310203": "Fieldstone and Brookstone",
    "310204": "Augusta / New Augusta",
    "310305": "Northwest High School",
    "310306": "International Marketplace",
    "310308": "Guion Lakes",
    "310309": "Snacks / Guion Creek",
    "310310": "Liberty Creek North",
    "310311": "Snacks / Guion Creek",
    "310312": "Deer Creek",
    "320105": "Misty Lake",
    "320106": "St Vincent / Greenbriar",
    "320107": "College Commons",
    "320108": "St Vincent / Greenbriar",
    "320109": "St Vincent / Greenbriar",
    "320202": "North Central",
    "320203": "Sherwood Forest",
    "320205": "Keystone at the Crossing",
    "320206": "Driftwood Hills",
    "320301": "Clearwater",
    "320303": "Castleton",
    "320305": "Ivy Hills",
    "320306": "Allisonville",
    "320400": "Allisonville",
    "320500": "Glendale",
    "320600": "Ravenswood",
    "320700": "Warfleigh",
    "320800": "Meridian Hills/Williams Creek",
    "320901": "Delaware Trails",
    "320902": "Crooked Creek",
    "320903": "Crooked Creek",
    "321001": "Crooked Creek",
    "321002": "Crooked Creek Civic League",
    "321100": "Highland-Kessler",
    "321200": "Warfleigh",
    "321300": "Broad Ripple",
    "321400": "Millersville",
    "321600": "Devon",
    "321700": "Canterbury-Chatard",
    "321800": "Meridian-Kessler",
    "321900": "Butler-Tarkington",
    "322000": "Butler-Tarkington",
    "322100": "Meridian-Kessler",
    "322200": "Oliver Johnson's Woods",
    "322300": "Meridian-Kessler",
    "322400": "Fairgrounds",
    "322500": "Fairgrounds",
    "322601": "Meadows",
    "322602": "Meadows",
    "322700": "Forest Manor",
    "330103": "Castleton",
    "330105": "Castleton",
    "330106": "I-69/Fall Creek",
    "330107": "I-69/Fall Creek",
    "330108": "Geist",
    "330109": "I-69/Fall Creek",
    "330203": "Geist",
    "330204": "Lawrence-Fort Ben-Oaklandon",
    "330206": "Lawrence Woods",
    "330208": "Bay Ridge",
    "330210": "Lawrence",
    "330211": "Far Eastside",
    "330212": "Lawrence",
    "330213": "Oakland Hills at Geist",
    "330401": "Devonshire",
    "330500": "Devington",
    "330600": "Lawrence",
    "330701": "Lawrence",
    "330702": "Lawrence",
    "330803": "Far Eastside",
    "330804": "Far Eastside",
    "330805": "Lawrence",
    "330806": "Far Eastside",
    "330900": "Devington",
    "331000": "Devington",
    "340101": "Chapel Glen",
    "340102": "Chapel Hill Village",
    "340108": "Northwest High School",
    "340111": "Key Meadows",
    "340112": "Key Meadows",
    "340113": "Chapel Hill / Ben Davis",
    "340114": "Key Meadows",
    "340115": "Aspen Ridge",
    "340201": "Northwest High School",
    "340202": "Speedway",
    "340301": "Eagledale",
    "340302": "Eagledale",
    "340400": "Eagledale",
    "340500": "Venerable Flackville",
    "340600": "Marian - Cold Springs",
    "340700": "Speedway",
    "340800": "Speedway",
    "340901": "Westridge",
    "340903": "Speedway",
    "340904": "Speedway",
    "341000": "Speedway",
    "341100": "Near Westside",
    "341200": "West Side",
    "341600": "Haughville",
    "341701": "Near Westside",
    "341702": "Garden City",
    "341902": "Chapel Hill / Ben Davis",
    "341903": "Garden City",
    "341904": "Garden City",
    "342000": "Chapel Hill / Ben Davis",
    "342101": "Chapel Hill / Ben Davis",
    "342200": "Park Fletcher",
    "342300": "Mars Hill",
    "342400": "West Indianapolis",
    "342500": "Stout Field",
    "342600": "West Indianapolis",
    "350100": "Near NW - Riverside",
    "350300": "Crown Hill",
    "350400": "Mapleton - Fall Creek",
    "350500": "Meadows",
    "350600": "Forest Manor",
    "350700": "Martindale - Brightwood",
    "350800": "Martindale - Brightwood",
    "350900": "Mapleton - Fall Creek",
    "351000": "Crown Hill",
    "351200": "Near NW - Riverside",
    "351500": "Highland Vicinity",
    "351600": "Fall Creek Place",
    "351700": "Reagan Park",
    "351900": "Martindale - Brightwood",
    "352100": "Martindale - Brightwood",
    "352300": "Martindale - Brightwood",
    "352400": "Near Eastside",
    "352500": "Little Flower",
    "352600": "Near Eastside",
    "352700": "Windsor Park",
    "352800": "Hillside",
    "353300": "Near Northside",
    "353500": "Near NW - Riverside",
    "353600": "Riverside",
    "354201": "Lockerbie Square",
    "354202": "Chatham-Arch",
    "354400": "Holy Cross",
    "354500": "Near Eastside",
    "354700": "Near Eastside",
    "354800": "Near Eastside",
    "354900": "Near Eastside",
    "355000": "Englewood",
    "355100": "Tuxedo Park",
    "355300": "Emerson Heights",
    "355400": "Bosart Brown",
    "355500": "Christian Park",
    "355600": "Christian Park",
    "355700": "Christian Park",
    "355900": "Fountain Square",
    "356200": "Fletcher Place",
    "356400": "Near Westside",
    "356900": "Old Southside",
    "357000": "Bates-Hendricks",
    "357100": "Fountain Square",
    "357200": "Fountain Square",
    "357300": "Near Southeast",
    "357400": "Near Southeast",
    "357500": "Beech Grove",
    "357601": "Bean Creek",
    "357602": "Near Southeast",
    "357800": "Near Southside",
    "357900": "Garfield Park-South Neighborhood",
    "358000": "Garfield Park",
    "358100": "West Indianapolis",
    "360101": "Eastside",
    "360102": "Arlington Woods",
    "360201": "Arlington Woods",
    "360202": "Far Eastside",
    "360301": "Far Eastside",
    "360302": "Arlington Woods",
    "360401": "Far Eastside",
    "360402": "Far Eastside",
    "360405": "Far Eastside",
    "360406": "Far Eastside",
    "360407": "Far Eastside",
    "360501": "East Warren",
    "360502": "East Warren",
    "360601": "East Warren",
    "360602": "East Gate",
    "360700": "Irvington",
    "360800": "Warren",
    "360900": "Community Heights",
    "361000": "Irvington",
    "361100": "Irvington Historic District",
    "361200": "Irvington",
    "361300": "East Gate",
    "361401": "Raymond Park",
    "361402": "Glenroy Village",
    "361601": "Southeast Warren",
    "361602": "Southeast Warren",
    "370201": "Mars Hill",
    "370203": "Mars Hill",
    "370204": "Mars Hill",
    "370303": "Camby",
    "370304": "West Newton",
    "370305": "Valley Mills",
    "370306": "Valley Mills",
    "380101": "Glenns Valley",
    "380102": "Sunshine Gardens",
    "380103": "Sunshine Gardens",
    "380200": "North Perry",
    "380301": "University Heights",
    "380302": "Carson Heights",
    "380402": "Beech Grove",
    "380403": "Beech Grove",
    "380404": "University Heights",
    "380501": "Edgewood",
    "380502": "University Heights and Rosedale Hills",
    "380600": "Southdale",
    "380700": "Southdale",
    "380800": "Edgewood",
    "380901": "Perry Manor",
    "380902": "I-65 / South Emerson",
    "381002": "Homecroft",
    "381003": "Southport",
    "381004": "South Perry",
    "381101": "Richling Acres",
    "381102": "Linden Wood",
    "381203": "Winchester Village",
    "381204": "South Perry",
    "381205": "Richmond Hill",
    "381206": "Hill Valley Estates",
    "381207": "Hill Valley Estates",
    "390102": "Beech Grove",
    "390103": "Poplar Grove",
    "390104": "Five Points",
    "390200": "New Bethel",
    "390300": "Acton",
    "390405": "South Franklin",
    "390406": "Galludet",
    "390407": "South Franklin",
    "390408": "Galludet",
    "390409": "South Franklin",
    "390410": "I-65 / South Emerson",
    "390411": "I-65 / South Emerson",
    "390500": "Crown Hill",
    "390601": "Brendonwood",
    "390602": "Lawrence-Fort Ben-Oaklandon",
    "390700": "Hawthorne",
    "390801": "Airport",
    "390802": "Airport",
    "390900": "Kennedy King",
    "391001": "Downtown",
    "391002": "Mile Square",
}

# Google Maps ZIP code mapping (generated 2025-11-13)
# Maps census tracts to accurate ZIP codes for listings lookups
TRACT_TO_ZIP_MAPPING = {
    # Boone County (FIPS 011)
    "011": {
        "810100": "46052",
        "810200": "46071",
        "810300": "46052",
        "810400": "46052",
        "810500": "46052",
        "810601": "46075",
        "810604": "46077",
        "810605": "46077",
        "810606": "46077",
        "810607": "46077",
        "810700": "46052",
    },
    # Hamilton County (FIPS 057)
    "057": {
        "110101": "46060",
        "110102": "46060",
        "110201": "46030",
        "110202": "46034",
        "110301": "46074",
        "110302": "46074",
        "110303": "46069",
        "110401": "46074",
        "110404": "46032",
        "110405": "46033",
        "110406": "46074",
        "110505": "46060",
        "110509": "46062",
        "110511": "46062",
        "110512": "46062",
        "110513": "46060",
        "110514": "46060",
        "110515": "46033",
        "110516": "46074",
        "110517": "46062",
        "110518": "46062",
        "110600": "46060",
        "110700": "46060",
        "110805": "46037",
        "110807": "46037",
        "110810": "46038",
        "110811": "46038",
        "110812": "46038",
        "110813": "46040",
        "110814": "46037",
        "110815": "46037",
        "110816": "46037",
        "110817": "46038",
        "110818": "46038",
        "110819": "46038",
        "110820": "46038",
        "110821": "46037",
        "110822": "46037",
        "110904": "46033",
        "110905": "46032",
        "110906": "46032",
        "110907": "46033",
        "110909": "46032",
        "110910": "46074",
        "110911": "46033",
        "110912": "46033",
        "111003": "46033",
        "111004": "46033",
        "111006": "46032",
        "111007": "46032",
        "111009": "46032",
        "111010": "46077",
        "111011": "46032",
        "111012": "46032",
        "111101": "46033",
        "111103": "46032",
        "111104": "46280",
    },
    # Hancock County (FIPS 059)
    "059": {
        "410100": "46186",
        "410201": "46055",
        "410202": "46040",
        "410301": "46140",
        "410302": "46140",
        "410401": "46140",
        "410402": "46140",
        "410500": "46140",
        "410600": "46140",
        "410700": "46140",
        "410801": "46163",
        "410802": "46163",
        "410901": "46140",
        "410902": "46140",
        "411000": "46163",
    },
    # Hendricks County (FIPS 063)
    "063": {
        "210103": "46112",
        "210105": "46112",
        "210106": "46112",
        "210107": "46112",
        "210108": "46234",
        "210109": "46112",
        "210201": "46112",
        "210203": "46112",
        "210204": "46112",
        "210300": "46167",
        "210400": "46165",
        "210501": "46122",
        "210502": "46122",
        "210607": "46168",
        "210608": "46168",
        "210609": "46123",
        "210610": "46123",
        "210611": "46123",
        "210612": "46123",
        "210613": "46123",
        "210614": "46123",
        "210615": "46168",
        "210616": "46123",
        "210617": "46234",
        "210701": "46168",
        "210702": "46168",
        "210801": "46168",
        "210802": "46168",
        "210900": "46168",
        "211000": "46118",
        "211100": "46121",
    },
    # Johnson County (FIPS 081)
    "081": {
        "610101": "46143",
        "610102": "46184",
        "610201": "46143",
        "610203": "46143",
        "610204": "46143",
        "610300": "46142",
        "610401": "46142",
        "610403": "46143",
        "610404": "46142",
        "610501": "46184",
        "610502": "46184",
        "610603": "46142",
        "610605": "46142",
        "610606": "46142",
        "610607": "46143",
        "610608": "46143",
        "610703": "46143",
        "610704": "46143",
        "610705": "46106",
        "610706": "46106",
        "610801": "46106",
        "610802": "46131",
        "610900": "46131",
        "611000": "46131",
        "611100": "46131",
        "611200": "46131",
        "611300": "46124",
        "611400": "46181",
    },
    # Madison County (FIPS 095)
    "095": {
        "000300": "46016",
        "000400": "46016",
        "000500": "46016",
        "000800": "46016",
        "000900": "46016",
        "001000": "46016",
        "001100": "46012",
        "001200": "46012",
        "001300": "46012",
        "001400": "46012",
        "001500": "46011",
        "001600": "46011",
        "001700": "46011",
        "001801": "46013",
        "001802": "46013",
        "001901": "46013",
        "001902": "46013",
        "002000": "46013",
        "010100": "46070",
        "010200": "46036",
        "010300": "46036",
        "010400": "46036",
        "010500": "46001",
        "010600": "46001",
        "010700": "46012",
        "010800": "46011",
        "010900": "46036",
        "011000": "46011",
        "011100": "46051",
        "011200": "46017",
        "011300": "46017",
        "011400": "46013",
        "011501": "46064",
        "011502": "46064",
        "011600": "46064",
        "011700": "46064",
        "011800": "46064",
        "011900": "46016",
        "012000": "46016",
    },
    # Marion County (FIPS 097)
    "097": {
        "310104": "46268",
        "310105": "46268",
        "310106": "46268",
        "310108": "46234",
        "310110": "46254",
        "310111": "46254",
        "310112": "46278",
        "310113": "46278",
        "310201": "46268",
        "310203": "46268",
        "310204": "46268",
        "310305": "46254",
        "310306": "46254",
        "310308": "46254",
        "310309": "46254",
        "310310": "46254",
        "310311": "46228",
        "310312": "46254",
        "320105": "46260",
        "320106": "46260",
        "320107": "46240",
        "320108": "46260",
        "320109": "46260",
        "320202": "46240",
        "320203": "46240",
        "320205": "46240",
        "320206": "46240",
        "320301": "46240",
        "320303": "46250",
        "320305": "46250",
        "320306": "46250",
        "320400": "46220",
        "320500": "46220",
        "320600": "46220",
        "320700": "46220",
        "320800": "46240",
        "320901": "46260",
        "320902": "46260",
        "320903": "46260",
        "321001": "46228",
        "321002": "46228",
        "321100": "46228",
        "321200": "46220",
        "321300": "46220",
        "321400": "46220",
        "321600": "46220",
        "321700": "46220",
        "321800": "46220",
        "321900": "46208",
        "322000": "46208",
        "322100": "46205",
        "322200": "46205",
        "322300": "46205",
        "322400": "46205",
        "322500": "46205",
        "322601": "46205",
        "322602": "46205",
        "322700": "46226",
        "330103": "46250",
        "330105": "46250",
        "330106": "46256",
        "330107": "46256",
        "330108": "46256",
        "330109": "46256",
        "330203": "46236",
        "330204": "46236",
        "330206": "46236",
        "330208": "46236",
        "330210": "46235",
        "330211": "46235",
        "330212": "46235",
        "330213": "46236",
        "330401": "46220",
        "330500": "46226",
        "330600": "46226",
        "330701": "46226",
        "330702": "46235",
        "330803": "46235",
        "330804": "46235",
        "330805": "46226",
        "330806": "46226",
        "330900": "46226",
        "331000": "46226",
        "340101": "46234",
        "340102": "46214",
        "340108": "46224",
        "340111": "46214",
        "340112": "46214",
        "340113": "46234",
        "340114": "46234",
        "340115": "46214",
        "340201": "46224",
        "340202": "46224",
        "340301": "46224",
        "340302": "46224",
        "340400": "46222",
        "340500": "46222",
        "340600": "46222",
        "340700": "46222",
        "340800": "46224",
        "340901": "46214",
        "340903": "46224",
        "340904": "46224",
        "341000": "46224",
        "341100": "46222",
        "341200": "46222",
        "341600": "46222",
        "341701": "46222",
        "341702": "46222",
        "341902": "46214",
        "341903": "46224",
        "341904": "46224",
        "342000": "46231",
        "342101": "46241",
        "342200": "46241",
        "342300": "46241",
        "342400": "46241",
        "342500": "46241",
        "342600": "46221",
        "350100": "46208",
        "350300": "46208",
        "350400": "46205",
        "350500": "46218",
        "350600": "46218",
        "350700": "46218",
        "350800": "46218",
        "350900": "46205",
        "351000": "46208",
        "351200": "46208",
        "351500": "46208",
        "351600": "46208",
        "351700": "46205",
        "351900": "46218",
        "352100": "46218",
        "352300": "46218",
        "352400": "46218",
        "352500": "46201",
        "352600": "46201",
        "352700": "46201",
        "352800": "46218",
        "353300": "46202",
        "353500": "46202",
        "353600": "46202",
        "354201": "46202",
        "354202": "46202",
        "354400": "46202",
        "354500": "46201",
        "354700": "46201",
        "354800": "46201",
        "354900": "46201",
        "355000": "46201",
        "355100": "46201",
        "355300": "46201",
        "355400": "46201",
        "355500": "46201",
        "355600": "46201",
        "355700": "46201",
        "355900": "46203",
        "356200": "46225",
        "356400": "46222",
        "356900": "46225",
        "357000": "46203",
        "357100": "46203",
        "357200": "46203",
        "357300": "46203",
        "357400": "46203",
        "357500": "46107",
        "357601": "46203",
        "357602": "46203",
        "357800": "46203",
        "357900": "46203",
        "358000": "46225",
        "358100": "46219",
        "360101": "46218",
        "360102": "46218",
        "360201": "46226",
        "360202": "46226",
        "360301": "46219",
        "360302": "46219",
        "360401": "46229",
        "360402": "46235",
        "360405": "46229",
        "360406": "46235",
        "360407": "46235",
        "360501": "46229",
        "360502": "46229",
        "360601": "46219",
        "360602": "46219",
        "360700": "46219",
        "360800": "46219",
        "360900": "46219",
        "361000": "46219",
        "361100": "46219",
        "361200": "46219",
        "361300": "46219",
        "361401": "46239",
        "361402": "46203",
        "361601": "46239",
        "361602": "46239",
        "370201": "46221",
        "370203": "46241",
        "370204": "46221",
        "370303": "46113",
        "370304": "46221",
        "370305": "46221",
        "370306": "46221",
        "380101": "46217",
        "380102": "46217",
        "380103": "46217",
        "380200": "46217",
        "380301": "46237",
        "380302": "46227",
        "380402": "46237",
        "380403": "46107",
        "380404": "46237",
        "380501": "46227",
        "380502": "46227",
        "380600": "46227",
        "380700": "46217",
        "380800": "46227",
        "380901": "46227",
        "380902": "46237",
        "381002": "46227",
        "381003": "46227",
        "381004": "46227",
        "381101": "46217",
        "381102": "46217",
        "381203": "46227",
        "381204": "46227",
        "381205": "46237",
        "381206": "46227",
        "381207": "46217",
        "390102": "46203",
        "390103": "46237",
        "390104": "46239",
        "390200": "46239",
        "390300": "46259",
        "390405": "46237",
        "390406": "46259",
        "390407": "46259",
        "390408": "46237",
        "390409": "46237",
        "390410": "46237",
        "390411": "46237",
        "390500": "46208",
        "390601": "46226",
        "390602": "46216",
        "390700": "46222",
        "390801": "46241",
        "390802": "46241",
        "390900": "46202",
        "391001": "46204",
        "391002": "46204",
    },
    # Morgan County (FIPS 109)
    "109": {
        "510101": "46113",
        "510102": "46151",
        "510201": "46158",
        "510202": "46158",
        "510300": "46158",
        "510401": "46157",
        "510402": "46157",
        "510500": "46151",
        "510601": "46151",
        "510602": "46160",
        "510701": "46151",
        "510703": "46151",
        "510704": "46151",
        "510800": "46151",
        "510900": "46151",
        "511001": "46166",
        "511002": "46166",
    },
    # Shelby County (FIPS 145)
    "145": {
        "710100": "46161",
        "710200": "46126",
        "710300": "46176",
        "710400": "46176",
        "710500": "46176",
        "710601": "46176",
        "710602": "46176",
        "710700": "46176",
        "710800": "46176",
        "710900": "47234",
    },
}

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

def has_recent_starbucks(neighborhood: str, county_name: str) -> bool:
    """Check if neighborhood/city has a recent Starbucks opening (2024-2025)"""
    # Check full neighborhood name
    if neighborhood in STARBUCKS_RECENT_OPENINGS:
        return True

    # Check county-level cities (for suburbs)
    city_mappings = {
        "Hamilton": ["Noblesville", "Westfield"],
        "Boone": ["Zionsville"],
        "Hancock": ["Greenfield", "New Palestine"],
        "Hendricks": ["Brownsburg"],
        "Madison": ["Pendleton", "Anderson"],
        "Johnson": ["Greenwood"],
        "Morgan": ["Mooresville"],
    }

    cities = city_mappings.get(county_name, [])
    for city in cities:
        if city in neighborhood or city in STARBUCKS_RECENT_OPENINGS:
            return True

    return False

def neighborhood_label(county_name: str, tract: str) -> str:
    """Map census tracts to recognizable neighborhoods/cities using Google Maps data"""
    t = (tract or "").zfill(6)

    # For Marion County (Indianapolis), use Google Maps official neighborhood names
    if county_name == "Marion":
        # Check Google Maps data first (most accurate!)
        google_neighborhood = GOOGLE_MAPS_NEIGHBORHOODS.get(t)
        if google_neighborhood:
            return google_neighborhood

        # Fallback to manual mapping if Google Maps doesn't have this tract
        try:
            code = int(t[:4]) if len(t) >= 4 else 0
        except:
            code = 0

        # Fallback ranges (shouldn't hit these often with Google Maps data)
        if code < 3120:  return "Near Eastside"
        if code < 3140:  return "Eastside"
        if code < 3160:  return "Far Eastside"
        if code < 3180:  return "Lawrence/Castleton"
        if code < 3200:  return "Broad Ripple/Meridian-Kessler"
        if code < 3300:  return "Near Southeast/Fountain Square"
        if code < 3320:  return "Near Westside/Haughville"
        if code < 3380:  return "Irvington/Warren Park"
        if code < 3420:  return "Near Southside/Garfield Park"
        if code < 3480:  return "Southport/Beech Grove"
        if code < 3540:  return "Perry Township"
        if code < 3600:  return "Decatur/Southwest"
        if code < 3680:  return "Pike Township/Northwest"
        if code < 3780:  return "Washington Township"
        if code < 3880:  return "Lawrence Township"
        return "Wayne Township/Southwest"

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

# --- Location ID cache ---
_location_id_cache = {}  # { "neighborhood_city": {"ts": ISO_UTC, "location_data": {...}} }
LOCATION_ID_CACHE_DAYS = 30  # Location IDs don't change

def resolve_neighborhood_to_location_id(neighborhood: str, city: str, state_code: str) -> Optional[dict]:
    """
    Resolve a neighborhood name to a location ID using the autocomplete endpoint.
    Returns dict with 'area_type', 'slug_id', 'geo_id' if found.
    """
    cache_key = f"{neighborhood}_{city}_{state_code}".lower()

    # Check cache
    if cache_key in _location_id_cache:
        entry = _location_id_cache[cache_key]
        try:
            ts = datetime.fromisoformat(entry["ts"])
            if datetime.utcnow() - ts < timedelta(days=LOCATION_ID_CACHE_DAYS):
                return entry.get("location_data")
        except Exception:
            pass

    # Call autocomplete API
    search_query = f"{neighborhood} {city}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
    }

    try:
        logging.info(f"Resolving location: '{search_query}'")
        r = requests.get(
            RAPIDAPI_AUTOCOMPLETE_URL,
            params={"input": search_query, "limit": "10"},
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        data = r.json()

        # Log raw response for debugging
        autocomplete_results = data.get("autocomplete", [])
        logging.info(f"Autocomplete returned {len(autocomplete_results)} results")

        # Look for neighborhood or city match
        for idx, result in enumerate(autocomplete_results):
            result_area_type = result.get("area_type", "")
            result_city = result.get("city", "").lower()
            result_state = result.get("state_code", "").lower()
            result_name = result.get("_id", "")

            logging.info(f"  [{idx}] {result_name} - type: {result_area_type}, city: {result_city}, state: {result_state}")

            # Prefer neighborhood type, but accept city too
            if result_state == state_code.lower():
                if result_area_type == "neighborhood" or result_area_type == "city":
                    location_data = {
                        "area_type": result_area_type,
                        "slug_id": result.get("slug_id"),
                        "geo_id": result.get("geo_id"),
                        "city": result.get("city"),
                        "state_code": result.get("state_code")
                    }
                    logging.info(f"✓ Matched location: {location_data}")

                    # Cache it
                    _location_id_cache[cache_key] = {
                        "ts": datetime.utcnow().isoformat(),
                        "location_data": location_data
                    }
                    return location_data

        logging.warning(f"✗ No matching location found for '{search_query}' in {len(autocomplete_results)} results")
        return None

    except Exception as e:
        logging.error(f"✗ Exception resolving location '{search_query}': {e}")
        return None

# --- Listings cache (per ZIP) ---
_listings_cache = {}  # { zip: {"ts": ISO_UTC, "data": {...}} }
LISTINGS_CACHE_HOURS = 6
LISTINGS_CACHE_VERSION = "v3"  # Increment to invalidate all cached listings

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

# === CENSUS TRACT BOUNDARIES ===

# Cache for tract boundary polygons
_tract_boundaries_cache = {}  # { tract_geoid: {"ts": ISO_UTC, "polygon": [[[lon, lat], ...]]} }
TRACT_BOUNDARY_CACHE_DAYS = 30  # Boundaries don't change often

def _cache_get_tract_boundary(tract_geoid: str):
    """Get cached tract boundary polygon."""
    entry = _tract_boundaries_cache.get(tract_geoid)
    if not entry:
        return None
    try:
        ts = datetime.fromisoformat(entry["ts"])
        if datetime.utcnow() - ts > timedelta(days=TRACT_BOUNDARY_CACHE_DAYS):
            del _tract_boundaries_cache[tract_geoid]
            return None
    except Exception:
        del _tract_boundaries_cache[tract_geoid]
        return None
    return entry["polygon"]

def _cache_set_tract_boundary(tract_geoid: str, polygon: List) -> None:
    """Cache tract boundary polygon."""
    _tract_boundaries_cache[tract_geoid] = {
        "ts": datetime.utcnow().isoformat(),
        "polygon": polygon
    }

def fetch_tract_boundary(state_fips: str, county_fips: str, tract_code: str) -> Optional[List]:
    """
    Fetch census tract boundary polygon from Census TIGER API.
    Returns polygon as list of coordinate rings: [[[lon, lat], [lon, lat], ...]]
    """
    # Build full GEOID: state(2) + county(3) + tract(6)
    geoid = f"{state_fips}{county_fips}{tract_code}"

    # Check cache first
    cached = _cache_get_tract_boundary(geoid)
    if cached is not None:
        return cached

    # Fetch from TIGER API
    tiger_url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2023/MapServer/8/query"
    params = {
        "where": f"GEOID='{geoid}'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json"
    }

    try:
        r = requests.get(tiger_url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        features = data.get("features", [])
        if not features:
            logging.warning(f"No boundary found for tract {geoid}")
            return None

        # Extract polygon rings from first feature
        geometry = features[0].get("geometry", {})
        rings = geometry.get("rings", [])

        if not rings:
            logging.warning(f"No rings in geometry for tract {geoid}")
            return None

        # Cache and return
        _cache_set_tract_boundary(geoid, rings)
        return rings

    except Exception as e:
        logging.warning(f"Failed to fetch boundary for tract {geoid}: {e}")
        return None

def point_in_polygon(point_lon: float, point_lat: float, polygon_rings: List) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm.
    polygon_rings: list of rings, each ring is [[lon, lat], [lon, lat], ...]
    """
    if not polygon_rings:
        return False

    # Use first ring (exterior boundary)
    polygon = polygon_rings[0]

    # Ray casting algorithm
    inside = False
    n = len(polygon)

    p1_lon, p1_lat = polygon[0]

    for i in range(1, n + 1):
        p2_lon, p2_lat = polygon[i % n]

        if point_lat > min(p1_lat, p2_lat):
            if point_lat <= max(p1_lat, p2_lat):
                if point_lon <= max(p1_lon, p2_lon):
                    if p1_lat != p2_lat:
                        x_intersection = (point_lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                    if p1_lon == p2_lon or point_lon <= x_intersection:
                        inside = not inside

        p1_lon, p1_lat = p2_lon, p2_lat

    return inside

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
        if resp.status_code == 429:
            logging.warning("⚠️ RapidAPI rate limit exceeded for ZIP %s", zip_code)
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
    """Map census tracts to ZIP codes using Google Maps data"""
    t = (tract or "").zfill(6)
    county_map = TRACT_TO_ZIP_MAPPING.get(county_fips, {})
    return county_map.get(t)

# === SCORING ===

def score_tract_flip_potential(tract: Dict[str, Any], price_min: int, price_max: int) -> Dict[str, Any]:
    mhv = tract.get("median_home_value") or 0
    income = tract.get("median_income") or 0
    vacancy_pct = tract.get("vacancy_pct") or 0.0
    dom = tract.get("days_on_market")
    neighborhood = tract.get("neighborhood", "")
    county_name = tract.get("county_name", "")

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

    # Base score calculation
    total = 0.50*gap_score + 0.20*vacancy_score + 0.20*income_score + 0.10*velocity_score

    # Starbucks bonus: +3 points for recent commercial investment
    starbucks_bonus = 0.0
    has_starbucks = has_recent_starbucks(neighborhood, county_name)
    if has_starbucks:
        starbucks_bonus = 3.0

    # School ratings bonus: Critical for family buyers and resale value
    school_bonus = 0.0
    school_rating = NEIGHBORHOOD_SCHOOL_RATINGS.get(neighborhood)
    if school_rating is not None:
        if school_rating >= 8.0:
            school_bonus = 5.0  # Excellent schools - major selling point
        elif school_rating >= 7.0:
            school_bonus = 3.0  # Good schools - strong advantage
        elif school_rating >= 6.0:
            school_bonus = 1.0  # Decent schools - slight advantage
        elif school_rating <= 5.0:
            school_bonus = -2.0  # Below average - harder to sell to families

    # Cap final score at 100 for consistency
    total_score = min(100.0, round((total * 100) + starbucks_bonus + school_bonus, 1))

    insights, warnings = [], []

    # School rating insights (high priority for family buyers)
    if school_rating and school_rating >= 8.0:
        insights.append(f"🎓 Excellent schools (rated {school_rating}/10) — major family appeal")
    elif school_rating and school_rating >= 7.0:
        insights.append(f"🎓 Good schools (rated {school_rating}/10) — strong for families")
    elif school_rating and school_rating <= 5.0:
        warnings.append(f"⚠️ Below-average schools (rated {school_rating}/10) — may limit buyer pool")

    if has_starbucks:
        insights.append("⭐ New Starbucks opened (2024-2025) — strong retail investment")
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
        "starbucks_bonus": starbucks_bonus,
        "has_starbucks": has_starbucks,
        "school_rating": school_rating,
        "school_bonus": school_bonus,
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

    # Check if any tract in the group has Starbucks (should be consistent across group)
    has_starbucks = any(r.get("has_starbucks", False) for r in rows)

    # Get school rating (should be consistent across same neighborhood group)
    school_rating = None
    school_ratings = [r.get("school_rating") for r in rows if r.get("school_rating") is not None]
    if school_ratings:
        school_rating = sum(school_ratings) / len(school_ratings)  # Average if slightly different

    # 👉 Derive messages from the aggregated metrics (not by unioning tract messages)
    insights: List[str] = []
    warnings: List[str] = []

    # School rating insights (high priority for family buyers)
    if school_rating and school_rating >= 8.0:
        insights.append(f"🎓 Excellent schools (rated {school_rating:.1f}/10) — major family appeal")
    elif school_rating and school_rating >= 7.0:
        insights.append(f"🎓 Good schools (rated {school_rating:.1f}/10) — strong for families")
    elif school_rating and school_rating <= 5.0:
        warnings.append(f"⚠️ Below-average schools (rated {school_rating:.1f}/10) — may limit buyer pool")

    # Starbucks indicator
    if has_starbucks:
        insights.append("⭐ New Starbucks opened (2024-2025) — strong retail investment")

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

    # Select primary tract for boundary filtering (highest score)
    primary_tract = max(rows, key=lambda r: r.get("score", 0)) if rows else {}

    return {
        "median_home_value": round(med_home_val, 1) if med_home_val is not None else None,
        "median_income": round(med_income, 1) if med_income is not None else None,
        "vacancy_pct": round(vac_pct, 1) if vac_pct is not None else None,
        "days_on_market": int(dom) if dom is not None else None,
        "gap_ratio": round(gap_ratio, 2) if gap_ratio is not None else None,
        "total_pop": total_pop,
        "score": round(area_score, 1) if area_score is not None else 0.0,
        "has_starbucks": has_starbucks,
        "school_rating": round(school_rating, 1) if school_rating is not None else None,
        "insights": insights,
        "warnings": warnings,
        "member_tracts": members,
        "tracts_count": len(rows),
        "primary_tract_code": primary_tract.get("tract"),
        "primary_state_fips": primary_tract.get("state"),
        "primary_county_fips": primary_tract.get("county"),
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
            rehab_budget = int(req.params.get("rehab_budget", "15000"))
        except Exception:
            rehab_budget = 15000

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

        # Fetch market data for TOP neighborhoods after grouping (much more efficient!)
        rate_limit_hit = False
        if include_market_data and RAPIDAPI_KEY and neighborhoods:
            # Limit to top neighborhoods to avoid timeout
            fetch_limit = min(max_market_lookups, len(neighborhoods), 15)
            logging.info(f"🔍 Fetching market data for top {fetch_limit} neighborhoods...")
            looked = 0

            for neighborhood in neighborhoods[:fetch_limit]:
                try:
                    # Try to get ZIP from member tracts or guess
                    zip_code = neighborhood.get("zip_guess")
                    if not zip_code:
                        # Get ZIP from first member tract
                        members = neighborhood.get("member_tracts", [])
                        if members and members[0].get("zip_code"):
                            zip_code = members[0]["zip_code"]

                    if not zip_code:
                        continue

                    market_stats = get_market_stats_for_zip(zip_code)
                    dom = market_stats.get("median_days_on_market") if market_stats else None

                    if dom is not None:
                        neighborhood["days_on_market"] = int(dom)
                        looked += 1
                        logging.info(f"  ✓ {neighborhood.get('neighborhood')} (ZIP {zip_code}): {dom} days")

                        # Recalculate insights/warnings with DOM included
                        gap_ratio = neighborhood.get("gap_ratio")
                        vac_pct = neighborhood.get("vacancy_pct")
                        med_home_val = neighborhood.get("median_home_value")
                        med_income = neighborhood.get("median_income")
                        has_starbucks = neighborhood.get("has_starbucks", False)

                        insights = []
                        warnings = []

                        # Preserve Starbucks indicator (comes first for visibility)
                        if has_starbucks:
                            insights.append("⭐ New Starbucks opened (2024-2025) — strong retail investment")

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

                        # DOM insights
                        if dom < 40:
                            insights.append(f"⚡ Fast-moving market (~{int(dom)} days)")
                        elif dom > 90:
                            warnings.append(f"⚠️ Slower market (~{int(dom)} days to sell)")

                        neighborhood["insights"] = insights[:3]
                        neighborhood["warnings"] = warnings[:3]

                    time.sleep(0.15)  # Rate limit protection

                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        rate_limit_hit = True
                    logging.warning(f"  ✗ Failed to fetch market data: {e}")
                    continue

            logging.info(f"✅ Market data fetched for {looked} neighborhoods")
            if rate_limit_hit and looked == 0:
                errors.append("⚠️ RapidAPI rate limit exceeded. Market data unavailable.")

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
    Returns active listings for a location.
    Query params:
      zip          (required) - ZIP code to search
      neighborhood (optional) - Neighborhood name for more specific filtering
      city         (optional) - City name (defaults to Indianapolis for IN zips)
      state        (optional) - State code (defaults to IN for Indianapolis zips)
      tract        (optional) - 6-digit census tract code for boundary filtering (legacy)
      state_fips   (optional) - 2-digit state FIPS (default: 18 for Indiana)
      county_fips  (optional) - 3-digit county FIPS (default: 097 for Marion)
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

    # Get neighborhood/city parameters
    neighborhood = (req.params.get("neighborhood") or "").strip()
    city = (req.params.get("city") or "Indianapolis").strip()  # Default to Indianapolis
    state_code = (req.params.get("state") or "IN").strip()  # Default to Indiana

    # Legacy tract boundary filtering parameters (still supported as fallback)
    tract_code = (req.params.get("tract") or "").strip()
    state_fips = (req.params.get("state_fips") or "18").strip()  # Default: Indiana
    county_fips = (req.params.get("county_fips") or "097").strip()  # Default: Marion County

    # Fetch tract boundary if tract filtering requested
    tract_boundary = None
    if tract_code:
        logging.info(f"Tract filtering requested: state={state_fips}, county={county_fips}, tract={tract_code}")
        tract_boundary = fetch_tract_boundary(state_fips, county_fips, tract_code)
        if tract_boundary:
            logging.info(f"Successfully fetched boundary with {len(tract_boundary)} rings, first ring has {len(tract_boundary[0])} points")
        else:
            logging.warning(f"Could not fetch boundary for tract {tract_code}, proceeding without filtering")

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

    # Cache key based on ZIP code (neighborhood filtering not supported)
    if tract_code:
        cache_key = f"{LISTINGS_CACHE_VERSION}:{zip_code}:{tract_code}"
    else:
        cache_key = f"{LISTINGS_CACHE_VERSION}:{zip_code}"

    # Cache hit?
    cached = _cache_get_listings(cache_key)
    if cached is not None:
        data = cached
    else:
        # Call RapidAPI provider
        # Build payload - prefer location ID if we have it, otherwise use postal_code
        payload = {
            "limit": max(25, limit),
            "offset": 0,
            "status": ["for_sale", "under_contract"],
            "sort": {"direction": "desc", "field": "list_date"},
        }

        # Use postal_code for filtering (neighborhood filtering not supported)
        payload["postal_code"] = zip_code
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }
        try:
            r = requests.post(RAPIDAPI_TEST_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 404:
                data = {"results": [], "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}}
            elif r.status_code == 429:
                # Rate limit hit - return helpful message
                return func.HttpResponse(
                    json.dumps({
                        "status": "rate_limit",
                        "message": "Daily listing limit reached. Try again tomorrow!",
                        "results": [],
                        "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}
                    }),
                    mimetype="application/json",
                    headers=CORS_HEADERS
                )
            else:
                r.raise_for_status()
                raw = r.json()

                if raw is None:
                    data = {"results": [], "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}}
                    _cache_set_listings(cache_key, data)
                    return func.HttpResponse(json.dumps({
                        "status": "error",
                        "message": "API returned empty response",
                        "results": [],
                        "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}
                    }), mimetype="application/json", headers=CORS_HEADERS)

                props = (raw or {}).get("data", {}).get("home_search", {}).get("results", []) or []

                items = []
                under_budget = 0
                in_target = 0
                target_price = None
                if arv and discount:
                    target_price = int(arv * discount)

                total_props = len(props)
                logging.info(f"API returned {total_props} properties for ZIP {zip_code}")

                # Process properties
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
                    city_name = addr.get("city") or ""
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
                        "address": ", ".join([s for s in [line, city_name, state] if s]),
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

                # Determine if filtering was actually applied by location ID (or if we fell back to ZIP)
                filtering_applied = bool(location_id_data and (location_id_data.get("slug_id") or location_id_data.get("geo_id")))

                # Log filtering results
                logging.info(f"Filtering results for ZIP {zip_code}:")
                logging.info(f"  Total properties returned: {total_props}")
                if neighborhood:
                    logging.info(f"  Neighborhood requested: '{neighborhood}'")
                    if filtering_applied and location_id_data:
                        logging.info(f"  Location ID filtering applied via API")
                        if location_id_data.get("slug_id"):
                            logging.info(f"  Used slug_id: {location_id_data['slug_id']}")
                        elif location_id_data.get("geo_id"):
                            logging.info(f"  Used geo_id: {location_id_data['geo_id']}")
                    else:
                        logging.info(f"  No location ID found - fell back to ZIP {zip_code}")
                logging.info(f"  Final items count: {len(items)}")

                data = {
                    "results": sorted(items, key=lambda x: x["price"])[:limit],
                    "counts": {
                        "active_total": len(items),
                        "under_budget": under_budget,
                        "in_target_band": in_target
                    }
                }

            _cache_set_listings(cache_key, data)

        except Exception as e:
            logging.warning("Listings fetch failed for %s: %s", cache_key, e)
            data = {"results": [], "counts": {"active_total": 0, "under_budget": 0, "in_target_band": 0}}

    return func.HttpResponse(json.dumps({
        "status": "success",
        "zip": zip_code,
        "neighborhood": neighborhood if neighborhood else None,
        "counts": data.get("counts", {}),
        "results": data.get("results", [])
    }, indent=2), mimetype="application/json", headers=CORS_HEADERS)
