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

from src.data.boundaries import load_or_create_district_boundaries, MAHARASHTRA_DISTRICTS
from src.engine.demand import load_demand_params, estimate_district_stocks, get_impact_sigma
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
        "MAP_OVERVIEW",
        "SIMULATOR",
        "ALLOCATION",
        "GOVERNANCE",
        "PROVENANCE",
    ],
    format_func=lambda x: {
        "MAP_OVERVIEW": "🗺️ Regional Overview & Event Replay",
        "SIMULATOR": "🔮 Interactive What-If Simulator",
        "ALLOCATION": "⚖️ Multi-Objective Allocation Plan",
        "GOVERNANCE": "🛡️ Governance & Tamper-Evident Audit Log",
        "PROVENANCE": "📋 Data Sources & Provenance Registry"
    }[x]
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
if page == "MAP_OVERVIEW":
    st.title("🗺️ Regional Overview & Real Polygon Shortage Map")
    
    st.info("💡 **Methodological Note**: The impact prediction model supports relative risk ranking across districts/events, not exact casualty magnitudes.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Population (WorldPop)", f"{pop_df['population'].sum():,}", help="Tag: REAL (1km constrained raster zonal sum)")
    with col2:
        st.metric("Cleaned Health Facilities", f"{fac_df['total_facilities'].sum():,}", help="Tag: REAL (National Health Portal data.gov.in)")
    with col3:
        st.metric("State Total Hospital Beds", f"{cap_df['beds_mid'].sum():,}", help="Tag: ESTIMATED (Scaled from 144,983 state anchor)")
    with col4:
        st.metric("State ICU Beds Anchor", f"{cap_df['icu_beds_mid'].sum():,}", help="Tag: REAL (Kapoor et al. 2020 State Audit)")

    st.markdown("---")
    st.subheader("Maharashtra 35-District Shortage Risk Choropleth (Real Geometry)")

    gdf = load_or_create_district_boundaries()
    geojson_data = json.loads(gdf.to_json())

    if sim_df is not None:
        med_sel = st.selectbox("Select Medicine Class for Risk Map", ["antibiotics", "ors", "iv_fluids", "analgesics", "blood_units"])
        map_df = pd.merge(cap_df, sim_df[sim_df["medicine"] == med_sel], on="district")

        fig_map = px.choropleth(
            map_df,
            geojson=geojson_data,
            locations="district",
            featureidkey="properties.district",
            color="shortage_probability",
            color_continuous_scale="Reds",
            hover_name="district",
            hover_data=["population", "beds_mid", "shortage_probability", "risk_level"],
            title=f"District Shortage Probability ({med_sel.title()}) [REAL Geometry]"
        )
        fig_map.update_geos(fitbounds="locations", visible=False)
        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
        st.plotly_chart(fig_map, width="stretch")

    st.markdown("---")
    st.subheader("📜 Historical Real-Disaster Event Replay (EM-DAT Benchmark)")
    bt_path = REPORTS_DIR / "historical_backtest.csv"
    if bt_path.exists():
        bt_df = pd.read_csv(bt_path)
        st.dataframe(bt_df, width="stretch")

# -------------------------------------------------------------
# PAGE 2: INTERACTIVE WHAT-IF SIMULATOR
# -------------------------------------------------------------
elif page == "SIMULATOR":
    st.title("🔮 Interactive What-If Scenario Simulator")
    st.info("💡 **Methodological Note**: Model outputs provide decision support for resource prioritization; demand rates are derived from WHO IEHK / Sphere standards (ASSUMED).")

    col1, col2, col3 = st.columns(3)
    with col1:
        hazard_type = st.selectbox("Select Hazard Type", ["Flood", "Storm", "Earthquake", "Epidemic", "Extreme temperature"])
    with col2:
        epicentre = st.selectbox("Epicentre District", list(MAHARASHTRA_DISTRICTS.keys()), index=24) # Pune
    with col3:
        aff_input = st.number_input("Estimated Affected Population", min_value=1000, max_value=500000, value=75000, step=5000)

    st.markdown("---")
    if st.button("Run 2,000-Draw Monte-Carlo Simulation"):
        with st.spinner("Executing 2,000 stochastic draws sampling impact distributions x WHO parameters..."):
            inputs = {epicentre: {"hazard_type": hazard_type, "affected_mean_log": np.log1p(aff_input), "affected_std_log": get_impact_sigma("model_prediction")}}
            res_df = run_monte_carlo_district_simulation(inputs, n_draws=2000)
            st.success("Simulation complete!")
            st.dataframe(res_df[["district", "medicine", "demand_p10", "demand_p50", "demand_p75", "demand_p90", "available_stock", "shortage_probability", "risk_level"]], width="stretch")

