"""
Monte-Carlo Demand Simulation and Shortage Risk Engine.
Executes stochastic draws sampling (Impact Model Distribution) x (Epidemiological Parameter Ranges),
allocates event-level affected population to districts via spatial decay, applies population caps,
calculates P10/P50/P90 demand bands per district x medicine, computes exact P(demand > stock),
and assigns Low/Medium/High shortage risk levels.
"""
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.engine.demand import load_demand_params, estimate_district_stocks, get_impact_sigma
from src.data.boundaries import MAHARASHTRA_DISTRICTS, haversine_distance

PROCESSED_DIR = Path("data/processed")

def load_district_population_df() -> pd.DataFrame:
    """Load district population dataframe from data/processed/district_population.csv or fallback."""
    pop_path = PROCESSED_DIR / "district_population.csv"
    if pop_path.exists():
        return pd.read_csv(pop_path)
    
    # Fallback to MAHARASHTRA_DISTRICTS metadata
    records = []
    tot_weight = sum(info["pop_weight"] for info in MAHARASHTRA_DISTRICTS.values())
    for d_name, info in MAHARASHTRA_DISTRICTS.items():
        pop = int(round((info["pop_weight"] / tot_weight) * 124_500_000))
        records.append({"district": d_name, "population": pop})
    return pd.DataFrame(records)

def compute_spatial_allocation_weights(
    epicentre: str = "Pune",
    decay_km: float = 150.0,
    pop_df: pd.DataFrame = None
) -> Dict[str, float]:
    """
    Compute spatial allocation weights for each district:
    weight = population * exp(-distance_to_epicentre / decay_km)
    Weights sum to 1.0 across all districts.
    """
    if pop_df is None:
        pop_df = load_district_population_df()

    pop_map = dict(zip(pop_df["district"], pop_df["population"]))
    districts = list(MAHARASHTRA_DISTRICTS.keys())

    epi_name = epicentre if epicentre in MAHARASHTRA_DISTRICTS else "Pune"
    lat1, lon1 = MAHARASHTRA_DISTRICTS[epi_name]["lat"], MAHARASHTRA_DISTRICTS[epi_name]["lon"]

    raw_weights = {}
    for d in districts:
        lat2, lon2 = MAHARASHTRA_DISTRICTS[d]["lat"], MAHARASHTRA_DISTRICTS[d]["lon"]
        dist_km = haversine_distance(lat1, lon1, lat2, lon2)
        pop_val = float(pop_map.get(d, 1_000_000))
        decay_factor = np.exp(-dist_km / max(1.0, decay_km))
        raw_weights[d] = pop_val * decay_factor

    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        total_weight = 1.0

    normalized_weights = {d: w / total_weight for d, w in raw_weights.items()}
    return normalized_weights

