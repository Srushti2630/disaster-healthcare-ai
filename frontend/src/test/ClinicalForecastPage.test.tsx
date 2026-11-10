import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ForecastPage } from "../pages/ForecastPage";
import { api } from "../api/client";
import { ClinicalForecastResponse } from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  api: {
    getClinicalForecast: vi.fn(),
  },
}));

// Mock ResponsiveContainer for Recharts in jsdom
vi.mock("recharts", async () => {
  const actual: any = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 600, height: 400 }}>{children}</div>
    ),
  };
});

const sampleForecastResponse: ClinicalForecastResponse = {
  model_name: "Hybrid_Seasonal_Ridge",
  model_version: "1.0.0",
  generated_at: "2026-11-10T22:00:00Z",
  horizon_months: 6,
  total_forecasts: 24,
  forecasts: [
    {
      period_index: 157,
      horizon_step: 1,
      year: 2023,
      month: 1,
      service: "ICU",
      predicted_visits: 55.05,
      interval_lower: 38.75,
      interval_upper: 71.35,
      interval_width: 32.6,
      methodology: "Empirical Pre-Holdout Residual Quantile (90% Nominal Coverage)",
      calibration_samples: 144,
    },
    {
      period_index: 157,
      horizon_step: 1,
      year: 2023,
      month: 1,
      service: "Emergency",
      predicted_visits: 120.20,
      interval_lower: 23.70,
      interval_upper: 216.70,
      interval_width: 193.0,
      methodology: "Empirical Pre-Holdout Residual Quantile (90% Nominal Coverage)",
      calibration_samples: 144,
    },
    {
      period_index: 157,
      horizon_step: 1,
      year: 2023,
      month: 1,
      service: "General Medicine",
      predicted_visits: 188.29,
      interval_lower: 149.79,
      interval_upper: 226.79,
      interval_width: 77.0,
      methodology: "Empirical Pre-Holdout Residual Quantile (90% Nominal Coverage)",
      calibration_samples: 144,
    },
    {
      period_index: 157,
      horizon_step: 1,
      year: 2023,
      month: 1,
      service: "Surgery",
      predicted_visits: 81.17,
      interval_lower: 58.57,
      interval_upper: 103.77,
      interval_width: 45.2,
      methodology: "Empirical Pre-Holdout Residual Quantile (90% Nominal Coverage)",
      calibration_samples: 144,
    },
  ],
};

