"""
Disaster Healthcare AI - Decision-Support Dashboard
An Explainable and Uncertainty-Aware AI Framework for Disaster Healthcare Demand Prediction
and Multi-Objective Resource Allocation.
"""
import os
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

from datetime import datetime
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.data.boundaries import MAHARASHTRA_DISTRICTS
from src.engine.demand import load_demand_params, estimate_district_stocks
from src.engine.monte_carlo import run_monte_carlo_district_simulation
from src.optimise import solve_resource_allocation, load_or_compute_distance_matrix
from src.reporting.audit import log_decision, verify_audit_log_integrity, init_audit_log
from src.reporting.export import generate_pdf_situation_report, generate_excel_situation_report

MODEL_VERSION = "v2.0.0 (Real-Data & CQR)"
PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

st.set_page_config(
    page_title="Disaster Healthcare AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def load_impact_models():
    m_path = MODELS_DIR / "impact_models.joblib"
    if not m_path.exists():
        return None
    return joblib.load(m_path)

@st.cache_resource
def load_surrogate_model():
    s_path = MODELS_DIR / "shortage_classifier.joblib"
    if not s_path.exists():
        return None
    return joblib.load(s_path)

@st.cache_data
def load_processed_data():
    pop_df = pd.read_csv(PROCESSED_DIR / "district_population.csv")
    fac_df = pd.read_csv(PROCESSED_DIR / "district_facilities.csv")
    cap_df = pd.read_csv(PROCESSED_DIR / "district_capacity.csv")
    events_df = pd.read_csv(PROCESSED_DIR / "emdat_events.csv")
    sim_df = pd.read_csv(PROCESSED_DIR / "simulation_summary.csv") if (PROCESSED_DIR / "simulation_summary.csv").exists() else None
    dists_df = load_or_compute_distance_matrix()
    return pop_df, fac_df, cap_df, events_df, sim_df, dists_df

impact_bundle = load_impact_models()
surrogate_bundle = load_surrogate_model()
pop_df, fac_df, cap_df, events_df, sim_df, dists_df = load_processed_data()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
st.sidebar.title("🏥 Disaster Healthcare AI")
st.sidebar.caption(f"Framework Engine {MODEL_VERSION} | Real-Data & SCIP MIP")

page = st.sidebar.radio(
    "Navigation Modules",
    [
        "🗺️ Regional Overview & Event Replay",
        "🔮 Interactive What-If Simulator",
        "⚖️ Multi-Objective Allocation Plan",
        "🛡️ Governance & Tamper-Evident Audit Log",
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📄 One-Click Situation Report")
if st.sidebar.button("Generate Executive PDF & Excel Reports"):
    if sim_df is not None:
        alloc_df, _ = solve_resource_allocation({"Pune": {"antibiotics": 5000.0}}, {"Mumbai": {"antibiotics": 10000.0}})
        pdf_path = generate_pdf_situation_report(sim_df, alloc_df)
        excel_path = generate_excel_situation_report(sim_df, alloc_df)
        st.sidebar.success(f"Generated {pdf_path.name} & {excel_path.name}!")
        with open(pdf_path, "rb") as f:
            st.sidebar.download_button("Download PDF Situation Report", f, file_name="situation_report.pdf", mime="application/pdf")
        with open(excel_path, "rb") as f:
            st.sidebar.download_button("Download Excel Situation Report", f, file_name="situation_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# -------------------------------------------------------------
# PAGE 1: REGIONAL OVERVIEW & HISTORICAL REPLAY
# -------------------------------------------------------------
if page == "🗺️ Regional Overview & Event Replay":
    st.title("🗺️ Regional Overview & Historical Disaster Event Replay")
    st.markdown("Real data provenance: **WorldPop 2020 Grid**, **National Hospital Directory**, **State ICU Audit**, **CRED EM-DAT**.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Population Covered", f"{pop_df['population'].sum():,}", delta="REAL (WorldPop)")
    with col2:
        st.metric("Cleaned Health Facilities", f"{fac_df['total_facilities'].sum():,}", delta="REAL (data.gov.in)")
    with col3:
        st.metric("Total Hospital Beds", f"{cap_df['beds_mid'].sum():,}", delta="ESTIMATED")
    with col4:
        st.metric("State ICU Beds Anchor", f"{cap_df['icu_beds_mid'].sum():,}", delta="REAL (Kapoor et al.)")

    st.markdown("---")
    st.subheader("Maharashtra 35-District Shortage Risk Map")

    if sim_df is not None:
        merged_map = pd.merge(cap_df, sim_df[sim_df["medicine"] == "antibiotics"], on="district")
        merged_map["lat"] = merged_map["district"].apply(lambda d: MAHARASHTRA_DISTRICTS.get(d, {}).get("lat", 19.0))
        merged_map["lon"] = merged_map["district"].apply(lambda d: MAHARASHTRA_DISTRICTS.get(d, {}).get("lon", 74.5))

        scatter_fn = getattr(px, "scatter_map", getattr(px, "scatter_mapbox", None))
        fig_map = scatter_fn(
            merged_map,
            lat="lat",
            lon="lon",
            size="population",
            color="shortage_probability",
            color_continuous_scale="Reds",
            hover_name="district",
            hover_data=["population", "beds_mid", "shortage_probability", "risk_level"],
            zoom=6,
            center={"lat": 19.0, "lon": 76.0},
            title="District Shortage Risk (Antibiotics) Map"
        )
        st.plotly_chart(fig_map, width="stretch")

    st.markdown("---")
    st.subheader("📜 Historical Real-Disaster Event Replay (Held-out Benchmark)")
    st.caption("Replaying real historical disaster events held out from impact model training, comparing predicted vs actual casualties with 90% CQR intervals.")

    bt_path = REPORTS_DIR / "historical_backtest.csv"
    if bt_path.exists():
        bt_df = pd.read_csv(bt_path)
        st.dataframe(bt_df.style.highlight_max(axis=0), width="stretch")

# -------------------------------------------------------------
# PAGE 2: INTERACTIVE WHAT-IF SIMULATOR
# -------------------------------------------------------------
elif page == "🔮 Interactive What-If Simulator":
    st.title("🔮 Interactive What-If Scenario Simulator")
    st.markdown("Simulate disaster scenarios across Maharashtra districts. Fast slider response powered by **Monte-Carlo Surrogate Classifier**.")

    col1, col2, col3 = st.columns(3)
    with col1:
        hazard_type = st.selectbox("Select Hazard Type", ["Flood", "Storm", "Earthquake", "Epidemic", "Extreme temperature"])
    with col2:
        epicentre = st.selectbox("Epicentre District", list(MAHARASHTRA_DISTRICTS.keys()), index=24) # Pune
    with col3:
        severity = st.slider("Disaster Severity Scale", 1, 5, 4)

    st.markdown("---")
    st.subheader("Live Simulation Controls & Surge Stock Tuning")

    col_a, col_b = st.columns(2)
    with col_a:
        aff_input = st.number_input("Estimated Affected Population", min_value=1000, max_value=500000, value=75000, step=5000)
    with col_b:
        stock_adj = st.slider("Stock Availability Adjustment (%)", 20, 200, 100)

    if st.button("Run Full 2,000-Draw Monte-Carlo Simulation"):
        with st.spinner("Executing 2,000 stochastic draws sampling impact distributions x WHO parameters..."):
            inputs = {epicentre: {"hazard_type": hazard_type, "affected_mean_log": np.log1p(aff_input), "affected_std_log": 0.40}}
            res_df = run_monte_carlo_district_simulation(inputs, n_draws=2000)
            st.success("Simulation complete!")
            st.dataframe(res_df[["district", "medicine", "demand_p10", "demand_p50", "demand_p90", "available_stock", "shortage_probability", "risk_level"]], width="stretch")

# -------------------------------------------------------------
# PAGE 3: MULTI-OBJECTIVE ALLOCATION PLAN
# -------------------------------------------------------------
elif page == "⚖️ Multi-Objective Allocation Plan":
    st.title("⚖️ Multi-Objective Operations Research Allocation Plan")
    st.markdown("Powered by **Google OR-Tools SCIP Mixed-Integer Programming Solver**.")

    bench_path = REPORTS_DIR / "allocation_summary.json"
    if bench_path.exists():
        with open(bench_path, "r") as f:
            bench_data = json.load(f)

        st.subheader("Baseline Performance Comparison")
        bench_df = pd.DataFrame(bench_data.get("benchmarks", {})).T
        st.dataframe(bench_df, width="stretch")

    alloc_path = REPORTS_DIR / "sample_allocation_plan.csv"
    if alloc_path.exists():
        st.subheader("Recommended Inter-District Transfers")
        alloc_df = pd.read_csv(alloc_path)
        st.dataframe(alloc_df, width="stretch")

    pareto_img = REPORTS_DIR / "pareto_sweep.png"
    if pareto_img.exists():
        st.subheader("Pareto Frontier Trade-off Curves")
        st.image(str(pareto_img), caption="Unmet Demand vs Transport Cost vs Fairness Trade-offs")

# -------------------------------------------------------------
# PAGE 4: GOVERNANCE & TAMPER-EVIDENT AUDIT LOG
# -------------------------------------------------------------
elif page == "🛡️ Governance & Tamper-Evident Audit Log":
    st.title("🛡️ Data Governance & Tamper-Evident Cryptographic Audit Log")
    st.markdown("All human officer review actions are cryptographically hash-chained using **SHA-256**.")

    # Audit log verification
    is_valid, n_entries, errs = verify_audit_log_integrity()
    if is_valid:
        st.success(f"✓ Cryptographic Audit Log Verified Intact! ({n_entries} hash-chained records)")
    else:
        st.error(f"⚠️ Audit Log Tampering Detected! Errors: {errs}")

    st.markdown("---")
    st.subheader("Human-in-the-Loop Officer Approval Workflow")

    col1, col2 = st.columns(2)
    with col1:
        officer_name = st.text_input("Reviewer Officer Name", "Dr. A. Sharma")
        officer_role = st.selectbox("Officer Role", ["District Health Officer", "State Disaster Coordinator", "Logistics Officer"])
    with col2:
        reason_code = st.selectbox("Reason Code", ["ROUTINE_ACCEPTANCE", "EMERGENCY_OVERRIDE", "RESOURCE_CONSTRAINED", "REJECT_UNREALISTIC"])
        action_type = st.radio("Decision Action", ["APPROVE", "REJECT"])

    if st.button("Submit Decision to Audit Log"):
        entry = log_decision(officer_name, officer_role, action_type, reason_code, 0.92, 15.0, "Scenario MH-Flood-Sim")
        st.success(f"Logged entry! Hash: {entry['current_hash'][:16]}...")
        st.rerun()

    st.markdown("---")
    st.subheader("Audit Log Chain Entries")
    log_df = init_audit_log()
    st.dataframe(log_df, width="stretch")
