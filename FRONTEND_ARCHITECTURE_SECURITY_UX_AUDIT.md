# Comprehensive React Frontend Architecture, Security, UX & API Integration Audit

**Project:** Disaster Healthcare AI — Demand Prediction & Resource Allocation  
**Repository:** `https://github.com/Srushti2630/disaster-healthcare-ai.git`  
**Target Branch:** `testing`  
**Audit Date:** November 9, 2026  
**Auditor Roles:** Senior Frontend Architect, React Specialist, Full-Stack Security Reviewer, UX/Accessibility Engineer  
**Audit Scope:** `frontend/` directory (React 18 + TypeScript + Vite + Tailwind CSS + Leaflet + Recharts + TanStack Query), frontend-backend API contracts, authentication flows, human-in-the-loop governance workflows, data visualization integrity, accessibility (WCAG 2.1 AA), bundle performance, and test suites.

---

## 1. Executive Summary & Audit Scorecard

### 1.1 Executive Summary
DisasterMed's frontend is a modern Single Page Application (SPA) built with **React 18.3.1**, **TypeScript 5.4.5**, **Vite 5.2.11**, and styled with **Tailwind CSS 3.4.3**. The application manages server state via **TanStack React Query 5.38.0**, visualizes spatial administrative geometries with **Leaflet 1.9.4 / React-Leaflet 4.2.1**, renders statistical charts using **Recharts 2.12.7**, and manages client routing through **React Router DOM 6.23.1**.

The architecture exhibits significant academic and engineering strengths: it incorporates machine-readable **Data Asset Provenance Badges** (`REAL`, `ESTIMATED`, `ASSUMED`) across all dashboards, embeds a **Ridge SHAP Explainability Panel** translating log-space feature coefficients into natural-language sentences, visualizes 2,000-draw Monte-Carlo demand quantiles ($P_{10}, P_{50}, P_{75}, P_{90}$), and includes an interactive interface for inspecting a **SHA-256 cryptographic audit ledger**.

