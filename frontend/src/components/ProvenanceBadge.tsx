import React from "react";
import { ProvenanceTag } from "../types";

interface ProvenanceBadgeProps {
  tag: ProvenanceTag | string;
  className?: string;
  showTooltip?: boolean;
}

export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({
  tag,
  className = "",
}) => {
  const normTag = tag.toUpperCase();

  let colorClasses = "bg-slate-100 text-slate-700 border-slate-300";
  let description = "Unspecified provenance";

  if (normTag.includes("REAL")) {
    colorClasses = "bg-emerald-100 text-emerald-800 border-emerald-300";
    description = "REAL: Directly measured empirical public data (EM-DAT, WorldPop, National Health Portal, State Audit).";
  } else if (normTag.includes("ESTIMATED")) {
    colorClasses = "bg-sky-100 text-sky-800 border-sky-300";
    description = "ESTIMATED: Derived from state anchors, facility counts, or model regression.";
  } else if (normTag.includes("ASSUMED")) {
    colorClasses = "bg-amber-100 text-amber-800 border-amber-300";
    description = "ASSUMED: Epidemiological consumption standards (WHO IEHK 2017 / Sphere) or road circuity (1.3x).";
  } else if (normTag.includes("SYNTHETIC")) {
    colorClasses = "bg-purple-100 text-purple-800 border-purple-300";
    description = "SYNTHETIC: Stochastically generated Monte-Carlo realizations or test fixtures.";
  } else if (normTag.includes("USER")) {
    colorClasses = "bg-indigo-100 text-indigo-800 border-indigo-300";
    description = "USER-PROVIDED: Officer-entered custom inventory adjustments.";
  }

  return (
    <span
      title={description}
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${colorClasses} ${className}`}
    >
      {normTag}
    </span>
  );
};
