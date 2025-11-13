# 🗺️ One-Time Data Collection Scripts

These scripts fetch valuable neighborhood data **once**, hardcode it into your app, then you delete the scripts. Never pay API costs again!

## 📋 Scripts Overview

| Script | Data Source | Cost | Impact on Flipping |
|--------|-------------|------|-------------------|
| `01_google_maps_neighborhoods.py` | Google Maps Geocoding | ~$1 | ⭐⭐⭐⭐⭐ Accurate neighborhood names |
| `02_walk_score_mapper.py` | Walk Score API | FREE | ⭐⭐⭐⭐ Walkability attracts buyers |
| `03_school_ratings_mapper.py` | GreatSchools API | FREE | ⭐⭐⭐⭐⭐ HUGE for family buyers |
| `04_crime_data_mapper.py` | Indianapolis Open Data | FREE | ⭐⭐⭐⭐ Safety = higher values |
| `05_amenities_mapper.py` | OpenStreetMap | FREE | ⭐⭐⭐ Lifestyle appeal |

**Total Cost: ~$1** (one-time payment)

---

## 🚀 How to Use

### 1. Google Maps Neighborhoods (REQUIRED - fixes your ZIP 46203 bug!)

```bash
# Get API key from Google Cloud Console
export GOOGLE_MAPS_API_KEY='your-key-here'

# Run script
python3 scripts/01_google_maps_neighborhoods.py

# Copy output into function_app.py
# Delete script
```

**Cost:** ~$1 (200 tracts × $0.005 per request)

**Why this matters:** Gets official Google Maps neighborhood names that match what Realtor.com and Zillow use!

---

### 2. Walk Score (Walkability bonus points)

```bash
# Get FREE API key: https://www.walkscore.com/professional/api.php
export WALK_SCORE_API_KEY='your-key-here'

# Run script
python3 scripts/02_walk_score_mapper.py
```

**Cost:** FREE (5,000 requests/day limit)

**Scoring idea:**
```python
if walk_score >= 70:
    bonus_points += 2  # Very walkable - millennials love this
elif walk_score >= 50:
    bonus_points += 1
```

**Why this matters:** Walkable neighborhoods command 10-20% price premiums!

---

### 3. School Ratings (Family buyer magnet)

```bash
# Request FREE API key: https://www.greatschools.org/api-request/
export GREATSCHOOLS_API_KEY='your-key-here'

# Run script
python3 scripts/03_school_ratings_mapper.py
```

**Cost:** FREE

**Scoring idea:**
```python
if school_rating >= 7:
    bonus_points += 3  # Great schools = HUGE selling point
elif school_rating >= 5:
    bonus_points += 1
```

**Why this matters:** School district is the #1 factor for families with kids. Can add 15-30% to home values!

---

### 4. Crime Data (Safety scores)

```bash
# No API key needed - public data!
python3 scripts/04_crime_data_mapper.py
```

**Cost:** FREE

**Scoring idea:**
```python
if safety_score >= 80:
    bonus_points += 2  # Very safe
elif safety_score >= 60:
    bonus_points += 1
elif safety_score < 40:
    bonus_points -= 2  # High crime = harder to sell
```

**Why this matters:** Safety concerns kill deals. Low-crime neighborhoods sell faster and for more money.

---

### 5. Amenities (Lifestyle appeal)

```bash
# No API key needed - uses OpenStreetMap!
python3 scripts/05_amenities_mapper.py
```

**Cost:** FREE

**Scoring idea:**
```python
if amenity_score >= 70:
    bonus_points += 2  # Tons of restaurants/shops/parks
elif amenity_score >= 40:
    bonus_points += 1
```

**Why this matters:** Millennials and young families want walkable amenities. Adds perceived value.

---

## 🎯 Recommended Scoring Weights

Here's how I'd weight these factors for house flipping:

