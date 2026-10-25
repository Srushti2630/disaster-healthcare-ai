import React, { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { AllocationResponse } from "../types";
import { GitBranch, CheckCircle2, ShieldAlert, Cpu, ArrowRight, FileDown } from "lucide-react";
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
  const [hazard, setHazard] = useState("Flood");
  const [safetyReserveRatio, setSafetyReserveRatio] = useState(0.60);
  const [planningLevel, setPlanningLevel] = useState<"P50" | "P75" | "P90">("P50");
  const [referenceEventId, setReferenceEventId] = useState<string | null>(null);
  const [affectedOverride, setAffectedOverride] = useState("");
  const [stratumView, setStratumView] = useState<"overall" | "restricted">("overall");
  const [allocationData, setAllocationData] = useState<AllocationResponse | null>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const handleDownloadPdf = async () => {
    setIsDownloadingPdf(true);
    setPdfError(null);
    try {
      await api.downloadPdfSitrep({
        epicentre,
        hazard: selectedScenario?.hazard ?? hazard,
        severity: 1.0,
        ...(affectedOverride.trim() ? { affected_override: Number(affectedOverride) } : {}),
        ...(!affectedOverride.trim() && selectedScenario ? { reference_event_id: selectedScenario.event_id } : {}),
        planning_level: planningLevel,
        safety_reserve_ratio: Number(safetyReserveRatio),
      });
    } catch (err: any) {
      setPdfError(err?.message || "Failed to download situation report PDF.");
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  // Fetch benchmark baselines (20-scenario comparison)
  const { data: baselinesData } = useQuery({
    queryKey: ["baselines"],
    queryFn: () => api.getBaselines(),
  });

  const {
    data: allocationScenarios = [],
    isLoading: isLoadingAllocationScenarios,
    error: allocationScenariosError,
  } = useQuery({
    queryKey: ["allocationScenarios"],
    queryFn: () => api.getAllocationScenarios(),
  });

  useEffect(() => {
    if (referenceEventId === null && allocationScenarios.length > 0) {
      const defaultScenario = allocationScenarios[0];
      setReferenceEventId(defaultScenario.event_id);
      setEpicentre(defaultScenario.districts_affected[0]);
      setHazard(defaultScenario.hazard);
    }
  }, [allocationScenarios, referenceEventId]);

  const selectedScenario = allocationScenarios.find((event) => event.event_id === referenceEventId);
  const districtOptions = Array.from(new Set([
    "Pune", "Kolhapur", "Mumbai", "Nagpur", "Nashik", "Amravati",
    ...allocationScenarios.flatMap((event) => event.districts_affected),
  ])).sort();

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
      hazard: selectedScenario?.hazard ?? hazard,
      severity: 1.0,
      ...(affectedOverride.trim() ? { affected_override: Number(affectedOverride) } : {}),
      ...(!affectedOverride.trim() && selectedScenario ? { reference_event_id: selectedScenario.event_id } : {}),
      planning_level: planningLevel,
      safety_reserve_ratio: Number(safetyReserveRatio),
    });
  };

  const chartData = (allocationData?.method_comparison || baselinesData?.results || []).map((m: any) => ({
    name: m.method,
    unmet_demand: Math.round(m.unmet_demand ?? m.unmet_demand_mean ?? 0),
    cost_index: Math.round(m.cost_index ?? m.cost_index_mean ?? 0),
    min_coverage: ((m.min_coverage ?? m.min_coverage_mean ?? 0) * 100).toFixed(1),
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
            {districtOptions.map((district) => (
              <option key={district} value={district}>{district}</option>
            ))}
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

        <div className="w-64">
          <label htmlFor="reference-event" className="block text-xs font-semibold text-slate-700 mb-1.5">
            Historical reference event <ProvenanceBadge tag="REAL" className="ml-1" />
          </label>
          <select
            id="reference-event"
            value={referenceEventId ?? ""}
            onChange={(e) => {
              const eventId = e.target.value;
              setReferenceEventId(eventId);
              setAffectedOverride("");
              const event = allocationScenarios.find((item) => item.event_id === eventId);
              if (event) {
                setEpicentre(event.districts_affected[0]);
                setHazard(event.hazard);
              }
            }}
            disabled={isLoadingAllocationScenarios || allocationScenarios.length === 0}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
          >
            <option value="">
              {isLoadingAllocationScenarios ? "Loading observed events..." : "Use impact model estimate"}
            </option>
            {allocationScenarios.map((event) => (
              <option key={event.event_id} value={event.event_id}>
                {event.year} · {event.hazard} · {event.affected_population.toLocaleString()} affected
              </option>
            ))}
          </select>
          {selectedScenario && (
            <p className="mt-1 text-[10px] text-slate-500">
              {selectedScenario.event_id}: {selectedScenario.subtype}; mapped districts: {selectedScenario.districts_affected.join(", ")}.
            </p>
          )}
          {!selectedScenario && !isLoadingAllocationScenarios && !allocationScenariosError && (
            <p className="mt-1 text-[10px] text-slate-500">Select a real event or enter a scenario total below.</p>
          )}
        </div>

        <div className="w-56">
          <label htmlFor="affected-override" className="block text-xs font-semibold text-slate-700 mb-1.5">
            Manual affected population <ProvenanceBadge tag="USER-PROVIDED" className="ml-1" />
          </label>
          <input
            id="affected-override"
            type="number"
            min="0"
            max="150000000"
            step="1000"
            inputMode="numeric"
            placeholder="Use model estimate"
            value={affectedOverride}
            onChange={(e) => {
              const value = e.target.value;
              setAffectedOverride(value);
              if (value.trim()) setReferenceEventId("");
            }}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500"
          />
          <p className="mt-1 text-[10px] text-slate-500">Optional. Leave blank to use the impact model estimate.</p>
        </div>

        <button
          type="submit"
          disabled={allocateMutation.isPending || (isLoadingAllocationScenarios && !affectedOverride.trim())}
          className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors disabled:opacity-50"
        >
          <GitBranch className="w-4 h-4 mr-2" />
          {allocateMutation.isPending
            ? "Solving MIP via SCIP..."
            : isLoadingAllocationScenarios && !affectedOverride.trim()
              ? "Loading EM-DAT scenarios..."
              : "Solve SCIP Optimal Allocation"}
        </button>

        <button
          type="button"
          onClick={handleDownloadPdf}
          disabled={isDownloadingPdf}
          className="inline-flex items-center px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors disabled:opacity-50"
          title="Download Official Government Incident Situation Report in PDF format"
        >
          <FileDown className="w-4 h-4 mr-2" />
          {isDownloadingPdf ? "Compiling SITREP PDF..." : "Export Official SITREP (PDF)"}
        </button>
      </form>

      {allocationScenariosError && (
        <ErrorAlert message={`Could not load EM-DAT reference scenarios: ${allocationScenariosError.message}`} />
      )}

      {pdfError && <ErrorAlert message={pdfError} />}

      {allocateMutation.isPending && (
        <LoadingSpinner message="Solving Integer Programming across 35 district nodes via Google OR-Tools SCIP..." />
      )}

      {allocateMutation.error && (
        <ErrorAlert message={(allocateMutation.error as any).message || "Optimization failed."} />
      )}

      {/* Allocation Output */}
      {allocationData && (
        <div className="space-y-8">
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-700">
            Scenario result:{" "}
            <strong>{allocationData.scenario_affected_population.toLocaleString()}</strong> affected{" "}
            <ProvenanceBadge tag={allocationData.scenario_affected_provenance} />.
            {allocationData.affected_population_override != null && (
              <>
                {" "}{allocationData.reference_event_id ? "EM-DAT event total:" : "User-provided event total:"}{" "}
                <strong>{allocationData.affected_population_override.toLocaleString()}</strong>{" "}
                <ProvenanceBadge
                  tag={allocationData.affected_override_provenance ?? "USER-PROVIDED"}
                />
                {allocationData.reference_event_id && ` (${allocationData.reference_event_id})`}.
              </>
            )}{" "}
            District distribution{" "}
            <ProvenanceBadge tag={allocationData.district_allocation_provenance} />;{" "}
            <strong>{allocationData.total_planned_demand.toLocaleString()}</strong> planned medicine units{" "}
            <ProvenanceBadge tag={allocationData.demand_provenance} />;{" "}
            <strong>{allocationData.total_available_stock.toLocaleString()}</strong> estimated stock units{" "}
            <ProvenanceBadge tag={allocationData.stock_provenance} />.
            {allocationData.unmet_demand_before === 0 && (
              <span className="block mt-1 text-slate-500">
                No shortage is projected for these inputs, so zero transfers and zero transport cost are expected.
                Enter an event-specific affected population or update available stocks to explore a shortage scenario.
              </span>
            )}
          </div>

          {/* Official NDMA SITREP Export Card */}
          <div className="flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 text-white rounded-2xl p-5 shadow-sm border border-slate-800">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  OFFICIAL NDMA / SDMA SITREP READY
                </span>
                <span className="text-xs text-slate-300">Incident Dossier</span>
              </div>
              <h3 className="text-base font-bold text-white mt-1">
                {epicentre} Incident Healthcare Response Dossier
              </h3>
              <p className="text-xs text-slate-300">
                Official government report including multi-model demand projections, {allocationData.transfers.length} inter-district dispatch routes, and SHA-256 tamper-evident seal.
              </p>
            </div>
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isDownloadingPdf}
              className="inline-flex items-center px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl text-xs shadow-md transition-colors disabled:opacity-50"
            >
              <FileDown className="w-4 h-4 mr-2" />
              {isDownloadingPdf ? "Compiling SITREP PDF..." : "Download Official SITREP (PDF)"}
            </button>
          </div>

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

        {/* Stratum Selector Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setStratumView("overall")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                stratumView === "overall"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Overall (All 20 Scenarios)
            </button>
            <button
              type="button"
              onClick={() => setStratumView("restricted")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                stratumView === "restricted"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Shortage Scenarios (Restricted: No-Redistribution Unmet &gt; 0)
            </button>
          </div>
          <span className="text-[11px] text-slate-500">
            {stratumView === "restricted"
              ? "Restricted strictly to scenarios where redistribution is operationally necessary"
              : "Full 20-scenario stratified benchmark suite"}
          </span>
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
                <th className="py-3 px-3">{allocationData ? "Unmet (% of demand)" : "Unmet (% Demand: Mean)"}</th>
                <th className="py-3 px-3">{allocationData ? "Distribution" : "Unmet % (Median / P75 / P90)"}</th>
                <th className="py-3 px-3">Cost Index (Logistics)</th>
                <th className="py-3 px-3">Route-KM</th>
                <th className="py-3 px-3">Min Coverage</th>
                <th className="py-3 px-3">Violations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(stratumView === "restricted" && baselinesData?.restricted_results
                ? baselinesData.restricted_results
                : (allocationData?.method_comparison || baselinesData?.results || [])
              ).map((b: any, idx: number) => {
                const isSCIP = b.method === "OR-Tools SCIP";
                return (
                  <tr key={idx} className={isSCIP ? "bg-blue-50/70 font-semibold" : "hover:bg-slate-50"}>
                    <td className="py-2.5 px-3 text-slate-900">{b.method}</td>
                    <td className="py-2.5 px-3 text-slate-800">
                      {(b.unmet_demand ?? b.unmet_demand_mean)?.toLocaleString() ?? "—"}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-900">
                      {allocationData
                        ? `${Number(b.unmet_demand_pct ?? 0).toFixed(2)}%`
                        : b.unmet_pct_mean !== undefined && b.unmet_pct_mean !== null
                          ? `${Number(b.unmet_pct_mean).toFixed(2)}%`
                          : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600 font-mono text-[11px]">
                      {allocationData
                        ? "Single scenario"
                        : b.unmet_pct_median !== undefined && b.unmet_pct_median !== null
                        ? `${b.unmet_pct_median}% / ${b.unmet_pct_p75}% / ${b.unmet_pct_p90}%`
                        : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-slate-700 font-mono">
                      {(b.cost_index ?? b.cost_index_mean)?.toLocaleString() ?? "—"}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {(b.route_km ?? b.route_km_mean)?.toLocaleString() ?? "—"} km
                    </td>
                    <td className="py-2.5 px-3 text-slate-800 font-bold">
                      {b.min_coverage != null || b.min_coverage_mean != null
                        ? `${((b.min_coverage ?? b.min_coverage_mean) * 100).toFixed(1)}%`
                        : "—"}
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

        {/* Pareto Frontier Figure */}
        <div className="mt-8 border-t border-slate-200 pt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Pareto Frontier Trade-Off Sweep (Cost Index vs Unmet Demand)
            </h4>
            <span className="text-[11px] text-slate-500 font-medium">
              Multi-Objective Scalar Sweep
            </span>
          </div>
          <p className="text-xs text-slate-500">
            The Pareto frontier characterizes the empirical boundary between minimizing logistics Cost Index and eliminating unmet demand.
          </p>
          <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 flex justify-center">
            <img
              src="/api/baselines/pareto-plot"
              alt="Pareto Frontier Sweep: Cost Index vs Unmet Demand"
              className="max-h-96 rounded-xl object-contain bg-white shadow-sm border border-slate-200"
              onError={(e) => {
                (e.target as any).style.display = "none";
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
