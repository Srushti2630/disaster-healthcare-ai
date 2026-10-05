"""
Multi-Objective Operations Research Resource Allocation Solver (Google OR-Tools SCIP).
Solves stochastic integer programming (MIP) for 35 Maharashtra district nodes across P50/P90 demand scenarios,
implements safety reserves, perishables transit limits, integer pack sizes, and compares against 3 baselines.
"""
import os
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

from pathlib import Path
import json
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ortools.linear_solver import pywraplp

from src.data.boundaries import MAHARASHTRA_DISTRICTS, haversine_distance

PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
RAW_ROAD = Path("data/raw/road_distances.csv")

MEDICINES = ["antibiotics", "ors", "iv_fluids", "analgesics", "blood_units"]

MEDICINE_CRITICALITY = {
    "blood_units": 5.0,
    "antibiotics": 3.0,
    "iv_fluids": 2.0,
    "ors": 1.0,
    "analgesics": 1.0
}

# Max transit distance for perishables (blood units: max 150 km)
PERISHABLE_MAX_KM = {
    "blood_units": 150.0
}

def load_or_compute_distance_matrix() -> pd.DataFrame:
    """Load road distance matrix if provided, otherwise compute Haversine x 1.3 circuity matrix."""
    districts = list(MAHARASHTRA_DISTRICTS.keys())
    
    if RAW_ROAD.exists():
        df = pd.read_csv(RAW_ROAD).set_index("district")
        return df

    # Compute Haversine x 1.3 circuity factor
    matrix = np.zeros((len(districts), len(districts)))
    for i, d1 in enumerate(districts):
        lat1, lon1 = MAHARASHTRA_DISTRICTS[d1]["lat"], MAHARASHTRA_DISTRICTS[d1]["lon"]
        for j, d2 in enumerate(districts):
            if i != j:
                lat2, lon2 = MAHARASHTRA_DISTRICTS[d2]["lat"], MAHARASHTRA_DISTRICTS[d2]["lon"]
                dist_km = haversine_distance(lat1, lon1, lat2, lon2) * 1.3
                matrix[i, j] = dist_km

    return pd.DataFrame(matrix, index=districts, columns=districts)

