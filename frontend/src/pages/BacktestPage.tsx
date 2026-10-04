import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { History, AlertCircle } from "lucide-react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from "recharts";

export const BacktestPage: React.FC = () => {
  const { data: backtestData, isLoading, error, refetch } = useQuery({
    queryKey: ["backtest"],
    queryFn: () => api.getBacktest(),
  });

  if (isLoading) {
    return <LoadingSpinner message="Loading historical disaster backtesting logs..." />;
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <ErrorAlert message={(error as any).message || "Failed to load backtest."} onRetry={refetch} />
      </div>
    );
  }

  const records = backtestData?.records || [];

  // Log10 transform for scatter plot
  const scatterPoints = records.map((r: any) => {
    const disno = r["DisNo."] || r.disno || "Disaster";
    const actual = r.actual || 1;
    const pred = r.predicted_median || 1;
    return {
      name: disno,
      actualLog: Number(Math.log10(actual).toFixed(2)),
      predLog: Number(Math.log10(pred).toFixed(2)),
      actual: actual,
      predicted: pred,
      scope: r.scope,
    };
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Historical Disaster Backtest Replay (CRED EM-DAT)
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Leave-One-Event-Out validation by DisNo. across benchmark Indian disasters.
        </p>
      </div>

      {/* Honest Scientific Disclaimer */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-xs text-amber-900 space-y-1">
          <p className="font-semibold">Backtest Evaluation & Scope Limitations</p>
          <p>
            {backtestData?.disclaimer ||
              "Historical backtesting demonstrates that while event rankings correlate with observed casualties, very large events are underestimated by 30-150x."}
          </p>
          <p className="text-[11px] text-amber-700">
            EM-DAT disaster event totals are national or multi-state; local district shares are <ProvenanceBadge tag="ASSUMED" /> population-proportional.
          </p>
        </div>
      </div>

      {/* Scatter Plot Log-Log */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <h3 className="text-lg font-bold text-slate-900">
          Predicted Median vs. Actual Casualties (Log₁₀ Scale)
        </h3>
        <p className="text-xs text-slate-500">
          Events clustered below the 45-degree line indicate underestimation of extreme catastrophe events.
        </p>

        <div className="w-full h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="actualLog"
                name="Actual (log10)"
                unit=" dex"
                domain={[3, 8]}
                tick={{ fontSize: 11 }}
                label={{ value: "Actual Casualties (log10)", position: "insideBottom", offset: -10, fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="predLog"
                name="Predicted (log10)"
                unit=" dex"
                domain={[3, 8]}
                tick={{ fontSize: 11 }}
                label={{ value: "Predicted Median (log10)", angle: -90, position: "insideLeft", fontSize: 11 }}
              />
              <ZAxis range={[100, 100]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={({ payload }) => {
                  if (payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-slate-900 text-white text-xs p-3 rounded-lg shadow-lg space-y-1">
                        <p className="font-bold">{data.name}</p>
                        <p>Actual: {data.actual.toLocaleString()}</p>
                        <p>Predicted: {data.predicted.toLocaleString()}</p>
                        <p>Scope: {data.scope}</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Scatter name="Disasters" data={scatterPoints} fill="#2563eb" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Backtest Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <h3 className="text-lg font-bold text-slate-900">
          Leave-One-Event-Out Historical Disaster Backtest Table
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">DisNo.</th>
                <th className="py-3 px-3">Location Details</th>
                <th className="py-3 px-3">Spatial Scope</th>
                <th className="py-3 px-3">Predicted Median</th>
                <th className="py-3 px-3">CQR 90% Interval [P10 – P90]</th>
                <th className="py-3 px-3">Actual Affected</th>
                <th className="py-3 px-3">Pred/Actual Ratio</th>
                <th className="py-3 px-3">Interval Width</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {records.map((r: any, idx: number) => {
                const disno = r["DisNo."] || r.disno;
                const loc = r.Location || r.location;
                const isMulti = r.scope === "multi-state";
                return (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-3 font-mono font-bold text-slate-900">{disno}</td>
                    <td className="py-3 px-3 max-w-xs text-slate-600 truncate" title={loc}>
                      {loc}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-[11px] font-bold ${
                          isMulti
                            ? "bg-purple-100 text-purple-800 border border-purple-300"
                            : "bg-blue-100 text-blue-800 border border-blue-300"
                        }`}
                      >
                        {r.scope}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-800">
                      {r.predicted_median.toLocaleString()}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-600">
                      [{r.predicted_p10_nominal90.toLocaleString()} – {r.predicted_p90_nominal90.toLocaleString()}]
                    </td>
                    <td className="py-3 px-3 font-bold text-slate-900">
                      {r.actual.toLocaleString()}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-700">
                      {(r.ratio * 100).toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-slate-500 font-mono">
                      {r.interval_width_orders_of_magnitude.toFixed(1)} orders
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
