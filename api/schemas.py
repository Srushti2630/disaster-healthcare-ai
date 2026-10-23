"""Pydantic v2 schemas and models for Disaster Healthcare AI API."""
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict, AliasChoices

class ProvenanceTag(str, Enum):
    REAL = "REAL"
    ESTIMATED = "ESTIMATED"
    ASSUMED = "ASSUMED"
    ESTIMATED_SIMULATION = "ESTIMATED_SIMULATION"
    USER_PROVIDED = "USER-PROVIDED"

class PlanningLevel(str, Enum):
    P50 = "P50"
    P75 = "P75"
    P90 = "P90"

class HazardType(str, Enum):
    FLOOD = "Flood"
    STORM = "Storm"
    EARTHQUAKE = "Earthquake"
    EPIDEMIC = "Epidemic"
    EXTREME_TEMP = "Extreme temperature"
    MASS_MOVEMENT = "Mass movement (wet)"
    OTHER = "Other"

# -------------------------------------------------------------
# DISTRICT MODELS
# -------------------------------------------------------------
class DistrictBedCapacity(BaseModel):
    beds_low: int = Field(..., description="Estimated lower bound total beds")
    beds_mid: int = Field(..., description="Estimated central hospital beds")
    beds_high: int = Field(..., description="Estimated upper bound total beds")
    icu_beds_low: int = Field(..., description="Estimated lower bound ICU beds")
    icu_beds_mid: int = Field(..., description="Estimated central ICU beds")
    icu_beds_high: int = Field(..., description="Estimated upper bound ICU beds")
    provenance: ProvenanceTag = ProvenanceTag.ESTIMATED

class DistrictFacilities(BaseModel):
    total_facilities: int
    public_facilities: int
    private_facilities: int
    provenance: ProvenanceTag = ProvenanceTag.REAL

class DistrictDetail(BaseModel):
    district: str
    population: int
    area_sqkm: float
    pop_density_sqkm: float
    capacity: DistrictBedCapacity
    facilities: DistrictFacilities
    total_facilities: Optional[int] = Field(default=None, description="Direct total facilities count")
    provenance: ProvenanceTag = ProvenanceTag.REAL

class DistrictListResponse(BaseModel):
    total_districts: int
    total_state_population: int
    state_hospital_beds_anchor: int
    state_icu_beds_anchor: int
    total_facilities: Optional[int] = Field(default=None, description="Statewide total cleaned facilities")
    total_cleaned_facilities: Optional[int] = Field(default=None, description="Total cleaned facilities across state")
    districts: List[DistrictDetail]

# -------------------------------------------------------------
# METRICS, BACKTEST & BASELINE MODELS
# -------------------------------------------------------------
class MetricsResponse(BaseModel):
    dataset: str
    sample_size: int
    split_policy: str
    impact_model_residual_sigma: float
    models_benchmarked: Dict[str, Any]
    ridge_bootstrap_ci: Dict[str, Any]
    conformal_quantile_regression: Dict[str, Any]
    surrogate_fidelity: Dict[str, Any]
    limitations: List[str]

class BacktestRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    disno: str = Field(..., validation_alias=AliasChoices("disno", "DisNo.", "DisNo"), serialization_alias="DisNo.")
    location: str = Field(..., validation_alias=AliasChoices("location", "Location"), serialization_alias="Location")
    provinces_count: int
    scope: str
    predicted_median: int
    predicted_p10_nominal90: int
    predicted_p90_nominal90: int
    actual: int
    ratio: float
    interval_width_orders_of_magnitude: float
    in_training_period: bool

class BacktestResponse(BaseModel):
    count: int
    disclaimer: str
    records: List[BacktestRecord]

class BaselineComparisonRow(BaseModel):
    method: str
    unmet_demand_mean: float
    unmet_pct_mean: Optional[float] = None
    unmet_pct_median: Optional[float] = None
    unmet_pct_p75: Optional[float] = None
    unmet_pct_p90: Optional[float] = None
    cost_index_mean: float
    unit_km_mean: float
    route_km_mean: float
    min_coverage_mean: float
    violations_mean: float

class BaselineResponse(BaseModel):
    evaluation_formula: str
    scenarios_evaluated: int
    results: List[BaselineComparisonRow]
    restricted_results: Optional[List[BaselineComparisonRow]] = None
    pareto_plot_url: Optional[str] = "/api/baselines/pareto-plot"