def run_monte_carlo_district_simulation(
    district_impact_predictions: Optional[dict] = None,
    epicentre: str = "Pune",
    event_affected_mean_log: Optional[float] = None,
    hazard_type: str = "Flood",
    severity: float = 1.0,
    district_stocks: Optional[dict] = None,
    n_draws: int = 2000,
    horizon_days: int = 7,
    random_seed: int = 42,
    decay_km: Optional[float] = None
) -> pd.DataFrame:
    """
    Run Monte-Carlo simulation by sampling ONE event total per draw and allocating spatially to districts.
    
    - Sample ONE event total per draw (lognormal; mean log from impact model / override; sigma = get_impact_sigma("model_prediction"))
    - Allocate to districts via ASSUMED rule: population * exp(-distance / decay_km), normalized so weights sum to 1.
    - District affected = min(allocation, district population).
    - Draws shared across districts and medicines.
    - Injured = sampled fraction of affected.
    """
    params = load_demand_params()
    default_sigma = get_impact_sigma("model_prediction")
    
    if decay_km is None:
        decay_km = float(params.get("spatial_decay_km", 150.0))

    rng = np.random.default_rng(seed=random_seed)

    # Determine event affected mean log
    if event_affected_mean_log is None:
        if district_impact_predictions and isinstance(district_impact_predictions, dict):
            # If district_impact_predictions dict passed, check for explicit epicentre or max mean log
            for d_k, d_v in district_impact_predictions.items():
                if d_v.get("affected_mean_log", 0) > 9.0:
                    epicentre = d_k
                    break
            first_val = next(iter(district_impact_predictions.values()))
            event_affected_mean_log = float(first_val.get("affected_mean_log", 9.5))
            hazard_type = first_val.get("hazard_type", hazard_type)
        else:
            event_affected_mean_log = 9.5

    pop_df = load_district_population_df()
    pop_map = dict(zip(pop_df["district"], pop_df["population"]))
    districts = list(MAHARASHTRA_DISTRICTS.keys())

    if district_stocks is None:
        district_stocks = estimate_district_stocks()

    weights = compute_spatial_allocation_weights(epicentre=epicentre, decay_km=decay_km, pop_df=pop_df)

    h_info = params["hazard_multipliers"].get(hazard_type, {"severity_scaling": 1.0})
    hazard_scale = float(h_info["severity_scaling"]) * float(severity)

    # 1. Sample ONE Event Total per Draw (Shared across all districts & medicines)
    event_log_draws = rng.normal(loc=event_affected_mean_log, scale=default_sigma, size=n_draws)
    event_affected_draws = np.expm1(np.clip(event_log_draws, 0, 18))

    # Sample ONE Injured Fraction per Draw (Shared across all districts)
    inj_frac_draws = rng.uniform(0.02, 0.15, size=n_draws)

    # 2. Sample Epidemiological Consumption Rates per Draw (Shared across all districts)
    rate_draws = {}
    for med, m_info in params["medicines"].items():
        rate_key = "rate_per_injured_day" if med == "blood_units" else "rate_per_affected_day"
        r_min = float(m_info[rate_key]["min"])
        r_max = float(m_info[rate_key]["max"])
        rate_draws[med] = rng.uniform(r_min, r_max, size=n_draws)

    # 3. Allocate to Districts and Apply Population Cap
    summary_records = []
    cap_bound_count = 0
    total_allocations_count = 0

    for d_name in districts:
        w_d = weights[d_name]
        d_pop = float(pop_map.get(d_name, 1_000_000))
        
        # Allocation before capping
        uncapped_alloc = event_affected_draws * w_d
        
        # Cap affected population at district population
        affected_draws = np.minimum(uncapped_alloc, d_pop)
        
        # Track capping frequency
        cap_bound_count += int(np.sum(uncapped_alloc > d_pop))
        total_allocations_count += n_draws

        # Injured population for district
        injured_draws = affected_draws * inj_frac_draws

        stock_dict = district_stocks.get(d_name, {})

        for med in params["medicines"].keys():
            if med == "blood_units":
                demand_draws = injured_draws * rate_draws[med] * horizon_days * hazard_scale
            else:
                demand_draws = affected_draws * rate_draws[med] * horizon_days * hazard_scale

            demand_draws = np.clip(demand_draws, 0, None)
            avail_stock = float(stock_dict.get(med, 1000.0))

            p10 = float(np.percentile(demand_draws, 10))
            p50 = float(np.percentile(demand_draws, 50))
            p75 = float(np.percentile(demand_draws, 75))
            p90 = float(np.percentile(demand_draws, 90))

            p_shortage = float(np.mean(demand_draws > avail_stock))

            if p_shortage < 0.10:
                risk_level = "Low"
            elif p_shortage <= 0.40:
                risk_level = "Medium"
            else:
                risk_level = "High"

            summary_records.append({
                "district": d_name,
                "medicine": med,
                "hazard_type": hazard_type,
                "horizon_days": horizon_days,
                "demand_p10": round(p10, 1),
                "demand_p50": round(p50, 1),
                "demand_p75": round(p75, 1),
                "demand_p90": round(p90, 1),
                "available_stock": round(avail_stock, 1),
                "expected_shortage_qty": round(max(0.0, p50 - avail_stock), 1),
                "shortage_probability": round(p_shortage, 4),
                "risk_level": risk_level,
                "provenance": "ESTIMATED_SIMULATION"
            })

    summary_df = pd.DataFrame(summary_records)
    summary_df.attrs["cap_bound_count"] = cap_bound_count
    summary_df.attrs["total_allocations_count"] = total_allocations_count
    summary_df.attrs["cap_bound_pct"] = round((cap_bound_count / max(1, total_allocations_count)) * 100.0, 2)
    return summary_df

if __name__ == "__main__":
    res_df = run_monte_carlo_district_simulation(n_draws=2000)
    print(f"Executed Monte-Carlo simulation for {len(res_df)} district x medicine pairs.")
    print(f"Population cap bound percentage: {res_df.attrs.get('cap_bound_pct', 0.0)}%")
    print(res_df[["district", "medicine", "demand_p50", "available_stock", "shortage_probability", "risk_level"]].head(10))
