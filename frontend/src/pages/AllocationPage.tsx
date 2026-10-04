import React, { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { AllocationResponse } from "../types";
import { GitBranch, CheckCircle2, ShieldAlert, Cpu, ArrowRight } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export const AllocationPage: React.FC = () => {
  const [epicentre, setEpicentre] = useState("Pune");
  const [safetyReserveRatio, setSafetyReserveRatio] = useState(0.60);
  const [planningLevel, setPlanningLevel] = useState<"P50" | "P75" | "P90">("P50");
  const [allocationData, setAllocationData] = useState<AllocationResponse | null>(null);

  // Fetch benchmark baselines (20-scenario comparison)
  const { data: baselinesData } = useQuery({
    queryKey: ["baselines"],
    queryFn: () => api.getBaselines(),
  });

  const allocateMutation = useMutation({
    mutationFn: (payload: any) => api.allocate(payload),
    onSuccess: (data) => {
      setAllocationData(data);
    },
  });

  const handleRunOptimizer = (e: React.FormEvent) => {
    e.preventDefault();
    allocateMutation.mutate({
      epicentre,
      hazard: "Flood",
      severity: 1.0,
      planning_level: planningLevel,
      safety_reserve_ratio: Number(safetyReserveRatio),
    });
  };

  const chartData = (allocationData?.method_comparison || baselinesData?.results || []).map((m: any) => ({
    name: m.method,
    unmet_demand: Math.round(m.unmet_demand || m.unmet_demand_mean),
    cost_index: Math.round(m.cost_index || m.cost_index_mean),
    min_coverage: ((m.min_coverage || m.min_coverage_mean) * 100).toFixed(1),
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Operations Research Multi-Objective Allocation
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Google OR-Tools SCIP Mixed-Integer Linear Programming (MIP) Solver with perishables distance constraints and local safety reserves.
        </p>
      </div>

      {/* Cost Index Explanatory Note */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3">
        <Cpu className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
        <div className="text-xs text-blue-900 space-y-1">
          <p className="font-semibold">Logistics Evaluation Score: Cost Index</p>
          <p>
            Transport cost is measured as an abstract logistics score:{" "}
            <code className="bg-blue-100 px-1 py-0.5 rounded font-mono">
              Cost Index = unit_km × 15.0 + active_routes × 500.0
            </code>
            . This is a mathematical optimization cost function, <strong>not commercial currency</strong>.
          </p>
        </div>
      </div>

      {/* Solver Controls Form */}
      <form
        onSubmit={handleRunOptimizer}
        className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-wrap items-end gap-6"
      >
        <div className="w-48">
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Disaster Epicentre
          </label>
          <select
            value={epicentre}
            onChange={(e) => setEpicentre(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500"
          >
            <option value="Pune">Pune</option>
            <option value="Kolhapur">Kolhapur</option>
            <option value="Mumbai">Mumbai</option>
            <option value="Nagpur">Nagpur</option>
            <option value="Nashik">Nashik</option>
            <option value="Amravati">Amravati</option>
          </select>
        </div>

        <div className="w-48">
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Planning Level
          </label>
          <select
            value={planningLevel}
            onChange={(e) => setPlanningLevel(e.target.value as any)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500"
          >
            <option value="P50">P50 (Median Demand)</option>
            <option value="P75">P75 (Buffer Demand)</option>
            <option value="P90">P90 (Worst-Case Surge)</option>
          </select>
        </div>

        <div className="w-56">
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Local Safety Reserve: <span className="font-bold text-blue-600">{(safetyReserveRatio * 100).toFixed(0)}%</span>
          </label>
          <input
            type="range"
            min="0.30"
            max="0.90"
            step="0.05"
            value={safetyReserveRatio}
            onChange={(e) => setSafetyReserveRatio(Number(e.target.value))}
            className="w-full accent-blue-600 cursor-pointer"
          />
        </div>

        <button
          type="submit"
          disabled={allocateMutation.isPending}
          className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors disabled:opacity-50"
        >
          <GitBranch className="w-4 h-4 mr-2" />
          {allocateMutation.isPending ? "Solving MIP via SCIP..." : "Solve SCIP Optimal Allocation"}
        </button>
      </form>

      {allocateMutation.isPending && (
        <LoadingSpinner message="Solving Integer Programming across 35 district nodes via Google OR-Tools SCIP..." />
      )}

      {allocateMutation.error && (
        <ErrorAlert message={(allocateMutation.error as any).message || "Optimization failed."} />
      )}

      {/* Allocation Output */}
      {allocationData && (
        <div className="space-y-8">
          {/* Metrics Overview Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <span className="text-xs font-medium text-slate-500">Solver Status</span>
              <div className="my-2 flex items-center gap-2">
                <span className="text-xl font-bold text-emerald-600">{allocationData.solve_status}</span>
                <span className="text-xs text-slate-400 font-mono">({allocationData.solve_time_ms} ms)</span>
              </div>
              <p className="text-xs text-slate-500">Google OR-Tools SCIP</p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <span className="text-xs font-medium text-slate-500">Transferred Units</span>
              <div className="my-2">
                <span className="text-xl font-bold text-slate-800">
                  {allocationData.total_transferred_units.toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-slate-500">Across {allocationData.transfers.length} inter-district routes</p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <span className="text-xs font-medium text-slate-500">Demand Reduction</span>
              <div className="my-2">
                <span className="text-xl font-bold text-blue-600">
                  {allocationData.demand_reduction_pct.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Unmet: {allocationData.unmet_demand_after.toLocaleString()} vs {allocationData.unmet_demand_before.toLocaleString()}
              </p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <span className="text-xs font-medium text-slate-500">Transport Cost Index</span>
              <div className="my-2">
                <span className="text-xl font-bold text-slate-800">
                  {allocationData.cost_index.toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-slate-500">Logistics index (not currency)</p>
            </div>
          </div>

          {/* Operational Constraint Checks */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Operational Constraint Validation
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Safety Reserve</h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Remaining stock ≥ {(allocationData.constraint_checks.safety_reserve_ratio * 100).toFixed(0)}% of demand
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Perishables Limit</h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Blood transfers strictly ≤ 150 km
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-slate-800">High-Risk Export</h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Districts with high risk cannot export
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Integrality Check</h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Total violations: <strong>{allocationData.constraint_checks.total_violations}</strong>
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Transfers Table */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Recommended Inter-District Transfers ({allocationData.transfers.length} Routes)
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-3">Route (Source → Destination)</th>
                    <th className="py-3 px-3">Medicine</th>
                    <th className="py-3 px-3">Quantity</th>
                    <th className="py-3 px-3">Distance</th>
                    <th className="py-3 px-3">Cost Index</th>
                    <th className="py-3 px-3">Priority</th>
                    <th className="py-3 px-3">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {allocationData.transfers.map((t, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-slate-900 flex items-center gap-1.5">
                        <span>{t.source_region}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                        <span className="text-blue-600">{t.dest_region}</span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">{t.medicine.replace("_", " ")}</td>
                      <td className="py-2.5 px-3 font-bold text-slate-800">{t.quantity.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-slate-500">{t.distance_km} km</td>
                      <td className="py-2.5 px-3 text-slate-500 font-mono">{t.cost_index.toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold ${
                            t.priority === "CRITICAL"
                              ? "bg-red-100 text-red-800 border border-red-300"
                              : "bg-blue-100 text-blue-800 border border-blue-300"
                          }`}
                        >
                          {t.priority}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">{(t.confidence * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                  {allocationData.transfers.length === 0 && (
                    <tr>
                      <td colSpan={7} className="text-center py-6 text-slate-400">
                        No inter-district transfers required for this scenario.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Baseline Comparison (Shared Evaluator) */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            Method Comparison Benchmark (Shared Constraint Evaluator)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluated across 20 Monte-Carlo scenarios using unified cost: Cost Index = unit_km × 15.0 + active_routes × 500.0.
          </p>
        </div>

        {/* Chart */}
        {chartData.length > 0 && (
          <div className="w-full h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis yAxisId="left" orientation="left" tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="unmet_demand" fill="#dc2626" name="Mean Unmet Demand" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Comparison Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">Method</th>
                <th className="py-3 px-3">Unmet Demand (units)</th>
                <th className="py-3 px-3">Cost Index (Logistics)</th>
                <th className="py-3 px-3">Unit-KM</th>
                <th className="py-3 px-3">Route-KM</th>
                <th className="py-3 px-3">Min Coverage</th>
                <th className="py-3 px-3">Violations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(allocationData?.method_comparison || baselinesData?.results || []).map((b: any, idx: number) => {
                const isSCIP = b.method === "OR-Tools SCIP";
                return (
                  <tr key={idx} className={isSCIP ? "bg-blue-50/70 font-semibold" : "hover:bg-slate-50"}>
                    <td className="py-2.5 px-3 text-slate-900">{b.method}</td>
                    <td className="py-2.5 px-3 text-slate-800">
                      {(b.unmet_demand || b.unmet_demand_mean).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-slate-700 font-mono">
                      {(b.cost_index || b.cost_index_mean).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {(b.unit_km || b.unit_km_mean).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {(b.route_km || b.route_km_mean).toLocaleString()} km
                    </td>
                    <td className="py-2.5 px-3 text-slate-800 font-bold">
                      {((b.min_coverage || b.min_coverage_mean) * 100).toFixed(1)}%
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-emerald-700 font-bold">
                        {b.violations ?? b.violations_mean}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
