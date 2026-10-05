# Disaster Healthcare AI: 5-Minute Full-Stack Viva Presentation & Demo Script

This script guides project authors through a structured, 5-minute live examination demonstration of the **React + TypeScript + FastAPI** production stack.

---

## ⏱️ Timeline & Agenda Overview

- **Minute 0:00 – 1:00**: System Architecture, JWT Role-Based Auth & Provenance Policy
- **Minute 1:00 – 2:00**: 35-District Geospatial Choropleth & Real Demographics (`/` Overview)
- **Minute 2:00 – 3:00**: Stochastic Surge Simulator with Population Capping (`/simulator`)
- **Minute 3:00 – 4:00**: Multi-Objective OR-Tools SCIP Allocation & Cost Index (`/allocation`)
- **Minute 4:00 – 4:45**: SHA-256 Cryptographic Audit Ledger & Safety Interlock (`/governance`)
- **Minute 4:45 – 5:00**: Scientific Limitations, Honest Benchmarks & Conclusion (`/limitations`)

---

## 🚀 Step-by-Step Live Demonstration

### 1. Architectural Setup & JWT Authentication (Minute 0:00 – 1:00)

**Presenter Setup**:
Ensure backend and frontend are running:
```bash
# Terminal 1: FastAPI Backend
uvicorn api.main:app --port 8000

# Terminal 2: React Vite Frontend
cd frontend && npm run dev
```
Open browser at `http://localhost:5173`.

**Presenter Action**:
1. Click **"Login"** in the top navigation bar.
2. Enter username `officer` and password `officer123` (or click the quick-login badge for `officer`).
3. Point out the JWT token exchange, persistent session, and the `[OFFICER]` role badge in the navbar.

**Talking Points**:
> *"Good morning, esteemed examiners. Today we present an explainable, uncertainty-aware, full-stack decision-support platform for disaster healthcare logistics across Maharashtra's 35 districts.*  
> *Our architecture combines a high-performance FastAPI backend with an interactive React and TypeScript frontend, secured by JWT Role-Based Access Control.*  
> *Central to our scientific contribution is complete data provenance: every single number in the system is explicitly badged as REAL, ESTIMATED, or ASSUMED to eliminate data fabrication."*

---

### 2. Regional Overview & Real Boundary Choropleth (Minute 1:00 – 2:00)

**Presenter Action**:
1. Navigate to **Regional Overview** (`/`).
2. Show the KPI summary cards: 131.9M population (`REAL`), 4,767 health facilities (`REAL`), and 11,571 ICU beds (`ESTIMATED`).
3. Hover over districts on the interactive Leaflet choropleth map (e.g., Pune, Mumbai Suburban, Thane).
4. Click on **Pune** to filter the district demographic drawer.

**Talking Points**:
> *"Here on the Regional Overview, our geospatial layer renders real detailed district boundary polygons (median 899 vertices per district) extracted from government census records, replacing crude rectangular bounding boxes.*  
> *District population is derived from raw WorldPop 2020 1km constrained raster zonal sums totaling 131.9 million. We openly disclose a 5.97% gap compared to the 124.5M government projection rather than artificially rescaling the telemetry.*  
> *Hospital facility counts (4,767 facilities) are grounded in the National Health Portal India directory, while ICU capacities are estimated from state audit anchors."*

---

### 3. Stochastic Simulator with Population Capping (Minute 2:00 – 3:00)

**Presenter Action**:
1. Navigate to **Simulator** (`/simulator`).
2. Select Epicentre: `Pune`, Hazard: `Flood`, Severity: `1.2`, Planning Level: `P75`.
3. Set Safety Reserve to `60%`.
4. Click **"Run 2,000-Draw Monte-Carlo Simulation"**.
5. Highlight the casualty projection, population cap confirmation (`min(affected, district_pop)`), and the medicine shortage breakdown.

**Talking Points**:
> *"In a disaster surge, demand is stochastic, not deterministic. Our simulator samples 2,000 Monte-Carlo draws from log-normal casualty distributions against WHO IEHK 2017 and Sphere clinical consumption guidelines.*  
> *Critically, we enforce a strict physical invariant: simulated casualties are capped at total district population via `min(affected, district_pop)`, preventing runaway synthetic artifacts.*  
> *Planning levels (P50, P75, P90) allow emergency planners to choose risk tolerances based on incident severity."*

---

### 4. Multi-Objective OR-Tools SCIP Optimization (Minute 3:00 – 4:00)

**Presenter Action**:
1. Navigate to **Resource Allocation** (`/allocation`).
2. Submit an allocation optimization for `Pune` with `Flood` severity `1.0`.
3. Point out the SCIP solver execution time (~300ms) and the generated transfer route table.
4. Highlight the **Cost Index** metric, active route count, and zero safety violations.

**Talking Points**:
> *"Once shortages are identified, we redistribute resources using Google OR-Tools SCIP Mixed-Integer Programming solver.*  
> *The solver enforces 5 non-negotiable safety constraints:*
> 1. *60% safety reserves: source districts must retain 60% of their local demand.*
> 2. *High-risk export ban: districts facing high shortages cannot export stock.*
> 3. *Perishables transit limit: blood units are strictly restricted to routes $\le 150\text{ km}$.*
> 4. *Integer shipment packs: preventing partial pill or fractional vial transfers.*
> 5. *Non-negative stock balance.*  
> *Notice our cost metric: we strictly report a unitless **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$), never currency, because road freight contracts vary wildly across public agencies."*

---

### 5. Cryptographic Governance & Safety Interlock (Minute 4:00 – 4:45)

**Presenter Action**:
1. Navigate to **Governance & Audit** (`/governance`).
2. Point out the SHA-256 hash-chained ledger table with genesis block and prior block linking.
3. In the review panel, show an approval submission with low confidence (< 0.60): show the safety guard blocking approval (HTTP 409 Conflict).
4. Enter an approval with confidence `0.85`, reason `ROUTINE_ACCEPTANCE`, and submit.
5. Click **"Re-Verify Chain"** to demonstrate instantaneous cryptographic validation.

**Talking Points**:
> *"In safety-critical healthcare AI, human accountability is paramount.*  
> *Every officer decision is cryptographically sealed into a SHA-256 hash-chained ledger: $H_k = \text{SHA256}(H_{k-1} \parallel \text{action} \parallel \text{user} \parallel \text{timestamp} \parallel \text{scenario})$.*  
> *If any past database record is modified, the hash chain breaks instantly, alerting auditors.*  
> *Furthermore, our API enforces an automated safety guard: it strictly blocks autonomous approval if scenario prediction confidence is below 0.60, requiring clinical modification or escalation."*

---

### 6. Scientific Limitations & Conclusion (Minute 4:45 – 5:00)

**Presenter Action**:
1. Navigate to **Limitations & Ethics** (`/limitations`).
2. Review the transparent disclosures: fat-tailed disaster data, the $\rho \approx 0.52$ ranking vs extreme outlier underestimation, and proxy bed allocations.

**Talking Points**:
> *"To conclude, we emphasize scientific honesty over exaggerated claims:*  
> *Our impact model achieves a strong Spearman rank correlation ($\rho \approx 0.52$) across 512 historical CRED EM-DAT disaster events, proving it reliably ranks district risk priorities. However, due to the extreme fat tails of natural disasters, extreme outliers can exceed median point estimates by 30 to 150 times.*  
> *Our platform is therefore designed as an explainable, uncertainty-bounded decision aid—never an autonomous replacement for clinical logistics officers.*  
> *Thank you. We welcome your questions."*