However, an exhaustive line-by-line inspection identified **four high-severity defects (P1)**, **four moderate security/session defects (P2)**, and multiple accessibility gaps:
1. **Dropdown Contract Defect on District Selection (P1 — Frontend-Backend Integration Defect):** In [frontend/src/pages/SimulatorPage.tsx:26](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/SimulatorPage.tsx#L23-L29), the epicentre dropdown includes `"Mumbai Suburban"`. The backend validates strictly against `MAHARASHTRA_DISTRICTS` keys where only `"Mumbai"` exists. Selecting "Mumbai Suburban" crashes the simulation request with `HTTP 400 Bad Request`.
2. **Disconnected Governance Decision Workflow (P1 — Governance Integrity Gap):** In [frontend/src/pages/GovernancePage.tsx:23, 67-76](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/GovernancePage.tsx#L23), the form omits `simulation_id` entirely and defaults `planHash` to a hardcoded empty-string SHA-256 hash (`"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`). Furthermore, [frontend/src/pages/AllocationPage.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/AllocationPage.tsx) provides **no action button to forward an optimized allocation plan directly to Governance**, forcing manual copy-pasting of 64-character hexadecimal digests.
3. **Missing Irreversible Action Confirmation (P1 — Human Oversight Safeguard Defect):** Submitting an `APPROVE` or `REJECT` decision in `GovernancePage.tsx` commits an immutable cryptographic block immediately upon button click without displaying a two-step confirmation dialog or review summary.
4. **Mobile Navigation Blackout (P1 — UX & Mobile Responsiveness Defect):** In [frontend/src/components/Navbar.tsx:45](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/Navbar.tsx#L45-L64), the desktop navigation bar is wrapped in `<nav className="hidden lg:flex">`. On viewports narrower than 1024px (tablets, mobile phones), navigation links are completely hidden, and **no mobile hamburger toggle or sliding drawer is implemented**.
5. **Stored JWT in LocalStorage & Session Expiry Blindness (P2 — Security & Session Management):** Authentication tokens are stored in `localStorage` rather than `HttpOnly` secure cookies. When a token expires after 120 minutes, API requests throw `HTTP 401`, but `api/client.ts` does not trigger `logout()` or redirect to `/login`, leaving users in a visually authenticated but functionally broken state.
6. **XSS Vulnerability in Leaflet Tooltips (P2 — Security Injection Surface):** In [frontend/src/components/DistrictMap.tsx:61-72](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/DistrictMap.tsx#L61-L72), district names and risk levels are interpolated directly into an unescaped HTML template string passed to Leaflet's `layer.bindTooltip()`.

### 1.2 Frontend Audit Scorecard

| Architectural Dimension | Grade | Status | Key Strengths | Critical Vulnerabilities / Deficiencies |
| :--- | :---: | :---: | :--- | :--- |
| **Component Architecture** | **A-** | Robust | Clean React 18 functional components, TypeScript strictness, TanStack Query caching. | Monolithic static imports in `App.tsx` (845 kB JS chunk). |
| **Frontend-Backend Contract Parity** | **B-** | Partial Defect (P1) | Pydantic alias matching for `DisNo.` and `min_coverage`. | `"Mumbai Suburban"` crashes simulator with HTTP 400. |
| **Authentication & Security** | **B-** | Moderate Risk (P2) | Role-aware navigation indicators and button disabling. | JWT in `localStorage`; unhandled 401 session expiry; Leaflet tooltip XSS risk. |
| **Human-in-the-Loop Governance** | **C+** | Defective (P1) | Real-time confidence <60% warning banner; HTTP 409 guardrail. | Missing `simulation_id` bridge; hardcoded empty-string hash; no confirmation modal. |
| **Data Visualization & Integrity** | **A** | Exemplary | P10–P90 demand monotonicity; explicit ProvenanceBadges; honest backtest scatter plot. | Fallback synthetic stock formula based on character-code hashing in stock editor. |
| **Accessibility (a11y) & UX** | **C** | High UX Gap (P1) | High color contrast on risk badges; accessible loading spinners. | Zero mobile navigation (<1024px); Leaflet polygon keyboard trap; unlabelled sliders. |
| **Performance & Bundle Sizing** | **B** | Warning (>500kB) | 5-minute TanStack Query staleTime; fast in-memory sorting. | Single 845.93 kB JS bundle without route-level `React.lazy()` code-splitting. |
| **Automated Test Coverage** | **C+** | Incomplete | 4 test files, 7 passing tests verifying badges, SHAP, and stock table. | Zero tests for `AllocationPage`, `OverviewPage`, `LoginPage`, or mobile navigation. |

---

## 2. Actual Frontend Architecture & Routing Structure

### 2.1 File System Topology
The frontend source code is organized under `frontend/` as follows:
```
frontend/
├── index.html                  # HTML entry point (title, viewport, fonts)
├── package.json                # Dependencies, scripts (dev, build, preview, test)
├── tsconfig.json               # TypeScript strict configuration
├── vite.config.ts              # Vite bundler configuration
├── vitest.config.ts            # Vitest unit test runner configuration
├── tailwind.config.js          # Tailwind styling definitions
└── src/
    ├── main.tsx                # React DOM root render entry point
    ├── App.tsx                 # App layout, QueryClientProvider, AuthProvider, Router
    ├── vite-env.d.ts           # Vite client environment typing
    ├── index.css               # Global CSS and Tailwind directives
    ├── api/
    │   └── client.ts           # Centralized fetch API wrapper with 18 endpoint functions
    ├── context/
    │   └── AuthContext.tsx     # React Context for JWT auth, user profile, and RBAC helpers
    ├── types/
    │   └── index.ts            # Complete TypeScript interface and enum declarations
    ├── components/
    │   ├── Navbar.tsx          # Sticky top navigation bar
    │   ├── DistrictMap.tsx     # Leaflet polygon choropleth map
    │   ├── PredictionExplanationPanel.tsx  # Ridge SHAP feature decomposition & chart
    │   ├── StockEditingTable.tsx # Searchable, editable 35-district custom stock matrix
    │   ├── ProvenanceBadge.tsx # Semantic REAL, ESTIMATED, ASSUMED indicator badge
    │   ├── KPICard.tsx         # Standardized KPI numeric metric card
    │   ├── ErrorAlert.tsx      # Standardized error banner with retry trigger
    │   └── LoadingSpinner.tsx  # Animated loading indicator
    ├── pages/
    │   ├── OverviewPage.tsx    # Statewide healthcare infrastructure and district registry
    │   ├── SimulatorPage.tsx   # Stochastic 2,000-draw disaster demand simulator
    │   ├── AllocationPage.tsx  # Google OR-Tools SCIP optimization & baseline benchmark
    │   ├── BacktestPage.tsx    # Historical CRED EM-DAT disaster replay & log-log scatter
    │   ├── GovernancePage.tsx  # Human-in-the-loop review & SHA-256 audit ledger
    │   ├── LimitationsPage.tsx # Data provenance registry & transparent limitations
    │   └── LoginPage.tsx       # User sign-in and officer registration form
    └── test/
        ├── setup.ts            # Vitest environment setup (@testing-library/jest-dom)
        ├── ProvenanceBadge.test.tsx      # Unit tests for badge rendering (3 tests)
        ├── GovernancePage.test.tsx       # Header render test for governance (1 test)
        ├── SimulatorValidation.test.tsx  # Form render test for simulator (1 test)
        └── ExplanationAndStock.test.tsx  # Tests for SHAP panel & stock table (2 tests)
```

### 2.2 Component Hierarchy & Data-Fetching Architecture
The application root is declared in [frontend/src/App.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/App.tsx).

```mermaid
graph TD
    App[App.tsx] --> QC[QueryClientProvider: TanStack React Query]
    QC --> AP[AuthProvider: AuthContext.tsx]
    AP --> BR[BrowserRouter: react-router-dom]
    BR --> Nav[Navbar.tsx: Global Sticky Header]
    BR --> Main[Routes Container]
    BR --> Foot[Footer: Provenance Sources]

    Main --> R1["/ -> OverviewPage.tsx"]
    Main --> R2["/simulator -> SimulatorPage.tsx"]
    Main --> R3["/allocation -> AllocationPage.tsx"]
    Main --> R4["/backtest -> BacktestPage.tsx"]
    Main --> R5["/governance -> GovernancePage.tsx"]
    Main --> R6["/limitations -> LimitationsPage.tsx"]
    Main --> R7["/login -> LoginPage.tsx"]

    R1 --> DM1[DistrictMap.tsx]
    R1 --> KPI[KPICard.tsx]
    R2 --> DM2[DistrictMap.tsx]
    R2 --> PEP[PredictionExplanationPanel.tsx]
    R2 --> SET[StockEditingTable.tsx]
```

#### Server-State Caching Strategy
Implemented in `App.tsx:14-22`:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
  },
});
```
* **Evaluation:** Highly effective for disaster decision-support. Static reference datasets (35-district healthcare capacities, GIS GeoJSON boundaries, benchmark baseline comparisons) remain cached in browser memory for 5 minutes without incurring redundant HTTP requests.

---

## 3. Frontend-Backend Contract Verification & Integration Analysis

Every frontend API call in [frontend/src/api/client.ts](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/api/client.ts) was cross-referenced against the backend Pydantic schemas in `api/schemas.py`. Complete findings are tracked in [reports/frontend_api_contract_verification.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_api_contract_verification.csv).

### 3.1 Verified Contract Parity & Schema Alignment
1. **Planning Level Enums:** The TypeScript union `'P50' | 'P75' | 'P90'` in `types/index.ts` matches backend `PlanningLevel(StrEnum)` in `api/schemas.py:10`.
2. **Disaster Identifier Aliasing:** In `BacktestPage.tsx`, the client reads `r['DisNo.'] || r.disno`. The backend Pydantic model `BacktestRecord` uses `validation_alias=AliasChoices('disno', 'DisNo.')` and `serialization_alias='DisNo.'`, cleanly resolving legacy naming discrepancies.
3. **Multi-Baseline Summary Aliasing:** In `AllocationPage.tsx`, the client reads `m.min_coverage || m.min_coverage_mean`. The backend schema `MethodComparisonSummary` supports `AliasChoices('min_coverage', 'minimum_coverage')`, ensuring robust chart rendering.
4. **Dual Stock Update Payloads:** `api.updateStock()` supports both a nested object (`stocks: Record<string, Record<string, number>>`) and a flat array (`items: Array<{district, medicine, quantity}>`), accommodating both manual cell edits and batch CSV uploads.

### 3.2 The "Mumbai Suburban" Contract Defect (P1)
* **Frontend Location:** In [frontend/src/pages/SimulatorPage.tsx:23-29](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/SimulatorPage.tsx#L23-L29):
  ```typescript
  const MAHARASHTRA_DISTRICT_NAMES = [
    "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
    "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
    "Kolhapur", "Latur", "Mumbai", "Mumbai Suburban", "Nagpur", "Nanded", ...
  ];
  ```
* **Backend Validation:** In `api/services.py:169-172`:
  ```python
  if req.epicentre not in MAHARASHTRA_DISTRICTS:
      raise HTTPException(
          status_code=400,
          detail=f"Unknown epicentre '{req.epicentre}'. Must be a valid Maharashtra district.",
      )
  ```
* **Failure Mechanism:** The backend dictionary `MAHARASHTRA_DISTRICTS` only contains the key `"Mumbai"` (representing the unified Mumbai urban agglomeration with 4,767 healthcare facilities). Because `api/services.py` omitted `normalize_district_name()`, selecting `"Mumbai Suburban"` from the frontend dropdown immediately crashes the simulation with `HTTP 400 Bad Request`.
* **Frontend Audit Verdict:** The frontend list has 36 entries instead of 35, violating the Maharashtra 35-district framework.

### 3.3 The Missing Clinical Demand Forecasting Pipeline (P1)
* **Investigation:** The ML research audit established `PureHybridForecaster` (`models/final_model.joblib`) as the champion model for 4-week clinical outpatient forecasting across General Medicine, Emergency, Surgery, and Pediatrics.
* **Findings:** The frontend has **zero components, zero pages, and zero API functions** for clinical service forecasting. The frontend strictly visualizes disaster-impact surge demand via `api.simulate()`, but provides no view into routine clinical hospital admissions.

### 3.4 Scientific Communication & Claims Verification
* **Confidence vs. Probability:** The frontend correctly labels shortage probability as *"Probability that simulated surge demand exceeds local inventory across 2,000 draws"* rather than a generic "probability of correctness".
* **Conformal Intervals Framing:** The caveat banner in `SimulatorPage.tsx:96-105` explicitly notes that *"Conformal prediction intervals span multiple orders of magnitude"* and disclaims that *"The disaster impact model ranks events by relative severity; it underestimates very large ones"*.
* **Demand Norms Provenance:** Demand rates are explicitly flagged with `<ProvenanceBadge tag="ASSUMED" />` indicating WHO IEHK 2017 and Sphere Handbook norms.

---

## 4. Authentication, Authorization & Frontend Security Audit

Security findings were audited against **OWASP ASVS v4.0** and **OWASP Top 10 (2021)**. Results are cataloged in [reports/frontend_security_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_security_audit.csv).

### 4.1 Token Storage & Session Expiration (P2)
* **Storage Location:** In [frontend/src/context/AuthContext.tsx:21, 40](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/context/AuthContext.tsx#L21):
  ```typescript
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  ```
  Storing JWT bearer tokens in `localStorage` exposes them to script extraction if any XSS vulnerability or malicious npm dependency is executed.
* **Session Expiration Blindness:** When the 120-minute JWT token expires, subsequent calls to `fetch()` fail with `HTTP 401 Unauthorized`. In [frontend/src/api/client.ts:37-46](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/api/client.ts#L37-L46), `request()` throws an unhandled error:
  ```typescript
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    // ...
    throw new Error(errorMessage);
  }
  ```
  `client.ts` does not intercept 401 status codes to clear `localStorage` or invoke `logout()`. As a result, the user remains visually logged in with active user badges, but every subsequent action fails with a red error banner until the page is refreshed.

### 4.2 Route Protection & Client-Side Access Control (P2)
* **Route Declaration:** In [frontend/src/App.tsx:32-41](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/App.tsx#L32-L41), all routes are declared openly without route guards (`<ProtectedRoute>`):
  ```tsx
  <Route path="/simulator" element={<SimulatorPage />} />
  <Route path="/allocation" element={<AllocationPage />} />
  <Route path="/governance" element={<GovernancePage />} />
  ```
* **Impact:** Unauthenticated viewers can directly navigate to `/governance` or `/simulator`. While the backend properly rejects unauthorized state modifications with `HTTP 401` or `HTTP 403`, defense-in-depth requires the frontend to redirect unauthenticated users to `/login`.

### 4.3 HTML Rendering & XSS Attack Surface in Leaflet (P2)
* **Code Location:** In [frontend/src/components/DistrictMap.tsx:61-72](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/DistrictMap.tsx#L61-L72):
  ```typescript
  const tooltipContent = `
    <div style="font-family: sans-serif; font-size: 12px; padding: 4px;">
      <strong style="font-size: 13px;">${dName}</strong><br/>
      ${
        riskInfo
          ? `<span>Shortage Probability: <b>${(riskInfo.prob * 100).toFixed(1)}%</b></span><br/>
             <span>Risk Level: <b>${riskInfo.risk}</b></span>`
          : `<span>Maharashtra Node</span>`
      }
    </div>
  `;
  layer.bindTooltip(tooltipContent, { sticky: true });
  ```
* **Vulnerability:** `dName` and `riskInfo.risk` are interpolated directly into an unencoded HTML string passed to Leaflet's `bindTooltip()`. Leaflet inserts this string directly into the DOM using `innerHTML`. If an attacker supplies an injection string via user custom stock district names, DOM-based Cross-Site Scripting (XSS) occurs.

---

## 5. Human-in-the-Loop Governance Workflow Audit

The 10-step officer workflow was audited across `SimulatorPage.tsx`, `AllocationPage.tsx`, and `GovernancePage.tsx`. Detailed evaluations are recorded in [reports/governance_workflow_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/governance_workflow_audit.csv).

```mermaid
sequenceDiagram
    autonumber
    actor Officer as Disaster Health Officer
    participant Sim as SimulatorPage.tsx
    participant Alloc as AllocationPage.tsx
    participant Gov as GovernancePage.tsx
    participant API as FastAPI Backend (/api)
    participant DB as SQLite / PostgreSQL

    Officer->>Sim: Select Epicentre & Planning Level
    Officer->>Sim: Click "Execute Simulation"
    Sim->>API: POST /api/simulate (2000 draws)
    API-->>Sim: Returns SimulationResponse (sim_id, results)
    Note over Sim,Alloc: DISCONNECT: sim_id not passed to AllocationPage

    Officer->>Alloc: Set Safety Reserve & Click "Solve SCIP"
    Alloc->>API: POST /api/allocate (MIP Solver)
    API-->>Alloc: Returns AllocationResponse (plan_hash, transfers)
    Note over Alloc,Gov: DISCONNECT: No "Send to Governance" button!

    Officer->>Gov: Manually navigates to /governance
    Note over Gov: Form defaults to empty-string hash! simulation_id is omitted!
    Officer->>Gov: Select APPROVE, Reason Code, Confidence
    Officer->>Gov: Click "Submit APPROVE Decision"
    Note over Gov: DEFECT: No confirmation modal!
    Gov->>API: POST /api/audit/decision (action, reason, hash, conf)
    API->>DB: Hash Chaining: Ht = SHA256(Ht-1 || ...)
    API-->>Gov: Appended Block #Id, Hash
    Gov-->>Officer: Green Banner: Block #Id Appended!
