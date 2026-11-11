import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { SimulatorPage } from "../pages/SimulatorPage";
import { AllocationPage } from "../pages/AllocationPage";
import { GovernancePage } from "../pages/GovernancePage";
import { api } from "../api/client";
import {
  SimulationResponse,
  AllocationResponse,
  PendingAllocationSummary,
  AllocationDetailResponse,
  AuditVerifyResponse,
  AuditListResponse,
  AuditEvent,
} from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  api: {
    simulate: vi.fn(),
    allocate: vi.fn(),
    getBaselines: vi.fn(),
    getPendingAllocations: vi.fn(),
    getAllocationById: vi.fn(),
    recordAuditDecision: vi.fn(),
    getAuditLog: vi.fn(),
    verifyAuditChain: vi.fn(),
    getMe: vi.fn(),
  },
}));

// Mock leaflet / maps / charts
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: any) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  GeoJSON: () => <div data-testid="geojson-layer" />,
  CircleMarker: ({ children }: any) => <div data-testid="circle-marker">{children}</div>,
  Tooltip: ({ children }: any) => <div data-testid="tooltip">{children}</div>,
}));

vi.mock("recharts", async () => {
  const actual: any = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 600, height: 400 }}>{children}</div>
    ),
  };
});

const mockSimulationResult: SimulationResponse = {
  simulation_id: "sim-xyz-789",
  hazard: "Flood",
  epicentre: "Pune",
  severity: 1.5,
  planning_level: "P75",
  total_affected_simulated: 45000,
  affected_capped_flag: false,
  results: [
    {
      district: "Pune",
      medicine: "Oxygen Cylinders",
      demand_p10: 50,
      demand_p50: 80,
      demand_p75: 110,
      demand_p90: 150,
      selected_planning_demand: 110,
      available_stock: 40,
      expected_shortage_qty: 70,
      shortage_probability: 0.85,
      risk_level: "High",
      provenance: "ESTIMATED_SIMULATION",
    },
    {
      district: "Satara",
      medicine: "Oxygen Cylinders",
      demand_p10: 10,
      demand_p50: 20,
      demand_p75: 30,
      demand_p90: 45,
      selected_planning_demand: 30,
      available_stock: 100,
      expected_shortage_qty: 0,
      shortage_probability: 0.05,
      risk_level: "Low",
      provenance: "ESTIMATED_SIMULATION",
    },
  ],
};

const mockAllocationResult: AllocationResponse = {
  allocation_id: "alloc-abc-123",
  simulation_id: "sim-xyz-789",
  plan_hash: "f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201",
  status: "PENDING_REVIEW",
  solve_status: "OPTIMAL",
  solve_time_ms: 85,
  total_transferred_units: 350,
  demand_reduction_pct: 78.4,
  unmet_demand_before: 1200,
  unmet_demand_after: 260,
  cost_index: 3850,
  cost_index_note: "Logistics cost score (not currency)",
  min_coverage_before: 0.45,
  min_coverage_after: 0.88,
  constraint_checks: {
    safety_reserve_ratio: 0.15,
    perishables_150km_limit_passed: true,
    high_risk_export_prohibition_passed: true,
    integrality_and_non_negative_passed: true,
    total_violations: 0,
  },
  transfers: [
    {
      source_region: "Satara",
      dest_region: "Pune",
      medicine: "Oxygen_Cylinders",
      quantity: 120,
      distance_km: 110,
      cost_index: 2150,
      priority: "CRITICAL",
      confidence: 0.9,
    },
  ],
  method_comparison: [
    {
      method: "OR-Tools SCIP MIP",
      unmet_demand: 260,
      cost_index: 3850,
      unit_km: 13200,
      route_km: 110,
      min_coverage: 0.88,
      violations: 0,
    },
  ],
};

const mockPendingSummary: PendingAllocationSummary = {
  allocation_id: "alloc-abc-123",
  id: "alloc-abc-123",
  simulation_id: "sim-xyz-789",
  created_at: "2026-11-10T14:30:00Z",
  updated_at: "2026-11-10T14:30:00Z",
  status: "PENDING_REVIEW",
  plan_hash: "f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201",
  cost_index: 3850,
  unmet_demand_after: 260,
  transfers_count: 1,
  total_transferred_units: 350,
  creator: {
    id: 2,
    email: "officer@example.com",
    role: "officer",
  },
};

