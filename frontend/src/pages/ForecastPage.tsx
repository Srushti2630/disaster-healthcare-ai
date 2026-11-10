import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import {
  TrendingUp,
  AlertTriangle,
  RefreshCw,
  Clock,
  Activity,
  BarChart3,
  CheckCircle2,
  Info,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

const FULL_MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const SERVICES_LIST = [
  { id: "ALL", label: "All Specialties", color: "#3b82f6" },
  { id: "ICU", label: "Intensive Care Unit (ICU)", color: "#8b5cf6" },
  { id: "Emergency", label: "Emergency Medicine", color: "#ef4444" },
  { id: "General Medicine", label: "General Medicine", color: "#2563eb" },
  { id: "Surgery", label: "Surgery", color: "#10b981" },
];

export const ForecastPage: React.FC = () => {
  const [horizonMonths, setHorizonMonths] = useState<number>(6);
  const [selectedService, setSelectedService] = useState<string>("ALL");

  const {
    data: forecastData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["clinicalForecast", horizonMonths, selectedService],
    queryFn: () =>
      api.getClinicalForecast(
        horizonMonths,
        selectedService === "ALL" ? undefined : selectedService
      ),
  });

  const rawForecasts = useMemo(
    () => forecastData?.forecasts || [],
    [forecastData]
  );

  // Active records respecting filter
  const activeForecasts = useMemo(() => {
    if (selectedService === "ALL") return rawForecasts;
    return rawForecasts.filter((item) => item.service === selectedService);
  }, [rawForecasts, selectedService]);

  // Transform data for Recharts chronological multi-line or single-service view
  const chartData = useMemo(() => {
    if (activeForecasts.length === 0) return [];

    if (selectedService !== "ALL") {
      // Single specialty view: include point prediction and genuine bounds tuple
      return activeForecasts
        .sort((a, b) => a.horizon_step - b.horizon_step)
        .map((item) => ({
          horizon_step: item.horizon_step,
          period_index: item.period_index,
          monthLabel: `${MONTH_NAMES[item.month - 1]} ${item.year}`,
          fullMonth: `${FULL_MONTH_NAMES[item.month - 1]} ${item.year}`,
          predicted_visits: item.predicted_visits,
          interval_lower: item.interval_lower,
          interval_upper: item.interval_upper,
          interval_bounds: [item.interval_lower, item.interval_upper],
          interval_width: item.interval_width,
          service: item.service,
        }));
    }

    // All specialties mode: pivot points by horizon_step so each service is displayed independently
    const stepsMap: Record<number, any> = {};
    activeForecasts.forEach((item) => {
      const step = item.horizon_step;
      if (!stepsMap[step]) {
        stepsMap[step] = {
          horizon_step: step,
          period_index: item.period_index,
          monthLabel: `${MONTH_NAMES[item.month - 1]} ${item.year}`,
          fullMonth: `${FULL_MONTH_NAMES[item.month - 1]} ${item.year}`,
        };
      }
      stepsMap[step][item.service] = item.predicted_visits;
      stepsMap[step][`${item.service}_lower`] = item.interval_lower;
      stepsMap[step][`${item.service}_upper`] = item.interval_upper;
    });

    return Object.values(stepsMap).sort((a, b) => a.horizon_step - b.horizon_step);
  }, [activeForecasts, selectedService]);

  // Aggregate KPI summary respecting selected service and horizon without double counting
  const summaryKPIs = useMemo(() => {
    if (activeForecasts.length === 0) {
      return { totalVisits: 0, avgMonthlyVisits: 0, peakMonth: "N/A", peakVisits: 0, peakService: "N/A" };
    }

    const total = activeForecasts.reduce((acc, curr) => acc + curr.predicted_visits, 0);
    const avg = total / Math.max(1, horizonMonths);

    let peak = activeForecasts[0];
    activeForecasts.forEach((item) => {
      if (item.predicted_visits > peak.predicted_visits) {
        peak = item;
      }
    });

    return {
      totalVisits: Math.round(total),
      avgMonthlyVisits: Math.round(avg),
      peakMonth: `${MONTH_NAMES[peak.month - 1]} ${peak.year}`,
      peakVisits: Math.round(peak.predicted_visits),
      peakService: peak.service,
    };
  }, [activeForecasts, horizonMonths]);

  // Parse HTTP error codes if any
  const errorMessage = useMemo(() => {
    if (!error) return null;
    const msg = (error as any).message || String(error);
    if (msg.includes("503") || msg.toLowerCase().includes("not loaded") || msg.toLowerCase().includes("unavailable")) {
      return "Clinical forecasting model artifact (final_model.joblib) is unavailable or loading on the backend server.";
    }
    if (msg.includes("422")) {
      return "Validation error: Forecast horizon must be an integer between 1 and 12 months.";
    }
    if (msg.includes("400")) {
      return "Validation error: Unsupported clinical specialty filter.";
    }
    return msg;
  }, [error]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8" data-testid="clinical-forecast-page">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 text-blue-600 font-semibold text-xs tracking-wider uppercase">
            <TrendingUp className="w-4 h-4" />
            <span>Service-Level Predictive Intelligence</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight mt-1">
            Clinical Specialty Demand Forecasting
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Autoregressive multi-step service-level monthly patient visit projections across four clinical specialties.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200 font-medium">
            <Activity className="w-3.5 h-3.5 mr-1 text-blue-500" />
            Model: Hybrid Seasonal Ridge
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-medium">
            <Clock className="w-3.5 h-3.5 mr-1 text-slate-500" />
            Baseline History: 156 Months (2010–2022)
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-500" />
            Unit: Monthly Visits
          </span>
        </div>
      </div>

      {/* Uncertainty & Methodology Advisory Banner (Exact Wording) */}
      <div
        className="bg-amber-50 border border-amber-200 rounded-xl p-4 sm:p-5 flex items-start gap-3.5 text-amber-900"
        data-testid="uncertainty-methodology-banner"
      >
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1.5 text-xs">
          <p className="text-amber-950 font-semibold leading-relaxed">
            Uncertainty methodology: The displayed bounds are empirical heuristic training bounds calculated from in-sample training residuals (144 observations per specialty). Holdout evaluation coverage is reported as an observed result on a separate 12-month test period. These bounds are not statistically validated 90% prediction intervals and do not provide a formal finite-sample coverage guarantee.
          </p>
          <p className="text-amber-800 leading-relaxed">
            <strong>Primary Forecast:</strong> The solid trajectories represent service-level monthly point predictions for patient visits generated by the Two-Stage Hybrid Forecaster (Seasonal Naive Base + Residual L2 Ridge Regression).
          </p>
        </div>
      </div>

      {/* Interactive Controls Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Horizon Selector */}
          <div className="space-y-1.5">
            <label
              htmlFor="horizon-select"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
            >
              Forecast Horizon (Months)
            </label>
            <div className="flex items-center gap-2">
              <select
                id="horizon-select"
                aria-label="Forecast Horizon"
                value={horizonMonths}
                onChange={(e) => setHorizonMonths(Number(e.target.value))}
                className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => (
                  <option key={m} value={m}>
                    {m} Month{m > 1 ? "s" : ""} (thru {MONTH_NAMES[(m - 1) % 12]} {2023 + Math.floor((m - 1) / 12)})
                  </option>
                ))}
              </select>

              <div className="hidden sm:flex items-center gap-1">
                {[3, 6, 9, 12].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setHorizonMonths(preset)}
                    className={`px-2.5 py-1.5 text-xs rounded-md font-medium border transition-colors ${
                      horizonMonths === preset
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {preset}M
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Specialty Filter */}
          <div className="space-y-1.5">
            <label
              htmlFor="service-select"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
            >
              Clinical Specialty
            </label>
            <div className="flex flex-wrap items-center gap-1.5">
              {SERVICES_LIST.map((svc) => (
                <button
                  key={svc.id}
                  type="button"
                  aria-label={`Select ${svc.label}`}
                  onClick={() => setSelectedService(svc.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    selectedService === svc.id
                      ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                      : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {svc.id !== "ALL" && (
                    <span
                      className="inline-block w-2 h-2 rounded-full mr-1.5"
                      style={{ backgroundColor: svc.color }}
                    />
                  )}
                  {svc.label}
                </button>
              ))}
            </div>
          </div>

          {/* Refresh Action */}
          <div className="self-end lg:self-center pt-1 lg:pt-0">
            <button
              type="button"
              aria-label="Refresh Forecast Data"
              onClick={() => refetch()}
              disabled={isFetching}
              className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <LoadingSpinner message="Calculating recursive autoregressive clinical demand forecasts..." />
      )}

      {/* Error State */}
      {error && !isLoading && (
        <ErrorAlert
          message={errorMessage || "Failed to load clinical forecast data from the backend."}
          onRetry={() => refetch()}
        />
      )}

      {/* Empty State */}
      {!isLoading && !error && activeForecasts.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center space-y-3" data-testid="empty-forecast-state">
          <Info className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">No Forecast Observations Available</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            The backend returned an empty forecast dataset for the selected horizon and specialty.
          </p>
        </div>
      )}

      {/* Main Content Area */}
      {!isLoading && !error && activeForecasts.length > 0 && (
        <>
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="forecast-kpis">
            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">
                Total Projected Visits
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {summaryKPIs.totalVisits.toLocaleString()}
                </span>
                <span className="text-xs text-slate-500">visits</span>
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Cumulative across {horizonMonths} month{horizonMonths > 1 ? "s" : ""} ({selectedService === "ALL" ? "all 4 specialties" : selectedService})
              </span>
            </div>

            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">
                Average Monthly Demand
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-blue-600">
                  {summaryKPIs.avgMonthlyVisits.toLocaleString()}
                </span>
                <span className="text-xs text-slate-500">visits / mo</span>
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Rate per month ({selectedService === "ALL" ? "all 4 specialties" : selectedService})
              </span>
            </div>

            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">
                Peak Demand Specialty
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-xl font-bold text-slate-900 truncate">
                  {summaryKPIs.peakService}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 mt-1 block">
                Peak: {summaryKPIs.peakVisits.toLocaleString()} visits ({summaryKPIs.peakMonth})
              </span>
            </div>

            <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block">
                Model Architecture
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-lg font-bold text-slate-900">
                  Hybrid L2 Ridge
                </span>
              </div>
              <span className="text-[11px] text-emerald-600 font-medium mt-1 block">
                Expanding CV R² = 0.7405
              </span>
            </div>
          </div>

          {/* Chart Section */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-600" />
                  <span>Monthly Service Demand Forecast Trajectory</span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Chronological service-level point forecasts {selectedService === "ALL" ? "across all 4 specialties" : `for ${selectedService}`} over the next {horizonMonths} months (visits / month).
                </p>
              </div>

              {selectedService !== "ALL" && (
                <div className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-blue-600 inline-block" />
                    <span className="text-slate-600 font-medium">Point Forecast</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-2 bg-blue-100 border border-blue-300 inline-block" />
                    <span className="text-slate-600 font-medium">Empirical heuristic training bounds</span>
                  </div>
                </div>
              )}
            </div>

            <div className="w-full h-80 sm:h-96" data-testid="forecast-chart-container">
              <ResponsiveContainer width="100%" height="100%">
                {selectedService !== "ALL" ? (
                  <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis
                      dataKey="monthLabel"
                      stroke="#64748b"
                      fontSize={12}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={12}
                      tickLine={false}
                      domain={['auto', 'auto']}
                      label={{ value: "Visits / Month", angle: -90, position: "insideLeft", fontSize: 12, fill: "#64748b" }}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => {
                        if (name === "interval_bounds" && Array.isArray(value)) {
                          return [`[${Number(value[0]).toFixed(1)}, ${Number(value[1]).toFixed(1)}] visits`, "Empirical heuristic training bounds"];
                        }
                        if (name === "interval_upper") return [`${Number(value).toFixed(1)} visits`, "Empirical heuristic training upper bound"];
                        if (name === "interval_lower") return [`${Number(value).toFixed(1)} visits`, "Empirical heuristic training lower bound"];
                        return [`${Number(value).toFixed(1)} visits`, "Point Forecast"];
                      }}
                      labelFormatter={(label) => `Month: ${label}`}
                      contentStyle={{ backgroundColor: "#ffffff", borderColor: "#cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                    />
                    {/* Empirical bounds shaded band genuinely between lower and upper */}
                    <Area
                      type="monotone"
                      dataKey="interval_bounds"
                      stroke="#93c5fd"
                      strokeDasharray="3 3"
                      strokeWidth={1}
                      fill="#3b82f6"
                      fillOpacity={0.15}
                      name="interval_bounds"
                    />
                    {/* Primary point forecast line visually distinct from bounds */}
                    <Line
                      type="monotone"
                      dataKey="predicted_visits"
                      stroke="#1d4ed8"
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: "#1d4ed8" }}
                      activeDot={{ r: 6 }}
                      name="predicted_visits"
                    />
                  </ComposedChart>
                ) : (
                  <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis
                      dataKey="monthLabel"
                      stroke="#64748b"
                      fontSize={12}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={12}
                      tickLine={false}
                      label={{ value: "Visits / Month", angle: -90, position: "insideLeft", fontSize: 12, fill: "#64748b" }}
                    />
                    <Tooltip
                      formatter={(value: any, name: string) => [`${Number(value).toFixed(1)} visits`, name]}
                      labelFormatter={(label) => `Forecast: ${label}`}
                      contentStyle={{ backgroundColor: "#ffffff", borderColor: "#cbd5e1", borderRadius: "8px", fontSize: "12px" }}
                    />
                    <Legend wrapperStyle={{ paddingTop: "12px", fontSize: "12px" }} />
                    <Line type="monotone" dataKey="General Medicine" stroke="#2563eb" strokeWidth={2.2} dot={{ r: 3 }} name="General Medicine" />
                    <Line type="monotone" dataKey="Emergency" stroke="#ef4444" strokeWidth={2.2} dot={{ r: 3 }} name="Emergency" />
                    <Line type="monotone" dataKey="Surgery" stroke="#10b981" strokeWidth={2.2} dot={{ r: 3 }} name="Surgery" />
                    <Line type="monotone" dataKey="ICU" stroke="#8b5cf6" strokeWidth={2.2} dot={{ r: 3 }} name="ICU" />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>

          {/* Accessible Numerical Forecast Table (uses the exact same API response data) */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden" data-testid="forecast-table-container">
            <div className="p-4 sm:p-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="font-semibold text-slate-900 text-sm">
                  Numerical Monthly Forecast Registry
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Granular chronological values with point predictions and empirical heuristic training bounds.
                </p>
              </div>
              <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md font-medium border border-slate-200 self-start sm:self-auto">
                {activeForecasts.length} Total Monthly Projections
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700" aria-label="Clinical Specialty Monthly Forecasts">
                <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Step</th>
                    <th className="py-3 px-4">Period</th>
                    <th className="py-3 px-4">Calendar Month</th>
                    <th className="py-3 px-4">Specialty</th>
                    <th className="py-3 px-4 text-right">Point Forecast (Visits)</th>
                    <th className="py-3 px-4 text-right">Heuristic Lower Bound</th>
                    <th className="py-3 px-4 text-right">Heuristic Upper Bound</th>
                    <th className="py-3 px-4 text-right">Bound Width</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activeForecasts.map((row, idx) => (
                    <tr
                      key={`${row.period_index}-${row.service}`}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        idx % 2 === 0 ? "bg-white" : "bg-slate-50/30"
                      }`}
                    >
                      <td className="py-2.5 px-4 font-medium text-slate-900">
                        Month {row.horizon_step}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-[11px] text-slate-500">
                        t = {row.period_index}
                      </td>
                      <td className="py-2.5 px-4 font-medium text-slate-800">
                        {FULL_MONTH_NAMES[row.month - 1]} {row.year}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className="inline-flex items-center gap-1.5 font-medium">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{
                              backgroundColor:
                                SERVICES_LIST.find((s) => s.id === row.service)?.color || "#64748b",
                            }}
                          />
                          {row.service}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right font-bold text-slate-900">
                        {row.predicted_visits.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-slate-600">
                        {row.interval_lower.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-slate-600">
                        {row.interval_upper.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-slate-500">
                        ± {(row.interval_width / 2).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="p-3 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-500 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <span>
                * Bounds represent empirical heuristic training bounds calculated from in-sample training residuals (n=144 per specialty).
              </span>
              <span>
                Generated at: {forecastData?.generated_at ? new Date(forecastData.generated_at).toLocaleString() : "N/A"}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
