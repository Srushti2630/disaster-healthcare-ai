# Disaster Healthcare AI: 5-Minute Prototype Presentation & Live Demo Script

This script provides project authors with an exact, time-stamped, step-by-step walkthrough for presenting the live application to external examiners, viva review committees, and technical evaluators.

---

## ⏱️ 5-MINUTE PRESENTATION TIMELINE

```
+------------------+-------------------------------------------------------------+
| TIME WINDOW      | PRESENTATION TOPIC & SCREEN                                 |
+------------------+-------------------------------------------------------------+
| 0:00 - 1:00      | System Motivation, Stack Architecture & RBAC Login          |
| 1:00 - 2:00      | Regional Overview: Real Boundary Map & Data Provenance      |
| 2:00 - 3:00      | Disaster Simulation: Population Capping & SHAP Explainers   |
| 3:00 - 4:00      | SCIP MIP Optimization: Constraints & Inter-District Routes  |
| 4:00 - 5:00      | Cryptographic Governance Ledger, Chain Verification & Q&A   |
+------------------+-------------------------------------------------------------+
```

---

## 🚀 STEP-BY-STEP PRESENTATION SCRIPT

### Phase 1: Authentication & Role-Based Security (Minute 0:00 – 1:00)

**URL**: `http://localhost/login` (or `http://localhost:5173/login`)

#### Presenter Action:
1. Open the browser to `http://localhost/login`.
2. Point out the **"Pre-Configured System Accounts"** card above the login form.
3. Click the **`Officer`** button (this auto-fills `officer@example.com` and `Password123!`).
4. Click **Sign In**.
5. Notice the instant JWT token issue and the user role badge displayed in the top right of the navigation bar.

#### What to Say:
> *"Respected examiners, catastrophic disasters require rapid, coordinated healthcare logistics across entire states. Today we present **Disaster Healthcare AI**, an explainable, uncertainty-aware decision-support platform designed for Maharashtra's 35 districts.*  
> 
> *Our system is deployed as an isolated multi-container production stack: a FastAPI backend serving REST APIs, an Nginx reverse proxy, and a React 18 + TypeScript frontend.*  
> 
> *To protect disaster logistics from unauthorized interference, we enforce strict Role-Based Access Control (RBAC). Notice on our login screen that public self-registration is disabled—only administrators can provision accounts. We are logging in using our pre-configured Disaster Officer credentials."*

---

### Phase 2: Regional Overview & Data Provenance (Minute 1:00 – 2:00)

**URL**: `http://localhost/`

#### Presenter Action:
1. You are automatically redirected to the **Regional Overview** (`/`).
2. Point to the 4 Top KPI Cards:
   - **Total Population**: `131,936,179` with `[REAL]` badge.
   - **Total Cleaned Facilities**: `4,767` with `[REAL]` badge.
   - **Hospital Bed Baseline**: `144,983` with `[ESTIMATED]` badge.
   - **ICU Beds Anchor**: `11,587` with `[REAL]` badge.
3. Point to the **"Data Provenance & Empirical Grounding Architecture"** callout below the KPIs.
4. Interact with the 35-district Leaflet choropleth map: hover over **Pune**, **Mumbai**, or **Nagpur** to highlight district capacities.

#### What to Say:
> *"A critical priority of our research is scientific integrity: **zero fabricated numbers**.*  
> 
> *On this Regional Overview, every value carries an explicit Data Provenance badge:  
> - Our population count of 131.9 million is not an arbitrary estimate—it is extracted directly from **WorldPop 2020 100-meter high-resolution raster zonal statistics**.  
> - The 4,767 healthcare facilities are geocoded directly from the **National Health Portal India directory**.  
> - Our hospital and ICU beds are anchored to the official **National Health Profile** and **State ICU Bed Census**. Notice our transparent disclosure: disaggregating 11,587 ICU beds across 35 districts with integer rounding leaves an expected 16-bed residue (11,571 sum), achieving 99.87% mathematical fidelity.*  
> 
> *Our Leaflet map renders official Survey of India boundary polygons with complete topological fidelity."*

---

### Phase 3: What-If Disaster Simulation & Explainability (Minute 2:00 – 3:00)

**URL**: `http://localhost/simulator`

#### Presenter Action:
1. Click **Simulator** in the top navigation bar.
2. In the Scenario Setup form, select:
   - **Epicenter District**: `Pune`
   - **Hazard Type**: `Flood`
   - **Hazard Severity**: `1.5`
   - **Planning Level**: `P75 (Buffer Demand)`
3. Click **"Run Disaster Simulation"**.
4. Show the simulation results appearing in $<200\text{ ms}$:
   - Show the estimated casualties.
   - Point out the **Population Cap Guarantee**: simulated casualties are strictly capped by district population via `min(demand, population)`.
   - Scroll down to the **"Prediction Explanation Panel"** to show the **Tree-SHAP local feature attribution chart** and plain-English sentences.
5. Click the green button: **"Proceed to Optimal Allocation"**.

#### What to Say:
> *"Now let us simulate an active emergency. Disaster planners cannot rely on deterministic guesswork; they need uncertainty-bounded projections.*  
> 
> *Here we simulate a Severity 1.5 Flood in Pune at the P75 buffer planning level. Our backend executes regularized Ridge regression calibrated via Leave-One-Event-Out cross-validation on CRED EM-DAT disaster records.*  
> 
> *Notice our physical safety invariant: simulated casualties can never exceed the actual WorldPop resident count of the district.*  
> 
> *Furthermore, for clinical interpretability, the system computes **Tree-SHAP feature attributions**. It translates mathematical game theory into actionable medical explanations: showing exactly how Pune's urban population density increased predicted bed demand, and how regional historical vulnerability moderated the risk.*  
> 
> *Let us now proceed to optimal supply redistribution."*