const mockDetailResponse: AllocationDetailResponse = {
  allocation_id: "alloc-abc-123",
  id: "alloc-abc-123",
  simulation_id: "sim-xyz-789",
  created_at: "2026-11-10T14:30:00Z",
  updated_at: "2026-11-10T14:30:00Z",
  status: "PENDING_REVIEW",
  plan_hash: "f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201",
  cost_index: 3850,
  unmet_demand_after: 260,
  transfers_count: 1,
  total_transferred_units: 350,
  creator: {
    id: 2,
    email: "officer@example.com",
    role: "officer",
  },
  shipments: [
    {
      source_region: "Satara",
      dest_region: "Pune",
      medicine: "Oxygen_Cylinders",
      quantity: 120,
      distance_km: 110,
      cost_index: 2150,
      priority: "CRITICAL",
      confidence: 0.9,
    },
  ],
};

const mockVerifyResponse: AuditVerifyResponse = {
  is_valid: true,
  total_blocks_verified: 5,
  message: "Ledger chain is cryptographically intact and verified",
};

const mockAuditLog: AuditListResponse = {
  items: [
    {
      id: 1,
      user_id: 1,
      created_at: "2026-11-10T14:35:00Z",
      action: "APPROVE",
      plan_hash: "f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201",
      allocation_id: "alloc-abc-123",
      simulation_id: "sim-xyz-789",
      prev_hash: "0000000000000000000000000000000000000000000000000000000000000000",
      current_hash: "1111111111111111111111111111111111111111111111111111111111111111",
      reason_code: "OPERATIONAL_SURGE_MET",
      confidence: 0.9,
    },
  ],
  total_count: 1,
  page: 1,
  page_size: 50,
};