describe("ClinicalForecastPage (ForecastPage)", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <ForecastPage />
      </QueryClientProvider>
    );

  it("1. Successfully renders forecast header, KPIs, chart container, and numerical table", async () => {
    (api.getClinicalForecast as any).mockResolvedValueOnce(sampleForecastResponse);

    renderComponent();

    // Wait for async query to resolve and content to render
    await waitFor(() => {
      expect(screen.getByTestId("forecast-kpis")).toBeInTheDocument();
    });

    expect(screen.getByText("Clinical Specialty Demand Forecasting")).toBeInTheDocument();
    expect(screen.getByText("Total Projected Visits")).toBeInTheDocument();
    expect(screen.getByText("Average Monthly Demand")).toBeInTheDocument();
    expect(screen.getByText("Peak Demand Specialty")).toBeInTheDocument();

    // Check Chart container
    expect(screen.getByTestId("forecast-chart-container")).toBeInTheDocument();

    // Check numerical table
    expect(screen.getByTestId("forecast-table-container")).toBeInTheDocument();
    expect(screen.getByText("Numerical Monthly Forecast Registry")).toBeInTheDocument();
    expect(screen.getByText("55.05")).toBeInTheDocument(); // ICU point forecast
    expect(screen.getByText("120.20")).toBeInTheDocument(); // Emergency point forecast
  });

  it("2. Handles service selection and triggers query with chosen specialty filter", async () => {
    (api.getClinicalForecast as any).mockResolvedValue(sampleForecastResponse);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText("Clinical Specialty Demand Forecasting")).toBeInTheDocument();
    });

    // Initial call without specialty filter (ALL)
    expect(api.getClinicalForecast).toHaveBeenCalledWith(6, undefined);

    // Select Emergency Medicine
    const emergencyBtn = screen.getByRole("button", { name: /Select Emergency Medicine/i });
    fireEvent.click(emergencyBtn);

    await waitFor(() => {
      expect(api.getClinicalForecast).toHaveBeenCalledWith(6, "Emergency");
    });
  });

  it("3. Handles horizon selection and triggers query with updated horizon", async () => {
    (api.getClinicalForecast as any).mockResolvedValue(sampleForecastResponse);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText(/Forecast Horizon/i)).toBeInTheDocument();
    });

    const horizonSelect = screen.getByLabelText(/Forecast Horizon/i);
    fireEvent.change(horizonSelect, { target: { value: "12" } });

    await waitFor(() => {
      expect(api.getClinicalForecast).toHaveBeenCalledWith(12, undefined);
    });

    // Preset button click (3M)
    const preset3M = screen.getByRole("button", { name: "3M" });
    fireEvent.click(preset3M);

    await waitFor(() => {
      expect(api.getClinicalForecast).toHaveBeenCalledWith(3, undefined);
    });
  });

  it("4. Displays loading state with informative spinner during fetch", () => {
    (api.getClinicalForecast as any).mockReturnValue(new Promise(() => {})); // Never resolves

    renderComponent();

    expect(
      screen.getByText(/Calculating recursive autoregressive clinical demand forecasts\.\.\./i)
    ).toBeInTheDocument();
  });

  it("5. Displays clear empty state message when backend returns zero forecasts", async () => {
    (api.getClinicalForecast as any).mockResolvedValueOnce({
      model_name: "Hybrid_Seasonal_Ridge",
      model_version: "1.0.0",
      generated_at: "2026-11-10T22:00:00Z",
      horizon_months: 6,
      total_forecasts: 0,
      forecasts: [],
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("empty-forecast-state")).toBeInTheDocument();
      expect(screen.getByText("No Forecast Observations Available")).toBeInTheDocument();
    });
  });

  it("6. Displays friendly error explanation when backend returns HTTP 503 model-unavailable", async () => {
    (api.getClinicalForecast as any).mockRejectedValueOnce(
      new Error("HTTP 503: Clinical forecasting model not loaded or unavailable.")
    );

    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByText(/Clinical forecasting model artifact \(final_model\.joblib\) is unavailable or loading/i)
      ).toBeInTheDocument();
    });
  });

  it("7. Displays validation error when backend rejects invalid horizon (HTTP 422)", async () => {
    (api.getClinicalForecast as any).mockRejectedValueOnce(
      new Error("HTTP 422: Unprocessable Entity")
    );

    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByText(/Validation error: Forecast horizon must be an integer between 1 and 12 months\./i)
      ).toBeInTheDocument();
    });
  });

  it("8. Exactly labels uncertainty bounds as 'Empirical heuristic training bounds'", async () => {
    (api.getClinicalForecast as any).mockResolvedValueOnce(sampleForecastResponse);

    renderComponent();

    await waitFor(() => {
      const banner = screen.getByTestId("uncertainty-methodology-banner");
      expect(banner).toBeInTheDocument();
      expect(banner.textContent).toContain("Empirical Heuristic Training Bounds");
      expect(banner.textContent).toContain("empirical heuristic training bounds");
      expect(banner.textContent).toContain("not statistically validated 90% prediction intervals");
    });
  });

  it("9. Strictly omits misleading conformal or guaranteed-coverage claims", async () => {
    (api.getClinicalForecast as any).mockResolvedValueOnce(sampleForecastResponse);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("clinical-forecast-page")).toBeInTheDocument();
    });

    const pageContent = screen.getByTestId("clinical-forecast-page").textContent || "";

    // Prohibited terms
    expect(pageContent).not.toMatch(/90%\s+conformal\s+interval/i);
    expect(pageContent).not.toMatch(/90%\s+confidence\s+interval/i);
    expect(pageContent).not.toMatch(/90%\s+guaranteed/i);
    expect(pageContent).not.toMatch(/guaranteed\s+coverage/i);
  });

  it("10. Provides accessible controls with aria labels and semantic labels", async () => {
    (api.getClinicalForecast as any).mockResolvedValueOnce(sampleForecastResponse);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText("Forecast Horizon")).toBeInTheDocument();
      expect(screen.getByLabelText("Refresh Forecast Data")).toBeInTheDocument();
      expect(screen.getByRole("table", { name: "Clinical Specialty Monthly Forecasts" })).toBeInTheDocument();
    });
  });
});