# -------------------------------------------------------------
# PREDICT IMPACT MODELS
# -------------------------------------------------------------
class ImpactPredictionRequest(BaseModel):
    hazard: HazardType = Field(default=HazardType.FLOOD, description="Disaster hazard category")
    magnitude: Optional[float] = Field(default=None, ge=0.0, le=1000.0, description="Hazard magnitude metric (e.g. Richter scale or wind speed)")
    month: Optional[int] = Field(default=7, ge=1, le=12, description="Month of event occurrence (1-12)")
    state: Optional[str] = Field(default="Maharashtra", description="Target region or state name")

class ModelPredictionItem(BaseModel):
    model_name: str
    predicted_affected: int
    architecture: str
    is_active: bool = False

class ImpactPredictionResponse(BaseModel):
    hazard: str
    month: int
    predicted_median_affected: int
    predicted_p10_affected: int
    predicted_p90_affected: int
    interval_width_orders_of_magnitude: float
    multiplicative_factor: float
    caveat: str
    provenance: ProvenanceTag = ProvenanceTag.ESTIMATED
    model_architecture: Optional[str] = "Heterogeneous Voting Ensemble (Ridge + Random Forest + XGBoost)"
    ensemble_breakdown: Optional[List[ModelPredictionItem]] = None

# -------------------------------------------------------------
# EXPLAINABILITY (SHAP) SCHEMAS
# -------------------------------------------------------------
class FeatureContribution(BaseModel):
    feature: str = Field(..., description="Human-readable feature name")
    raw_feature: str = Field(..., description="Encoded feature column name")
    feature_value: Any = Field(default=None, description="Input value of feature")
    contribution: float = Field(..., description="Contribution in log units (beta * z)")
    direction: str = Field(..., description="'positive' (increases risk) or 'negative' (decreases risk)")
    plain_english: str = Field(..., description="Plain-English explanation of this feature effect")

class LocalExplanationResponse(BaseModel):
    hazard: str
    predicted_log: float
    predicted_median: int
    base_value: float = Field(..., description="Baseline log casualty intercept / mean")
    model_name: str = Field(default="Ridge Regression (Linear Explainer)")
    top_contributions: List[FeatureContribution] = Field(..., description="Top 6 dominant feature contributions")
    all_contributions: List[FeatureContribution] = Field(..., description="All feature contributions")
    xgboost_comparison: Optional[List[FeatureContribution]] = Field(default=None, description="Optional tree-SHAP contributions for comparison")
    summary_sentence: str
    provenance: ProvenanceTag = ProvenanceTag.ESTIMATED

class GlobalFeatureImportance(BaseModel):
    feature: str
    importance: float
    direction: str

class GlobalExplanationResponse(BaseModel):
    model_name: str = "Ridge Regression & XGBoost Tree-SHAP"
    top_features: List[GlobalFeatureImportance]
    summary_plot_url: Optional[str] = "/api/explain/summary-plot"
    summary_plot_base64: Optional[str] = None
    description: str

# -------------------------------------------------------------
# SIMULATE MODELS
# -------------------------------------------------------------
class SimulationRequest(BaseModel):
    epicentre: str = Field(default="Pune", description="Epicentre district name in Maharashtra")
    hazard: HazardType = Field(default=HazardType.FLOOD, description="Disaster hazard type")
    severity: float = Field(default=1.0, ge=0.1, le=10.0, description="Severity scaling multiplier")
    affected_override: Optional[float] = Field(default=None, ge=0.0, le=150000000.0, description="Optional manual override for total affected population")
    planning_level: PlanningLevel = Field(default=PlanningLevel.P50, description="Demand quantile planning level (P50, P75, or P90)")
    stock_adjustment_pct: float = Field(default=0.0, ge=-100.0, le=500.0, description="Percentage adjustment to current medical stocks")
    custom_stocks: Optional[Dict[str, Dict[str, float]]] = Field(default=None, description="Optional user-provided custom district stocks")
    model_choice: Optional[str] = Field(default="ensemble", description="Model choice: 'ensemble', 'xgb', 'rf', 'ridge'")

# -------------------------------------------------------------
# CUSTOM STOCK MODELS
# -------------------------------------------------------------
class StockItem(BaseModel):
    district: str
    medicine: str
    quantity: float = Field(ge=0.0, description="Available stock quantity")
    provenance: str = Field(default="USER-PROVIDED", description="Data provenance classification")

