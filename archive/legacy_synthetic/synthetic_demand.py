#!/usr/bin/env python3
"""
synthetic_demand.py
Semi-synthetic generator for disaster healthcare demand, inventory and
shortage-risk data. No public dataset records medicine demand per region per
day during disasters, so this builds one from explicit, editable assumptions.

!! IMPORTANT !!
Every number in the ASSUMPTIONS section below is a PLACEHOLDER chosen to give
plausible shapes, not a published value. Before you report results, replace
them with figures from WHO Interagency Emergency Health Kit / Sphere Handbook /
literature, and cite them. State in your report that the data is semi-synthetic
and what the models can and cannot claim as a result.

Outputs (data/synthetic/)
  regions.csv            region id, name, lat, lon, population, beds
  region_distances.csv   pairwise haversine distance (km) for the optimiser
  scenarios.csv          one row per disaster scenario
  demand_daily.csv       scenario x region x medicine x day demand (units)
  shortage_dataset.csv   scenario x region x medicine: features, 7-day demand,
                         stock, shortage quantity, risk level (Low/Medium/High)

Usage
  python synthetic_demand.py --n-scenarios 400 --seed 42
  python synthetic_demand.py --regions my_regions.csv   # your own region table
      (columns: region, lat, lon, population, beds)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ============================== ASSUMPTIONS ===============================
MEDICINES = ["antibiotics", "ors", "iv_fluids", "analgesics", "blood_units"]
HORIZON_DAYS = 14

# Illustrative regions (approximate, rounded). Replace with WorldPop/Census
# aggregates via --regions for anything you report.
DEFAULT_REGIONS = [
    # name, lat, lon, population, hospital beds
    ("Pune", 18.52, 73.86, 9_400_000, 14_000),
    ("Mumbai", 19.08, 72.88, 12_400_000, 38_000),
    ("Nashik", 20.00, 73.79, 6_100_000, 7_500),
    ("Nagpur", 21.15, 79.09, 4_600_000, 9_000),
    ("Kolhapur", 16.70, 74.24, 3_900_000, 5_200),
    ("Satara", 17.69, 74.00, 3_000_000, 3_300),
    ("Ratnagiri", 16.99, 73.30, 1_600_000, 2_000),
    ("Sangli", 16.85, 74.58, 2_800_000, 3_000),
    ("Aurangabad", 19.88, 75.34, 3_700_000, 5_000),
    ("Solapur", 17.66, 75.91, 4_300_000, 4_200),
]

DISASTERS = ["flood", "cyclone", "earthquake"]
DISASTER_PROB = [0.5, 0.25, 0.25]
# Severity 1..5 mix. Deliberately tilted toward serious events so the shortage
# classes are learnable; real catalogues are dominated by minor events.
SEVERITY_PROB = [0.15, 0.20, 0.25, 0.25, 0.15]

# Fraction of regional population affected at severity 1..5 at the epicentre
AFFECTED_FRAC = {1: 0.005, 2: 0.02, 3: 0.06, 4: 0.15, 5: 0.35}
# How fast impact decays with distance from the epicentre (km)
IMPACT_RADIUS_KM = {"flood": 120, "cyclone": 250, "earthquake": 150}
# Of affected people: share who become injured / ill
INJURY_RATE = {"flood": 0.010, "cyclone": 0.020, "earthquake": 0.080}
ILLNESS_RATE = {"flood": 0.120, "cyclone": 0.060, "earthquake": 0.040}
# Day on which illness cases (diarrhoeal, respiratory, wound infection) peak
ILLNESS_PEAK_DAY = {"flood": 6, "cyclone": 5, "earthquake": 8}
INJURY_TAU_DAYS = 2.0       # injuries are front-loaded (exponential decay)
ILLNESS_SD_DAYS = 3.0

# Units consumed per injured / ill patient per day (placeholder values)
PER_INJURED = {"antibiotics": 3.0, "ors": 0.0, "iv_fluids": 3.0,
               "analgesics": 4.0, "blood_units": 0.4}
PER_ILL = {"antibiotics": 2.0, "ors": 4.0, "iv_fluids": 2.0,
           "analgesics": 0.5, "blood_units": 0.0}

# Normal (non-disaster) consumption per bed per day, and days of stock held
BASELINE_PER_BED = {"antibiotics": 0.8, "ors": 0.5, "iv_fluids": 0.6,
                    "analgesics": 1.0, "blood_units": 0.05}
STOCK_DAYS_RANGE = {"antibiotics": (7, 22), "ors": (7, 22), "iv_fluids": (7, 22),
                    "analgesics": (7, 22), "blood_units": (6, 12)}

# Risk thresholds on coverage = surge stock / 7-day surge demand
HIGH_BELOW, MEDIUM_BELOW = 0.5, 2.0   # conservative: <2x cover is not 'Low'
DEMAND_NOISE_SIGMA = 0.20   # lognormal noise on daily demand
# ===========================================================================


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_regions(path):
    if path:
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(DEFAULT_REGIONS,
                          columns=["region", "lat", "lon", "population", "beds"])
    df.insert(0, "region_id", range(len(df)))
    return df


def epidemic_curves(kind, days):
    t = np.arange(days)
    inj = np.exp(-t / INJURY_TAU_DAYS)
    inj /= inj.sum()
    ill = np.exp(-((t - ILLNESS_PEAK_DAY[kind]) ** 2) / (2 * ILLNESS_SD_DAYS ** 2))
    ill /= ill.sum()
    return inj, ill


def make_scenarios(n, regions, rng):
    lat_lo, lat_hi = regions["lat"].min() - 1, regions["lat"].max() + 1
    lon_lo, lon_hi = regions["lon"].min() - 1, regions["lon"].max() + 1
    rows = []
    for i in range(n):
        kind = rng.choice(DISASTERS, p=DISASTER_PROB)
        sev = int(rng.choice([1, 2, 3, 4, 5], p=SEVERITY_PROB))
        month = int(rng.integers(1, 13))
        # hazard intensity proxy tied to severity (what a real model would see)
        if kind == "flood":
            intensity = 80 + 60 * sev + rng.normal(0, 15)      # rainfall mm / day
        elif kind == "cyclone":
            intensity = 60 + 35 * sev + rng.normal(0, 8)       # wind km/h
        else:
            intensity = 4.5 + 0.6 * sev + rng.normal(0, 0.15)  # magnitude
        rows.append(dict(scenario_id=i, disaster_type=kind, severity=sev, month=month,
                         hazard_intensity=round(float(intensity), 2),
                         epi_lat=rng.uniform(lat_lo, lat_hi),
                         epi_lon=rng.uniform(lon_lo, lon_hi)))
    return pd.DataFrame(rows)


def simulate(scenarios, regions, rng):
    demand_rows, ds_rows = [], []
    base_stock = {}
    for _, rg in regions.iterrows():            # pre-disaster stock, fixed per region
        for m in MEDICINES:
            lo, hi = STOCK_DAYS_RANGE[m]
            days = rng.uniform(lo, hi)
            base_stock[(rg.region_id, m)] = rg.beds * BASELINE_PER_BED[m] * days

    for _, sc in scenarios.iterrows():
        kind = sc.disaster_type
        inj_curve, ill_curve = epidemic_curves(kind, HORIZON_DAYS)
        for _, rg in regions.iterrows():
            dist = float(haversine(sc.epi_lat, sc.epi_lon, rg.lat, rg.lon))
            frac = AFFECTED_FRAC[sc.severity] * np.exp(-dist / IMPACT_RADIUS_KM[kind])
            affected = rg.population * min(frac, 0.6)
            injured = affected * INJURY_RATE[kind]
            ill = affected * ILLNESS_RATE[kind]
            # stock varies a little per scenario (ongoing consumption / restocking)
            for m in MEDICINES:
                clean = (injured * inj_curve * PER_INJURED[m]
                         + ill * ill_curve * PER_ILL[m])
                noisy = clean * rng.lognormal(0, DEMAND_NOISE_SIGMA, HORIZON_DAYS)
                for d in range(HORIZON_DAYS):
                    demand_rows.append((sc.scenario_id, rg.region_id, m, d, noisy[d]))

                stock = base_stock[(rg.region_id, m)] * rng.uniform(0.85, 1.15)
                normal_use_7d = rg.beds * BASELINE_PER_BED[m] * 7
                surge_stock = max(stock - normal_use_7d, 0.0)  # what is spare for surge
                demand_7d = float(noisy[:7].sum())
                shortage = max(demand_7d - surge_stock, 0.0)
                coverage = surge_stock / demand_7d if demand_7d > 0 else np.inf
                if demand_7d < 1e-6 or coverage >= MEDIUM_BELOW:
                    risk = "Low"
                elif coverage >= HIGH_BELOW:
                    risk = "Medium"
                else:
                    risk = "High"
                ds_rows.append(dict(
                    scenario_id=sc.scenario_id, region_id=rg.region_id, medicine=m,
                    disaster_type=kind, severity=sc.severity, month=sc.month,
                    hazard_intensity=sc.hazard_intensity, distance_km=round(dist, 1),
                    population=rg.population, beds=rg.beds,
                    affected_pop=round(affected), injured=round(injured),
                    ill=round(ill), stock_units=round(stock, 1),
                    demand_7d=round(demand_7d, 1), shortage_qty=round(shortage, 1),
                    coverage_ratio=round(min(coverage, 99), 3), risk_level=risk))
    demand = pd.DataFrame(demand_rows,
                          columns=["scenario_id", "region_id", "medicine", "day",
                                   "demand_units"])
    demand["demand_units"] = demand["demand_units"].round(2)
    return demand, pd.DataFrame(ds_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-scenarios", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--regions", default=None, help="CSV: region,lat,lon,population,beds")
    ap.add_argument("--out", default="data/synthetic")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    regions = load_regions(a.regions)
    scenarios = make_scenarios(a.n_scenarios, regions, rng)
    demand, shortage = simulate(scenarios, regions, rng)

    dist = pd.DataFrame(
        [[float(haversine(r1.lat, r1.lon, r2.lat, r2.lon)) for _, r2 in regions.iterrows()]
         for _, r1 in regions.iterrows()],
        index=regions.region, columns=regions.region).round(1)

    regions.to_csv(out / "regions.csv", index=False)
    dist.to_csv(out / "region_distances.csv")
    scenarios.to_csv(out / "scenarios.csv", index=False)
    demand.to_csv(out / "demand_daily.csv", index=False)
    shortage.to_csv(out / "shortage_dataset.csv", index=False)

    print(f"Wrote {out}/  ({len(scenarios)} scenarios, {len(regions)} regions)")
    print("\nRisk-level balance (aim for a usable spread, not 95% Low):")
    print(shortage["risk_level"].value_counts(normalize=True).round(3).to_string())
    print("\nBy disaster type:")
    print(pd.crosstab(shortage["disaster_type"], shortage["risk_level"],
                      normalize="index").round(2).to_string())


if __name__ == "__main__":
    main()
