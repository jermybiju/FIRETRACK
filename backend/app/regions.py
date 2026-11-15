"""Preset areas of interest and a small offline gazetteer.

The gazetteer exists so "search for a location" works with no network access and
no third-party geocoding service. It covers fire-prone regions and major cities;
any other point can be entered as latitude/longitude or drawn on the map.
"""

from __future__ import annotations

from .geo import AOI

# id -> preset area
REGIONS: dict[str, dict] = {
    "aegean": {
        "name": "Aegean & Anatolia",
        "bbox": [20.0, 35.0, 28.0, 41.0],
        "description": "Greece, the Aegean and western Türkiye: a Mediterranean summer fire regime, "
                       "observable from 2000 to the present.",
        "biome": "Mediterranean",
    },
    "sahel_belt": {
        "name": "Sahel & Sudan fire belt",
        "bbox": [21.0, 7.0, 33.0, 14.0],
        "description": "Sudan, South Sudan and CAR savanna: the dominant November burning region on Earth.",
        "biome": "Tropical savanna",
    },
    "west_africa": {
        "name": "West African savanna",
        "bbox": [-13.0, 9.0, 2.0, 15.0],
        "description": "Senegal, Mali, Burkina Faso and Guinea: agricultural and pastoral burning.",
        "biome": "Savanna / cropland",
    },
    "angola_zambia": {
        "name": "Angola–Zambia woodlands",
        "bbox": [18.0, -16.0, 30.0, -8.0],
        "description": "Miombo woodland with intense late-dry-season burning.",
        "biome": "Miombo woodland",
    },
    "amazon_arc": {
        "name": "Amazon deforestation arc",
        "bbox": [-60.0, -12.0, -48.0, -4.0],
        "description": "Eastern and southern Amazon: deforestation and pasture fires.",
        "biome": "Tropical moist forest",
    },
    "indonesia": {
        "name": "Kalimantan & Sumatra",
        "bbox": [109.0, -4.0, 118.0, 2.0],
        "description": "Peatland and land-clearing fires in insular Southeast Asia.",
        "biome": "Peat swamp / forest",
    },
    "australia_savanna": {
        "name": "Northern Australian savanna",
        "bbox": [122.0, -20.0, 134.0, -12.0],
        "description": "Tropical savanna with early-dry-season prescribed and wild fires.",
        "biome": "Tropical savanna",
    },
    "california": {
        "name": "California",
        "bbox": [-122.5, 36.0, -118.0, 40.0],
        "description": "Mediterranean shrubland with a summer–autumn fire season.",
        "biome": "Chaparral",
    },
    "mediterranean_east": {
        "name": "Eastern Mediterranean",
        "bbox": [5.0, 36.0, 20.0, 45.0],
        "description": "Greece, Italy and Türkiye: summer agricultural and wildland fires.",
        "biome": "Mediterranean",
    },
    "canada_boreal": {
        "name": "Western Canadian boreal",
        "bbox": [-120.0, 52.0, -100.0, 60.0],
        "description": "Boreal forest with increasingly large summer fire seasons.",
        "biome": "Boreal forest",
    },
    "siberia": {
        "name": "Central Siberia",
        "bbox": [80.0, 52.0, 110.0, 62.0],
        "description": "Larch and pine forest with remote, long-burning summer fires.",
        "biome": "Boreal forest",
    },
}

