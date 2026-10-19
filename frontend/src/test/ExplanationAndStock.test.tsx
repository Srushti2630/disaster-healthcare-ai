import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../context/AuthContext";
import { PredictionExplanationPanel } from "../components/PredictionExplanationPanel";
import { StockEditingTable } from "../components/StockEditingTable";
import { api } from "../api/client";

// Mock the API client
vi.mock("../api/client", () => ({
  api: {
    explain: vi.fn(),
    getGlobalExplanation: vi.fn(),
    getStock: vi.fn(),
    updateStock: vi.fn(),
    resetStock: vi.fn(),
    getMe: vi.fn().mockResolvedValue({
      id: "test-user-id",
      email: "officer@mahadisaster.gov.in",
      role: "officer",
      created_at: "2026-01-01T00:00:00"
    }),
  },
}));

// Mock ResponsiveContainer for recharts in jsdom
vi.mock("recharts", async () => {
  const actual: any = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

describe("PredictionExplanationPanel Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  it("renders Ridge SHAP explanation, top feature contributions, and plain-English sentences", async () => {
    (api.explain as any).mockResolvedValueOnce({
      hazard: "Flood",
      predicted_log: 9.85,
      predicted_median: 18958,
      base_value: 8.50,
      top_contributions: [
        {
          feature: "rainfall_deviation",
          value: 45.2,
          contribution: 0.82,
          direction: "positive",
          plain_english: "Rainfall anomaly (+45.20%) added ~0.82 log units to predicted casualties.",
        },
        {
          feature: "hazard_severity",
          value: 1.0,
          contribution: 0.55,
          direction: "positive",
          plain_english: "Event severity (1.00) added ~0.55 log units to expected demand.",
        },
      ],
      summary_sentence: "Prediction is +1.35 log units above baseline, driven mostly by rainfall_deviation and hazard_severity.",
      xgboost_comparison: [],
    });

    render(
      <QueryClientProvider client={queryClient}>
        <PredictionExplanationPanel hazard="Flood" magnitude={6.5} month={8} />
      </QueryClientProvider>
    );

    // Verify main header
    await waitFor(() => {
      expect(screen.getByText(/Explain this Prediction/i)).toBeInTheDocument();
    });

    // Verify model overview callouts
    expect(screen.getByText("Evaluated Hazard:")).toBeInTheDocument();
    expect(screen.getByText("Predicted Log Impact:")).toBeInTheDocument();

    // Verify summary narrative
    expect(screen.getByText(/Feature Attribution Summary:/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Prediction is \+1\.35 log units above baseline/i)
    ).toBeInTheDocument();

    // Verify plain-English feature list
    const plainEnglishList = screen.getByTestId("plain-english-list");
    expect(plainEnglishList).toBeInTheDocument();
    expect(
      screen.getByText(/Rainfall anomaly \(\+45\.20%\) added ~0\.82 log units to predicted casualties\./i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Event severity \(1\.00\) added ~0\.55 log units to expected demand\./i)
    ).toBeInTheDocument();
  });
});

describe("StockEditingTable Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  it("renders stock editing table with controls and handles custom stock", async () => {
    (api.getStock as any).mockResolvedValueOnce({
      provenance: "USER-PROVIDED",
      total_records: 1,
      stocks: {
        Pune: {
          antibiotics: 85000,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StockEditingTable />
        </AuthProvider>
      </QueryClientProvider>
    );

    // Verify table header and provenance
    expect(
      screen.getByText("District Inventory & Custom Stock Override")
    ).toBeInTheDocument();

    // Verify action buttons
    expect(screen.getByTestId("save-stock-button")).toBeInTheDocument();
    expect(screen.getByTestId("reset-stock-button")).toBeInTheDocument();

    // Verify district search input
    expect(screen.getByPlaceholderText("Search district...")).toBeInTheDocument();

    // Verify district table rendered
    await waitFor(() => {
      expect(screen.getByText("Pune")).toBeInTheDocument();
      expect(screen.getByText("Mumbai")).toBeInTheDocument();
    });
  });
});
