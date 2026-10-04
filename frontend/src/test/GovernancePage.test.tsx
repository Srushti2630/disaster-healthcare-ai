import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../context/AuthContext";
import { GovernancePage } from "../pages/GovernancePage";

describe("GovernancePage Component", () => {
  it("renders audit ledger verification header and action form", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <GovernancePage />
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(screen.getByText("Governance & Cryptographic Audit Ledger")).toBeInTheDocument();
    expect(screen.getByText(/human-in-the-loop officer review/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /re-verify chain/i })).toBeInTheDocument();
  });
});
