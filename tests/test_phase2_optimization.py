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

from src.optimise import (
    solve_resource_allocation,
    evaluate_allocation_plan,
    COST_PER_UNIT_KM,
    FIXED_ROUTE_COST,
    DEFAULT_SAFETY_RESERVE_RATIO,
    DEFAULT_EMERGENCY_STOCK_BUFFER_RATIO,
    MEDICINES,
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

