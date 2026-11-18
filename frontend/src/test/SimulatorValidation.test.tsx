import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../context/AuthContext";
import { SimulatorPage } from "../pages/SimulatorPage";

describe("SimulatorPage Component", () => {
  it("renders simulator form controls and caveat banner", () => {
    const queryClient = new QueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <SimulatorPage />
          </AuthProvider>
        </QueryClientProvider>
      </BrowserRouter>
    );

    // Check title
    expect(screen.getByText("Stochastic What-If Scenario Simulator")).toBeInTheDocument();

    // Check risk classification legend
    expect(screen.getByText("Monte-Carlo Shortage Risk Classification:")).toBeInTheDocument();

    // Check epicentre selection
    expect(screen.getByText("Epicentre District")).toBeInTheDocument();

    // Check execute button
    expect(screen.getByRole("button", { name: /execute simulation/i })).toBeInTheDocument();
  });
});
