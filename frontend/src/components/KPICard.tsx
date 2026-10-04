import React from "react";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { ProvenanceTag } from "../types";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  tag?: ProvenanceTag | string;
  icon?: React.ReactNode;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  subtitle,
  tag,
  icon,
}) => {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex flex-col justify-between hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>
      <div className="my-3 flex items-baseline justify-between gap-2">
        <span className="text-2xl font-bold text-slate-800 tracking-tight">
          {typeof value === "number" ? value.toLocaleString() : value}
        </span>
        {tag && <ProvenanceBadge tag={tag} />}
      </div>
      {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
    </div>
  );
};