class UpdateStockRequest(BaseModel):
    stocks: Optional[Dict[str, Dict[str, float]]] = Field(default=None, description="Nested mapping: district -> medicine -> quantity")
    items: Optional[List[StockItem]] = Field(default=None, description="Flat list of stock items")

class UserStockResponse(BaseModel):
    user_id: int
    total_records: int
    provenance: str = "USER-PROVIDED"
    stocks: Dict[str, Dict[str, float]]
    updated_at: Optional[str] = None
    message: str = "Custom stock updated successfully."

class DistrictMedicineDemand(BaseModel):
    district: str
    medicine: str
    demand_p10: float
    demand_p50: float
    demand_p75: float
    demand_p90: float
    selected_planning_demand: float
    available_stock: float
    expected_shortage_qty: float
    shortage_probability: float
    risk_level: str
    provenance: ProvenanceTag = ProvenanceTag.ESTIMATED_SIMULATION

class SimulationResponse(BaseModel):
    simulation_id: str
    epicentre: str
    hazard: str
    severity: float
    planning_level: str
    total_affected_simulated: int
    affected_capped_flag: bool
    results: List[DistrictMedicineDemand]
    model_used: Optional[str] = "Voting Ensemble (Ridge + Random Forest + XGBoost)"
    ensemble_comparison: Optional[Dict[str, int]] = None

# -------------------------------------------------------------
# ALLOCATE MODELS
# -------------------------------------------------------------
class AllocationRequest(BaseModel):
    simulation_id: Optional[str] = None
    epicentre: Optional[str] = "Pune"
    hazard: Optional[HazardType] = HazardType.FLOOD
    severity: Optional[float] = 1.0
    planning_level: Optional[PlanningLevel] = PlanningLevel.P50
    stock_adjustment_pct: Optional[float] = 0.0
    safety_reserve_ratio: Optional[float] = Field(default=0.60, ge=0.0, le=1.0)
    custom_stocks: Optional[Dict[str, Dict[str, float]]] = Field(default=None, description="Optional user-provided custom district stocks")

class TransferRow(BaseModel):
    source_region: str
    dest_region: str
    medicine: str
    quantity: int
    distance_km: float
    cost_index: float
    priority: str
    confidence: float

class ConstraintCheck(BaseModel):
    safety_reserve_ratio: float
    perishables_150km_limit_passed: bool
    high_risk_export_prohibition_passed: bool
    integrality_and_non_negative_passed: bool
    total_violations: int

class MethodComparisonSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    method: str
    unmet_demand: float
    cost_index: float
    unit_km: float
    route_km: float
    min_coverage: float = Field(..., validation_alias=AliasChoices("min_coverage", "minimum_coverage"))
    violations: int

class AllocationResponse(BaseModel):
    solve_status: str
    solve_time_ms: float
    total_transferred_units: int
    cost_index: float
    cost_index_note: str = "Cost index is an abstract logistics evaluation score (unit_km * 15.0 + active_routes * 500.0), NOT currency."
    unmet_demand_before: float
    unmet_demand_after: float
    demand_reduction_pct: float
    min_coverage_before: float
    min_coverage_after: float
    transfers: List[TransferRow]
    constraint_checks: ConstraintCheck
    method_comparison: List[MethodComparisonSummary]

# -------------------------------------------------------------
# AUTH & USER SCHEMAS
# -------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (at least 6 characters)")
    role: Optional[str] = Field(default="viewer", description="Role: viewer, officer, coordinator, admin")

class UserLoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str

# -------------------------------------------------------------
# AUDIT LEDGER SCHEMAS
# -------------------------------------------------------------
class AuditDecisionRequest(BaseModel):
    simulation_id: Optional[str] = None
    action: str = Field(..., description="'APPROVE' or 'REJECT'")
    reason_code: str = Field(..., description="Standardized operational reason code")
    plan_hash: str = Field(..., description="SHA-256 hash of the proposed allocation plan")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluated plan confidence score (0.0 to 1.0)")

class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    simulation_id: Optional[str]
    action: str
    reason_code: str
    plan_hash: str
    confidence: float
    prev_hash: str
    current_hash: str
    created_at: str

class AuditListResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: List[AuditEventResponse]

class AuditVerifyResponse(BaseModel):
    is_valid: bool
    total_blocks_verified: int
    broken_block: Optional[Dict[str, Any]] = None
    message: str

