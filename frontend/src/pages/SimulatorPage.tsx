import React, { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { DistrictMap } from "../components/DistrictMap";
import { SimulationResponse, DistrictMedicineDemand } from "../types";
import { PredictionExplanationPanel } from "../components/PredictionExplanationPanel";
import { Play, Info, AlertTriangle, Filter } from "lucide-react";
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

const MAHARASHTRA_DISTRICT_NAMES = [
  "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
  "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
  "Kolhapur", "Latur", "Mumbai", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar",
  "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri",
  "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"
];

export const SimulatorPage: React.FC = () => {
  const [epicentre, setEpicentre] = useState("Pune");
  const [hazard, setHazard] = useState("Flood");
  const [severity, setSeverity] = useState(1.0);
  const [planningLevel, setPlanningLevel] = useState<"P50" | "P75" | "P90">("P50");
  const [stockAdjustmentPct, setStockAdjustmentPct] = useState(0);
  const [affectedOverride, setAffectedOverride] = useState<string>("");
  const [selectedMedicineFilter, setSelectedMedicineFilter] = useState("antibiotics");
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);

  const { data: geoJsonData } = useQuery({
    queryKey: ["geoDistricts"],
    queryFn: () => api.getGeoDistricts(),
  });

  const simulateMutation = useMutation({
    mutationFn: (data: any) => api.simulate(data),
    onSuccess: (data) => {
      setSimulationResult(data);
    },
  });

  const handleRunSimulation = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: any = {
      epicentre,
      hazard,
      severity: Number(severity),
      planning_level: planningLevel,
      stock_adjustment_pct: Number(stockAdjustmentPct),
    };
    if (affectedOverride && !isNaN(Number(affectedOverride))) {
      payload.affected_override = Number(affectedOverride);
    }
    simulateMutation.mutate(payload);
  };

  const results: DistrictMedicineDemand[] = simulationResult?.results || [];
  const filteredResults = results.filter((r) => r.medicine === selectedMedicineFilter);

  // Top 10 shortage districts for chart
  const chartData = filteredResults
    .filter((r) => r.shortage_probability > 0)
    .sort((a, b) => b.shortage_probability - a.shortage_probability)
    .slice(0, 8)
    .map((r) => ({
      name: r.district,
      Demand: Math.round(r.selected_planning_demand),
      Stock: Math.round(r.available_stock),
      RiskProb: Math.round(r.shortage_probability * 100),
    }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Stochastic What-If Scenario Simulator
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          2,000-draw Monte-Carlo demand simulation coupling empirical impact distributions with WHO IEHK / Sphere standards.
        </p>
      </div>

      {/* Mandatory Honest Methodological Caveat */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-xs text-amber-800 space-y-1">
          <p className="font-semibold">Honest Methodological Framing</p>
          <p>
            The disaster impact prediction model <strong>ranks events by relative severity</strong> and is intended for prioritizing districts, but <strong>underestimates very large tail outliers</strong>.
            Demand consumption rates are <ProvenanceBadge tag="ASSUMED" /> from WHO IEHK 2017 & Sphere Handbook standards. Simulated affected casualties are strictly capped at each district's real population.
          </p>
        </div>
      </div>

      {/* Simulation Controls Form */}
      <form
        onSubmit={handleRunSimulation}
        className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Epicentre District
            </label>
            <select
              value={epicentre}
              onChange={(e) => setEpicentre(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:bg-white"
            >
              {MAHARASHTRA_DISTRICT_NAMES.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Hazard Category
            </label>
            <select
              value={hazard}
              onChange={(e) => setHazard(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:bg-white"
            >
              <option value="Flood">Flood</option>
              <option value="Storm">Storm</option>
              <option value="Earthquake">Earthquake</option>
              <option value="Epidemic">Epidemic</option>
              <option value="Extreme temperature">Extreme Temperature</option>
              <option value="Mass movement (wet)">Mass Movement (Wet)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Planning Demand Quantile
            </label>
            <select
              value={planningLevel}
              onChange={(e) => setPlanningLevel(e.target.value as any)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:bg-white"
            >
              <option value="P50">P50 (Median Expected Demand)</option>
              <option value="P75">P75 (Conservative Buffer)</option>
              <option value="P90">P90 (90th Percentile Worst-Case Surge)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Severity Scale: <span className="font-bold text-blue-600">{severity}x</span>
            </label>
            <input
              type="range"
              min="0.2"
              max="5.0"
              step="0.1"
              value={severity}
              onChange={(e) => setSeverity(Number(e.target.value))}
              className="w-full accent-blue-600 cursor-pointer"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Inventory Stress Adjustment:{" "}
              <span className={`font-bold ${stockAdjustmentPct < 0 ? "text-red-600" : "text-emerald-600"}`}>
                {stockAdjustmentPct > 0 ? `+${stockAdjustmentPct}%` : `${stockAdjustmentPct}%`}
              </span>
            </label>
            <input
              type="range"
              min="-70"
              max="50"
              step="5"
              value={stockAdjustmentPct}
              onChange={(e) => setStockAdjustmentPct(Number(e.target.value))}
              className="w-full accent-blue-600 cursor-pointer"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Optional Casualty Override (Count)
            </label>
            <input
              type="number"
              placeholder="e.g. 85000"
              value={affectedOverride}
              onChange={(e) => setAffectedOverride(e.target.value)}
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={simulateMutation.isPending}
            className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors disabled:opacity-50"
          >
            <Play className="w-4 h-4 mr-2" />
            {simulateMutation.isPending ? "Executing 2,000 Stochastic Draws..." : "Execute Simulation"}
          </button>
        </div>
      </form>

      {simulateMutation.isPending && (
        <LoadingSpinner message="Sampling 2,000 draws (Impact Model Residual Sigma x WHO Consumption Norms)..." />
      )}

      {simulateMutation.error && (
        <ErrorAlert message={(simulateMutation.error as any).message || "Simulation failed."} />
      )}

      {/* Simulation Results Section */}
      {simulationResult && (
        <div className="space-y-8">
          {/* Summary Banner */}
          <div className="bg-slate-900 text-white rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <span className="text-xs uppercase tracking-wider text-blue-400 font-bold">
                Simulation Complete
              </span>
              <h3 className="text-xl font-bold mt-1">
                {simulationResult.hazard} Event centered at {simulationResult.epicentre}
              </h3>
              <p className="text-xs text-slate-300 mt-1">
                Total statewide casualties evaluated:{" "}
                <span className="font-semibold text-white">
                  {simulationResult.total_affected_simulated.toLocaleString()}
                </span>
                {simulationResult.affected_capped_flag && (
                  <span className="ml-2 text-amber-300 font-semibold">(Capped at district population)</span>
                )}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-lg text-xs font-semibold">
                Quantile: {simulationResult.planning_level}
              </span>
              <ProvenanceBadge tag="ESTIMATED_SIMULATION" />
            </div>
          </div>

          {/* Choropleth Map with Risk Colors */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Shortage Risk Choropleth Map
                </h3>
                <p className="text-xs text-slate-500">
                  Color-coded shortage probabilities across all 35 district polygons:{" "}
                  <span className="text-red-600 font-semibold">Red (High &gt;40%)</span>,{" "}
                  <span className="text-amber-600 font-semibold">Yellow (Medium 10-40%)</span>,{" "}
                  <span className="text-emerald-600 font-semibold">Green (Low &lt;10%)</span>.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-400" />
                <select
                  value={selectedMedicineFilter}
                  onChange={(e) => setSelectedMedicineFilter(e.target.value)}
                  className="px-3 py-1.5 bg-slate-50 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-blue-500"
                >
                  <option value="antibiotics">Antibiotics</option>
                  <option value="ors">ORS Sachets</option>
                  <option value="iv_fluids">IV Fluids</option>
                  <option value="analgesics">Analgesics</option>
                  <option value="blood_units">Blood Units</option>
                </select>
              </div>
            </div>

            {geoJsonData && (
              <DistrictMap
                geoJsonData={geoJsonData}
                simulationResults={results}
                selectedMedicine={selectedMedicineFilter}
              />
            )}
          </div>

          {/* Shortage Gap Bar Chart */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">
                Top Priority Deficit Districts ({selectedMedicineFilter.replace("_", " ").toUpperCase()})
              </h3>
              <p className="text-xs text-slate-500">
                Comparing required surge demand ({simulationResult.planning_level}) against available local stock.
              </p>

              <div className="w-full h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="Demand" fill="#ef4444" name="Surge Demand" />
                    <Bar dataKey="Stock" fill="#3b82f6" name="Available Stock" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Simulation Output Table */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Monte-Carlo Demand Quantiles & Shortage Risks
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-3">District</th>
                    <th className="py-3 px-3">Medicine</th>
                    <th className="py-3 px-3">P10 Demand</th>
                    <th className="py-3 px-3">P50 (Median)</th>
                    <th className="py-3 px-3">P75</th>
                    <th className="py-3 px-3">P90</th>
                    <th className="py-3 px-3">Stock</th>
                    <th className="py-3 px-3">Shortage Prob</th>
                    <th className="py-3 px-3">Risk Level</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredResults.map((r, idx) => {
                    const isHigh = r.risk_level === "High";
                    const isMed = r.risk_level === "Medium";
                    return (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-slate-900">{r.district}</td>
                        <td className="py-2.5 px-3 text-slate-600">{r.medicine.replace("_", " ")}</td>
                        <td className="py-2.5 px-3 text-slate-500">{r.demand_p10.toLocaleString()}</td>
                        <td className="py-2.5 px-3 font-medium text-slate-800">{r.demand_p50.toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-slate-500">{r.demand_p75.toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-slate-500">{r.demand_p90.toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-slate-700">{r.available_stock.toLocaleString()}</td>
                        <td className="py-2.5 px-3 font-semibold">
                          {(r.shortage_probability * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-[11px] font-bold ${
                              isHigh
                                ? "bg-red-100 text-red-800 border border-red-300"
                                : isMed
                                ? "bg-amber-100 text-amber-800 border border-amber-300"
                                : "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            }`}
                          >
                            {r.risk_level}
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
      )}

      {/* Explain this Prediction (SHAP) Section */}
      <PredictionExplanationPanel
        hazard={hazard}
        magnitude={severity}
        month={7}
      />
    </div>
  );
};