function renderWithProviders(ui: React.ReactElement, initialRoute = "/") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Phase 3D-2 End-to-End Workflow & Governance Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("token", "coordinator-valid-token");
    // Default mock user profile (coordinator)
    vi.mocked(api.getMe).mockResolvedValue({
      id: 1,
      email: "coordinator@example.com",
      role: "coordinator",
    });
    vi.mocked(api.getBaselines).mockResolvedValue({
      dataset: "Maharastra",
      results: [],
    } as any);
    vi.mocked(api.verifyAuditChain).mockResolvedValue(mockVerifyResponse);
    vi.mocked(api.getAuditLog).mockResolvedValue(mockAuditLog);
    vi.mocked(api.getPendingAllocations).mockResolvedValue([mockPendingSummary]);
    vi.mocked(api.getAllocationById).mockResolvedValue(mockDetailResponse);
  });

  // 1 & 2: Scenario Simulator execution retains simulation_id and provides CTA button
  it("Requirement 1 & 2: Simulator executes, displays simulation_id and CTA to proceed to Allocation", async () => {
    vi.mocked(api.simulate).mockResolvedValue(mockSimulationResult);

    renderWithProviders(<SimulatorPage />, "/simulator");

    const submitBtn = screen.getByRole("button", { name: /execute simulation/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.simulate).toHaveBeenCalled();
    });

    // Displays simulation ID
    await waitFor(() => {
      expect(screen.getByText("sim-xyz-789")).toBeInTheDocument();
    });

    // CTA button exists
    const ctaBtn = screen.getByRole("button", { name: /proceed to allocation/i });
    expect(ctaBtn).toBeInTheDocument();
  });

  // 3: Allocation page shows warning and disables submit when no simulation_id is present
  it("Requirement 3: Allocation page displays unlinked warning and disables solve when simulation_id is missing", () => {
    renderWithProviders(<AllocationPage />, "/allocation");

    expect(screen.getByText("No Active Disaster Simulation Context")).toBeInTheDocument();
    expect(screen.getByText(/Go to Scenario Simulator/i)).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /simulation required/i });
    expect(submitBtn).toBeDisabled();
  });

  // 4 & 5: Allocation page receives simulation_id from state, enables submit, and sends simulation_id
  it("Requirement 4 & 5: Allocation page consumes simulation_id from router state, enables solve, and sends payload", async () => {
    vi.mocked(api.allocate).mockResolvedValue(mockAllocationResult);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/allocation",
              state: {
                simulation_id: "sim-xyz-789",
                epicentre: "Pune",
                hazard: "Flood",
                severity: 1.5,
                planning_level: "P75",
              },
            },
          ]}
        >
          <AuthProvider>
            <AllocationPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Shows active simulation linked banner
    expect(screen.getByText(/Active Simulation Linked:/i)).toBeInTheDocument();
    expect(screen.getByText("sim-xyz-789")).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /solve scip optimal allocation/i });
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.allocate).toHaveBeenCalledWith(
        expect.objectContaining({
          simulation_id: "sim-xyz-789",
          epicentre: "Pune",
          hazard: "Flood",
          severity: 1.5,
          planning_level: "P75",
        })
      );
    });
  });

  // 6: Allocation page displays PENDING_REVIEW banner and link to Governance on success
  it("Requirement 6: Allocation displays PENDING_REVIEW banner with allocation_id, plan_hash, and link to Governance", async () => {
    vi.mocked(api.allocate).mockResolvedValue(mockAllocationResult);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/allocation",
              state: { simulation_id: "sim-xyz-789" },
            },
          ]}
        >
          <AuthProvider>
            <AllocationPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const submitBtn = screen.getByRole("button", { name: /solve scip optimal allocation/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("PENDING_REVIEW")).toBeInTheDocument();
      expect(screen.getByText("alloc-abc-123")).toBeInTheDocument();
      expect(screen.getByText(/Proceed to Governance/i)).toBeInTheDocument();
    });
  });

  // 7, 8, 9: Governance queue fetches pending items, handles empty, loading, error
  it("Requirement 7: Governance queue renders pending items from /api/allocations/pending", async () => {
    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(api.getPendingAllocations).toHaveBeenCalledWith(10, 0);
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
      expect(screen.getByTitle("sim-xyz-789")).toBeInTheDocument();
    });
  });

  it("Requirement 8: Governance queue renders empty state when zero allocations are pending", async () => {
    vi.mocked(api.getPendingAllocations).mockResolvedValue([]);

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByText("Governance Queue Cleared")).toBeInTheDocument();
    });
  });

  it("Requirement 9: Governance queue handles error states gracefully", async () => {
    vi.mocked(api.getPendingAllocations).mockRejectedValue(new Error("Network connection error"));

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByText(/Network connection error/i)).toBeInTheDocument();
    });
  });

  // 10: Allocation inspection modal displays full details, shipments, and plan_hash
  it("Requirement 10: Allocation inspection modal loads full details from /api/allocations/{id}", async () => {
    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
    });

    const reviewBtn = screen.getByRole("button", { name: /review plan/i });
    fireEvent.click(reviewBtn);

    await waitFor(() => {
      expect(api.getAllocationById).toHaveBeenCalledWith("alloc-abc-123");
      expect(screen.getByText("Allocation Plan Review & Determination")).toBeInTheDocument();
      expect(screen.getByText("f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201")).toBeInTheDocument();
      expect(screen.getByText("Satara")).toBeInTheDocument();
      expect(screen.getByText("Pune")).toBeInTheDocument();
      expect(screen.getByText("Oxygen_Cylinders")).toBeInTheDocument();
    });
  });

  // 11, 12, 13: Decision submission sends required fields and confirmation dialog protects both actions
  it("Requirement 11 & 12: Approval flow opens confirmation dialog and submits allocation_id, simulation_id, and plan_hash", async () => {
    vi.mocked(api.recordAuditDecision).mockResolvedValue({
      id: 2,
      action: "APPROVE",
      status: "SUCCESS",
    } as any);

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /review plan/i }));

    await waitFor(() => {
      expect(screen.getByText("Allocation Plan Review & Determination")).toBeInTheDocument();
      expect(screen.getByText("Satara")).toBeInTheDocument();
    });

    // Click Submit Decision (triggers confirm modal)
    const submitBtn = screen.getByRole("button", { name: /submit approve decision/i });
    fireEvent.click(submitBtn);

    // Confirmation dialog appears
    expect(screen.getByText(/Confirm APPROVE Decision on Allocation/i)).toBeInTheDocument();

    // Confirm inside modal
    const confirmBtn = screen.getByRole("button", { name: /^confirm approve$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.recordAuditDecision).toHaveBeenCalledWith({
        allocation_id: "alloc-abc-123",
        simulation_id: "sim-xyz-789",
        plan_hash: "f4b8a21390e1f7c358482ad0e22a84efc71b1e9b27b322a49281a179d39b8201",
        action: "APPROVE",
        reason_code: "OPERATIONAL_SURGE_MET",
        confidence: 0.85,
      });
    });
  });

  it("Requirement 13: Rejection flow also shows confirmation dialog and submits REJECT action", async () => {
    vi.mocked(api.recordAuditDecision).mockResolvedValue({
      id: 3,
      action: "REJECT",
      status: "SUCCESS",
    } as any);

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /review plan/i }));

    await waitFor(() => {
      expect(screen.getByText("Allocation Plan Review & Determination")).toBeInTheDocument();
      expect(screen.getByText("Satara")).toBeInTheDocument();
    });

    // Select Reject
    const actionSelect = screen.getByLabelText(/Action Decision/i);
    fireEvent.change(actionSelect, { target: { value: "REJECT" } });

    // Click Submit
    fireEvent.click(screen.getByRole("button", { name: /submit reject decision/i }));

    // Confirm dialog
    expect(screen.getByText(/Confirm REJECT Decision on Allocation/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole("button", { name: /^confirm reject$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.recordAuditDecision).toHaveBeenCalledWith(
        expect.objectContaining({
          allocation_id: "alloc-abc-123",
          action: "REJECT",
        })
      );
    });
  });

  // 14: Decision failure (409 Conflict) displays clear error message to user
  it("Requirement 14: Decision failure (HTTP 409) displays warning alert to the user", async () => {
    vi.mocked(api.recordAuditDecision).mockRejectedValue(
      new Error("409 Conflict: Allocation alloc-abc-123 has already reached terminal status APPROVED")
    );

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /review plan/i }));
    await waitFor(() => {
      expect(screen.getByText("Allocation Plan Review & Determination")).toBeInTheDocument();
      expect(screen.getByText("Satara")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /submit approve decision/i }));
    fireEvent.click(screen.getByRole("button", { name: /^confirm approve$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Decision Conflict \(HTTP 409\):/i)).toBeInTheDocument();
    });
  });

  // 15: Decision success updates the UI and invalidates queries
  it("Requirement 15: Decision success shows success banner and closes inspection modal", async () => {
    vi.mocked(api.recordAuditDecision).mockResolvedValue({
      id: 4,
      action: "APPROVE",
      status: "SUCCESS",
    } as any);

    renderWithProviders(<GovernancePage />, "/governance");

    await waitFor(() => {
      expect(screen.getByTitle("alloc-abc-123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /review plan/i }));
    await waitFor(() => {
      expect(screen.getByText("Allocation Plan Review & Determination")).toBeInTheDocument();
      expect(screen.getByText("Satara")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /submit approve decision/i }));
    fireEvent.click(screen.getByRole("button", { name: /^confirm approve$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Action 'APPROVE' recorded! Block #4 appended to audit ledger/i)).toBeInTheDocument();
      // Inspection modal is closed
      expect(screen.queryByText("Allocation Plan Review & Determination")).not.toBeInTheDocument();
    });
  });

  // 16 & 17: Route protection
  it("Requirement 16: Unauthenticated user accessing protected route is redirected to /login", async () => {
    // No token in localStorage -> unauthenticated
    localStorage.removeItem("token");

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/allocation"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<div>Login Page Screen</div>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/allocation" element={<div>Protected Allocation Content</div>} />
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Login Page Screen")).toBeInTheDocument();
      expect(screen.queryByText("Protected Allocation Content")).not.toBeInTheDocument();
    });
  });

  it("Requirement 17: Authenticated user accessing protected route renders target page", async () => {
    localStorage.setItem("token", "valid-jwt-token");
    vi.mocked(api.getMe).mockResolvedValue({
      id: 1,
      email: "user@example.com",
      role: "viewer",
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/protected-test"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<div>Login Page Screen</div>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/protected-test" element={<div>Protected Content Rendered Successfully</div>} />
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Protected Content Rendered Successfully")).toBeInTheDocument();
      expect(screen.queryByText("Login Page Screen")).not.toBeInTheDocument();
    });
  });
});
