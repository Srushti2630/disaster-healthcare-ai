"""
EM-DAT International Disaster Database cleaning module.
Parses real historical India disaster events, extracts target casualties without imputation,
constructs event dates, maps spatial admin units, and outputs data/processed/emdat_events.csv.
"""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

from src.data.boundaries import normalize_district_name, MAHARASHTRA_DISTRICTS

RAW_EMDAT = Path("data/raw/emdat.xlsx")
PROCESSED_DIR = Path("data/processed")

def parse_admin_units(admin_str, loc_str):
    """Parse EM-DAT Admin Units or Location text to extract state and district names."""
    states = set()
    districts = set()
    
    text = f"{admin_str} {loc_str}".lower()
    
    if "maharashtra" in text or "maharastra" in text:
        states.add("Maharashtra")

    for d_name in MAHARASHTRA_DISTRICTS.keys():
        if d_name.lower() in text:
            districts.add(d_name)
            states.add("Maharashtra")

    scope = "district" if len(districts) == 1 else ("multi-district" if len(districts) > 1 else ("state" if states else "national"))
    return list(states), list(districts), scope

def clean_emdat_disasters() -> pd.DataFrame:
    """Clean real EM-DAT India disaster events catalogue."""
    if not RAW_EMDAT.exists():
        raise FileNotFoundError(f"Missing {RAW_EMDAT}")

    df = pd.read_excel(RAW_EMDAT)
    initial_rows = len(df)

    # Filter India records
    ind_mask = (df["ISO"].astype(str).str.upper() == "IND") | (df["Country"].astype(str).str.lower() == "india")
    df = df[ind_mask].copy().reset_index(drop=True)

    # Standardize columns
    df["event_id"] = df["DisNo."].astype(str)
    df["disaster_type"] = df["Disaster Type"].fillna("Unknown").astype(str)
    df["disaster_subtype"] = df["Disaster Subtype"].fillna("Unknown").astype(str)
    df["magnitude"] = pd.to_numeric(df["Magnitude"], errors="coerce")
    df["magnitude_scale"] = df["Magnitude Scale"].fillna("").astype(str)
    df["lat"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Dates
    df["start_year"] = pd.to_numeric(df["Start Year"], errors="coerce").fillna(2000).astype(int)
    df["start_month"] = pd.to_numeric(df["Start Month"], errors="coerce").fillna(6).astype(int).clip(1, 12)
    df["start_day"] = pd.to_numeric(df["Start Day"], errors="coerce").fillna(1).astype(int).clip(1, 31)

    def build_date_str(r):
        try:
            return f"{r['start_year']:04d}-{r['start_month']:02d}-{r['start_day']:02d}"
        except Exception:
            return f"{r['start_year']:04d}-06-01"

    df["event_date"] = df.apply(build_date_str, axis=1)
    df["event_date_dt"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["decade"] = (df["start_year"] // 10) * 10

    # Real Casualty Targets — STRICT NON-IMPUTATION POLICY
    df["total_affected"] = pd.to_numeric(df["Total Affected"], errors="coerce")
    df["no_injured"] = pd.to_numeric(df["No. Injured"], errors="coerce")
    df["total_deaths"] = pd.to_numeric(df["Total Deaths"], errors="coerce")

    # Log1p transforms (preserving NaN for missing targets)
    df["log1p_affected"] = np.log1p(df["total_affected"].clip(lower=0))
    df["log1p_injured"] = np.log1p(df["no_injured"].clip(lower=0))
    df["log1p_deaths"] = np.log1p(df["total_deaths"].clip(lower=0))

    # Spatial mapping
    states_list, districts_list, scopes = [], [], []
    for _, r in df.iterrows():
        st, dists, sc = parse_admin_units(r.get("Admin Units", ""), r.get("Location", ""))
        states_list.append(",".join(st) if st else "India")
        districts_list.append(",".join(dists) if dists else "Statewide")
        scopes.append(sc)

    df["states_affected"] = states_list
    df["districts_affected"] = districts_list
    df["scope"] = scopes
    df["is_maharashtra"] = df["states_affected"].str.contains("Maharashtra", na=False)
    df["provenance"] = "REAL"

    # Save processed events
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_DIR / "emdat_events.csv"
    df.to_csv(out_csv, index=False)

    print(f"Cleaned {len(df)} real EM-DAT India disaster events (written to {out_csv}).")
    print(f"Events with recorded Total Affected: {df['total_affected'].notna().sum()}")
    print(f"Maharashtra disaster events: {df['is_maharashtra'].sum()}")

    return df

if __name__ == "__main__":
    clean_emdat_disasters()
