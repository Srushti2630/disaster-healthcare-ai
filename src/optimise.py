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

CLEAN_DIR = Path("data/processed/clean")
REPORTS_DIR = Path("reports")
MEDICINES = ["antibiotics", "ors", "iv_fluids", "analgesics", "blood_units"]


def load_distance_matrix():
    """Load and format pairwise distance matrix between regions."""
    dist_path = CLEAN_DIR / "region_distances_clean.csv"
    if not dist_path.exists():
        dist_path = Path("data/synthetic/region_distances.csv")
    df = pd.read_csv(dist_path).set_index("region")
    return df


def solve_resource_allocation(
    region_demands: dict,
    region_stocks: dict,
    region_risks: dict,
    region_confidences: dict,
    distances_df: pd.DataFrame,
    safety_reserve_ratio: float = 0.60,
    cost_per_km_unit: float = 0.05,
    w_unmet: float = 1.0,
    w_cost: float = 0.10,
    w_fairness: float = 0.50,
):
    """
    Solve multi-objective stock transfer problem via Mixed-Integer Programming (SCIP).

    Parameters:
    -----------
    region_demands : dict {region: {medicine: float}}
    region_stocks : dict {region: {medicine: float}}
    region_risks : dict {region: {medicine: str ('Low'|'Medium'|'High')}}
    region_confidences : dict {region: {medicine: float}}
    distances_df : pd.DataFrame (pairwise km)
    safety_reserve_ratio : fraction of predicted demand a source MUST keep for itself
    cost_per_km_unit : transport cost multiplier per unit per km
    w_unmet : weight for minimizing unmet demand
    w_cost : weight for minimizing transport cost
    w_fairness : weight for maximizing minimum coverage ratio across regions
    """
    regions = list(region_demands.keys())
    medicines = MEDICINES
    max_dist = float(distances_df.values.max()) if distances_df.values.max() > 0 else 1.0

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        raise RuntimeError("OR-Tools SCIP solver could not be initialized.")

    start_time = time.time()

    # 1. Variables
    # x[i, j, m]: integer units of medicine m moved from region i to region j (i != j)
    x = {}
    for i in regions:
        for j in regions:
            if i != j:
                for m in medicines:
                    x[i, j, m] = solver.IntVar(0, solver.infinity(), f"x_{i}_{j}_{m}")

    # unmet[j, m]: unmet demand at destination j for medicine m
    unmet = {}
    for j in regions:
        for m in medicines:
            unmet[j, m] = solver.NumVar(0.0, solver.infinity(), f"unmet_{j}_{m}")

    # theta: minimum coverage ratio across all (region, medicine) with demand > 0
    theta = solver.NumVar(0.0, 1.0, "min_coverage_theta")

    # 2. Constraints

    # (a) Source supply limit with safety reserve:
    # A source cannot export units beyond (stock - reserve * demand)
    for i in regions:
        for m in medicines:
            stk = region_stocks.get(i, {}).get(m, 0.0)
            dem = region_demands.get(i, {}).get(m, 0.0)
            reserve = safety_reserve_ratio * dem
            exportable = max(0, int(np.floor(stk - reserve)))
            solver.Add(
                solver.Sum([x[i, j, m] for j in regions if j != i]) <= exportable,
                f"reserve_limit_{i}_{m}"
            )

    # (b) Destination intake limit: transfers into j should not exceed deficit
    for j in regions:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            deficit = max(0, int(np.ceil(dem - stk)))
            solver.Add(
                solver.Sum([x[i, j, m] for i in regions if i != j]) <= deficit,
                f"intake_limit_{j}_{m}"
            )

    # (c) Net inventory & unmet demand definition:
    # Final stock A[j, m] = S[j, m] - exports + imports
    # unmet[j, m] >= D[j, m] - A[j, m]
    total_system_demand = 0.0
    for j in regions:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            total_system_demand += dem

            net_final_stock = (
                stk
                - solver.Sum([x[j, k, m] for k in regions if k != j])
                + solver.Sum([x[i, j, m] for i in regions if i != j])
            )
            solver.Add(unmet[j, m] >= dem - net_final_stock, f"unmet_def_{j}_{m}")

            # Fairness constraint: A[j, m] >= theta * dem
            if dem > 10.0:  # Enforce fairness on non-trivial demand
                solver.Add(net_final_stock >= theta * dem, f"fairness_coverage_{j}_{m}")

    total_system_demand = max(1.0, total_system_demand)

    # 3. Multi-Objective Function
    # Min: w_unmet * sum(unmet) + w_cost * sum(dist/max_dist * x) - w_fairness * (theta * total_demand)
    obj = solver.Objective()

    for j in regions:
        for m in medicines:
            obj.SetCoefficient(unmet[j, m], float(w_unmet))

    for i in regions:
        for j in regions:
            if i != j:
                d_ij = float(distances_df.loc[i, j])
                norm_dist_cost = (d_ij / max_dist) * cost_per_km_unit
                for m in medicines:
                    obj.SetCoefficient(x[i, j, m], float(w_cost * norm_dist_cost))

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
        for i in regions:
            for j in regions:
                if i != j:
                    d_ij = float(distances_df.loc[i, j])
                    for m in medicines:
                        qty = int(x[i, j, m].solution_value())
                        if qty > 0:
                            cost = round(qty * d_ij * cost_per_km_unit, 2)
                            risk = region_risks.get(j, {}).get(m, "Medium")
                            conf = region_confidences.get(j, {}).get(m, 0.85)

                            priority = "CRITICAL" if risk == "High" else "HIGH" if risk == "Medium" else "STANDARD"

                            allocations.append({
                                "source_region": i,
                                "dest_region": j,
                                "medicine": m,
                                "quantity": qty,
                                "distance_km": round(d_ij, 1),
                                "cost": cost,
                                "priority": priority,
                                "confidence": round(float(conf), 3),
                            })
                            total_transferred += qty
                            total_cost += cost

    alloc_df = pd.DataFrame(allocations)

    # Compute baseline metrics before transfers
    unmet_before = 0.0
    coverages_before = []
    for j in regions:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            unmet_before += max(0.0, dem - stk)
            if dem > 0:
                coverages_before.append(min(1.0, stk / dem))

    # Compute metrics after transfers
    unmet_after = 0.0
    coverages_after = []
    for j in regions:
        for m in medicines:
            stk = region_stocks.get(j, {}).get(m, 0.0)
            dem = region_demands.get(j, {}).get(m, 0.0)
            # Add net transfer
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
        "min_coverage_after": float(round(float(min_cov_after), 3)),
    }

    return alloc_df, summary


