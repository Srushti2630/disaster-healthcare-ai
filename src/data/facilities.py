"""
National Hospital Directory cleaning and facility count aggregation module.
Cleans 4,807 Maharashtra facilities from hospital_directory (1).csv, parses coordinates,
and outputs data/processed/district_facilities.csv and cleaned facility records.
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd

from src.data.boundaries import normalize_district_name, MAHARASHTRA_DISTRICTS

RAW_HOSP = Path("data/raw/hospital_directory (1).csv")
PROCESSED_DIR = Path("data/processed")

def parse_coordinates(coord_str):
    """Safely parse 'lat, lon' string into (lat, lon) floats."""
    if not coord_str or pd.isna(coord_str):
        return np.nan, np.nan
    try:
        s = str(coord_str).strip().replace("\"", "").replace("'", "")
        parts = re.split(r"[,;:\s]+", s)
        if len(parts) >= 2:
            lat, lon = float(parts[0]), float(parts[1])
            if 8.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0:
                return lat, lon
    except Exception:
        pass
    return np.nan, np.nan

def clean_hospital_directory() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean facility records for Maharashtra and aggregate metrics per district."""
    if not RAW_HOSP.exists():
        raise FileNotFoundError(f"Missing hospital directory at {RAW_HOSP}")

    df = pd.read_csv(RAW_HOSP, low_memory=False)
    initial_national = len(df)

    # Filter Maharashtra records
    mh_mask = df["State"].astype(str).str.upper().str.contains("MAHARASHTRA|MAHARASTRA", na=False)
    mh_df = df[mh_mask].copy()
    initial_mh = len(mh_df)

    # Standardize district name
    mh_df["district"] = mh_df["District"].apply(normalize_district_name)

    # Parse coordinates
    coords = mh_df["Location_Coordinates"].apply(parse_coordinates)
    mh_df["lat_parsed"] = [c[0] for c in coords]
    mh_df["lon_parsed"] = [c[1] for c in coords]

    # Assign coordinate quality
    def assign_coord_quality(row):
        if not pd.isna(row["lat_parsed"]) and not pd.isna(row["lon_parsed"]):
            return "exact"
        elif not pd.isna(row.get("Pincode")) and str(row.get("Pincode")).strip().isdigit():
            return "pincode"
        return "district"

    mh_df["coord_quality"] = mh_df.apply(assign_coord_quality, axis=1)

    # Fallback missing lat/lon to district centroid
    def fill_lat(row):
        if not pd.isna(row["lat_parsed"]):
            return row["lat_parsed"]
        d = row["district"]
        return MAHARASHTRA_DISTRICTS.get(d, {}).get("lat", 19.0)

    def fill_lon(row):
        if not pd.isna(row["lon_parsed"]):
            return row["lon_parsed"]
        d = row["district"]
        return MAHARASHTRA_DISTRICTS.get(d, {}).get("lon", 74.5)

    mh_df["lat"] = mh_df.apply(fill_lat, axis=1)
    mh_df["lon"] = mh_df.apply(fill_lon, axis=1)

    # Clean beds (drop >5000 or <1 as corrupt)
    mh_df["Total_Num_Beds"] = pd.to_numeric(mh_df["Total_Num_Beds"], errors="coerce")
    mh_df["beds_valid"] = mh_df["Total_Num_Beds"].apply(lambda v: v if (pd.notna(v) and 1 <= v <= 5000) else np.nan)

    # Categorize Public vs Private
    def categorize_sector(cat_str):
        s = str(cat_str).lower()
        if any(k in s for k in ["public", "govt", "government", "district hospital", "chc", "phc", "municipal"]):
            return "Public"
        if any(k in s for k in ["private", "trust", "society", "nongovt"]):
            return "Private"
        return "Public"  # Default majority in NHP registry

    mh_df["sector"] = mh_df["Hospital_Category"].apply(categorize_sector)

    # Deduplicate on Hospital_Name + Pincode
    mh_df["pincode_str"] = mh_df["Pincode"].astype(str).str.extract(r"(\d{6})")[0].fillna("000000")
    mh_df["name_clean"] = mh_df["Hospital_Name"].astype(str).str.lower().str.replace(r"[^\w\s]", "", regex=True)
    dedup_cols = ["name_clean", "pincode_str", "district"]
    mh_clean = mh_df.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    # Save cleaned facility level data
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_facilities = PROCESSED_DIR / "cleaned_facilities.csv"
    mh_clean.to_csv(out_facilities, index=False)

    # Aggregate district level facility counts
    district_records = []
    for d_name in MAHARASHTRA_DISTRICTS.keys():
        d_fac = mh_clean[mh_clean["district"] == d_name]
        total_fac = len(d_fac)
        pub_fac = len(d_fac[d_fac["sector"] == "Public"])
        priv_fac = len(d_fac[d_fac["sector"] == "Private"])
        exact_coords = len(d_fac[d_fac["coord_quality"] == "exact"])

        district_records.append({
            "district": d_name,
            "total_facilities": total_fac,
            "public_facilities": pub_fac,
            "private_facilities": priv_fac,
            "public_ratio": round(pub_fac / max(1, total_fac), 3),
            "exact_coord_facilities": exact_coords,
            "coord_coverage_pct": round(exact_coords / max(1, total_fac) * 100, 1),
            "provenance": "REAL"
        })

    dist_df = pd.DataFrame(district_records)
    out_dist = PROCESSED_DIR / "district_facilities.csv"
    dist_df.to_csv(out_dist, index=False)

    print(f"Processed {len(mh_clean)} cleaned Maharashtra facilities across {len(dist_df)} districts.")
    print(f"District facility counts written to {out_dist}")

    return mh_clean, dist_df

if __name__ == "__main__":
    clean_hospital_directory()