# name, country, latitude, longitude
CITIES: list[dict] = [
    {"name": "Khartoum", "country": "Sudan", "lat": 15.50, "lon": 32.56},
    {"name": "Juba", "country": "South Sudan", "lat": 4.85, "lon": 31.58},
    {"name": "Bangui", "country": "Central African Republic", "lat": 4.37, "lon": 18.56},
    {"name": "N'Djamena", "country": "Chad", "lat": 12.11, "lon": 15.05},
    {"name": "Ouagadougou", "country": "Burkina Faso", "lat": 12.37, "lon": -1.53},
    {"name": "Bamako", "country": "Mali", "lat": 12.64, "lon": -8.00},
    {"name": "Dakar", "country": "Senegal", "lat": 14.69, "lon": -17.45},
    {"name": "Lagos", "country": "Nigeria", "lat": 6.52, "lon": 3.38},
    {"name": "Abuja", "country": "Nigeria", "lat": 9.08, "lon": 7.40},
    {"name": "Lusaka", "country": "Zambia", "lat": -15.42, "lon": 28.28},
    {"name": "Luanda", "country": "Angola", "lat": -8.84, "lon": 13.23},
    {"name": "Harare", "country": "Zimbabwe", "lat": -17.83, "lon": 31.05},
    {"name": "Manaus", "country": "Brazil", "lat": -3.12, "lon": -60.02},
    {"name": "Porto Velho", "country": "Brazil", "lat": -8.76, "lon": -63.90},
    {"name": "Cuiabá", "country": "Brazil", "lat": -15.60, "lon": -56.10},
    {"name": "Brasília", "country": "Brazil", "lat": -15.79, "lon": -47.88},
    {"name": "Belém", "country": "Brazil", "lat": -1.46, "lon": -48.50},
    {"name": "Jakarta", "country": "Indonesia", "lat": -6.21, "lon": 106.85},
    {"name": "Palangka Raya", "country": "Indonesia", "lat": -2.21, "lon": 113.92},
    {"name": "Kuala Lumpur", "country": "Malaysia", "lat": 3.14, "lon": 101.69},
    {"name": "Darwin", "country": "Australia", "lat": -12.46, "lon": 130.84},
    {"name": "Perth", "country": "Australia", "lat": -31.95, "lon": 115.86},
    {"name": "Sydney", "country": "Australia", "lat": -33.87, "lon": 151.21},
    {"name": "Sacramento", "country": "United States", "lat": 38.58, "lon": -121.49},
    {"name": "Los Angeles", "country": "United States", "lat": 34.05, "lon": -118.24},
    {"name": "San Francisco", "country": "United States", "lat": 37.77, "lon": -122.42},
    {"name": "Seattle", "country": "United States", "lat": 47.61, "lon": -122.33},
    {"name": "Boulder", "country": "United States", "lat": 40.01, "lon": -105.27},
    {"name": "Missoula", "country": "United States", "lat": 46.87, "lon": -113.99},
    {"name": "Edmonton", "country": "Canada", "lat": 53.55, "lon": -113.49},
    {"name": "Yellowknife", "country": "Canada", "lat": 62.45, "lon": -114.37},
    {"name": "Prince George", "country": "Canada", "lat": 53.92, "lon": -122.75},
    {"name": "Athens", "country": "Greece", "lat": 37.98, "lon": 23.73},
    {"name": "Rome", "country": "Italy", "lat": 41.90, "lon": 12.50},
    {"name": "Palermo", "country": "Italy", "lat": 38.12, "lon": 13.36},
    {"name": "Ankara", "country": "Türkiye", "lat": 39.93, "lon": 32.86},
    {"name": "Antalya", "country": "Türkiye", "lat": 36.90, "lon": 30.71},
    {"name": "Madrid", "country": "Spain", "lat": 40.42, "lon": -3.70},
    {"name": "Lisbon", "country": "Portugal", "lat": 38.72, "lon": -9.14},
    {"name": "Marseille", "country": "France", "lat": 43.30, "lon": 5.37},
    {"name": "Yakutsk", "country": "Russia", "lat": 62.03, "lon": 129.73},
    {"name": "Krasnoyarsk", "country": "Russia", "lat": 56.01, "lon": 92.87},
    {"name": "Irkutsk", "country": "Russia", "lat": 52.29, "lon": 104.28},
    {"name": "Ulaanbaatar", "country": "Mongolia", "lat": 47.89, "lon": 106.91},
    {"name": "New Delhi", "country": "India", "lat": 28.61, "lon": 77.21},
    {"name": "Chandigarh", "country": "India", "lat": 30.73, "lon": 76.78},
    {"name": "Kathmandu", "country": "Nepal", "lat": 27.72, "lon": 85.32},
    {"name": "Bangkok", "country": "Thailand", "lat": 13.76, "lon": 100.50},
    {"name": "Hanoi", "country": "Vietnam", "lat": 21.03, "lon": 105.85},
    {"name": "Cape Town", "country": "South Africa", "lat": -33.92, "lon": 18.42},
    {"name": "Johannesburg", "country": "South Africa", "lat": -26.20, "lon": 28.05},
    {"name": "Nairobi", "country": "Kenya", "lat": -1.29, "lon": 36.82},
    {"name": "Addis Ababa", "country": "Ethiopia", "lat": 9.02, "lon": 38.75},
    {"name": "Cairo", "country": "Egypt", "lat": 30.04, "lon": 31.24},
    {"name": "Mexico City", "country": "Mexico", "lat": 19.43, "lon": -99.13},
    {"name": "Santiago", "country": "Chile", "lat": -33.45, "lon": -70.67},
    {"name": "Buenos Aires", "country": "Argentina", "lat": -34.60, "lon": -58.38},
    {"name": "London", "country": "United Kingdom", "lat": 51.51, "lon": -0.13},
    {"name": "Berlin", "country": "Germany", "lat": 52.52, "lon": 13.41},
    {"name": "Tokyo", "country": "Japan", "lat": 35.68, "lon": 139.69},
]


def region_aoi(region_id: str) -> AOI | None:
    region = REGIONS.get(region_id)
    if not region:
        return None
    return AOI(
        name=region["name"],
        bbox=tuple(region["bbox"]),
        polygon=region.get("polygon"),
        kind="region",
        id=region_id,
    )


def preset_list() -> list[dict]:
    return [
        {"id": rid, **{k: v for k, v in reg.items() if k != "polygon"}}
        for rid, reg in REGIONS.items()
    ]


def search(term: str, limit: int = 12) -> list[dict]:
    """Search presets and the offline gazetteer."""
    q = (term or "").strip().lower()
    if not q:
        return []
    out: list[dict] = []
    for rid, reg in REGIONS.items():
        haystack = f"{reg['name']} {reg.get('biome', '')} {reg.get('description', '')}".lower()
        if q in haystack or rid in q:
            out.append({
                "kind": "region", "id": rid, "name": reg["name"],
                "subtitle": reg.get("biome", ""), "bbox": reg["bbox"],
            })
    for city in CITIES:
        haystack = f"{city['name']} {city['country']}".lower()
        if q in haystack:
            lat, lon = city["lat"], city["lon"]
            span = 1.5
            out.append({
                "kind": "city",
                "id": f"city:{city['name']}",
                "name": city["name"],
                "subtitle": city["country"],
                "lat": lat,
                "lon": lon,
                "bbox": [lon - span, lat - span, lon + span, lat + span],
            })
    return out[:limit]