```python
# Example combined bonus system
total_bonus = 0

# Schools (most important for resale)
if school_rating >= 7: total_bonus += 3
elif school_rating >= 5: total_bonus += 1

# Safety (second most important)
if safety_score >= 80: total_bonus += 2
elif safety_score >= 60: total_bonus += 1
elif safety_score < 40: total_bonus -= 2

# Walkability (growing importance)
if walk_score >= 70: total_bonus += 2
elif walk_score >= 50: total_bonus += 1

# Amenities (nice to have)
if amenity_score >= 70: total_bonus += 2
elif amenity_score >= 40: total_bonus += 1

# Starbucks (you already have this!)
if has_starbucks: total_bonus += 3

# Add to final score
final_score = base_score + total_bonus
```

---

## 💡 Additional Free Data Ideas

Want even more scoring factors? Here are other free/cheap sources:

### 6. **Transit Access** (FREE)
- Source: GTFS data from IndyGo
- URL: https://www.indygo.net/gtfs/
- Why: Proximity to bus lines adds value

### 7. **Building Permits** (FREE)
- Source: Indianapolis Open Data
- URL: https://data.indy.gov/
- Why: Recent permits = neighborhood investment

### 8. **Grocery Stores** (Cheap)
- Source: Google Places API
- Cost: $17 per 1,000 requests (do once)
- Why: "Food desert" areas are harder to sell

### 9. **Flood Zones** (FREE)
- Source: FEMA Flood Map Service
- URL: https://msc.fema.gov/portal/
- Why: Flood risk kills deals and insurance costs

### 10. **Historic Districts** (FREE)
- Source: National Register of Historic Places
- URL: https://www.nps.gov/subjects/nationalregister/
- Why: Historic districts have strict rules = harder/more expensive flips

---

## 📊 Expected Impact on Scores

If you implement all 5 scripts, here's the expected impact:

| Neighborhood Type | Base Score | With Bonuses | Delta |
|------------------|-----------|--------------|-------|
| Downtown/Mass Ave | 72 | 82 | +10 |
| Broad Ripple | 68 | 80 | +12 |
| Fountain Square | 65 | 74 | +9 |
| Carmel (suburbs) | 75 | 87 | +12 |
| High-crime area | 60 | 54 | -6 |

**Net effect:** Better differentiation between truly great neighborhoods and mediocre ones!

---

## 🔧 Integration Steps

After running all scripts:

1. **Copy all output dictionaries** into `function_app.py` at the top
2. **Create a combined scoring function:**

```python
def get_neighborhood_bonus(neighborhood: str) -> float:
    """Calculate bonus points from hardcoded neighborhood data"""
    bonus = 0

    # Get all the scores
    walk = NEIGHBORHOOD_WALK_SCORES.get(neighborhood, 0)
    school = NEIGHBORHOOD_SCHOOL_RATINGS.get(neighborhood, 0)
    safety = NEIGHBORHOOD_SAFETY_SCORES.get(neighborhood, 0)
    amenity = NEIGHBORHOOD_AMENITY_SCORES.get(neighborhood, 0)

    # Apply bonuses
    if school >= 7: bonus += 3
    elif school >= 5: bonus += 1

    if safety >= 80: bonus += 2
    elif safety >= 60: bonus += 1
    elif safety < 40: bonus -= 2

    if walk >= 70: bonus += 2
    elif walk >= 50: bonus += 1

    if amenity >= 70: bonus += 2
    elif amenity >= 40: bonus += 1

    return bonus
```

3. **Update `score_tract_flip_potential()`:**

```python
# Add this line after starbucks_bonus
neighborhood_bonus = get_neighborhood_bonus(neighborhood)
total_score = round((total * 100) + starbucks_bonus + neighborhood_bonus, 1)
```

4. **Delete all scripts!** You don't need them anymore - data is hardcoded.

---

## 📝 Notes

- **Refresh frequency:** Run scripts once a year to keep data current
- **API limits:** All FREE scripts have generous limits for one-time use
- **Accuracy:** This data is MORE accurate than manually guessing ranges
- **Maintenance:** Zero - once hardcoded, it's static data

---

## 🎉 Result

After running all scripts, your scoring will be **dramatically more accurate** and based on real data that matters to buyers:

- ✅ Schools (families)
- ✅ Safety (everyone)
- ✅ Walkability (millennials)
- ✅ Amenities (lifestyle)
- ✅ Commercial growth (Starbucks)

**Your flips will target the RIGHT neighborhoods with confidence!** 🏡💰