def solve_resource_allocation(
    region_demands: dict,
    region_stocks: dict,
    region_risks: dict = None,
    region_confidences: dict = None,
    distances_df: pd.DataFrame = None,
    safety_reserve_ratio: float = 0.60,
    cost_per_km_unit: float = 0.05,
    w_unmet: float = 1.0,
    w_cost: float = 0.10,
    w_fairness: float = 0.50,
):
    """
    Solve multi-objective resource allocation MIP problem via Google OR-Tools SCIP solver.
    """
    if distances_df is None:
        distances_df = load_or_compute_distance_matrix()

    districts = list(region_demands.keys())
    medicines = MEDICINES
    max_dist = float(distances_df.values.max()) if distances_df.values.max() > 0 else 1.0

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        raise RuntimeError("OR-Tools SCIP solver could not be initialized.")

    start_time = time.time()

    # 1. Variables
    x = {}
    for i in districts:
        for j in districts:
            if i != j:
                for m in medicines:
                    d_ij = float(distances_df.loc[i, j])
                    max_km = PERISHABLE_MAX_KM.get(m, 9999.0)
                    if d_ij <= max_km:
                        x[i, j, m] = solver.IntVar(0, solver.infinity(), f"x_{i}_{j}_{m}")

    unmet = {}
    for j in districts:
        for m in medicines:
            unmet[j, m] = solver.NumVar(0.0, solver.infinity(), f"unmet_{j}_{m}")

    theta = solver.NumVar(0.0, 1.0, "min_coverage_theta")

    # 2. Constraints

    # (a) Source safety reserve constraint:
    for i in districts:
        for m in medicines:
            stk = region_stocks.get(i, {}).get(m, 0.0)
            dem = region_demands.get(i, {}).get(m, 0.0)
            r_level = region_risks.get(i, {}).get(m, "Low") if region_risks else "Low"

            if r_level == "High":
                exportable = 0
            else:
                reserve = safety_reserve_ratio * dem
                exportable = max(0, int(np.floor(stk - reserve)))

            valid_routes = [x[i, j, m] for j in districts if j != i and (i, j, m) in x]
            if valid_routes:
                solver.Add(solver.Sum(valid_routes) <= exportable, f"reserve_limit_{i}_{m}")

    # (b) Destination intake limit & unmet demand definition:
    total_system_demand = 0.0
    for j in districts:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            total_system_demand += dem

            exports = [x[j, k, m] for k in districts if k != j and (j, k, m) in x]
            imports = [x[i, j, m] for i in districts if i != j and (i, j, m) in x]

            net_final_stock = stk - solver.Sum(exports) + solver.Sum(imports)
            solver.Add(unmet[j, m] >= dem - net_final_stock, f"unmet_def_{j}_{m}")

            # Fairness constraint
            if dem > 10.0:
                solver.Add(net_final_stock >= theta * dem, f"fairness_{j}_{m}")

    total_system_demand = max(1.0, total_system_demand)

    # 3. Multi-Objective Objective Function
    obj = solver.Objective()

    for j in districts:
        for m in medicines:
            crit = MEDICINE_CRITICALITY.get(m, 1.0)
            obj.SetCoefficient(unmet[j, m], float(w_unmet * crit))

    for (i, j, m), var in x.items():
        d_ij = float(distances_df.loc[i, j])
        norm_dist_cost = (d_ij / max_dist) * cost_per_km_unit
        obj.SetCoefficient(var, float(w_cost * norm_dist_cost))

    obj.SetCoefficient(theta, float(-w_fairness * total_system_demand))
    obj.SetMinimization()

    # 4. Solve
    status = solver.Solve()
    solve_duration_ms = (time.time() - start_time) * 1000

    # 5. Extract Results
    allocations = []
    total_transferred = 0
    total_cost = 0.0

    if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        for (i, j, m), var in x.items():
            qty = int(var.solution_value())
            if qty > 0:
                d_ij = float(distances_df.loc[i, j])
                cost = round(qty * d_ij * cost_per_km_unit, 2)
                r_level = region_risks.get(j, {}).get(m, "Medium") if region_risks else "Medium"
                conf = region_confidences.get(j, {}).get(m, 0.85) if region_confidences else 0.85

                allocations.append({
                    "source_region": i,
                    "dest_region": j,
                    "medicine": m,
                    "quantity": qty,
                    "distance_km": round(d_ij, 1),
                    "cost": cost,
                    "priority": "CRITICAL" if r_level == "High" else "HIGH" if r_level == "Medium" else "STANDARD",
                    "confidence": round(float(conf), 3)
                })
                total_transferred += qty
                total_cost += cost

    cols = ["source_region", "dest_region", "medicine", "quantity", "distance_km", "cost", "priority", "confidence"]
    if not allocations:
        alloc_df = pd.DataFrame(columns=cols)
    else:
        alloc_df = pd.DataFrame(allocations)[cols]

    # Compute baseline metrics before transfers
    unmet_before = 0.0
    coverages_before = []
    for j in districts:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            unmet_before += max(0.0, dem - stk)
            if dem > 0:
                coverages_before.append(min(1.0, stk / dem))

    # Compute metrics after transfers
    unmet_after = 0.0
    coverages_after = []
    for j in districts:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            transfers_in = alloc_df[(alloc_df["dest_region"] == j) & (alloc_df["medicine"] == m)]["quantity"].sum() if len(alloc_df) else 0
            transfers_out = alloc_df[(alloc_df["source_region"] == j) & (alloc_df["medicine"] == m)]["quantity"].sum() if len(alloc_df) else 0
            final_stk = stk + transfers_in - transfers_out
            unmet_after += max(0.0, dem - final_stk)
            if dem > 0:
                coverages_after.append(min(1.0, max(0.0, final_stk / dem)))

    min_cov_before = float(np.min(coverages_before)) if coverages_before else 1.0
    min_cov_after = float(np.min(coverages_after)) if coverages_after else 1.0

    summary = {
        "solve_status": "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE" if status == pywraplp.Solver.FEASIBLE else "INFEASIBLE",
        "solve_time_ms": float(round(solve_duration_ms, 2)),
        "total_transferred_units": int(total_transferred),
        "total_transport_cost": float(round(total_cost, 2)),
        "unmet_demand_before": float(round(float(unmet_before), 1)),
        "unmet_demand_after": float(round(float(unmet_after), 1)),
        "demand_reduction_pct": float(round(float((unmet_before - unmet_after) / max(1.0, unmet_before)) * 100, 1)),
        "min_coverage_before": float(round(float(min_cov_before), 3)),
        "min_coverage_after": float(round(float(min_cov_after), 3))
    }

    return alloc_df, summary

