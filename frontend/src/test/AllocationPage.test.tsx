import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { AllocationPage } from "../pages/AllocationPage";

describe("AllocationPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    );
    vi.spyOn(api, "getBaselines").mockResolvedValue({
      evaluation_formula: "test",
      scenarios_evaluated: 1,
      results: [],
    });
    vi.spyOn(api, "getAllocationScenarios").mockResolvedValue([
      {
        event_id: "2005-0541-IND",
        year: 2005,
        hazard: "Flood",
        subtype: "Riverine flood",
        affected_population: 550000,
        districts_affected: ["Nagpur", "Bhandara"],
        scope: "multi-district",
        provenance: "REAL",
      },
    ]);
    vi.spyOn(api, "allocate").mockResolvedValue({
      solve_status: "OPTIMAL",
      solve_time_ms: 10,
      total_transferred_units: 0,
      cost_index: 0,
      cost_index_note: "Test cost index",
      unmet_demand_before: 0,
      unmet_demand_after: 0,
      demand_reduction_pct: 0,
      min_coverage_before: 1,
      min_coverage_after: 1,
      scenario_affected_population: 50000,
      scenario_affected_provenance: "ESTIMATED_SIMULATION",
      affected_population_override: null,
      affected_override_provenance: null,
      reference_event_id: "2005-0541-IND",
      total_planned_demand: 100,
      demand_provenance: "ESTIMATED_SIMULATION",
      total_available_stock: 1000,
      stock_provenance: "ESTIMATED",
      district_allocation_provenance: "ASSUMED",
      transfers: [],
      constraint_checks: {
        safety_reserve_ratio: 0.6,
        perishables_150km_limit_passed: true,
        high_risk_export_prohibition_passed: true,
        integrality_and_non_negative_passed: true,
        total_violations: 0,
      },
      method_comparison: [
        {
          method: "OR-Tools SCIP",
          unmet_demand: 0,
          cost_index: 0,
          unit_km: 0,
          route_km: 0,
          min_coverage: 1,
          violations: 0,
        },
        {
          method: "No Redistribution",
          unmet_demand: 0,
          cost_index: 0,
          unit_km: 0,
          route_km: 0,
          min_coverage: 1,
          violations: 0,
        },
      ],
    });
  });

  it("renders allocation results with zero-valued comparison metrics", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AllocationPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /historical reference event/i })).toHaveValue("2005-0541-IND");
    });
    fireEvent.click(screen.getByRole("button", { name: /solve scip optimal allocation/i }));

    await waitFor(() => {
      expect(screen.getByText("Recommended Inter-District Transfers (0 Routes)")).toBeInTheDocument();
    });
    expect(screen.getByText("No Redistribution")).toBeInTheDocument();
  });

  it("sends a user-provided event total to the optimizer", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AllocationPage />
      </QueryClientProvider>
    );

    fireEvent.change(screen.getByLabelText(/manual affected population/i), {
      target: { value: "10000000" },
    });
    fireEvent.click(screen.getByRole("button", { name: /solve scip optimal allocation/i }));

    await waitFor(() => {
      expect(api.allocate).toHaveBeenCalledWith(expect.objectContaining({ affected_override: 10000000 }));
    });
  });

  it("uses the default real EM-DAT event when solving", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AllocationPage />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /historical reference event/i })).toHaveValue("2005-0541-IND");
    });
    fireEvent.click(screen.getByRole("button", { name: /solve scip optimal allocation/i }));

    await waitFor(() => {
      expect(api.allocate).toHaveBeenCalledWith(expect.objectContaining({
        reference_event_id: "2005-0541-IND",
        epicentre: "Nagpur",
        hazard: "Flood",
      }));
    });
  });
});
