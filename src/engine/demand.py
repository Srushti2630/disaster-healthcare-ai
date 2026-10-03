"""
Epidemiological Healthcare Demand Engine & Stock Estimator module.
Calculates transparent 7-day and 14-day medicine demand based on WHO IEHK 2017 & Sphere standards,
and estimates baseline hospital surge stocks per district.
"""
from pathlib import Path
import yaml
import numpy as np
import pandas as pd

CONFIG_PATH = Path("config/demand_params.yaml")
CAPACITY_PATH = Path("data/processed/district_capacity.csv")
PROCESSED_DIR = Path("data/processed")

def load_demand_params():
    """Load epidemiological parameters from config/demand_params.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def compute_point_demand(affected_pop: float, injured_pop: float, hazard_type: str, horizon_days: int = 7) -> dict:
    """Compute point estimate 7-day or 14-day demand per medicine for a given casualty count."""
    params = load_demand_params()
    h_info = params["hazard_multipliers"].get(hazard_type, {"severity_scaling": 1.0, "duration_days": 7})
    scale = h_info["severity_scaling"]

    demands = {}
    for med, m_info in params["medicines"].items():
        if med == "blood_units":
            rate = m_info["rate_per_injured_day"]["mid"]
            raw_d = injured_pop * rate * horizon_days * scale
        else:
            rate = m_info["rate_per_affected_day"]["mid"]
            raw_d = affected_pop * rate * horizon_days * scale

        demands[med] = round(max(0.0, raw_d), 2)
    return demands

def estimate_district_stocks(capacity_df: pd.DataFrame = None) -> dict:
    """Estimate baseline available surge stock per district from hospital beds."""
    if capacity_df is None:
        if not CAPACITY_PATH.exists():
            raise FileNotFoundError(f"Missing {CAPACITY_PATH}")
        capacity_df = pd.read_csv(CAPACITY_PATH)

    params = load_demand_params()
    surge_mult = params["stock_norms"]["beds_surge_multiplier"]

    stocks = {}
    for _, row in capacity_df.iterrows():
        d_name = row["district"]
        beds = row["beds_mid"]
        icu = row["icu_beds_mid"]

        stocks[d_name] = {
            "antibiotics": round(beds * surge_mult * 4.0, 1),
            "ors": round(beds * surge_mult * 10.0, 1),
            "iv_fluids": round(beds * surge_mult * 3.0, 1),
            "analgesics": round(beds * surge_mult * 6.0, 1),
            "blood_units": round(icu * 8.0, 1)  # Anchored to ICU beds
        }
    return stocks

if __name__ == "__main__":
    p_dem = compute_point_demand(affected_pop=50000, injured_pop=2000, hazard_type="Flood", horizon_days=7)
    print("Sample 7-Day Point Demand (50k affected, 2k injured Flood):", p_dem)
    stocks = estimate_district_stocks()
    print(f"Estimated baseline stock for {len(stocks)} districts.")
