"""
Monte-Carlo Demand Simulation and Shortage Risk Engine.
Executes 2,000+ stochastic draws sampling (Impact Model Distribution) x (Epidemiological Parameter Ranges),
calculates P10/P50/P90 demand bands per district x medicine, computes exact P(demand > stock),
and assigns Low/Medium/High shortage risk levels.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from src.engine.demand import load_demand_params, estimate_district_stocks, get_impact_sigma
from src.data.boundaries import MAHARASHTRA_DISTRICTS

PROCESSED_DIR = Path("data/processed")

def run_monte_carlo_district_simulation(
    district_impact_predictions: dict,
    district_stocks: dict = None,
    n_draws: int = 2000,
    horizon_days: int = 7,
    random_seed: int = 42
) -> pd.DataFrame:
    """
    Run 2,000+ Monte-Carlo draws for each district and medicine class.
    
    district_impact_predictions: dict of {district_name: {"hazard_type": str, "affected_mean_log": float, "affected_std_log": float, "injured_mean_log": float, "injured_std_log": float}}
    """
    rng = np.random.default_rng(seed=random_seed)
    params = load_demand_params()
    default_sigma = get_impact_sigma("model_prediction")
    
    if district_stocks is None:
        district_stocks = estimate_district_stocks()

    summary_records = []

    for d_name, imp in district_impact_predictions.items():
        h_type = imp.get("hazard_type", "Flood")
        h_info = params["hazard_multipliers"].get(h_type, {"severity_scaling": 1.0})
        scale = h_info["severity_scaling"]
        aff_std = imp.get("affected_std_log", default_sigma)

        # 1. Sample Log-Casualties
        aff_log_draws = rng.normal(imp["affected_mean_log"], aff_std, size=n_draws)
        inj_log_draws = rng.normal(imp.get("injured_mean_log", imp["affected_mean_log"] - 2.0), imp.get("injured_std_log", 0.50), size=n_draws)

        aff_draws = np.expm1(np.clip(aff_log_draws, 0, 16))
        inj_draws = np.expm1(np.clip(inj_log_draws, 0, 14))

        stock_dict = district_stocks.get(d_name, {})

        for med, m_info in params["medicines"].items():
            # 2. Sample Epidemiological Consumption Rates
            if med == "blood_units":
                rate_draws = rng.uniform(m_info["rate_per_injured_day"]["min"], m_info["rate_per_injured_day"]["max"], size=n_draws)
                demand_draws = inj_draws * rate_draws * horizon_days * scale
            else:
                rate_draws = rng.uniform(m_info["rate_per_affected_day"]["min"], m_info["rate_per_affected_day"]["max"], size=n_draws)
                demand_draws = aff_draws * rate_draws * horizon_days * scale

            demand_draws = np.clip(demand_draws, 0, None)
            avail_stock = stock_dict.get(med, 1000.0)

            p10 = float(np.percentile(demand_draws, 10))
            p50 = float(np.percentile(demand_draws, 50))
            p75 = float(np.percentile(demand_draws, 75))
            p90 = float(np.percentile(demand_draws, 90))

            shortage_draws = demand_draws - avail_stock
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
                "hazard_type": h_type,
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
    return summary_df

if __name__ == "__main__":
    # Test simulation across Maharashtra districts
    test_preds = {}
    for idx, d_name in enumerate(MAHARASHTRA_DISTRICTS.keys()):
        test_preds[d_name] = {
            "hazard_type": "Flood" if idx % 2 == 0 else "Storm",
            "affected_mean_log": 9.5 if idx in [0, 4, 16, 24] else 7.0,
            "affected_std_log": 0.40,
            "injured_mean_log": 7.0 if idx in [0, 4, 16, 24] else 4.5,
            "injured_std_log": 0.50
        }

    res_df = run_monte_carlo_district_simulation(test_preds, n_draws=2000)
    print(f"Executed Monte-Carlo simulation for {len(res_df)} district x medicine pairs.")
    print(res_df[["district", "medicine", "demand_p50", "available_stock", "shortage_probability", "risk_level"]].head(10))