# -------------------------------------------------------------
# PAGE 3: MULTI-OBJECTIVE ALLOCATION PLAN
# -------------------------------------------------------------
elif page == "ALLOCATION":
    st.title("⚖️ Multi-Objective Operations Research Allocation Plan")
    st.markdown("Powered by **Google OR-Tools SCIP Mixed-Integer Programming Solver**.")

    comp_csv = REPORTS_DIR / "baseline_comparison.csv"
    if comp_csv.exists():
        st.subheader("Baseline Performance Comparison (20 Monte-Carlo Scenarios)")
        comp_df = pd.read_csv(comp_csv)
        st.dataframe(comp_df, width="stretch")

    plot_img = REPORTS_DIR / "baseline_comparison_plot.png"
    if plot_img.exists():
        st.subheader("Multi-Objective Tradeoff: Unmet Demand vs. Transport Cost")
        st.image(str(plot_img), caption="Mean Unmet Demand vs Transport Cost across 20 Scenarios (Shared Evaluator)")

    alloc_path = REPORTS_DIR / "sample_allocation_plan.csv"
    if alloc_path.exists():
        st.subheader("Recommended Inter-District Transfers")
        alloc_df = pd.read_csv(alloc_path)
        st.dataframe(alloc_df, width="stretch")

# -------------------------------------------------------------
# PAGE 4: GOVERNANCE & TAMPER-EVIDENT AUDIT LOG
# -------------------------------------------------------------
elif page == "GOVERNANCE":
    st.title("🛡️ Data Governance & Tamper-Evident Cryptographic Audit Log")
    st.markdown("All human officer review actions are cryptographically hash-chained using **SHA-256**.")

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

    st.markdown("---")
    st.subheader("Audit Log Chain Entries")
    log_df = init_audit_log()
    st.dataframe(log_df, width="stretch")

# -------------------------------------------------------------
# PAGE 5: DATA SOURCES & PROVENANCE REGISTRY
# -------------------------------------------------------------
elif page == "PROVENANCE":
    st.title("📋 Data Sources & Provenance Registry")
    st.markdown("Every table column and metric carries a verified provenance classification.")

    prov_records = [
        {"Dataset / Field": "EM-DAT Historical Disaster Catalogue", "Tag": "REAL", "Source": "CRED EM-DAT International Disaster Database (1900-2026)", "Details": "810 India disaster events; target casualties non-imputed"},
        {"Dataset / Field": "WorldPop Population Zonal Sums", "Tag": "REAL", "Source": "WorldPop 2020 1km Constrained Raster Grid", "Details": "Raw zonal sums for 35 districts; Total 131.9M vs 124.5M projection"},
        {"Dataset / Field": "National Hospital Directory Facilities", "Tag": "REAL", "Source": "National Health Portal India (data.gov.in)", "Details": "4,767 Maharashtra facilities classified public/private"},
        {"Dataset / Field": "State ICU Bed Capacity Anchor", "Tag": "REAL", "Source": "Kapoor et al. (2020) / NHP State Audit", "Details": "Maharashtra: 2,572 public / 9,015 private / 11,587 total ICU beds"},
        {"Dataset / Field": "District Hospital Bed Capacity", "Tag": "ESTIMATED", "Source": "State ICU Anchor + Facility Count Allocation", "Details": "Scaled from 144,983 state total bed anchor across 35 districts"},
        {"Dataset / Field": "Epidemiological Consumption Rates", "Tag": "ASSUMED", "Source": "WHO Interagency Emergency Health Kit (IEHK 2017) & Sphere Norms", "Details": "Daily per-patient medicine consumption rates and epidemic durations"},
        {"Dataset / Field": "Road Distance Matrix", "Tag": "ASSUMED", "Source": "Haversine Distance x 1.3 Circuity Factor", "Details": "Road transport distance matrix between 35 district centroids"}
    ]

    prov_df = pd.DataFrame(prov_records)
    st.dataframe(prov_df, width="stretch")

    metrics_path = REPORTS_DIR / "metrics.json"
    if metrics_path.exists():
        st.markdown("---")
        st.subheader("Model Evaluation & Calibration Summary (`reports/metrics.json`)")
        with open(metrics_path, "r") as f:
            m_data = json.load(f)
        st.json(m_data)
