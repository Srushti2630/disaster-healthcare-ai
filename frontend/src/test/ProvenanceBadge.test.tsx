import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { ProvenanceBadge } from "../components/ProvenanceBadge";

describe("ProvenanceBadge Component", () => {
  it("renders REAL tag with emerald styling", () => {
    render(<ProvenanceBadge tag="REAL" />);
    const badge = screen.getByText("REAL");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-emerald-100");
  });

  it("renders ESTIMATED tag with sky blue styling", () => {
    render(<ProvenanceBadge tag="ESTIMATED" />);
    const badge = screen.getByText("ESTIMATED");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-sky-100");
  });

  it("renders ASSUMED tag with amber styling", () => {
    render(<ProvenanceBadge tag="ASSUMED" />);
    const badge = screen.getByText("ASSUMED");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-amber-100");
  });
});
