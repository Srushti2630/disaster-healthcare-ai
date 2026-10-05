# Disaster Healthcare AI: REST API Reference Documentation

Comprehensive API reference for the **Disaster Healthcare AI** production backend built with FastAPI, SQLAlchemy, Pydantic v2, and Google OR-Tools SCIP solver.

---

## 🌐 Overview & Base URL

- **Base URL**: `http://localhost:8000`
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

All requests and responses use standard `application/json` payloads. Every response includes request tracking headers:
- `X-Request-ID`: Unique UUIDv4 assigned to each request.
- `X-Process-Time`: Total server-side execution time in seconds.

---

## 🔐 Authentication & Role-Based Access Control (RBAC)

The system secures administrative and governance routes using JWT Bearer authentication (`HS256` signature).

### User Roles & Privileges
| Role | Permissions |
|---|---|
| `viewer` | Read-only access to districts, predictions, simulations, allocations, and audit history. |
| `officer` | All `viewer` permissions + authority to submit human review decisions (`APPROVE`, `MODIFY`, `REJECT`). |
| `admin` | Full system access, including cryptographic audit log recomputation and user administration. |

### Default Seed Accounts (Development)
| Username | Password | Role | Description |
|---|---|---|---|
| `admin` | `admin123` | `admin` | System Administrator |
| `officer` | `officer123` | `officer` | District Health Officer |
| `viewer` | `viewer123` | `viewer` | Public / NGO Observer |

---

## 🏷️ Data Provenance Standard

In accordance with strict scientific transparency, all metrics returned by the API include explicit provenance tags:
- **`REAL`**: Derived directly from authoritative public datasets (CRED EM-DAT, WorldPop 2020 1km raster zonal sums, National Health Portal India facility directory, State ICU Bed Audit).
- **`ESTIMATED`**: Derived mathematically from real datasets (e.g., district bed allocations weighted by facility counts against official state anchors).
- **`ASSUMED`**: Literature parameters from WHO IEHK 2017 / Sphere Project clinical consumption rates or transport physics (Haversine $\times 1.3$ road circuity).

> [!IMPORTANT]
> Logistics transport cost is strictly quantified as a **Cost Index** ($\text{unit\_km} \times 15.0 + \text{active\_routes} \times 500.0$) and is **never** presented as currency (`₹` / `INR`).

---

## 📋 Endpoint Summary Table

| Category | Method | Endpoint | Role Required | Rate Limit | Description |
|---|---|---|---|---|---|
| **System** | `GET` | `/health` | Public | None | Liveness & subsystem status probe |
| **Auth** | `POST` | `/api/auth/register` | Public | 10 / min | Register new user account |
| **Auth** | `POST` | `/api/auth/token` | Public | 20 / min | Authenticate and obtain JWT access token |
| **Auth** | `GET` | `/api/auth/me` | Authenticated | 60 / min | Get current user profile and role |
| **Districts** | `GET` | `/api/districts` | Public | 60 / min | List 35 Maharashtra districts with demographics |
| **Districts** | `GET` | `/api/districts/{name}` | Public | 60 / min | Retrieve specific district profile |
| **Districts** | `GET` | `/api/districts/{name}/shortage` | Public | 60 / min | Check baseline shortage across 5 medicine classes |
| **Model** | `POST` | `/api/predict-impact` | Public | 30 / min | Conformalized quantile regression impact prediction |
| **Simulator**| `POST` | `/api/simulate` | Public | 10 / min | 2,000-draw Monte-Carlo scenario surge simulator |
| **Optimiser**| `POST` | `/api/allocate` | Public | 10 / min | Multi-objective OR-Tools SCIP redistribution solver |
| **Backtest** | `GET` | `/api/backtest` | Public | 60 / min | Real historical Leave-One-Out validation records |
| **Audit** | `GET` | `/api/audit` | Authenticated | 60 / min | Retrieve SHA-256 chained audit ledger entries |
| **Audit** | `POST` | `/api/audit` | `officer`, `admin` | 30 / min | Record official human review decision |
| **Audit** | `GET` | `/api/audit/verify` | Authenticated | 60 / min | Cryptographically verify integrity of entire chain |
| **Audit** | `POST` | `/api/audit/recompute` | `admin` | 5 / min | Re-seal audit hash chain after manual review |

---

## 🛠️ Detailed Endpoint Specifications

### 1. System Health
#### `GET /health`
Returns system operational status, model availability, and database connectivity.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-10-05T01:00:00.000Z",
  "components": {
    "database": "connected",
    "impact_model": "loaded",
    "conformal_intervals": "active",
    "district_data": "35 districts loaded"
  }
}
```

---

### 2. Authentication

#### `POST /api/auth/token`
Authenticate with username and password to obtain an access token.

**Request Body** (`application/x-www-form-urlencoded` or JSON):
```json
{
  "username": "officer",
  "password": "officer123"
}
```

**Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "officer",
  "username": "officer"
}
```

---

### 3. Spatial & District Demographics

#### `GET /api/districts`
Returns demographic, healthcare capacity, and geospatial metadata for all 35 Maharashtra districts.