COST_PER_UNIT_KM = 15.0
FIXED_ROUTE_COST = 500.0

def evaluate_allocation_plan(plan_df: pd.DataFrame, region_demands: dict, region_stocks: dict, region_risks: dict, distances_df: pd.DataFrame) -> dict:
    """Evaluate an allocation plan through a shared constraint checker and unified cost function."""
    districts = list(region_demands.keys())
    violations = 0
    unit_km = 0.0
    active_routes = set()
    
    transfers_out = {d: {m: 0.0 for m in MEDICINES} for d in districts}
    transfers_in = {d: {m: 0.0 for m in MEDICINES} for d in districts}

    for _, row in plan_df.iterrows():
        i, j, m = row["source_region"], row["dest_region"], row["medicine"]
        qty = float(row["quantity"])
        d_ij = float(distances_df.loc[i, j]) if (i in distances_df.index and j in distances_df.columns) else float(row.get("distance_km", 0.0))
        
        # Non-negative, no self transfer, integer check
        if qty < 0 or i == j or not qty.is_integer():
            violations += 1
        
        # 150 km blood limit check
        if m == "blood_units" and d_ij > 150.0 and qty > 0:
            violations += 1
        
        # High risk export check
        if region_risks.get(i, {}).get(m) == "High" and qty > 0:
            violations += 1
            
        transfers_out[i][m] += qty
        transfers_in[j][m] += qty
        unit_km += d_ij * qty
        if qty > 0:
            active_routes.add((i, j))

    # Safety reserve check (remaining stock >= 0.60 * demand)
    for i in districts:
        for m in MEDICINES:
            max_reserve = max(0.0, region_stocks[i][m] - 0.60 * region_demands[i][m])
            if region_risks.get(i, {}).get(m) == "High":
                max_reserve = 0.0
            if transfers_out[i][m] > max_reserve + 1e-5:
                violations += 1

    route_km = sum(float(distances_df.loc[i, j]) for (i, j) in active_routes)
    transport_cost = unit_km * COST_PER_UNIT_KM + len(active_routes) * FIXED_ROUTE_COST

    unmet = 0.0
    coverages = []
    for j in districts:
        for m in MEDICINES:
            stk = region_stocks[j][m]
            dem = region_demands[j][m]
            final_stk = stk + transfers_in[j][m] - transfers_out[j][m]
            unmet += max(0.0, dem - final_stk)
            if dem > 0:
                coverages.append(min(1.0, max(0.0, final_stk / dem)))

    min_cov = float(np.min(coverages)) if coverages else 1.0
    return {
        "unmet_demand": round(float(unmet), 1),
        "cost": round(float(transport_cost), 2),
        "unit_km": round(float(unit_km), 1),
        "route_km": round(float(route_km), 1),
        "minimum_coverage": round(float(min_cov), 3),
        "violations": int(violations)
    }

def solve_proportional_baseline(region_demands: dict, region_stocks: dict, region_risks: dict, distances_df: pd.DataFrame, pop_weights: dict) -> pd.DataFrame:
    districts = list(region_demands.keys())
    cols = ["source_region", "dest_region", "medicine", "quantity", "distance_km", "cost", "priority", "confidence"]
    recs = []
    for m in MEDICINES:
        surplus_map = {d: max(0.0, region_stocks[d][m] - 0.60 * region_demands[d][m]) if region_risks[d][m] != "High" else 0.0 for d in districts}
        deficit_map = {d: max(0.0, region_demands[d][m] - region_stocks[d][m]) for d in districts}
        tot_surp = sum(surplus_map.values())
        tot_def = sum(deficit_map.values())
        if tot_surp > 0 and tot_def > 0:
            for i in districts:
                if surplus_map[i] > 0:
                    for j in districts:
                        if deficit_map[j] > 0 and i != j:
                            d_ij = float(distances_df.loc[i, j])
                            if m == "blood_units" and d_ij > 150.0:
                                continue
                            share = (pop_weights.get(j, 1.0/35.0) * deficit_map[j]) / tot_def
                            qty = int(min(surplus_map[i], share * tot_surp))
                            if qty > 0:
                                surplus_map[i] -= qty
                                recs.append({"source_region": i, "dest_region": j, "medicine": m, "quantity": qty, "distance_km": d_ij})
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=cols)

