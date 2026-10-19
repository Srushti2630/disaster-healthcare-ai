export type ProvenanceTag = "REAL" | "ESTIMATED" | "ASSUMED" | "ESTIMATED_SIMULATION";

export interface DistrictBedCapacity {
  beds_low: number;
  beds_mid: number;
  beds_high: number;
  icu_beds_low: number;
  icu_beds_mid: number;
  icu_beds_high: number;
  provenance: ProvenanceTag;
}

export interface DistrictFacilities {
  total_facilities: number;
  public_facilities: number;
  private_facilities: number;
  provenance: ProvenanceTag;
}

export interface DistrictDetail {
  district: string;
  population: number;
  area_sqkm: number;
  pop_density_sqkm: number;
  capacity: DistrictBedCapacity;
  facilities: DistrictFacilities;
  total_facilities?: number;
  provenance: ProvenanceTag;
}

export interface DistrictListResponse {
  total_districts: number;
  total_state_population: number;
  state_hospital_beds_anchor: number;
  state_icu_beds_anchor: number;
  total_facilities?: number;
  total_cleaned_facilities?: number;
  districts: DistrictDetail[];
}

export interface MetricsResponse {
  dataset: string;
  sample_size: number;
  split_policy: string;
  impact_model_residual_sigma: number;
  models_benchmarked: Record<string, {
    test_mae_log: number;
    test_rmse_log?: number;
    test_r2: number;
    test_spearman_rho: number;
    accuracy_within_half_order_of_magnitude_pct: number;
  }>;
  ridge_bootstrap_ci: {
    r2_95_ci: [number, number];
    spearman_rho_95_ci: [number, number];
  };
  conformal_quantile_regression: {
    nominal_confidence: number;
    empirical_test_coverage_pct: number;
    coverage_95_ci_pct: [number, number];
    median_interval_multiplicative_factor: number;
    conformal_margin_log_units: number;
    calibration_disclaimer?: string;
  };
  surrogate_fidelity: {
    held_out_accuracy: number;
    macro_f1: number;
    ece: number;
    n_scenarios_evaluated: number;
  };
  limitations: string[];
}

export interface BacktestRecord {
  "DisNo."?: string;
  disno?: string;
  Location?: string;
  location?: string;
  provinces_count: number;
  scope: string;
  predicted_median: number;
  predicted_p10_nominal90: number;
  predicted_p90_nominal90: number;
  actual: number;
  ratio: number;
  interval_width_orders_of_magnitude: number;
  in_training_period: boolean;
}

export interface BacktestResponse {
  count: number;
  disclaimer: string;
  records: BacktestRecord[];
}

export interface BaselineComparisonRow {
  method: string;
  unmet_demand_mean: number;
  cost_index_mean: number;
  unit_km_mean: number;
  route_km_mean: number;
  min_coverage_mean: number;
  violations_mean: number;
}

export interface BaselineResponse {
  evaluation_formula: string;
  scenarios_evaluated: number;
  results: BaselineComparisonRow[];
}

export interface ImpactPredictionResponse {
  hazard: string;
  month: number;
  predicted_median_affected: number;
  predicted_p10_affected: number;
  predicted_p90_affected: number;
  interval_width_orders_of_magnitude: number;
  multiplicative_factor: number;
  caveat: string;
  provenance: ProvenanceTag;
}

export interface DistrictMedicineDemand {
  district: string;
  medicine: string;
  demand_p10: number;
  demand_p50: number;
  demand_p75: number;
  demand_p90: number;
  selected_planning_demand: number;
  available_stock: number;
  expected_shortage_qty: number;
  shortage_probability: number;
  risk_level: "Low" | "Medium" | "High";
  provenance: ProvenanceTag;
}

export interface SimulationResponse {
  simulation_id: string;
  epicentre: string;
  hazard: string;
  severity: number;
  planning_level: string;
  total_affected_simulated: number;
  affected_capped_flag: boolean;
  results: DistrictMedicineDemand[];
}

export interface TransferRow {
  source_region: string;
  dest_region: string;
  medicine: string;
  quantity: number;
  distance_km: number;
  cost_index: number;
  priority: string;
  confidence: number;
}

export interface ConstraintCheck {
  safety_reserve_ratio: number;
  perishables_150km_limit_passed: boolean;
  high_risk_export_prohibition_passed: boolean;
  integrality_and_non_negative_passed: boolean;
  total_violations: number;
}

export interface MethodComparisonSummary {
  method: string;
  unmet_demand: number;
  cost_index: number;
  unit_km: number;
  route_km: number;
  min_coverage: number;
  violations: number;
}

export interface AllocationResponse {
  solve_status: string;
  solve_time_ms: number;
  total_transferred_units: number;
  cost_index: number;
  cost_index_note: string;
  unmet_demand_before: number;
  unmet_demand_after: number;
  demand_reduction_pct: number;
  min_coverage_before: number;
  min_coverage_after: number;
  transfers: TransferRow[];
  constraint_checks: ConstraintCheck;
  method_comparison: MethodComparisonSummary[];
}

export interface User {
  id: number;
  email: string;
  role: "viewer" | "officer" | "coordinator" | "admin";
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  email: string;
}

export interface AuditEvent {
  id: number;
  user_id: number;
  simulation_id: string | null;
  action: "APPROVE" | "REJECT";
  reason_code: string;
  plan_hash: string;
  confidence: number;
  prev_hash: string;
  current_hash: string;
  created_at: string;
}

export interface AuditListResponse {
  total_count: number;
  page: number;
  page_size: number;
  items: AuditEvent[];
}

export interface AuditVerifyResponse {
  is_valid: boolean;
  total_blocks_verified: number;
  broken_block?: {
    broken_row_id: number;
    row_index: number;
    error_type: string;
    expected_hash?: string;
    found_hash?: string;
    expected_prev_hash?: string;
    found_prev_hash?: string;
  } | null;
  message: string;
}

export interface FeatureContribution {
  feature: string;
  raw_feature: string;
  feature_value?: any;
  contribution: number;
  direction: "positive" | "negative";
  plain_english: string;
}

export interface LocalExplanationResponse {
  hazard: string;
  predicted_log: number;
  predicted_median: number;
  base_value: number;
  model_name: string;
  top_contributions: FeatureContribution[];
  all_contributions: FeatureContribution[];
  xgboost_comparison?: FeatureContribution[];
  summary_sentence: string;
  provenance: ProvenanceTag;
}

export interface GlobalFeatureImportance {
  feature: string;
  importance: number;
  direction: string;
}

export interface GlobalExplanationResponse {
  model_name: string;
  top_features: GlobalFeatureImportance[];
  summary_plot_url?: string;
  summary_plot_base64?: string;
  description: string;
}