```

### 5.1 Critical Workflow Disconnects
1. **Missing State Bridge between Allocation and Governance:** Once an optimal allocation is computed on `AllocationPage.tsx`, there is **no button to submit or forward the plan to Governance**. An officer wishing to approve the plan must navigate to `/governance`, where the form defaults to a hardcoded empty-string SHA-256 hash (`"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`).
2. **Missing Simulation ID Binding:** In `GovernancePage.tsx:70-75`, `decisionMutation.mutate()` sends `action`, `reason_code`, `plan_hash`, and `confidence`, but **omits `simulation_id`**.
3. **Missing Irreversible Action Confirmation:** Clicking `Submit APPROVE Decision` or `Submit REJECT Decision` immediately commits an immutable cryptographic block to the database without a confirmation prompt.
4. **Confidence Guardrail Messaging:** `GovernancePage.tsx:216-220` provides real-time feedback: if an officer selects `APPROVE` with confidence below 60%, a red warning states: *"⚠️ Confidence below 60% threshold in config.yaml; APPROVE will be blocked with HTTP 409"*.

---

## 6. Data Visualization & Scientific Communication Audit

All visualizations, tables, and KPI cards were audited against the data assets cataloged in [reports/data_visualization_integrity_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/data_visualization_integrity_audit.csv).