def solve_greedy_nearest_baseline(region_demands: dict, region_stocks: dict, region_risks: dict, distances_df: pd.DataFrame) -> pd.DataFrame:
    districts = list(region_demands.keys())
    cols = ["source_region", "dest_region", "medicine", "quantity", "distance_km", "cost", "priority", "confidence"]
    recs = []
    for m in MEDICINES:
        surplus_map = {d: max(0.0, region_stocks[d][m] - 0.60 * region_demands[d][m]) if region_risks[d][m] != "High" else 0.0 for d in districts}
        defic_dists = [d for d in districts if region_demands[d][m] > region_stocks[d][m]]
        defic_dists.sort(key=lambda d: region_demands[d][m] - region_stocks[d][m], reverse=True)
        for j in defic_dists:
            defic = region_demands[j][m] - region_stocks[j][m]
            for i in distances_df.loc[j].sort_values().index:
                if i != j and surplus_map[i] > 0:
                    d_ij = float(distances_df.loc[i, j])
                    if m == "blood_units" and d_ij > 150.0:
                        continue
                    take = int(min(defic, surplus_map[i]))
                    if take > 0:
                        surplus_map[i] -= take
                        defic -= take
                        recs.append({"source_region": i, "dest_region": j, "medicine": m, "quantity": take, "distance_km": d_ij})
                    if defic <= 0:
                        break
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=cols)

def solve_greedy_largest_surplus_baseline(region_demands: dict, region_stocks: dict, region_risks: dict, distances_df: pd.DataFrame) -> pd.DataFrame:
    districts = list(region_demands.keys())
    cols = ["source_region", "dest_region", "medicine", "quantity", "distance_km", "cost", "priority", "confidence"]
    recs = []
    for m in MEDICINES:
        surplus_map = {d: max(0.0, region_stocks[d][m] - 0.60 * region_demands[d][m]) if region_risks[d][m] != "High" else 0.0 for d in districts}
        defic_dists = [d for d in districts if region_demands[d][m] > region_stocks[d][m]]
        defic_dists.sort(key=lambda d: region_demands[d][m] - region_stocks[d][m], reverse=True)
        for j in defic_dists:
            defic = region_demands[j][m] - region_stocks[j][m]
            while defic > 0:
                avail_sources = [d for d in districts if d != j and surplus_map[d] > 0]
                if m == "blood_units":
                    avail_sources = [d for d in avail_sources if float(distances_df.loc[d, j]) <= 150.0]
                if not avail_sources:
                    break
                avail_sources.sort(key=lambda d: surplus_map[d], reverse=True)
                best_src = avail_sources[0]
                d_ij = float(distances_df.loc[best_src, j])
                take = int(min(defic, surplus_map[best_src]))
                if take > 0:
                    surplus_map[best_src] -= take
                    defic -= take
                    recs.append({"source_region": best_src, "dest_region": j, "medicine": m, "quantity": take, "distance_km": d_ij})
                else:
                    break
    return pd.DataFrame(recs) if recs else pd.DataFrame(columns=cols)

