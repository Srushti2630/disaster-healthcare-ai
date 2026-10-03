"""
District hospital and ICU capacity estimation module.
Uses statewise ICU bed audit CSV (2,572 public / 9,015 private / 11,587 total) as a hard anchor,
and scales total hospital beds across Maharashtra's 35 districts using facility counts and population weighting.
Outputs data/processed/district_capacity.csv with Low/Mid/High ranges tagged ESTIMATED.
"""
from pathlib import Path
import numpy as np
import pandas as pd

RAW_ICU = Path("data/raw/ICU beds count in India - Statewise.csv")
PROCESSED_DIR = Path("data/processed")

# Maharashtra anchors
STATE_TOTAL_ICU_BEDS = 11_587
STATE_PUBLIC_ICU_BEDS = 2_572
STATE_PRIVATE_ICU_BEDS = 9_015
STATE_TOTAL_HOSPITAL_BEDS = 145_000  # NHP 2021 / NITI Aayog state estimate

def compute_district_capacity() -> pd.DataFrame:
    """Compute low/mid/high hospital and ICU bed capacity estimates per district."""
    pop_path = PROCESSED_DIR / "district_population.csv"
    fac_path = PROCESSED_DIR / "district_facilities.csv"

    if not pop_path.exists() or not fac_path.exists():
        raise FileNotFoundError("Missing district_population.csv or district_facilities.csv")

    pop_df = pd.read_csv(pop_path)
    fac_df = pd.read_csv(fac_path)

    merged = pd.merge(pop_df, fac_df, on="district")

    # Composite capacity weight = 0.50 * (population share) + 0.50 * (facility count share)
    total_pop = merged["population"].sum()
    total_fac = merged["total_facilities"].sum()

    merged["capacity_weight"] = (
        0.50 * (merged["population"] / total_pop) +
        0.50 * (merged["total_facilities"] / max(1, total_fac))
    )
    merged["capacity_weight"] = merged["capacity_weight"] / merged["capacity_weight"].sum()

    # Calculate mid bed counts
    merged["beds_mid"] = (merged["capacity_weight"] * STATE_TOTAL_HOSPITAL_BEDS).astype(int)
    merged["beds_low"] = (merged["beds_mid"] * 0.80).astype(int)
    merged["beds_high"] = (merged["beds_mid"] * 1.20).astype(int)

    # Calculate mid ICU bed counts anchored to 11,587 state total
    merged["icu_beds_mid"] = (merged["capacity_weight"] * STATE_TOTAL_ICU_BEDS).astype(int)
    merged["icu_beds_low"] = (merged["icu_beds_mid"] * 0.80).astype(int)
    merged["icu_beds_high"] = (merged["icu_beds_mid"] * 1.20).astype(int)

    merged["provenance"] = "ESTIMATED"

    out_cols = [
        "district", "population", "total_facilities", "public_facilities", "private_facilities",
        "beds_low", "beds_mid", "beds_high",
        "icu_beds_low", "icu_beds_mid", "icu_beds_high",
        "provenance"
    ]

    out_df = merged[out_cols].copy()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_DIR / "district_capacity.csv"
    out_df.to_csv(out_csv, index=False)

    print(f"District capacity estimates written to {out_csv}")
    print(f"State Total Hospital Beds: {out_df['beds_mid'].sum():,}, Total ICU Beds: {out_df['icu_beds_mid'].sum():,}")
    return out_df

if __name__ == "__main__":
    compute_district_capacity()
