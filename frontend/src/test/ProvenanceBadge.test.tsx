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

  it("renders SYNTHETIC tag with purple styling", () => {
    render(<ProvenanceBadge tag="SYNTHETIC" />);
    const badge = screen.getByText("SYNTHETIC");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-purple-100");
  });

  it("renders USER-PROVIDED tag with indigo styling", () => {
    render(<ProvenanceBadge tag="USER-PROVIDED" />);
    const badge = screen.getByText("USER-PROVIDED");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-indigo-100");
  });
});