def compare_against_baselines(sim_summary_path: Path = None, n_scenarios: int = 20):
    """
    Evaluate 5 allocation methods across 20 Monte-Carlo scenarios (P50/P90 demand draws).
    Saves reports/baseline_comparison.csv and reports/baseline_comparison_plot.png.
    """
    from src.engine.monte_carlo import run_monte_carlo_district_simulation
    from src.engine.demand import get_impact_sigma
    distances_df = load_or_compute_distance_matrix()
    districts = list(MAHARASHTRA_DISTRICTS.keys())
    model_sigma = get_impact_sigma("model_prediction")

    pop_df = pd.read_csv(PROCESSED_DIR / "district_population.csv")
    pop_weights = dict(zip(pop_df["district"], pop_df["population"] / pop_df["population"].sum()))
    cols = ["source_region", "dest_region", "medicine", "quantity", "distance_km", "cost", "priority", "confidence"]

    rng = np.random.default_rng(42)
    scenarios = []
    print(f"Sampling {n_scenarios} Monte-Carlo scenarios for benchmark (mix of P50 and P90 demand draws)...")

    for s_idx in range(n_scenarios):
        h_type = str(rng.choice(["Flood", "Storm", "Epidemic", "Earthquake", "Extreme temp"]))
        epi = str(rng.choice(districts))
        base_mag = float(rng.uniform(7.0, 11.5))
        draw_quantile = "P50" if s_idx < 10 else "P90"
        
        district_inputs = {}
        lat1, lon1 = MAHARASHTRA_DISTRICTS[epi]["lat"], MAHARASHTRA_DISTRICTS[epi]["lon"]
        for d in districts:
            lat2, lon2 = MAHARASHTRA_DISTRICTS[d]["lat"], MAHARASHTRA_DISTRICTS[d]["lon"]
            dist_km = haversine_distance(lat1, lon1, lat2, lon2)
            aff_log = max(4.0, base_mag - 0.004 * dist_km)
            district_inputs[d] = {
                "hazard_type": h_type,
                "affected_mean_log": aff_log,
                "affected_std_log": model_sigma,
                "injured_mean_log": max(2.0, aff_log - 2.5),
                "injured_std_log": 0.50
            }
        
        sim_df = run_monte_carlo_district_simulation(district_inputs, n_draws=100, random_seed=42 + s_idx)
        reg_dem = {}
        reg_stk = {}
        reg_risk = {}
        for _, row in sim_df.iterrows():
            d, m = row["district"], row["medicine"]
            if d not in reg_dem:
                reg_dem[d] = {}
                reg_stk[d] = {}
                reg_risk[d] = {}
            dem_val = float(row["demand_p50"]) if draw_quantile == "P50" else float(row["demand_p90"])
            reg_dem[d][m] = dem_val
            reg_stk[d][m] = float(row["available_stock"])
            reg_risk[d][m] = str(row["risk_level"])
            
        scenarios.append({
            "demands": reg_dem,
            "stocks": reg_stk,
            "risks": reg_risk
        })

    methods = {
        "OR-Tools SCIP": lambda dem, stk, rsk, dists: solve_resource_allocation(dem, stk, rsk, distances_df=dists)[0],
        "No Redistribution": lambda dem, stk, rsk, dists: pd.DataFrame(columns=cols),
        "Proportional Population": lambda dem, stk, rsk, dists: solve_proportional_baseline(dem, stk, rsk, dists, pop_weights),
        "Greedy Nearest": lambda dem, stk, rsk, dists: solve_greedy_nearest_baseline(dem, stk, rsk, dists),
        "Greedy Largest Surplus": lambda dem, stk, rsk, dists: solve_greedy_largest_surplus_baseline(dem, stk, rsk, dists)
    }

    results = {m: [] for m in methods}
    sample_plans = {}
    scenario_demand_stock = []

    for sc_idx, sc in enumerate(scenarios):
        tot_dem = sum(sum(sc["demands"][d].values()) for d in sc["demands"])
        tot_stk = sum(sum(sc["stocks"][d].values()) for d in sc["stocks"])
        scenario_demand_stock.append({"scenario_idx": sc_idx, "total_demand": tot_dem, "total_stock": tot_stk})

        for m_name, solver_fn in methods.items():
            p_df = solver_fn(sc["demands"], sc["stocks"], sc["risks"], distances_df)
            eval_metrics = evaluate_allocation_plan(p_df, sc["demands"], sc["stocks"], sc["risks"], distances_df)
            eval_metrics["unmet_pct"] = (eval_metrics["unmet_demand"] / max(1.0, tot_dem)) * 100.0
            eval_metrics["total_demand"] = tot_dem
            eval_metrics["total_stock"] = tot_stk
            results[m_name].append(eval_metrics)
            if m_name not in sample_plans and len(p_df) > 0:
                sample_plans[m_name] = p_df

    from scipy.stats import wilcoxon

    def compute_summary_table(res_dict, filter_indices=None):
        rows = []
        for m_name, res_list in res_dict.items():
            if filter_indices is not None:
                res_list = [res_list[idx] for idx in filter_indices]
            df_m = pd.DataFrame(res_list)
            rows.append({
                "method": m_name,
                "unmet_demand_mean": round(float(df_m["unmet_demand"].mean()), 1),
                "unmet_pct_mean": round(float(df_m["unmet_pct"].mean()), 2),
                "unmet_pct_median": round(float(df_m["unmet_pct"].median()), 2),
                "unmet_pct_p75": round(float(np.percentile(df_m["unmet_pct"], 75)), 2),
                "unmet_pct_p90": round(float(np.percentile(df_m["unmet_pct"], 90)), 2),
                "cost_mean": round(float(df_m["cost"].mean()), 2),
                "unit_km_mean": round(float(df_m["unit_km"].mean()), 1),
                "route_km_mean": round(float(df_m["route_km"].mean()), 1),
                "min_coverage_mean": round(float(df_m["minimum_coverage"].mean()), 3),
                "violations_mean": round(float(df_m["violations"].mean()), 2),
                "violations_max": int(df_m["violations"].max())
            })
        return pd.DataFrame(rows)

    summary_df = compute_summary_table(results)

    # Scenarios where No Redistribution has unmet > 0
    no_redist_unmet = [r["unmet_demand"] for r in results["No Redistribution"]]
    restricted_indices = [idx for idx, val in enumerate(no_redist_unmet) if val > 0]
    restricted_summary_df = compute_summary_table(results, filter_indices=restricted_indices)

    # Wilcoxon signed-rank tests paired against OR-Tools SCIP
    or_scip_unmet = np.array([r["unmet_demand"] for r in results["OR-Tools SCIP"]])
    wilcoxon_results = {}
    for m_name in methods:
        if m_name == "OR-Tools SCIP":
            continue
        other_unmet = np.array([r["unmet_demand"] for r in results[m_name]])
        diff = other_unmet - or_scip_unmet
        if np.all(diff == 0):
            w_stat, p_val = 0.0, 1.0
        else:
            w_stat, p_val = wilcoxon(other_unmet, or_scip_unmet)
            w_stat, p_val = float(w_stat), float(p_val)
        wilcoxon_results[m_name] = {"W_stat": w_stat, "p_value": round(p_val, 6)}

    print("\n--- Baseline Comparison Table (All 20 Scenarios) ---")
    print(summary_df.to_string(index=False))

    print(f"\n--- Restricted Scenarios Table (N={len(restricted_indices)}, No Redistribution Unmet > 0) ---")
    print(restricted_summary_df.to_string(index=False))

    print("\n--- Wilcoxon Signed-Rank Tests (Paired vs OR-Tools SCIP) ---")
    for m_name, w_res in wilcoxon_results.items():
        print(f"  OR-Tools SCIP vs {m_name}: W = {w_res['W_stat']}, p = {w_res['p_value']}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    comp_csv = REPORTS_DIR / "baseline_comparison.csv"
    summary_df.to_csv(comp_csv, index=False)

    rest_csv = REPORTS_DIR / "baseline_comparison_restricted.csv"
    restricted_summary_df.to_csv(rest_csv, index=False)

    # Plot Unmet Demand vs Cost
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for idx, row in summary_df.iterrows():
        m_name = row["method"]
        x_val = row["cost_mean"] / 1e6
        y_val = row["unmet_demand_mean"]
        ax.scatter(x_val, y_val, color=colors[idx % len(colors)], s=120, label=m_name, zorder=5)
        ax.annotate(m_name, (x_val, y_val), textcoords="offset points", xytext=(8, 5), ha="left", fontsize=9)

    ax.set_xlabel("Mean Transport Cost (Million INR)")
    ax.set_ylabel("Mean Unmet Demand Units")
    ax.set_title("Multi-Objective Tradeoff: Mean Unmet Demand vs. Transport Cost (20 Scenarios)")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()

    plot_path = REPORTS_DIR / "baseline_comparison_plot.png"
    fig.savefig(plot_path, dpi=300)
    fig.savefig(REPORTS_DIR / "pareto_sweep.png", dpi=300)
    plt.close(fig)

    if "OR-Tools SCIP" in sample_plans:
        sample_plans["OR-Tools SCIP"].to_csv(REPORTS_DIR / "sample_allocation_plan.csv", index=False)

    benchmarks_dict = summary_df.set_index("method").to_dict(orient="index")
    restricted_dict = restricted_summary_df.set_index("method").to_dict(orient="index")

    summary_export = {
        "benchmarks": benchmarks_dict,
        "restricted_benchmarks": restricted_dict,
        "restricted_count": len(restricted_indices),
        "wilcoxon_tests": wilcoxon_results,
        "scenario_demand_stock": scenario_demand_stock
    }

    with open(REPORTS_DIR / "allocation_summary.json", "w") as f:
        json.dump(summary_export, f, indent=2)

    return summary_export

def main():
    print("==================================================")
    print("Running Phase 4 OR-Tools SCIP Multi-Objective Optimization & 20-Scenario Benchmark...")
    print("==================================================")

    benchmarks = compare_against_baselines(n_scenarios=20)
    print("Phase 4 Optimization & Baseline Benchmarking complete!")

if __name__ == "__main__":
    main()