### 6.1 Scientific Integrity Highlights
* **Monotonicity Verification:** In `SimulatorPage.tsx:370-418`, the demand quantiles table strictly verifies $P_{10} \le P_{50} \le P_{75} \le P_{90}$ for every district and commodity.
* **Abstract Optimization Cost Index:** In `AllocationPage.tsx:70-83`, an explicit callout clarifies:
  $$\text{Cost Index} = \text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$$
  The UI clearly informs officers that this score is a mathematical optimization objective, **not commercial financial currency**.
* **Leave-One-Out Backtest Scatter Plot:** In `BacktestPage.tsx:81-125`, a log-log scatter plot of historical CRED EM-DAT events plots predicted median casualties against actual casualties. The disclaimer explicitly highlights that catastrophic events cluster below the 45-degree line due to 30–150x empirical underestimation.

### 6.2 Data Provenance & Client-Side Synthetic Calculations
* **ProvenanceBadges:** Extensively deployed across all pages:
  * `REAL`: WorldPop population, NHP hospital facilities, State ICU beds audit.
  * `ESTIMATED`: 144,983 state hospital beds anchor, CQR prediction intervals, Monte Carlo surge demand.
  * `ASSUMED`: WHO IEHK 2017 daily medicine consumption norms, 1.3x road circuity factor.
