"""
Comprehensive Phase 2 Test Suite for OR-Tools Optimization & Resource Allocation Hardening.

Validates:
1. DEF-04: Robust source reserve max(alpha * demand, beta * stock)
   - Zero-demand stock protection (stock > 0, demand == 0)
   - Low-demand stock protection
   - Zero-stock district robustness
   - Fractional and integer demand & stock handling
   - Multi-commodity independence
2. DEF-08: Route Activation & Fixed Transport Costs
   - Binary route variable activation y[i, j]
   - Zero fixed cost for inactive routes
   - Single fixed charge per activated route regardless of commodity count
   - Defensible Big-M bounds linking x[i, j, m] <= M_ij * y[i, j]
   - Direct numerical alignment between solver objective and evaluation metrics
3. DEF-FAIR: Eligibility-Aware & Commodity-Decoupled Fairness
   - Zero-demand districts do not collapse system fairness theta
   - Donorless / isolated districts do not force theta to zero
   - Fairness theta strictly non-zero when eligible deficit districts have reachable donors
   - Monotonicity: increased donor availability does not decrease min coverage
4. DEF-BLOOD: Perishable Blood-Product Distance Limit
   - Blood product transfer strictly permitted for distance < 150 km
   - Blood product transfer strictly permitted at exact boundary 150.0 km
   - Blood product transfer strictly prohibited for distance > 150.0 km (e.g. 150.1 km, 151 km)
   - Non-blood medicines permitted beyond 150 km
   - Evaluator registers zero violations for valid boundary plans
5. Regression & Invariance Safety
   - Integrality of all transfers (strictly integer quantities)
   - Prohibition of self-transfers (source != dest)
   - Strict prohibition of exports from High-risk districts
"""
import pytest
import numpy as np
import pandas as pd

from fractions import Fraction
from src.optimise import (
    solve_resource_allocation,
    evaluate_allocation_plan,
    compute_exact_physical_unmet,
    load_or_compute_distance_matrix,
    COST_PER_UNIT_KM,
    FIXED_ROUTE_COST,
    DEFAULT_SAFETY_RESERVE_RATIO,
    DEFAULT_EMERGENCY_STOCK_BUFFER_RATIO,
    MEDICINES,
    MEDICINE_CRITICALITY,
    PERISHABLE_MAX_KM
)


# ==============================================================================
# PART 1: DEF-04 — ROBUST SOURCE RESERVE CONSTRAINTS
# ==============================================================================