**Response `200 OK`**:
```json
[
  {
    "name": "Pune",
    "population": 9429408,
    "total_beds": 14210,
    "icu_beds": 1135,
    "facility_count": 412,
    "lat": 18.5204,
    "lon": 73.8567,
    "population_provenance": "REAL",
    "bed_provenance": "ESTIMATED"
  }
]
```

---

### 4. Machine Learning Impact Prediction

#### `POST /api/predict-impact`
Predicts total affected population and 90% Conformalized Quantile Regression (CQR) bounds.

**Request Body**:
```json
{
  "disaster_subgroup": "Hydrological",
  "disaster_type": "Flood",
  "affected_area_km2": 450.0,
  "duration_days": 4,
  "epicenter_lat": 18.5204,
  "epicenter_lon": 73.8567,
  "month": 7
}
```

**Response `200 OK`**:
```json
{
  "predicted_affected": 84520.0,
  "cqr_p10": 4210.0,
  "cqr_p90": 1690400.0,
  "confidence_score": 0.52,
  "evaluation_note": "ML model provides relative risk rank across districts (Spearman rho = 0.52). Tail outliers can exceed point estimates by 30-150x.",
  "provenance_tags": {
    "predicted_affected": "ESTIMATED",
    "cqr_intervals": "ESTIMATED"
  }
}
```

---

### 5. Stochastic What-If Scenario Simulator

#### `POST /api/simulate`
Executes Monte-Carlo draws sampling log-normal casualty distributions against WHO IEHK 2017 clinical standards, with population capping strictly enforced (`min(affected, district_pop)`).

**Request Body**:
```json
{
  "epicentre": "Pune",
  "hazard": "Flood",
  "severity": 1.2,
  "planning_level": "P75",
  "num_draws": 2000,
  "safety_reserve_ratio": 0.60
}
```

**Response `200 OK`**:
```json
{
  "epicentre": "Pune",
  "hazard": "Flood",
  "affected_population": 113428,
  "district_shortages": [
    {
      "district": "Pune",
      "medicine": "blood_units",
      "demand": 4537,
      "stock": 1135,
      "shortage": 3402,
      "risk_level": "High"
    }
  ],
  "summary_kpis": {
    "total_affected": 113428,
    "districts_at_risk": 7,
    "critical_shortage_items": 3
  },
  "provenance_tags": {
    "affected_population": "ESTIMATED",
    "clinical_demand": "ASSUMED"
  },
  "execution_ms": 42.5
}
```

---

### 6. Multi-Objective Resource Allocation

#### `POST /api/allocate`
Solves multi-commodity network flow Mixed-Integer Program using Google OR-Tools SCIP solver under 5 safety constraints.

**Request Body**:
```json
{
  "epicentre": "Pune",
  "hazard": "Flood",
  "severity": 1.0,
  "planning_level": "P50",
  "safety_reserve_ratio": 0.60,
  "perishables_dist_limit_km": 150.0
}
```

**Response `200 OK`**:
```json
{
  "routes": [
    {
      "source": "Satara",
      "destination": "Pune",
      "medicine": "blood_units",
      "quantity": 420,
      "distance_km": 105.3,
      "priority": "CRITICAL"
    }
  ],
  "total_cost_index": 82450.0,
  "unmet_demand_units": 1240.0,
  "min_regional_coverage": 0.742,
  "active_route_count": 14,
  "solve_status": "OPTIMAL",
  "computation_ms": 312.4,
  "provenance_tags": {
    "routes": "ESTIMATED",
    "cost_index": "ASSUMED"
  }
}
```

---

### 7. Governance & Tamper-Evident Audit Ledger

#### `GET /api/audit`
Retrieve chronological audit entries with SHA-256 chaining.

**Response `200 OK`**:
```json
[
  {
    "id": 1,
    "timestamp": "2026-10-04T12:00:00Z",
    "user_id": 2,
    "action": "APPROVE",
    "reason_code": "ROUTINE_ACCEPTANCE",
    "scenario_summary": "Pune Flood Severity 1.0 Allocation Plan",
    "confidence_score": 0.82,
    "previous_hash": "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000",
    "entry_hash": "a4f89d34e2c1b7890ef0123456789abcdef0123456789abcdef0123456789abc"
  }
]
```

#### `POST /api/audit`
Submit human officer review decision.

> [!WARNING]
> **Safety Guard**: If an officer attempts to `APPROVE` a plan where `confidence_score < 0.60`, the API rejects the request with **HTTP 409 Conflict** (`"Autonomous approval blocked: scenario confidence score is below safe operational threshold (0.60). Select MODIFY or REJECT with clinical justification."`).

**Request Body**:
```json
{
  "action": "APPROVE",
  "reason_code": "ROUTINE_ACCEPTANCE",
  "scenario_summary": "Pune Flood Severity 1.0 P50 Plan",
  "confidence_score": 0.85
}
```

#### `GET /api/audit/verify`
Recomputes SHA-256 hashes from genesis block across all records to verify chain integrity.

**Response `200 OK`**:
```json
{
  "is_valid": true,
  "total_records": 12,
  "tampered_index": null,
  "message": "Cryptographic audit chain intact: 12/12 blocks verified."
}
```
