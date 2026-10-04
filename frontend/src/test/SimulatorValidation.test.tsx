import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SimulatorPage } from "../pages/SimulatorPage";

describe("SimulatorPage Component", () => {
  it("renders simulator form controls and caveat banner", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <SimulatorPage />
      </QueryClientProvider>
    );

    // Check title
    expect(screen.getByText("Stochastic What-If Scenario Simulator")).toBeInTheDocument();

    // Check caveat text
    expect(screen.getByText("Honest Methodological Framing")).toBeInTheDocument();

    // Check epicentre selection
    expect(screen.getByText("Epicentre District")).toBeInTheDocument();

    // Check execute button
    expect(screen.getByRole("button", { name: /execute simulation/i })).toBeInTheDocument();
  });
});