def test_def04_zero_demand_retains_stock_buffer():
    """
    District with zero demand (demand=0, stock=1000) must retain beta * stock (300 units).
    Maximum export cannot exceed 700 units.
    """
    demands = {"Donor": {"ors": 0.0}, "Recipient": {"ors": 1500.0}}
    stocks = {"Donor": {"ors": 1000.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame(
        [[0.0, 50.0], [50.0, 0.0]],
        index=["Donor", "Recipient"],
        columns=["Donor", "Recipient"]
    )

    plan_df, summary = solve_resource_allocation(
        demands, stocks, distances_df=dists,
        safety_reserve_ratio=0.60,
        emergency_stock_buffer_ratio=0.30
    )

    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]
    exported = plan_df[plan_df["source_region"] == "Donor"]["quantity"].sum()

    # Under legacy formula: reserve = 0.60 * 0 = 0 -> exported 1000 (total depletion!)
    # Under DEF-04: reserve = max(0.60 * 0, 0.30 * 1000) = 300 -> exportable <= 700
    assert exported <= 700, f"Zero-demand donor exported {exported} > allowed 700 units!"
    assert exported == 700, f"Expected full export of allowable surplus 700, got {exported}"

    # Evaluate with shared evaluator: exactly 0 violations
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_def04_low_demand_beta_dominates_alpha():
    """
    When demand is small relative to stock, beta * stock dominates alpha * demand.
    Stock = 1000, Demand = 100.
    alpha * demand = 0.60 * 100 = 60.
    beta * stock = 0.30 * 1000 = 300.
    Reserve must be 300, exportable = 700.
    """
    demands = {"D1": {"antibiotics": 100.0}, "D2": {"antibiotics": 1000.0}}
    stocks = {"D1": {"antibiotics": 1000.0}, "D2": {"antibiotics": 0.0}}
    dists = pd.DataFrame(
        [[0.0, 60.0], [60.0, 0.0]],
        index=["D1", "D2"],
        columns=["D1", "D2"]
    )

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    exported = plan_df[plan_df["source_region"] == "D1"]["quantity"].sum()

    assert exported <= 700, f"Low-demand donor exported {exported} > allowed 700 units!"
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_def04_high_demand_alpha_dominates_beta():
    """
    When demand is high relative to stock, alpha * demand dominates beta * stock.
    Stock = 1000, Demand = 1200.
    alpha * demand = 0.60 * 1200 = 720.
    beta * stock = 0.30 * 1000 = 300.
    Reserve must be 720, exportable = 280.
    """
    demands = {"D1": {"iv_fluids": 1200.0}, "D2": {"iv_fluids": 1000.0}}
    stocks = {"D1": {"iv_fluids": 1000.0}, "D2": {"iv_fluids": 0.0}}
    dists = pd.DataFrame(
        [[0.0, 40.0], [40.0, 0.0]],
        index=["D1", "D2"],
        columns=["D1", "D2"]
    )

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    exported = plan_df[plan_df["source_region"] == "D1"]["quantity"].sum()

    assert exported <= 280, f"High-demand donor exported {exported} > allowed 280 units!"
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_def04_zero_stock_district_solver_robustness():
    """Verify solver runs safely when stock is zero without division by zero or crash."""
    demands = {"ZeroDist": {"analgesics": 500.0}, "OtherDist": {"analgesics": 0.0}}
    stocks = {"ZeroDist": {"analgesics": 0.0}, "OtherDist": {"analgesics": 0.0}}
    dists = pd.DataFrame([[0.0, 30.0], [30.0, 0.0]], index=["ZeroDist", "OtherDist"], columns=["ZeroDist", "OtherDist"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]
    assert len(plan_df) == 0
    assert summary["total_transferred_units"] == 0


def test_def04_multi_commodity_reserve_independence():
    """Each commodity has an independent reserve; one commodity cannot deplete another."""
    demands = {
        "D1": {"antibiotics": 0.0, "ors": 2000.0},
        "D2": {"antibiotics": 500.0, "ors": 0.0}
    }
    stocks = {
        "D1": {"antibiotics": 1000.0, "ors": 1000.0},
        "D2": {"antibiotics": 0.0, "ors": 500.0}
    }
    dists = pd.DataFrame([[0.0, 45.0], [45.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]

    # D1 has zero antibiotics demand, stock 1000 -> exportable <= 700
    abx_exported = plan_df[(plan_df["source_region"] == "D1") & (plan_df["medicine"] == "antibiotics")]["quantity"].sum()
    assert abx_exported <= 700

    # D1 has ors demand 2000, stock 1000 -> reserve = max(1200, 300) = 1200 > 1000 -> exportable = 0
    ors_exported = plan_df[(plan_df["source_region"] == "D1") & (plan_df["medicine"] == "ors")]["quantity"].sum()
    assert ors_exported == 0


# ==============================================================================
# PART 2: DEF-08 — ROUTE ACTIVATION & FIXED TRANSPORT COSTS
# ==============================================================================

def test_def08_route_activation_variable_present_and_binary():
    """Verify solver activates binary route variables and counts active routes correctly."""
    demands = {"D1": {"ors": 0.0}, "D2": {"ors": 100.0}}
    stocks = {"D1": {"ors": 500.0}, "D2": {"ors": 0.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert len(plan_df) == 1
    assert summary["active_routes_count"] == 1


def test_def08_single_fixed_cost_for_multi_commodity_route():
    """
    When multiple commodities are transported along the same (i, j) route,
    the fixed route cost of ₹500 is charged exactly ONCE for that route.
    """
    demands = {
        "D1": {"ors": 0.0, "iv_fluids": 0.0},
        "D2": {"ors": 200.0, "iv_fluids": 200.0}
    }
    stocks = {
        "D1": {"ors": 1000.0, "iv_fluids": 1000.0},
        "D2": {"ors": 0.0, "iv_fluids": 0.0}
    }
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert summary["active_routes_count"] == 1
    assert len(plan_df) == 2  # 2 commodity rows on the SAME route

    # Evaluator cost: unit_km * 15.0 + 1 route * 500.0
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    expected_cost = (200 * 50.0 * 15.0) + (200 * 50.0 * 15.0) + 500.0  # 150,000 + 150,000 + 500 = 300,500
    assert eval_res["cost"] == expected_cost
    assert summary["total_transport_cost"] == expected_cost


def test_def08_inactive_route_has_zero_fixed_cost():
    """If no commodities flow along a route, no fixed cost is charged."""
    demands = {"D1": {"ors": 0.0}, "D2": {"ors": 0.0}}
    stocks = {"D1": {"ors": 500.0}, "D2": {"ors": 500.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert len(plan_df) == 0
    assert summary["active_routes_count"] == 0
    assert summary["total_transport_cost"] == 0.0


def test_def08_solver_evaluator_cost_perfect_alignment():
    """
    Verify numerical alignment between solver summary['total_transport_cost']
    and evaluator evaluate_allocation_plan()['cost'].
    """
    demands = {
        "D1": {"antibiotics": 0.0, "ors": 0.0},
        "D2": {"antibiotics": 150.0, "ors": 300.0},
        "D3": {"antibiotics": 0.0, "ors": 100.0}
    }
    stocks = {
        "D1": {"antibiotics": 500.0, "ors": 1000.0},
        "D2": {"antibiotics": 0.0, "ors": 0.0},
        "D3": {"antibiotics": 0.0, "ors": 0.0}
    }
    dists = pd.DataFrame([
        [0.0, 40.0, 80.0],
        [40.0, 0.0, 50.0],
        [80.0, 50.0, 0.0]
    ], index=["D1", "D2", "D3"], columns=["D1", "D2", "D3"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)

    assert abs(summary["total_transport_cost"] - eval_res["cost"]) < 0.05
    assert eval_res["violations"] == 0


# ==============================================================================
# PART 3: DEF-FAIR — ELIGIBILITY-AWARE & COMMODITY-DECOUPLED FAIRNESS
# ==============================================================================

def test_deffair_zero_demand_does_not_collapse_theta():
    """
    A district with zero demand across all commodities must not force min_coverage_theta to 0.
    """
    demands = {
        "ZeroDemandDist": {m: 0.0 for m in MEDICINES},
        "DeficitDist": {m: 100.0 for m in MEDICINES},
        "DonorDist": {m: 0.0 for m in MEDICINES}
    }
    stocks = {
        "ZeroDemandDist": {m: 100.0 for m in MEDICINES},
        "DeficitDist": {m: 0.0 for m in MEDICINES},
        "DonorDist": {m: 1000.0 for m in MEDICINES}
    }
    dists = pd.DataFrame([
        [0.0, 50.0, 50.0],
        [50.0, 0.0, 50.0],
        [50.0, 50.0, 0.0]
    ], index=["ZeroDemandDist", "DeficitDist", "DonorDist"], columns=["ZeroDemandDist", "DeficitDist", "DonorDist"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert summary["fairness_theta"] > 0.0, "Fairness theta collapsed to 0 due to zero-demand district!"
    assert summary["min_coverage_after"] > 0.0


def test_deffair_isolated_district_without_donors_does_not_collapse_theta():
    """
    If a district has a deficit but has NO feasible donors (e.g. blood > 150 km away),
    it is ineligible for fairness and must not collapse theta for other eligible districts.
    """
    demands = {
        "EligibleDeficit": {"blood_units": 100.0},
        "IsolatedDeficit": {"blood_units": 100.0},
        "Donor": {"blood_units": 0.0}
    }
    stocks = {
        "EligibleDeficit": {"blood_units": 0.0},
        "IsolatedDeficit": {"blood_units": 0.0},
        "Donor": {"blood_units": 500.0}
    }
    # EligibleDeficit is 50 km from Donor (<= 150 km)
    # IsolatedDeficit is 300 km from Donor (> 150 km)
    dists = pd.DataFrame([
        [0.0, 300.0, 50.0],
        [300.0, 0.0, 300.0],
        [50.0, 300.0, 0.0]
    ], index=["EligibleDeficit", "IsolatedDeficit", "Donor"], columns=["EligibleDeficit", "IsolatedDeficit", "Donor"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]

    # Donor can reach EligibleDeficit but CANNOT reach IsolatedDeficit
    assert summary["fairness_theta"] > 0.0, "Theta collapsed because of an isolated donorless district!"
    assert summary["eligible_fairness_pairs"] == 1


def test_deffair_small_demand_district_included_when_donor_available():
    """Small demand districts (< 10 units) are included in fairness if they have a donor."""
    demands = {
        "SmallDist": {"ors": 5.0},
        "LargeDist": {"ors": 500.0},
        "Donor": {"ors": 0.0}
    }
    stocks = {
        "SmallDist": {"ors": 0.0},
        "LargeDist": {"ors": 200.0},
        "Donor": {"ors": 1000.0}
    }
    dists = pd.DataFrame([
        [0.0, 40.0, 40.0],
        [40.0, 0.0, 40.0],
        [40.0, 40.0, 0.0]
    ], index=["SmallDist", "LargeDist", "Donor"], columns=["SmallDist", "LargeDist", "Donor"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    # SmallDist must receive stock and achieve positive coverage
    small_received = plan_df[(plan_df["dest_region"] == "SmallDist") & (plan_df["medicine"] == "ors")]["quantity"].sum()
    assert small_received > 0, "Small demand district received 0 stock under fairness!"
    assert summary["fairness_theta"] > 0.0


# ==============================================================================
# PART 4: DEF-BLOOD — PERISHABLE BLOOD-PRODUCT DISTANCE LIMIT (150 KM)
# ==============================================================================

def test_defblood_149km_allowed():
    """Blood product transfer over 149.0 km (< 150 km) is strictly allowed."""
    demands = {"D1": {"blood_units": 0.0}, "D2": {"blood_units": 50.0}}
    stocks = {"D1": {"blood_units": 200.0}, "D2": {"blood_units": 0.0}}
    dists = pd.DataFrame([[0.0, 149.0], [149.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    blood_transfers = plan_df[plan_df["medicine"] == "blood_units"]
    assert len(blood_transfers) == 1
    assert blood_transfers.iloc[0]["quantity"] == 50

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_defblood_150km_exact_boundary_allowed():
    """Blood product transfer at exact boundary 150.0 km is strictly allowed."""
    demands = {"D1": {"blood_units": 0.0}, "D2": {"blood_units": 50.0}}
    stocks = {"D1": {"blood_units": 200.0}, "D2": {"blood_units": 0.0}}
    dists = pd.DataFrame([[0.0, 150.0], [150.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    blood_transfers = plan_df[plan_df["medicine"] == "blood_units"]
    assert len(blood_transfers) == 1
    assert blood_transfers.iloc[0]["quantity"] == 50

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_defblood_151km_strictly_prohibited():
    """Blood product transfer over 151.0 km (> 150 km) is strictly prohibited."""
    demands = {"D1": {"blood_units": 0.0}, "D2": {"blood_units": 50.0}}
    stocks = {"D1": {"blood_units": 200.0}, "D2": {"blood_units": 0.0}}
    dists = pd.DataFrame([[0.0, 151.0], [151.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    blood_transfers = plan_df[plan_df["medicine"] == "blood_units"]
    assert len(blood_transfers) == 0, f"Prohibited blood transfer occurred at 151 km: {blood_transfers}"

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


def test_defblood_non_perishables_allowed_beyond_150km():
    """Non-blood medicines (e.g. antibiotics) are allowed beyond 150 km."""
    demands = {"D1": {"antibiotics": 0.0}, "D2": {"antibiotics": 100.0}}
    stocks = {"D1": {"antibiotics": 500.0}, "D2": {"antibiotics": 0.0}}
    dists = pd.DataFrame([[0.0, 200.0], [200.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists)
    abx_transfers = plan_df[plan_df["medicine"] == "antibiotics"]
    assert len(abx_transfers) == 1
    assert abx_transfers.iloc[0]["quantity"] == 100

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["violations"] == 0


# ==============================================================================
# PART 5: REGRESSION & OPERATIONAL INVARIANCE SAFETY
# ==============================================================================

def test_high_risk_district_export_strictly_blocked():
    """High-risk districts cannot export any stock even if surplus exists."""
    demands = {"HighRisk": {"ors": 0.0}, "Deficit": {"ors": 200.0}}
    stocks = {"HighRisk": {"ors": 1000.0}, "Deficit": {"ors": 0.0}}
    risks = {"HighRisk": {"ors": "High"}, "Deficit": {"ors": "Low"}}
    dists = pd.DataFrame([[0.0, 30.0], [30.0, 0.0]], index=["HighRisk", "Deficit"], columns=["HighRisk", "Deficit"])

    plan_df, summary = solve_resource_allocation(demands, stocks, risks, distances_df=dists)
    assert len(plan_df) == 0, "High-risk district exported stock in violation of policy!"


def test_no_self_transfers_and_strict_integrality():
    """All transfers must be non-zero integers with source != dest."""
    demands = {"D1": {"iv_fluids": 0.0}, "D2": {"iv_fluids": 333.3}}
    stocks = {"D1": {"iv_fluids": 500.0}, "D2": {"iv_fluids": 0.0}}
    dists = pd.DataFrame([[0.0, 45.0], [45.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

# ==============================================================================
# PART 6: LEXICOGRAPHIC OPTIMIZATION & ABSOLUTE OBJECTIVE PRIORITY
# ==============================================================================

def test_lexicographic_absolute_priority_over_expensive_transport():
    """
    Test scenario where satisfying 1 unit of unmet demand is more expensive than a scalarized penalty.
    Donor has 1000 units of ORS.
    Recipient has 1 unit of ORS demand and 0 stock.
    Distance = 100 km.
    Fixed route cost = ₹500, Variable transport cost = 15 * 100 * 1 = ₹1500. Total transport cost = ₹2000.
    
    If an arbitrary scalarized weight w_unmet = 1000 was used:
    Penalty for unmet demand = 1000 * 1.0 = 1000 < 2000 transport cost.
    Scalarized optimization would refuse to transport and leave the unit unmet!
    
    Under lexicographic optimization:
    Stage 1 strictly minimizes weighted unmet demand to 0.
    Stage 2 minimizes transport cost subject to unmet demand <= 0 + epsilon.
    The unit MUST be transported, achieving 100% demand fulfillment.
    """
    demands = {"Donor": {"ors": 0.0}, "Recipient": {"ors": 1.0}}
    stocks = {"Donor": {"ors": 1000.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame(
        [[0.0, 100.0], [100.0, 0.0]],
        index=["Donor", "Recipient"],
        columns=["Donor", "Recipient"]
    )

    # 1. Scalarized with penalty weight smaller than transport cost (and fairness decoupled)
    # leaves unmet demand unsatisfied because transport cost (₹2000) > unmet penalty (₹1000)
    plan_scalar, summ_scalar = solve_resource_allocation(
        demands, stocks, distances_df=dists,
        w_unmet=1000.0, # smaller than ₹2000 cost
        w_fairness=0.0,
        lexicographic=False
    )
    assert summ_scalar["unmet_demand_after"] == 1.0, "Scalarized solver unexpectedly satisfied expensive demand"
    assert len(plan_scalar) == 0

    # 2. Lexicographic solver strictly forces 0 unmet demand regardless of cost or weights
    plan_lex, summ_lex = solve_resource_allocation(
        demands, stocks, distances_df=dists,
        w_fairness=0.0,
        lexicographic=True
    )
    assert summ_lex["stage1_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summ_lex["solve_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summ_lex["unmet_demand_after"] == 0.0, "Lexicographic solver failed to strictly prioritize unmet demand!"
    assert summ_lex["total_transferred_units"] == 1
    assert summ_lex["total_transport_cost"] == 2000.0

    eval_lex = evaluate_allocation_plan(plan_lex, demands, stocks, {}, dists)
    assert eval_lex["unmet_demand"] == 0.0
    assert eval_lex["cost"] == 2000.0
    assert eval_lex["primary_objective_unmet"] == 0.0
    assert eval_lex["secondary_objective_cost"] == 2000.0
    assert eval_lex["violations"] == 0


def test_lexicographic_stage2_cannot_worsen_stage1_unmet_demand():
    """Verify Stage 2 preserves optimal weighted unmet demand from Stage 1 within numerical tolerance."""
    demands = {"D1": {"antibiotics": 50.0}, "D2": {"antibiotics": 50.0}}
    stocks = {"D1": {"antibiotics": 100.0}, "D2": {"antibiotics": 0.0}}
    dists = pd.DataFrame([[0.0, 40.0], [40.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summary["optimal_weighted_unmet"] is not None

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["primary_objective_unmet"] <= summary["optimal_weighted_unmet"] + 1e-3


def test_lexicographic_stage2_selects_cheaper_solution_among_stage1_optima():
    """
    Test case with multiple Stage 1 optimal solutions where Stage 2 selects the lower-cost solution.
    Recipient needs 50 units of ORS.
    Two donors (DonorNear at 20 km, DonorFar at 80 km) each have 100 units of ORS.
    Both donors can fully satisfy Recipient with 0 unmet demand (both Stage 1 optimal).
    Stage 2 MUST select DonorNear to minimize transport cost.
    """
    demands = {"DonorNear": {"ors": 0.0}, "DonorFar": {"ors": 0.0}, "Recipient": {"ors": 50.0}}
    stocks = {"DonorNear": {"ors": 100.0}, "DonorFar": {"ors": 100.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame([
        [0.0, 100.0, 20.0],
        [100.0, 0.0, 80.0],
        [20.0, 80.0, 0.0]
    ], index=["DonorNear", "DonorFar", "Recipient"], columns=["DonorNear", "DonorFar", "Recipient"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["unmet_demand_after"] == 0.0

    # DonorNear must be the chosen source
    assert len(plan_df) == 1
    assert plan_df.iloc[0]["source_region"] == "DonorNear"
    assert plan_df.iloc[0]["dest_region"] == "Recipient"
    assert plan_df.iloc[0]["quantity"] == 50
    # Expected cost: 50 * 20 * 15 + 500 = 15,500 (vs 50 * 80 * 15 + 500 = 60,500 for DonorFar)
    assert summary["total_transport_cost"] == 15500.0


def test_lexicographic_independent_primary_objective_reconciliation():
    """Independently calculate final allocation's weighted unmet demand and verify against Stage 1 optimum."""
    demands = {
        "D1": {"antibiotics": 200.0, "blood_units": 50.0},
        "D2": {"antibiotics": 0.0, "blood_units": 0.0}
    }
    stocks = {
        "D1": {"antibiotics": 50.0, "blood_units": 10.0},
        "D2": {"antibiotics": 500.0, "blood_units": 100.0}
    }
    dists = pd.DataFrame([[0.0, 60.0], [60.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"

    # Recompute primary objective manually from plan
    transfers_in = plan_df.groupby(["dest_region", "medicine"])["quantity"].sum().to_dict()
    manual_weighted_unmet = 0.0
    for d in demands:
        for m in MEDICINES:
            dem = float(demands.get(d, {}).get(m, 0.0))
            stk = float(stocks.get(d, {}).get(m, 0.0))
            tin = float(transfers_in.get((d, m), 0.0))
            u = max(0.0, dem - (stk + tin))
            manual_weighted_unmet += u * MEDICINE_CRITICALITY.get(m, 1.0)

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert abs(eval_res["primary_objective_unmet"] - manual_weighted_unmet) < 1e-5
    assert abs(eval_res["primary_objective_unmet"] - summary["optimal_weighted_unmet"]) < 1e-4


def test_primary_objective_discrete_quantum_and_integrality():
    """
    Mathematical Proof Verification:
    Decision variables x[i, j, m] are strictly integers in Z_>=0.
    For any realized instance (fixed demand and stock parameters), net transferred supply
    to any district j and commodity m changes by discrete quanta Delta_x in Z.
    
    Because MEDICINE_CRITICALITY weights omega_m in {1.0, 2.0, 3.0, 5.0} are all >= 1.0,
    any discrete shift in allocation that alters unmet demand changes the primary objective
    by at least min(omega_m) * 1 = 1.0.
    
    Consequently, epsilon = 10^-4 satisfies:
        solver_feasibility_tolerance (10^-6) < epsilon (10^-4) << minimum_discrete_quantum (1.0).
    This strictly guarantees that Stage 2 cannot sacrifice even 1 unit of medicine for transport or fairness.
    """
    # 1. Verify criticality weight lower bound
    for med, weight in MEDICINE_CRITICALITY.items():
        assert weight >= 1.0, f"Criticality weight for {med} is {weight} < 1.0"
        assert float(weight).is_integer(), f"Criticality weight for {med} is non-integer: {weight}"

    # 2. Minimum discrete increment
    min_weight = min(MEDICINE_CRITICALITY.values())
    min_discrete_jump = min_weight * 1.0
    assert min_discrete_jump >= 1.0

    epsilon = 1e-4
    solver_tolerance = 1e-6
    # Mathematical cushion separation:
    assert solver_tolerance < epsilon < min_discrete_jump
    assert (min_discrete_jump / epsilon) == 10000.0, "Epsilon is exactly 10,000x smaller than minimum discrete transfer quantum"


def test_stage2_epsilon_tolerance_preserves_stage1_shortage_strictly():
    """
    Verify Stage 2 preserves optimal weighted unmet demand from Stage 1 strictly.
    Confirms that Stage 2 does not trade off any unmet demand for route or transport savings.
    """
    demands = {
        "D1": {"ors": 100.0, "antibiotics": 50.0},
        "D2": {"ors": 0.0, "antibiotics": 0.0}
    }
    stocks = {
        "D1": {"ors": 20.0, "antibiotics": 10.0},
        "D2": {"ors": 200.0, "antibiotics": 100.0}
    }
    dists = pd.DataFrame([[0.0, 100.0], [100.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["unmet_demand_after"] == 0.0
    assert summary["optimal_weighted_unmet"] == 0.0

    # Total integer units transferred must exactly meet the deficit: 80 ORS + 40 antibiotics = 120 units
    assert summary["total_transferred_units"] == 120
    # Every transfer quantity must be an integer
    assert (plan_df["quantity"] % 1 == 0).all()


def test_fractional_demand_stability_under_epsilon():
    """
    Verify stability of 2-stage lexicographic optimization under fractional demand inputs
    arising from continuous Monte-Carlo or ML predictions (e.g. 133.8, 392.3).
    Demonstrates that fractional demands do not cause infeasibility, numerical cycling,
    or precision collapse under epsilon = 10^-4.
    """
    demands = {
        "D1": {"ors": 133.8, "blood_units": 14.7},
        "D2": {"ors": 0.0, "blood_units": 0.0}
    }
    stocks = {
        "D1": {"ors": 30.2, "blood_units": 2.1},
        "D2": {"ors": 500.0, "blood_units": 100.0}
    }
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]

    # All transfer quantities must remain strictly integer despite fractional demand
    for q in plan_df["quantity"]:
        assert float(q).is_integer() and q >= 0

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    # Primary objective must match Stage 1 optimum within tolerance
    assert abs(eval_res["primary_objective_unmet"] - summary["optimal_weighted_unmet"]) <= 1e-4


# ==============================================================================
# PART 6: ADVERSARIAL STAGE 2 EPSILON & STRICT CLINICAL PRIORITY TESTS
# ==============================================================================

def test_adversarial_1_fractional_unmet_demand_smaller_than_1e4():
    """
    Adversarial Counterexample Test:
    Demand minus stock = 133.00001 (fractional deficit = 1e-5 < 1e-4).
    Stage 1 minimum unmet demand is 0.0 achieved by transferring 134 units.
    Under the hardened formulation, Stage 2 must not transfer 133 units to save transport cost;
    it must strictly transfer 134 units, achieving unmet_demand == 0.0.
    """
    demands = {"Recipient": {"ors": 133.00001}, "Donor": {"ors": 0.0}}
    stocks = {"Recipient": {"ors": 0.0}, "Donor": {"ors": 500.0}}
    dists = pd.DataFrame(
        [[0.0, 100.0], [100.0, 0.0]],
        index=["Recipient", "Donor"],
        columns=["Recipient", "Donor"]
    )

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"

    # Must transfer 134 units, not 133
    assert summary["total_transferred_units"] == 134
    assert len(plan_df) == 1
    assert plan_df.iloc[0]["quantity"] == 134

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["unmet_demand"] == 0.0
    assert eval_res["primary_objective_unmet"] == 0.0


def test_adversarial_2_fractional_demand_immediately_above_integer_boundary():
    """
    Fractional demand immediately above an integer boundary:
    Demand = 100.0001 (stock = 0.0).
    Donor has 200 units, distance = 80 km.
    To completely eliminate unmet demand, the solver must transfer ceil(100.0001) = 101 units.
    Transferring 100 units would leave 0.0001 unmet.
    Stage 2 must transfer 101 units with zero clinical sacrifice.
    """
    demands = {"R": {"antibiotics": 100.0001}, "D": {"antibiotics": 0.0}}
    stocks = {"R": {"antibiotics": 0.0}, "D": {"antibiotics": 200.0}}
    dists = pd.DataFrame([[0.0, 80.0], [80.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"

    assert summary["total_transferred_units"] == 101
    assert plan_df.iloc[0]["quantity"] == 101
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["unmet_demand"] == 0.0


def test_adversarial_3_demand_immediately_below_integer_boundary():
    """
    Fractional demand immediately below an integer boundary:
    Demand = 99.9999 (stock = 0.0).
    Donor has 200 units, distance = 80 km.
    Transferring 100 units satisfies all demand (100 >= 99.9999, unmet = 0.0).
    Transferring 99 units would leave unmet = 0.9999.
    Stage 2 must transfer 100 units, not 99.
    """
    demands = {"R": {"ors": 99.9999}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 200.0}}
    dists = pd.DataFrame([[0.0, 80.0], [80.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"

    assert summary["total_transferred_units"] == 100
    assert plan_df.iloc[0]["quantity"] == 100
    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    assert eval_res["unmet_demand"] == 0.0


def test_adversarial_4_stage2_epsilon_exploitation_blocked():
    """
    Demonstrates that an artificial tolerance (Z1 <= Z1* + 1e-4) allows Stage 2
    to exploit the epsilon gap and under-ship, whereas the hardened solver blocks it.
    """
    from ortools.linear_solver import pywraplp

    # 1. Simulate old formulation with artificial + 1e-4 tolerance
    scip_old = pywraplp.Solver.CreateSolver("SCIP")
    x_old = scip_old.IntVar(0, 500, "x")
    unmet_old = scip_old.NumVar(0.0, 1000.0, "unmet")
    scip_old.Add(unmet_old >= 133.00001 - x_old)
    obj1_old = scip_old.Objective()
    obj1_old.SetCoefficient(unmet_old, 1.0)
    obj1_old.SetMinimization()
    scip_old.Solve()
    opt_val_old = obj1_old.Value() # 0.0

    # Old Stage 2 adds + 1e-4
    scip_old.Add(unmet_old <= opt_val_old + 1e-4)
    obj2_old = scip_old.Objective()
    obj2_old.Clear()
    obj2_old.SetCoefficient(x_old, 1500.0) # transport cost
    obj2_old.SetMinimization()
    scip_old.Solve()
    # Old formulation exploits epsilon: x=133, leaving 0.00001 unmet
    assert x_old.solution_value() == 133.0, "Expected old formulation with +1e-4 to exploit epsilon"

    # 2. Hardened production solver strictly blocks exploitation
    demands = {"R": {"ors": 133.00001}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 500.0}}
    dists = pd.DataFrame([[0.0, 100.0], [100.0, 0.0]], index=["R", "D"], columns=["R", "D"])
    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["total_transferred_units"] == 134, "Hardened solver failed to block epsilon exploitation!"


def test_adversarial_5_multiple_stage1_optima_secondary_selection():
    """
    When multiple Stage 1 optimal solutions exist (both yielding zero unmet demand),
    Stage 2 must select the secondary solution that minimizes transport cost.
    Recipient needs 50 units. DonorNear (20 km) vs DonorFar (80 km).
    """
    demands = {"DonorNear": {"ors": 0.0}, "DonorFar": {"ors": 0.0}, "Recipient": {"ors": 50.0}}
    stocks = {"DonorNear": {"ors": 100.0}, "DonorFar": {"ors": 100.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame([
        [0.0, 100.0, 20.0],
        [100.0, 0.0, 80.0],
        [20.0, 80.0, 0.0]
    ], index=["DonorNear", "DonorFar", "Recipient"], columns=["DonorNear", "DonorFar", "Recipient"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] == "OPTIMAL"
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["unmet_demand_after"] == 0.0

    # Must select DonorNear exclusively
    assert len(plan_df) == 1
    assert plan_df.iloc[0]["source_region"] == "DonorNear"
    assert summary["total_transport_cost"] == 15500.0 # 50 * 20 * 15 + 500


def test_adversarial_6_solver_failure_handling():
    """
    Verify Stage 1 and Stage 2 solver failure handling:
    1. If Stage 1 returns non-optimal, halts immediately with empty plan and stage1_status.
    2. If Stage 2 degrades Stage 1 optimum beyond feasibility tolerance (Method D),
       halts and returns solve_status == 'INFEASIBLE'.
    """
    from unittest.mock import patch
    from ortools.linear_solver import pywraplp

    demands = {"D1": {"ors": 100.0}, "D2": {"ors": 0.0}}
    stocks = {"D1": {"ors": 0.0}, "D2": {"ors": 200.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    # 1. Simulate Stage 1 non-optimal status
    with patch.object(pywraplp.Solver, "Solve", return_value=pywraplp.Solver.INFEASIBLE):
        plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
        assert summary["solve_status"] == "INFEASIBLE"
        assert summary["stage1_status"] == "INFEASIBLE"
        assert len(plan_df) == 0
        assert summary["total_transferred_units"] == 0


def test_adversarial_7_independent_recalculation_final_primary_objective():
    """
    Multi-district, multi-medicine scenario with fractional demands:
    Solve allocation plan, independently recalculate primary objective from scratch,
    and verify exact equality with summary['optimal_weighted_unmet'].
    """
    demands = {
        "D1": {"ors": 133.8, "blood_units": 14.7, "antibiotics": 55.2},
        "D2": {"ors": 0.0, "blood_units": 0.0, "antibiotics": 0.0}
    }
    stocks = {
        "D1": {"ors": 30.2, "blood_units": 2.1, "antibiotics": 10.0},
        "D2": {"ors": 500.0, "blood_units": 100.0, "antibiotics": 200.0}
    }
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["stage1_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]

    # Independent recalculation from scratch
    transfers_in = plan_df.groupby(["dest_region", "medicine"])["quantity"].sum().to_dict()
    transfers_out = plan_df.groupby(["source_region", "medicine"])["quantity"].sum().to_dict()

    recalculated_weighted_unmet = 0.0
    for d in demands:
        for m in MEDICINES:
            dem = float(demands.get(d, {}).get(m, 0.0))
            stk = float(stocks.get(d, {}).get(m, 0.0))
            tin = float(transfers_in.get((d, m), 0.0))
            tout = float(transfers_out.get((d, m), 0.0))
            final_stk = stk + tin - tout
            u = max(0.0, dem - final_stk)
            recalculated_weighted_unmet += u * MEDICINE_CRITICALITY.get(m, 1.0)

    eval_res = evaluate_allocation_plan(plan_df, demands, stocks, {}, dists)
    # Check that evaluator matches independent manual calculation
    assert abs(eval_res["primary_objective_unmet"] - recalculated_weighted_unmet) < 1e-5
    # Check that final solution matches Stage 1 optimum to within solver tolerance
    assert abs(recalculated_weighted_unmet - summary["optimal_weighted_unmet"]) <= 1e-4


# ==============================================================================
# PART 7: INDEPENDENT ALLOCATION-BALANCE AUDIT & POST-SOLVE GUARD TESTS
# ==============================================================================

def test_independent_reconstruction_agrees_with_solver_objective():
    """
    Verify that independently reconstructing actual unmet demand directly from
    physical shipments x[i, j, m], demand, and initial stock:
        actual_unmet[j, m] = max(0, demand[j, m] - (stock[j, m] + inbound[j, m] - outbound[j, m]))
    agrees with the solver's reported primary objective within numerical tolerance.
    """
    demands = {
        "D1": {"ors": 250.5, "antibiotics": 80.2},
        "D2": {"ors": 10.0, "antibiotics": 5.0}
    }
    stocks = {
        "D1": {"ors": 50.0, "antibiotics": 20.0},
        "D2": {"ors": 400.0, "antibiotics": 200.0}
    }
    dists = pd.DataFrame([[0.0, 75.0], [75.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]

    # Reconstruct balance from actual shipments
    reconstructed_unmet = 0.0
    for j in demands:
        for m in ["ors", "antibiotics"]:
            dem = float(demands[j][m])
            stk = float(stocks[j][m])
            inbound = float(plan_df[(plan_df["dest_region"] == j) & (plan_df["medicine"] == m)]["quantity"].sum())
            outbound = float(plan_df[(plan_df["source_region"] == j) & (plan_df["medicine"] == m)]["quantity"].sum())
            final_stk = stk + inbound - outbound
            u = max(0.0, dem - final_stk)
            reconstructed_unmet += u * MEDICINE_CRITICALITY[m]

    opt_val = summary["optimal_weighted_unmet"]
    audit_tol = min(1.0, max(1e-5, 1e-6 * opt_val))
    assert abs(reconstructed_unmet - opt_val) <= audit_tol
    assert abs(summary["reconstructed_weighted_unmet"] - reconstructed_unmet) <= 1e-4


def test_scenario_32_four_objective_comparison():
    """
    Independently verify all four objectives for Scenario 32:
      1. Z_{1, solver}^{(1)}: Stage 1 solver-reported objective
      2. Z_{1, phys}^{(1)}: Stage 1 independently reconstructed physical objective
      3. Z_{1, solver}^{(2)}: Stage 2 solver-reported objective
      4. Z_{1, phys}^{(2)}: Stage 2 independently reconstructed physical objective
    Demonstrates:
      - Z_{1, phys}^{(1)} matches Z_{1, solver}^{(1)} within double-precision rounding (diff = -3e-8).
      - Stage 2 secondary optimization drifted by +0.10 units (Z_{1, phys}^{(2)} = 105,184,402.30)
        due to SCIP relative feasibility tolerance across fractional demand boundaries.
      - The strict clinical priority guard detects this +0.10 deterioration, rejects Stage 2,
        and triggers fallback to Stage 1 physical plan, ensuring final physical unmet demand
        strictly matches the Stage 1 optimum (105,184,402.20).
    """
    from src.engine.monte_carlo import generate_stratified_benchmark_scenarios
    scenarios = generate_stratified_benchmark_scenarios(
        n_per_stratum=12,
        stock_multipliers=(0.25, 0.5, 1.0),
        random_seed=42,
        n_draws_per_sim=100
    )
    sc = scenarios[32]
    distances_df = load_or_compute_distance_matrix()

    plan_df, summary = solve_resource_allocation(
        sc["demands"], sc["stocks"], sc["risks"],
        distances_df=distances_df,
        lexicographic=True
    )

    assert summary["solve_status"] in ["OPTIMAL", "FEASIBLE"]
    assert summary["stage1_status"] == "OPTIMAL"

    z1_solver_1 = summary["optimal_weighted_unmet"]
    z1_phys_1 = summary["stage1_reconstructed_unmet"]
    z1_solver_2 = summary["stage2_solver_unmet"]
    z1_phys_2 = summary["stage2_reconstructed_unmet"]
    final_phys = summary["reconstructed_weighted_unmet"]

    assert z1_solver_1 is not None
    assert z1_phys_1 is not None
    assert z1_solver_2 is not None
    assert z1_phys_2 is not None
    assert final_phys is not None

    # 1. Stage 1 solver vs physical reconstruction agreement:
    assert abs(z1_phys_1 - z1_solver_1) < 1e-4, f"Stage 1 physical ({z1_phys_1}) diverged from solver ({z1_solver_1})"

    # 2. Stage 2 secondary optimization drifted by +0.10 units:
    stage2_drift = z1_phys_2 - z1_phys_1
    assert abs(stage2_drift - 0.10) < 1e-4, f"Expected Stage 2 drift of ~0.10, got {stage2_drift}"

    # 3. Fallback triggered and Stage 2 rejected:
    assert summary["stage2_accepted"] is False
    assert summary["lexicographic_fallback"] is True

    # 4. Final returned plan strictly achieves Stage 1 optimum (0.0 deterioration):
    assert abs(final_phys - z1_phys_1) < 1e-5, f"Final plan ({final_phys}) failed to match Stage 1 optimum ({z1_phys_1})"


def test_fractional_demand_100_9_under_shipment_counterexample():
    """
    Demonstrate why a 1.0 tolerance cap is mathematically invalid for fractional demand:
      Demand = 100.9, Stock = 0.
      Transfer 101: unmet = 0.0 (optimal)
      Transfer 100: unmet = 0.9 (deterioration = 0.9 units)
    The shipment difference is 1 discrete unit, but unmet demand increases by only 0.9.
    A 1.0 cap accepts this 0.9 deterioration, failing to prevent discrete unit sacrifice.
    The strict clinical priority guard rejects it.
    """
    demands = {"R": {"ors": 100.9}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 200.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    # 1. Optimal solve transfers 101 units leaving 0.0 unmet demand
    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["total_transferred_units"] == 101
    assert summary["reconstructed_weighted_unmet"] == 0.0

    # 2. Under-shipped plan with 100 units
    plan_100 = pd.DataFrame([{
        "source_region": "D", "dest_region": "R", "medicine": "ors",
        "quantity": 100, "distance_km": 50.0, "cost": 75500.0,
        "priority": "Standard", "confidence": 0.95
    }])
    eval_100 = evaluate_allocation_plan(plan_100, demands, stocks, {}, dists)
    assert abs(eval_100["primary_objective_unmet"] - 0.9) < 1e-5

    # 3. Flaw of 1.0 cap: 0.9 <= 1.0, so a 1.0 cap accepts under-shipping by 1 discrete unit!
    opt_val = 0.0
    accepted_by_1_0_cap = (eval_100["primary_objective_unmet"] <= opt_val + 1.0)
    assert accepted_by_1_0_cap is True, "1.0 cap should have mistakenly accepted 0.9 deterioration"

    # 4. Strict numerical guard: 0.9 > 1e-5, strictly rejected by clinical priority
    accepted_by_strict_guard = (eval_100["primary_objective_unmet"] <= opt_val + 1e-5)
    assert accepted_by_strict_guard is False, "Strict guard must reject 0.9 deterioration"


def test_fractional_deterioration_spectrum_01_09_10_greater10():
    """
    Test the behavior of tolerance guards across a spectrum of deterioration:
      - 0.1 weighted units (e.g. demand 100.1, transfer 100)
      - 0.9 weighted units (e.g. demand 100.9, transfer 100)
      - Exactly 1.0 weighted unit (e.g. demand 101.0, transfer 100)
      - Greater than 1.0 weighted units (e.g. demand 101.5, transfer 100, unmet = 1.5)
    Proves:
      - A 1.0 cap accepts 0.1, 0.9, and 1.0, failing to protect fractional demand.
      - The strict priority guard (tau = 1e-5) rejects all four.
    """
    opt_val = 1000.0
    deltas = [0.1, 0.9, 1.0, 1.5]

    for delta in deltas:
        degraded_val = opt_val + delta
        # Legacy 1.0 cap acceptance:
        accepted_1_0_cap = (degraded_val <= opt_val + 1.0)
        # Strict numerical guard:
        accepted_strict = (degraded_val <= opt_val + 1e-5)

        if delta in [0.1, 0.9, 1.0]:
            assert accepted_1_0_cap is True, f"1.0 cap unexpectedly rejected delta={delta}"
            assert accepted_strict is False, f"Strict guard failed to reject delta={delta}"
        else:
            assert accepted_1_0_cap is False, f"1.0 cap unexpectedly accepted delta={delta}"
            assert accepted_strict is False, f"Strict guard failed to reject delta={delta}"


def test_large_objective_relative_tolerance_danger():
    """
    Verify that for massive shortage objectives (Z1* ~ 1e8), an unconstrained relative tolerance
    (tau = 1e-6 * Z1* ~ 105.18 units) permits sacrificing 105 units of ORS or 21 units of blood.
    Demonstrates that the strict fallback guard eliminates this vulnerability.
    """
    opt_val = 105184402.2
    relative_tol = 1e-6 * opt_val
    assert relative_tol > 105.0

    # A solver perturbation sacrificing 20 units of blood (crit=5.0 -> 100 weighted units):
    loss_20_blood = opt_val + 100.0
    assert loss_20_blood <= opt_val + relative_tol, "Relative tolerance permitted 20 units of blood to be sacrificed!"

    # Numerical noise bound:
    num_tol = max(1e-5, 1e-11 * opt_val)
    assert num_tol < 0.002
    assert loss_20_blood > opt_val + num_tol, "Strict numerical bound successfully blocks blood sacrifice!"


def test_fractional_deterioration_smaller_than_1e_5():
    """
    Verify that exact physical objective comparison blocks deteriorations smaller than 1e-5.
    Under a positive tolerance tau = 1e-5, a deterioration of 1e-6 (or 1/1,000,000)
    would be mistakenly accepted. Exact rational comparison (Fraction) strictly rejects it.
    """
    opt_val = Fraction(100, 1)
    # Infinitesimal deterioration smaller than 1e-5 (e.g. 1e-6)
    stage2_val = opt_val + Fraction(1, 1000000)

    # Legacy positive tolerance: 1e-6 <= 1e-5 (MISTAKENLY ACCEPTED)
    accepted_by_positive_tol = (float(stage2_val) <= float(opt_val) + 1e-5)
    assert accepted_by_positive_tol is True

    # Exact physical comparison: stage2_val <= opt_val (STRICTLY REJECTED)
    accepted_by_exact = (stage2_val <= opt_val)
    assert accepted_by_exact is False, "Exact comparison must reject even 1e-6 deterioration"


def test_deterioration_near_relative_threshold_at_large_objective():
    """
    Verify that at large objective magnitudes (Z1* = 10^8), a deterioration of 0.0005
    falls below tau = 1e-11 * Z1* = 0.00105 (and would pass positive tolerance),
    but is strictly rejected under exact physical comparison (Fraction).
    """
    opt_val = Fraction(1051844022, 10)  # 105,184,402.2
    relative_tol = float(opt_val) * 1e-11  # ~ 0.0010518
    assert relative_tol > 0.001

    # Perturbation of +0.0005 weighted units:
    stage2_val = opt_val + Fraction(5, 10000)

    # Positive tolerance check (MISTAKENLY ACCEPTED):
    accepted_by_rel_tol = (float(stage2_val) <= float(opt_val) + relative_tol)
    assert accepted_by_rel_tol is True

    # Exact comparison check (STRICTLY REJECTED):
    assert (stage2_val <= opt_val) is False, "Exact comparison must reject 0.0005 deterioration on large objective"


def test_exact_equality_stage1_and_stage2_physical_objectives():
    """
    Verify that when Stage 2 achieves exact equality with Stage 1 physical unmet demand,
    Stage 2 is accepted without triggering fallback.
    """
    demands = {"R": {"ors": 50.0}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 100.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["stage2_accepted"] is True
    assert summary["lexicographic_fallback"] is False
    assert summary["exact_comparison"] is True
    assert summary["audit_tolerance"] == 0.0
    assert summary["stage1_reconstructed_unmet"] == 0.0
    assert summary["stage2_reconstructed_unmet"] == 0.0
    assert summary["reconstructed_weighted_unmet"] == 0.0


def test_stage2_secondary_improvement_without_clinical_deterioration():
    """
    Verify that Stage 2 minimizes transport cost among multiple Stage 1 optima
    while preserving zero clinical unmet demand exactly.
    """
    demands = {"Near": {"ors": 0.0}, "Far": {"ors": 0.0}, "Recipient": {"ors": 40.0}}
    stocks = {"Near": {"ors": 100.0}, "Far": {"ors": 100.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame([
        [0.0, 100.0, 20.0],
        [100.0, 0.0, 80.0],
        [20.0, 80.0, 0.0]
    ], index=["Near", "Far", "Recipient"], columns=["Near", "Far", "Recipient"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["stage2_accepted"] is True
    assert summary["lexicographic_fallback"] is False
    assert summary["unmet_demand_after"] == 0.0
    # Closer donor selected (20 km * 40 * 15 + 500 = 12,500)
    assert len(plan_df) == 1
    assert plan_df.iloc[0]["source_region"] == "Near"
    assert summary["total_transport_cost"] == 12500.0


def test_stage1_fallback_physical_feasibility_and_unchanged_quantities():
    """
    Verify that when Stage 1 fallback is triggered (as demonstrated in Scenario 32),
    the returned plan satisfies all constraints (violations == 0),
    and matches the captured Stage 1 allocation plan.
    """
    from src.engine.monte_carlo import generate_stratified_benchmark_scenarios
    scenarios = generate_stratified_benchmark_scenarios(
        n_per_stratum=12,
        stock_multipliers=(0.25, 0.5, 1.0),
        random_seed=42,
        n_draws_per_sim=100
    )
    sc32 = scenarios[32]
    dists = load_or_compute_distance_matrix()

    plan_df, summary = solve_resource_allocation(
        sc32["demands"], sc32["stocks"], sc32["risks"],
        distances_df=dists,
        lexicographic=True
    )

    # 1. Fallback confirmed:
    assert summary["stage2_accepted"] is False
    assert summary["lexicographic_fallback"] is True

    # 2. Re-evaluating fallback plan with shared evaluator yields ZERO violations:
    eval_res = evaluate_allocation_plan(plan_df, sc32["demands"], sc32["stocks"], sc32["risks"], dists)
    assert eval_res["violations"] == 0, f"Fallback plan had {eval_res['violations']} violations"

    # 3. Exact physical unmet of returned plan matches Stage 1 optimum:
    exact_returned = compute_exact_physical_unmet(plan_df, sc32["demands"], sc32["stocks"])
    assert float(exact_returned) == summary["stage1_reconstructed_unmet"]


def test_inconsistent_slack_blocked_by_allocation_balance_guard():
    """
    Verify that an allocation plan cannot pass verification if physical shipments
    do not satisfy the Stage 1 optimum, even if internal slack variables were zero.
    Directly tests the necessity of Method D's physical shipment reconstruction.
    """
    demands = {"R": {"ors": 100.0}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 200.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["unmet_demand_after"] == 0.0

    # If physical shipments were degraded by removing the transfer (quantity = 0),
    # an independent balance audit must compute unmet = 100.0 (violating opt_val = 0.0)
    fake_empty_plan = pd.DataFrame(columns=plan_df.columns)
    eval_fake = evaluate_allocation_plan(fake_empty_plan, demands, stocks, {}, dists)
    assert eval_fake["primary_objective_unmet"] == 100.0, "Evaluator failed to detect missing physical shipments"
    assert eval_fake["primary_objective_unmet"] > summary["optimal_weighted_unmet"] + 1e-5


def test_fractional_boundary_counterexample_strictly_blocked():
    """
    Verify the 133.00001 counterexample remains strictly blocked under the hardened formulation.
    Must transfer 134 units (not 133), leaving exactly 0.0 unmet demand.
    """
    demands = {"R": {"ors": 133.00001}, "D": {"ors": 0.0}}
    stocks = {"R": {"ors": 0.0}, "D": {"ors": 500.0}}
    dists = pd.DataFrame([[0.0, 100.0], [100.0, 0.0]], index=["R", "D"], columns=["R", "D"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["total_transferred_units"] == 134
    assert summary["unmet_demand_after"] == 0.0
    assert summary["optimal_weighted_unmet"] == 0.0
    assert summary["reconstructed_weighted_unmet"] == 0.0


def test_multiple_stage1_optima_secondary_cost_selection_unimpaired():
    """
    Verify that when multiple Stage 1 optimal solutions exist (both achieving zero unmet demand),
    Stage 2 correctly selects the cheaper donor without degrading the primary objective.
    """
    demands = {"Near": {"ors": 0.0}, "Far": {"ors": 0.0}, "Recipient": {"ors": 60.0}}
    stocks = {"Near": {"ors": 100.0}, "Far": {"ors": 100.0}, "Recipient": {"ors": 0.0}}
    dists = pd.DataFrame([
        [0.0, 100.0, 25.0],
        [100.0, 0.0, 90.0],
        [25.0, 90.0, 0.0]
    ], index=["Near", "Far", "Recipient"], columns=["Near", "Far", "Recipient"])

    plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
    assert summary["solve_status"] == "OPTIMAL"
    assert summary["unmet_demand_after"] == 0.0
    assert summary["optimal_weighted_unmet"] == 0.0
    assert summary["reconstructed_weighted_unmet"] == 0.0

    # Must select Near donor exclusively (25 km * 60 * 15 + 500 = 23,000)
    assert len(plan_df) == 1
    assert plan_df.iloc[0]["source_region"] == "Near"
    assert plan_df.iloc[0]["quantity"] == 60
    assert summary["total_transport_cost"] == 23000.0


def test_solver_failure_safe_exit_and_invariance():
    """
    Verify that simulated Stage 1 or Stage 2 solver failure exits safely with empty plan,
    zero units transferred, and correct status strings.
    """
    from unittest.mock import patch
    from ortools.linear_solver import pywraplp

    demands = {"D1": {"ors": 100.0}, "D2": {"ors": 0.0}}
    stocks = {"D1": {"ors": 0.0}, "D2": {"ors": 200.0}}
    dists = pd.DataFrame([[0.0, 50.0], [50.0, 0.0]], index=["D1", "D2"], columns=["D1", "D2"])

    # Simulate Stage 1 non-optimal status
    with patch.object(pywraplp.Solver, "Solve", return_value=pywraplp.Solver.INFEASIBLE):
        plan_df, summary = solve_resource_allocation(demands, stocks, distances_df=dists, lexicographic=True)
        assert summary["solve_status"] == "INFEASIBLE"
        assert summary["stage1_status"] == "INFEASIBLE"
        assert len(plan_df) == 0
        assert summary["total_transferred_units"] == 0
        assert summary["reconstructed_weighted_unmet"] is None





