import {
  DistrictListResponse,
  MetricsResponse,
  BacktestResponse,
  BaselineResponse,
  ImpactPredictionResponse,
  LocalExplanationResponse,
  GlobalExplanationResponse,
  SimulationResponse,
  AllocationResponse,
  TokenResponse,
  User,
  AuditEvent,
  AuditListResponse,
  AuditVerifyResponse
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("token");
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.message || errorData.detail || errorMessage;
    } catch {
      // Use fallback error message
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export const api = {
  // Public & Data Endpoints
  getDistricts: () => request<DistrictListResponse>("/api/districts"),
  getGeoDistricts: () => request<any>("/api/geo/districts"),
  getMetrics: () => request<MetricsResponse>("/api/metrics"),
  getBacktest: () => request<BacktestResponse>("/api/backtest"),
  getBaselines: () => request<BaselineResponse>("/api/baselines"),

  // Decision Support & Simulation
  predictImpact: (data: { hazard: string; magnitude?: number; month?: number; state?: string }) =>
    request<ImpactPredictionResponse>("/api/predict-impact", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  explain: (data: { hazard: string; magnitude?: number; month?: number; state?: string }) =>
    request<LocalExplanationResponse>("/api/explain", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getGlobalExplanation: () => request<GlobalExplanationResponse>("/api/explain/global"),

  simulate: (data: {
    epicentre: string;
    hazard: string;
    severity: number;
    planning_level: "P50" | "P75" | "P90";
    stock_adjustment_pct?: number;
    affected_override?: number;
  }) =>
    request<SimulationResponse>("/api/simulate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  allocate: (data: {
    epicentre?: string;
    hazard?: string;
    severity?: number;
    planning_level?: "P50" | "P75" | "P90";
    safety_reserve_ratio?: number;
    stock_adjustment_pct?: number;
  }) =>
    request<AllocationResponse>("/api/allocate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Auth Endpoints
  login: (data: { email: string; password: string }) =>
    request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  register: (data: { email: string; password: string; role?: string }) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getMe: () => request<User>("/api/auth/me"),

  // Audit Endpoints
  recordAuditDecision: (data: {
    simulation_id?: string;
    action: "APPROVE" | "REJECT";
    reason_code: string;
    plan_hash: string;
    confidence: number;
  }) =>
    request<AuditEvent>("/api/audit/decision", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getAuditLog: (page = 1, pageSize = 20) =>
    request<AuditListResponse>(`/api/audit?page=${page}&page_size=${pageSize}`),

  verifyAuditChain: () => request<AuditVerifyResponse>("/api/audit/verify"),
};