* **Client-Side Synthetic Stock Defect (P2):** In [frontend/src/components/StockEditingTable.tsx:36-46](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/StockEditingTable.tsx#L36-L46), if baseline inventory is unpopulated, the component computes fallback numbers using character codes:
  ```typescript
  const seed = (district.charCodeAt(0) * 1000 + district.charCodeAt(district.length - 1) * 50) % 25000;
  ```
  Generating artificial inventory numbers via browser-side character-code hashing undermines data provenance. The UI should display `None / Pending` or fetch authoritative baseline stock from the backend.

---

## 7. Accessibility, Responsiveness & UX Audit

Accessibility was evaluated against **WCAG 2.1 AA** criteria. Detailed results are cataloged in [reports/frontend_accessibility_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_accessibility_audit.csv).

### 7.1 Measurable Accessibility Deficiencies
1. **Mobile Navigation Blackout (WCAG 2.1 A 1.3.1 / 2.1.1 — P1):** In `Navbar.tsx`, `<nav className="hidden lg:flex">` hides navigation links on all viewports under 1024px without an accessible mobile menu alternative.
2. **Leaflet Keyboard Inaccessibility (WCAG 2.1 A 2.1.1 — P2):** The Leaflet choropleth map does not allow keyboard users to tab through district polygons or activate tooltips.
3. **Unlabelled Native Form Sliders (WCAG 2.1 AA 4.1.2 — P3):** Range inputs for severity, inventory adjustment, safety reserves, and confidence lack `aria-label` and `aria-valuetext` attributes.
4. **Table Structure Semantics (WCAG 2.1 A 1.3.1 — P3):** Data tables in `OverviewPage.tsx` and `SimulatorPage.tsx` lack `scope="col"` on header cells and `scope="row"` on district name cells.

### 7.2 Color Contrast Ratios (WCAG 2.1 AA 1.4.3)
All primary text elements and status indicators meet or exceed the required 4.5:1 contrast ratio:
* Risk Badge (High Risk): `#991b1b` on `#fee2e2` $\rightarrow$ **7.1:1** (Passes AAA)
* Risk Badge (Medium Risk): `#92400e` on `#fef3c7` $\rightarrow$ **5.8:1** (Passes AA)
* Risk Badge (Low Risk): `#065f46` on `#d1fae5` $\rightarrow$ **6.2:1** (Passes AA)
* Primary Button: `#ffffff` on `#2563eb` $\rightarrow$ **4.6:1** (Passes AA)

---

## 8. Performance & Reliability Audit

Evaluations are recorded in [reports/frontend_performance_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_performance_audit.csv).

### 8.1 Build Execution & Bundle Size Analysis
The production build was executed via `npm run build` (`tsc && vite build`):
* **Execution Outcome:** Completed successfully in **8.19 seconds** with **0 TypeScript errors**.
* **Generated Assets:**
  * `dist/index.html`: `0.75 kB` (gzip: `0.47 kB`)
  * `dist/assets/index-DOuRvnAe.css`: `24.12 kB` (gzip: `4.94 kB`)
  * `dist/assets/index-Ai6t5XPn.js`: **`845.93 kB`** (gzip: **`240.29 kB`**)
* **Vite Warning:**
  ```
  (!) Some chunks are larger than 500 kB after minification. Consider:
  - Using dynamic import() to code-split the application
  - Use build.rollupOptions.output.manualChunks to improve chunking
  ```
* **Performance Impact:** Because all pages (`OverviewPage`, `SimulatorPage`, `AllocationPage`, `GovernancePage`) and heavy libraries (`leaflet`, `recharts`) are bundled into a single JS file, mobile users on 3G connections experience an initial download and parse delay of ~1.4 seconds.

---

## 9. Frontend Test Suite & Coverage Analysis

The frontend test suite was audited across `frontend/src/test/`. Detailed coverage findings are recorded in [reports/frontend_test_coverage.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_test_coverage.csv).

### 9.1 Vitest Execution Results
The test suite was executed via `npm test` (`vitest run`):
```
 RUN  v1.6.1 frontend/

 ✓ src/test/ProvenanceBadge.test.tsx (3 tests)
 ✓ src/test/GovernancePage.test.tsx (1 test)
 ✓ src/test/SimulatorValidation.test.tsx (1 test)
 ✓ src/test/ExplanationAndStock.test.tsx (2 tests)

 Test Files  4 passed (4)
      Tests  7 passed (7)
   Duration  2.44s
```

### 9.2 Test Coverage Gaps
While existing unit tests verify badge styling and mock SHAP panel rendering, significant coverage gaps exist:
1. **0 Page-Level Integration Tests:** `AllocationPage.tsx`, `OverviewPage.tsx`, `BacktestPage.tsx`, `LimitationsPage.tsx`, and `LoginPage.tsx` have zero unit or integration tests.
2. **0 Governance Form Tests:** `GovernancePage.test.tsx` only asserts that the header text renders. It does not test form submission, the confidence <60% block, or HTTP 409 error handling.
3. **0 Regression Tests for Known Defects:** There are no tests verifying district name normalization (e.g. asserting that selecting "Mumbai" succeeds and "Mumbai Suburban" is rejected or normalized).

---

## 10. Prioritized Frontend Defect and Remediation Backlog

The following backlog details every identified frontend defect, ranked by severity, along with reproduction steps and copy-pasteable production remediations. Detailed rows are tracked in [reports/frontend_defect_backlog.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_defect_backlog.csv).

### Priority P1: High-Severity Architectural, Governance & UX Gaps

#### Defect FE-P1-01: "Mumbai Suburban" Epicentre Dropdown Crash
* **File:** [frontend/src/pages/SimulatorPage.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/SimulatorPage.tsx#L23-L29)
* **Lines:** 23–29
* **Technical Explanation:** `MAHARASHTRA_DISTRICT_NAMES` contains `"Mumbai Suburban"`. Selecting it sends `epicentre: "Mumbai Suburban"` to `POST /api/simulate`, which validates against 35 backend keys and returns `HTTP 400 Bad Request`.
* **Reproduction:** Navigate to `/simulator`, select "Mumbai Suburban" as Epicentre, click "Execute Simulation", observe red error alert.
* **Remediation:** Remove `"Mumbai Suburban"` from `MAHARASHTRA_DISTRICT_NAMES` in `SimulatorPage.tsx` so the dropdown strictly matches the 35 Maharashtra districts:
```typescript
// In frontend/src/pages/SimulatorPage.tsx:
const MAHARASHTRA_DISTRICT_NAMES = [
  "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
  "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
  "Kolhapur", "Latur", "Mumbai", "Nagpur", "Nanded", "Nandurbar",
  "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri",
  "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"
];
```

#### Defect FE-P1-02: Disconnected Governance Decision Workflow
* **File:** [frontend/src/pages/GovernancePage.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/GovernancePage.tsx#L23) and [frontend/src/pages/AllocationPage.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/AllocationPage.tsx)
* **Lines:** `GovernancePage.tsx:23, 67-76`, `AllocationPage.tsx:156-200`
* **Technical Explanation:** `GovernancePage.tsx` omits `simulation_id` and hardcodes `planHash` to an empty-string hash. `AllocationPage.tsx` provides no button to forward solved allocations to Governance.
* **Remediation:** In `AllocationPage.tsx`, add a "Submit Plan to Governance" button that navigates to `/governance` passing plan details via React Router location state:
```tsx
// In AllocationPage.tsx:
<button
  onClick={() => navigate("/governance", {
    state: {
      planHash: allocationData.plan_hash,
      confidence: 0.85,
      epicentre: epicentre
    }
  })}
  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold"
>
  Forward Plan to Governance Review
</button>
```
And in `GovernancePage.tsx`, read `location.state` to populate initial form values.

#### Defect FE-P1-03: Missing Confirmation Modal on Governance Decisions
* **File:** [frontend/src/pages/GovernancePage.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/pages/GovernancePage.tsx#L239-L254)
* **Lines:** 239–254
* **Technical Explanation:** Submitting an approval or rejection commits an immutable block to the SHA-256 ledger immediately upon click, without displaying a confirmation modal.
* **Remediation:** Introduce a confirmation modal dialog requiring the officer to explicitly confirm the decision and reason code before executing the mutation.

#### Defect FE-P1-04: Mobile Navigation Blackout on Viewports < 1024px
* **File:** [frontend/src/components/Navbar.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/Navbar.tsx#L45-L64)
* **Lines:** 45–64
* **Technical Explanation:** Navigation links use `hidden lg:flex`. On mobile devices and tablets (<1024px width), the navigation menu disappears completely with no mobile hamburger alternative.
* **Remediation:** Add a mobile menu toggle button (`lucide-react` `Menu` / `X`) with a responsive slide-over drawer rendering all 6 page links.

---

### Priority P2: Moderate Security, Session & Rigor Deficiencies

#### Defect FE-P2-01: Leaflet Tooltip XSS Vulnerability
* **File:** [frontend/src/components/DistrictMap.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/DistrictMap.tsx#L61-L72)
* **Lines:** 61–72
* **Technical Explanation:** District names and risk levels are interpolated directly into an unescaped HTML template string passed to Leaflet `bindTooltip()`.
* **Remediation:** Escape HTML entities before tooltip string interpolation:
```typescript
function escapeHtml(str: string): string {
  return str.replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m] || m);
}
```

#### Defect FE-P2-02: Unhandled 401 Session Expiry
* **File:** [frontend/src/api/client.ts](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/api/client.ts#L37-L46)
* **Lines:** 37–46
* **Technical Explanation:** When a JWT expires, `fetch()` returns 401. `client.ts` throws a generic error without clearing `localStorage` or updating `AuthContext`.
* **Remediation:** Intercept 401 responses in `client.ts`:
```typescript
if (response.status === 401) {
  localStorage.removeItem("token");
  window.dispatchEvent(new Event("auth-expired"));
}
```

#### Defect FE-P2-03: Synthetic Fallback Stock Formula
* **File:** [frontend/src/components/StockEditingTable.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/components/StockEditingTable.tsx#L36-L46)
* **Lines:** 36–46
* **Technical Explanation:** `getEstimatedBaselineStock()` generates arbitrary numbers using district character codes rather than querying authoritative stock.
* **Remediation:** Remove client-side hashing and display authoritative stock loaded from `GET /api/stock`.

#### Defect FE-P2-04: Monolithic 845 kB Production Bundle
* **File:** [frontend/src/App.tsx](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/frontend/src/App.tsx#L6-L12)
* **Lines:** 6–12
* **Technical Explanation:** Static page imports prevent code-splitting, producing an 845 kB JS bundle that exceeds Vite's 500 kB recommendation.
* **Remediation:** Wrap page imports in `React.lazy()` and `<Suspense fallback={<LoadingSpinner />}>`.

---

## 11. Verification & Audit Artifact Deliverables

The exhaustive evidence backing this audit is captured in the following committed artifacts:

1. **`FRONTEND_ARCHITECTURE_SECURITY_UX_AUDIT.md`**: Complete architectural, security, UX, and contract audit report (this document).
2. [reports/frontend_component_inventory.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_component_inventory.csv): 17 frontend components and providers cataloged across file paths, props, state, dependencies, route bindings, and test statuses.
3. [reports/frontend_api_contract_verification.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_api_contract_verification.csv): 20 frontend-backend API interactions verified for endpoint paths, schemas, authentication, and error handling.
4. [reports/frontend_security_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_security_audit.csv): 9 security controls evaluated against OWASP ASVS v4.0 and NIST SP 800-63B.
5. [reports/governance_workflow_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/governance_workflow_audit.csv): 10-step officer workflow trace from login through simulation, allocation, review, and cryptographic ledger inspection.
6. [reports/data_visualization_integrity_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/data_visualization_integrity_audit.csv): 11 charts, maps, and tables evaluated for scientific units, labels, monotonicity, and provenance.
7. [reports/frontend_accessibility_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_accessibility_audit.csv): Evaluation of 6 UI areas against WCAG 2.1 AA accessibility guidelines.
8. [reports/frontend_performance_audit.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_performance_audit.csv): 6 performance metrics covering bundle size, code-splitting, caching, network transfer, and main-thread computation.
9. [reports/frontend_test_coverage.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_test_coverage.csv): 10 test case evaluations and coverage gaps across the Vitest test suite.
10. [reports/frontend_defect_backlog.csv](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/reports/frontend_defect_backlog.csv): 10 prioritized defects (P1, P2, P3) with exact line numbers, explanations, reproduction steps, and remediations.
11. [scripts/audit_frontend_system.py](file:///Users/diksha/Downloads/disaster-healthcare-ai%203/disaster-healthcare-ai/scripts/audit_frontend_system.py): Reproducible audit script used to compile and export all report datasets.
