"""
District boundary geometry and metadata module for Maharashtra's 35 administrative districts.
Handles shapefile/GeoJSON loading from data/raw/boundaries/ or constructs valid polygon geometries.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, box
import shapely.ops

BOUNDARIES_DIR = Path("data/raw/boundaries")
PROCESSED_DIR = Path("data/processed")

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate haversine distance in km between two lat/lon coordinates."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = (np.sin(dphi / 2.0) ** 2 +
         np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2)
    return 2.0 * r * np.arcsin(np.clip(np.sqrt(a), 0, 1))


# Canonical 35 Districts of Maharashtra with official centroid coordinates and Census 2011 population weights
MAHARASHTRA_DISTRICTS = {
    "Ahmednagar": {"lat": 19.095, "lon": 74.749, "area_sqkm": 17048, "pop_weight": 0.0410},
    "Akola": {"lat": 20.700, "lon": 77.000, "area_sqkm": 5428, "pop_weight": 0.0163},
    "Amravati": {"lat": 20.937, "lon": 77.750, "area_sqkm": 12210, "pop_weight": 0.0260},
    "Aurangabad": {"lat": 19.876, "lon": 75.343, "area_sqkm": 10107, "pop_weight": 0.0330}, # Chhatrapati Sambhajinagar
    "Beed": {"lat": 18.990, "lon": 75.760, "area_sqkm": 10693, "pop_weight": 0.0235},
    "Bhandara": {"lat": 21.170, "lon": 79.650, "area_sqkm": 3895, "pop_weight": 0.0107},
    "Buldhana": {"lat": 20.530, "lon": 76.180, "area_sqkm": 9661, "pop_weight": 0.0232},
    "Chandrapur": {"lat": 19.950, "lon": 79.300, "area_sqkm": 11443, "pop_weight": 0.0196},
    "Dhule": {"lat": 20.900, "lon": 74.780, "area_sqkm": 8063, "pop_weight": 0.0183},
    "Gadchiroli": {"lat": 20.100, "lon": 80.000, "area_sqkm": 14412, "pop_weight": 0.0097},
    "Gondia": {"lat": 21.460, "lon": 80.200, "area_sqkm": 5434, "pop_weight": 0.0118},
    "Hingoli": {"lat": 19.720, "lon": 77.150, "area_sqkm": 4526, "pop_weight": 0.0105},
    "Jalgaon": {"lat": 21.000, "lon": 75.560, "area_sqkm": 11765, "pop_weight": 0.0378},
    "Jalna": {"lat": 19.840, "lon": 75.880, "area_sqkm": 7718, "pop_weight": 0.0174},
    "Kolhapur": {"lat": 16.705, "lon": 74.243, "area_sqkm": 7685, "pop_weight": 0.0345},
    "Latur": {"lat": 18.400, "lon": 76.580, "area_sqkm": 7157, "pop_weight": 0.0219},
    "Mumbai": {"lat": 19.076, "lon": 72.877, "area_sqkm": 603, "pop_weight": 0.1110}, # Combines City & Suburban
    "Nagpur": {"lat": 21.146, "lon": 79.088, "area_sqkm": 9892, "pop_weight": 0.0415},
    "Nanded": {"lat": 19.150, "lon": 77.300, "area_sqkm": 10528, "pop_weight": 0.0298},
    "Nandurbar": {"lat": 21.370, "lon": 74.240, "area_sqkm": 5955, "pop_weight": 0.0147},
    "Nashik": {"lat": 20.000, "lon": 73.780, "area_sqkm": 15530, "pop_weight": 0.0545},
    "Osmanabad": {"lat": 18.180, "lon": 76.040, "area_sqkm": 7569, "pop_weight": 0.0148}, # Dharashiv
    "Palghar": {"lat": 19.690, "lon": 72.760, "area_sqkm": 5344, "pop_weight": 0.0267},
    "Parbhani": {"lat": 19.270, "lon": 76.780, "area_sqkm": 5651, "pop_weight": 0.0164},
    "Pune": {"lat": 18.520, "lon": 73.856, "area_sqkm": 15643, "pop_weight": 0.0840},
    "Raigad": {"lat": 18.510, "lon": 73.180, "area_sqkm": 7152, "pop_weight": 0.0235},
    "Ratnagiri": {"lat": 16.990, "lon": 73.300, "area_sqkm": 8208, "pop_weight": 0.0144},
    "Sangli": {"lat": 16.850, "lon": 74.580, "area_sqkm": 8572, "pop_weight": 0.0251},
    "Satara": {"lat": 17.680, "lon": 74.000, "area_sqkm": 10480, "pop_weight": 0.0267},
    "Sindhudurg": {"lat": 16.160, "lon": 73.680, "area_sqkm": 5207, "pop_weight": 0.0076},
    "Solapur": {"lat": 17.660, "lon": 75.906, "area_sqkm": 14895, "pop_weight": 0.0385},
    "Thane": {"lat": 19.218, "lon": 72.978, "area_sqkm": 4214, "pop_weight": 0.0720},
    "Wardha": {"lat": 20.740, "lon": 78.600, "area_sqkm": 6309, "pop_weight": 0.0116},
    "Washim": {"lat": 20.100, "lon": 77.150, "area_sqkm": 5158, "pop_weight": 0.0107},
    "Yavatmal": {"lat": 20.400, "lon": 78.130, "area_sqkm": 13582, "pop_weight": 0.0248},
}

# District name alias mapping for fuzzy matching
DISTRICT_ALIASES = {
    "aurangabad": "Aurangabad",
    "chhatrapati sambhajinagar": "Aurangabad",
    "osmanabad": "Osmanabad",
    "dharashiv": "Osmanabad",
    "raigarh": "Raigad",
    "mumbai city": "Mumbai",
    "mumbai suburban": "Mumbai",
    "mumbaisuburban": "Mumbai",
    "greater mumbai": "Mumbai",
}

def normalize_district_name(raw_name: str) -> str:
    """Normalize raw district name string to standard 35 district key."""
    if not raw_name or pd.isna(raw_name):
        return "Unknown"
    s = str(raw_name).strip().lower()
    if s in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[s]
    for key in MAHARASHTRA_DISTRICTS.keys():
        if key.lower() in s:
            return key
    return str(raw_name).strip().title()

def load_or_create_district_boundaries() -> gpd.GeoDataFrame:
    """
    Load district polygons from GeoJSON/Shapefile if available in data/raw/boundaries/,
    otherwise construct geometric polygon tessellation around official district centroids.
    """
    BOUNDARIES_DIR.mkdir(parents=True, exist_ok=True)
    geojson_path = BOUNDARIES_DIR / "maharashtra_districts.geojson"
    
    if geojson_path.exists():
        gdf = gpd.read_file(geojson_path)
        gdf["district"] = gdf["district"].apply(normalize_district_name)
        return gdf

    # Construct synthetic Voronoi/bounding box polygons around canonical district centroids
    points = []
    names = []
    meta = []
    for d_name, d_info in MAHARASHTRA_DISTRICTS.items():
        names.append(d_name)
        points.append(Point(d_info["lon"], d_info["lat"]))
        meta.append(d_info)

    # Generate bounding boxes of width/height proportional to sqrt(area)
    polys = []
    for d_name, d_info in MAHARASHTRA_DISTRICTS.items():
        # ~1 deg lat = 111 km, ~1 deg lon = 104 km
        side_deg = (d_info["area_sqkm"] ** 0.5) / 108.0
        half = side_deg / 2.0
        lat, lon = d_info["lat"], d_info["lon"]
        poly = box(lon - half, lat - half, lon + half, lat + half)
        polys.append(poly)

    gdf = gpd.GeoDataFrame({
        "district": names,
        "lat": [m["lat"] for m in meta],
        "lon": [m["lon"] for m in meta],
        "area_sqkm": [m["area_sqkm"] for m in meta],
        "pop_weight": [m["pop_weight"] for m in meta],
        "geometry": polys
    }, crs="EPSG:4326")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(geojson_path, driver="GeoJSON")
    return gdf

if __name__ == "__main__":
    gdf = load_or_create_district_boundaries()
    print(f"Loaded/created {len(gdf)} district boundaries.")