---

### Phase 4: Multi-Objective SCIP Optimal Resource Allocation (Minute 3:00 – 4:00)

**URL**: `http://localhost/allocation`

#### Presenter Action:
1. On the Allocation page, point out that the simulation context is automatically linked.
2. In the Solver Parameters, show the **Safety Reserve Ratio** set to `60%`.
3. Click **"Solve SCIP Optimal Allocation"**.
4. The solver completes in **$<30\text{ ms}$**:
   - Status shows `OPTIMAL`.
   - Demand reduction: shows high percentage fulfillment.
   - Total Constraint Violations: **`0`**.
5. Show the **"Recommended Inter-District Transfers"** table:
   - Point out specific shipments (e.g., blood units, emergency beds).
   - Point out the **Distance (km)** and **Cost Index** formula.
   - Point out the **PENDING_REVIEW** banner with the unique Allocation ID and cryptographic plan hash.

#### What to Say:
> *"Once local deficits are identified, how do we redistribute supplies across districts safely?  
> 
> We model this as a multi-commodity network flow Mixed-Integer Program solved using the **Google OR-Tools SCIP solver**, returning optimal dispatches in under 30 milliseconds.*  
> 
> *The solver strictly guarantees 5 non-negotiable operational constraints:*
> 1. *Conservation of Supply: Total outgoing shipments cannot exceed available physical stock.*
> 2. *Donor Safety Reserve: Donor districts must retain at least 60% of their local emergency demand to prevent secondary vulnerabilities.*
> 3. *Perishables Transit Cutoff: Blood units are strictly restricted to routes of 150 km or less to safeguard cold-chain viability.*
> 4. *High-Risk Export Ban: Epicenter and high-risk districts are prohibited from exporting supplies.*
> 5. *Integrality: All transfer quantities are non-negative integers—preventing fractional beds or split ampoules.*  
> 
> *Notice our transport cost: we strictly report an abstract **Logistics Cost Index** ($15.0 \cdot \text{unit\_km} + 500.0 \cdot \text{routes}$), avoiding false precision in rupees because government disaster transit rates fluctuate widely."*

---

### Phase 5: Cryptographic Governance & Tamper-Evident Ledger (Minute 4:00 – 5:00)

**URL**: `http://localhost/governance`

#### Presenter Action:
1. Logout as Officer, and click **`Admin`** (`admin@example.com` / `Password123!`) $\to$ **Sign In**.
2. Navigate to **Governance** (`/governance`).
3. In the **"Pending Governance Approval Queue"**, click **"Inspect & Review"** on the allocation plan just created.
4. Modal pops up displaying the allocation summary, plan hash, and solver statistics.
5. In the Decision Confirmation:
   - Select Action: **`APPROVE`**
   - Reason Code: **`ROUTINE_ACCEPTANCE`**
   - Reviewer Notes: *"Reviewed by State Disaster Coordinator. Optimal SCIP plan approved for dispatch."*
6. Click **"Confirm & Sign Decision"**.
7. Modal closes, and the decision appears as the newest block in the **"Tamper-Evident Audit Ledger"** below.
8. Click **"Re-Verify Ledger Chain"** button: point to the green badge confirming *"All SHA-256 block hashes cryptographically valid"*.

#### What to Say:
> *"In safety-critical disaster healthcare, AI must advise, but humans must govern.*  
> 
> *Only an authorized Coordinator or Administrator can approve a plan. Every decision is cryptographically sealed into a **SHA-256 hash-chained immutable audit ledger**:*
> $$H_k = \text{SHA256}(H_{k-1} \parallel \text{action} \parallel \text{officer} \parallel \text{timestamp} \parallel \text{plan\_hash})$$  
> 
> *If an intruder or corrupt database administrator alters any past decision or changes an allocation quantity in the SQLite database, the hash chain breaks immediately during verification, alerting state auditors.*  
> 
> *Furthermore, our API enforces an automated safety guard: if model confidence falls below 60%, the system aborts autonomous approval with an HTTP 409 conflict, mandating clinical review.*  
> 
> *To conclude: Disaster Healthcare AI bridges the gap between raw spatial data, machine learning explainability, mathematical optimization, and tamper-evident governance.*  
> 
> *Thank you, esteemed examiners. We are ready for your questions."*

---

## 💡 TIPS FOR HANDLING EXAMINER QUESTIONS

1. **Be humble about accuracy, confident about engineering**: If an examiner asks about model error, do not get defensive. Emphasize that disaster data is inherently fat-tailed and that the model is designed as a *relative risk ranker* and *constrained optimizer*, not a magic crystal ball.
2. **Emphasize the zero-fabrication policy**: Remind the examiner that whenever you faced a choice between inventing fake numbers to look good or honestly reporting real data gaps (such as the 16-bed integer rounding or the WorldPop raster gap), you chose scientific integrity.
3. **If asked to run tests in terminal**: Open a terminal and run:
   ```bash
   cd disaster-healthcare-ai
   /opt/miniconda3/bin/pytest tests/ tests_api/ -q
   ```
   Show that all 198 tests pass cleanly with zero failures.
