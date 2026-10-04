# Disaster Healthcare AI: 5-Minute Live Presentation & Demo Script

This script guides project authors through a 5-minute live demonstration during viva examinations, project defenses, or technical reviews.

---

## ⏱️ Timeline & Agenda Overview

- **Minute 0:00 – 1:00**: Problem Statement, Real-Data Architecture & Pipeline Quickstart
- **Minute 1:00 – 2:00**: Regional Overview Map & Real Boundary GeoJSON Choropleth (`app.py` Page 1)
- **Minute 2:00 – 3:00**: Interactive What-If Scenario Simulator & Fast Surrogate Classifier (`app.py` Page 2)
- **Minute 3:00 – 4:00**: Multi-Objective OR-Tools SCIP Optimization & Baseline Benchmarking (`app.py` Page 3)
- **Minute 4:00 – 5:00**: SHA-256 Hash-Chained Audit Log Governance & Automated Report Export (`app.py` Page 4)

---

## 🚀 Step-by-Step Presentation Guide

### 1. Terminal Setup & Pipeline Launch (Minute 0:00 – 1:00)
**Presenter Action**: Open terminal in project root directory and run full pipeline:
```bash
# Execute end-to-end pipeline
python run_all.py

# Verify test suite
pytest -q

# Launch decision-support dashboard
streamlit run app.py
```
**Talking Points**:
> *"Good morning. Today we present an explainable and uncertainty-aware AI framework for disaster healthcare demand prediction and multi-objective resource allocation across Maharashtra's 35 districts.*  
> *Unlike semi-synthetic prototypes, our entire pipeline is grounded in real public data: CRED EM-DAT historical disaster events, WorldPop 2020 1km constrained population rasters, National Health Portal India facility directories, and official State ICU bed audits. Every metric carries verified data provenance tagged as REAL, ESTIMATED, or ASSUMED."*

---

### 2. Regional Overview & Real Polygon Choropleth (Minute 1:00 – 2:00)
**Presenter Action**: Navigate to **`🗺️ Regional Overview & Event Replay`** in Streamlit sidebar.
**Talking Points**:
> *"Here on the Regional Overview page, we see macro metrics computed directly from real datasets: 131.9M population extracted via raster zonal sums across 35 district boundary polygons, 4,767 cleaned health facilities, and 11,587 state ICU beds.*  
> *Notice our 35-district interactive shortage risk choropleth map. It uses real detailed district boundary polygons from census data (median 899 vertices per polygon). We also highlight our methodological disclaimer: the ML impact model provides relative risk ranking across districts, rather than exact casualty point-estimates."*

---

### 3. Interactive What-If Scenario Simulator (Minute 2:00 – 3:00)
**Presenter Action**: Navigate to **`🔮 Interactive What-If Simulator`** in sidebar. Select `Flood` hazard in `Pune` district and click **Run 2,000-Draw Monte-Carlo Simulation**.
**Talking Points**:
> *"In a live disaster emergency, health logistics officers need instant scenario evaluation. Our simulator runs 2,000 stochastic Monte-Carlo draws sampling log-normal casualty distributions against WHO IEHK 2017 and Sphere Handbook clinical consumption standards.*  
> *To achieve sub-5ms slider response times without sacrificing rigor, we trained a Random Forest surrogate classifier over 500 diverse Monte-Carlo scenarios split strictly BY SCENARIO ID, achieving 98.27% held-out scenario fidelity and low Expected Calibration Error (0.0393)."*

---

### 4. OR-Tools SCIP Optimization & Baseline Comparison (Minute 3:00 – 4:00)
**Presenter Action**: Navigate to **`⚖️ Multi-Objective Allocation Plan`** in sidebar.
**Talking Points**:
> *"Once shortages are identified, how do we redistribute supplies across districts safely? We model resource allocation as a multi-commodity network flow MIP solved using Google OR-Tools SCIP solver.*  
> *Our solver enforces 5 critical real-world safety constraints: 60% source safety reserves, high-risk export prohibitions, 150 km perishables transit limits for blood units, integer pack sizes, and non-negative stock.*  
> *In a 20-scenario benchmark evaluating 5 methods under a shared evaluator and unified cost function ($\text{unit\_km} \times 15.0 + \text{routes} \times 500.0$), OR-Tools SCIP achieved the lowest mean unmet demand (20,829 units vs 465,298 for Greedy Nearest and 2.10M for No Redistribution), lowest active transport cost (10.49B INR), highest minimum coverage (57.8%), and zero rule violations."*

---

### 5. Cryptographic Audit Log & Situation Report Export (Minute 4:00 – 5:00)
**Presenter Action**: Navigate to **`🛡️ Governance & Tamper-Evident Audit Log`**. Submit an approval decision ("Dr. A. Sharma", "District Health Officer", "APPROVE", "ROUTINE_ACCEPTANCE"). Then click **Generate Executive PDF & Excel Reports** in sidebar.
**Talking Points**:
> *"For ethical AI governance, human officers remain in the loop. Every review decision is logged into a SHA-256 hash-chained audit log. If any past record is tampered with, the cryptographic chain verification immediately fails.*  
> *Finally, officers can generate one-click executive situation reports in PDF and Excel formats, complete with high-risk district priorities, recommended inter-district transfer routes, and complete data provenance disclosures.*  
> *Thank you. We are ready to answer your questions."*