def run_pareto_sweep(
    region_demands: dict,
    region_stocks: dict,
    region_risks: dict,
    region_confidences: dict,
    distances_df: pd.DataFrame,
    safety_reserve_ratio: float = 0.60,
):
    """
    Run Pareto frontier sweep across 6 objective weight configurations.
    Saves trade-off curves to reports/pareto_sweep.png.
    """
    configs = [
        {"name": "1. Pure Demand Priority", "w_unmet": 2.0, "w_cost": 0.01, "w_fairness": 0.0},
        {"name": "2. High Urgency", "w_unmet": 1.5, "w_cost": 0.05, "w_fairness": 0.2},
        {"name": "3. Balanced Standard", "w_unmet": 1.0, "w_cost": 0.10, "w_fairness": 0.5},
        {"name": "4. Fair Distribution", "w_unmet": 0.8, "w_cost": 0.10, "w_fairness": 1.5},
        {"name": "5. Cost-Conscious", "w_unmet": 0.6, "w_cost": 0.50, "w_fairness": 0.3},
        {"name": "6. Maximum Fairness", "w_unmet": 0.5, "w_cost": 0.05, "w_fairness": 2.5},
    ]

    sweep_results = []
    for cfg in configs:
        alloc_df, summary = solve_resource_allocation(
            region_demands=region_demands,
            region_stocks=region_stocks,
            region_risks=region_risks,
            region_confidences=region_confidences,
            distances_df=distances_df,
            safety_reserve_ratio=safety_reserve_ratio,
            w_unmet=cfg["w_unmet"],
            w_cost=cfg["w_cost"],
            w_fairness=cfg["w_fairness"],
        )
        sweep_results.append({
            "name": cfg["name"],
            "w_unmet": cfg["w_unmet"],
            "w_cost": cfg["w_cost"],
            "w_fairness": cfg["w_fairness"],
            "unmet_demand": summary["unmet_demand_after"],
            "transport_cost": summary["total_transport_cost"],
            "min_coverage": summary["min_coverage_after"],
            "transferred_units": summary["total_transferred_units"],
        })

    pareto_df = pd.DataFrame(sweep_results)

    # Plot Pareto Sweep
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Panel 1: Unmet Demand vs Transport Cost
    scatter1 = axes[0].scatter(
        pareto_df["transport_cost"],
        pareto_df["unmet_demand"],
        c=pareto_df["min_coverage"],
        cmap="viridis",
        s=140,
        edgecolor="black",
        zorder=3,
    )
    for _, row in pareto_df.iterrows():
        axes[0].annotate(
            row["name"].split(". ")[1],
            (row["transport_cost"], row["unmet_demand"]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
            weight="bold",
        )
    cbar1 = plt.colorbar(scatter1, ax=axes[0])
    cbar1.set_label("Min Regional Coverage Ratio", rotation=270, labelpad=15)
    axes[0].set_xlabel("Total Transport Cost (₹ / arb units)")
    axes[0].set_ylabel("Unmet Healthcare Demand (units)")
    axes[0].set_title("Pareto Trade-Off: Unmet Demand vs Transport Cost")
    axes[0].grid(True, alpha=0.3)

    # Panel 2: Minimum Coverage vs Transport Cost
    axes[1].bar(
        pareto_df["name"],
        pareto_df["min_coverage"],
        color="teal",
        alpha=0.85,
        edgecolor="black"
    )
    axes[1].set_ylabel("Minimum Regional Coverage Ratio")
    axes[1].set_title("Fairness Performance Across Weight Settings")
    axes[1].set_xticks(range(len(pareto_df)))
    axes[1].set_xticklabels(
        [n.split(". ")[1] for n in pareto_df["name"]],
        rotation=30,
        ha="right",
        fontsize=9
    )
    axes[1].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    sweep_plot_path = REPORTS_DIR / "pareto_sweep.png"
    plt.savefig(sweep_plot_path, dpi=150)
    plt.close()

    print(f"✓ Saved Pareto sweep figure to {sweep_plot_path}.")
    return pareto_df


def main():
    print("Beginning Stage 3: Multi-Objective Resource Allocation Optimization...")
    distances_df = load_distance_matrix()

    # Load clean shortage dataset to select an illustrative disaster scenario
    short_df = pd.read_csv(CLEAN_DIR / "shortage_dataset_clean.csv")
    region_df = pd.read_csv(CLEAN_DIR / "regions_clean.csv")
    region_id_to_name = dict(zip(region_df["region_id"], region_df["region"]))

    # Pick an acute high-shortage scenario (e.g. Scenario 4)
    sample_scenario_id = 4 if 4 in short_df["scenario_id"].values else int(short_df["scenario_id"].iloc[0])
    scen_data = short_df[short_df["scenario_id"] == sample_scenario_id].copy()

    region_demands = {}
    region_stocks = {}
    region_risks = {}
    region_confidences = {}

    for _, row in scen_data.iterrows():
        reg_name = region_id_to_name[row["region_id"]]
        med = row["medicine"]
        if reg_name not in region_demands:
            region_demands[reg_name] = {}
            region_stocks[reg_name] = {}
            region_risks[reg_name] = {}
            region_confidences[reg_name] = {}

        region_demands[reg_name][med] = float(row["demand_7d"])
        region_stocks[reg_name][med] = float(row["stock_units"])
        region_risks[reg_name][med] = str(row["risk_level"])
        # High confidence for demonstration
        region_confidences[reg_name][med] = 0.92 if row["risk_level"] == "High" else 0.85

    print(f"Running optimization for Disaster Scenario #{sample_scenario_id} ({scen_data['disaster_type'].iloc[0].upper()}, Severity {scen_data['severity'].iloc[0]})...")

    # 1. Base Balanced Allocation
    alloc_df, summary = solve_resource_allocation(
        region_demands=region_demands,
        region_stocks=region_stocks,
        region_risks=region_risks,
        region_confidences=region_confidences,
        distances_df=distances_df,
        safety_reserve_ratio=0.60,
    )

    print("\nBalanced Optimization Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print(f"\nTop Recommended Transfers ({len(alloc_df)} total):")
    if len(alloc_df) > 0:
        print(alloc_df.head(6).to_string(index=False))

    # Save allocation plan
    alloc_plan_path = REPORTS_DIR / "sample_allocation_plan.csv"
    alloc_df.to_csv(alloc_plan_path, index=False)
    print(f"\n✓ Saved allocation plan to {alloc_plan_path}.")

    # 2. Run Pareto Sweep
    pareto_df = run_pareto_sweep(
        region_demands=region_demands,
        region_stocks=region_stocks,
        region_risks=region_risks,
        region_confidences=region_confidences,
        distances_df=distances_df,
        safety_reserve_ratio=0.60,
    )

    summary_file = REPORTS_DIR / "allocation_summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "scenario_id": int(sample_scenario_id),
            "disaster_type": str(scen_data['disaster_type'].iloc[0]),
            "severity": int(scen_data['severity'].iloc[0]),
            "balanced_summary": summary,
            "pareto_sweep": pareto_df.to_dict(orient="records"),
        }, f, indent=2)
    print(f"✓ Saved allocation summary to {summary_file}.")
    print("Stage 3 completed successfully.")


if __name__ == "__main__":
    main()
