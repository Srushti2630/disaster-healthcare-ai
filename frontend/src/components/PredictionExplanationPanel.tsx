import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorAlert } from "./ErrorAlert";
import { ProvenanceBadge } from "./ProvenanceBadge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { HelpCircle, BarChart2, TrendingUp, TrendingDown, Image as ImageIcon } from "lucide-react";

interface PredictionExplanationPanelProps {
  hazard: string;
  magnitude?: number;
  month?: number;
}

export const PredictionExplanationPanel: React.FC<PredictionExplanationPanelProps> = ({
  hazard,
  magnitude,
  month = 7,
}) => {
  const [showGlobalPlot, setShowGlobalPlot] = useState(false);
  const [showTreeShapCompare, setShowTreeShapCompare] = useState(false);

  const {
    data: explainData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["explainPrediction", hazard, magnitude, month],
    queryFn: () => api.explain({ hazard, magnitude, month }),
  });

  const { data: globalData } = useQuery({
    queryKey: ["globalExplanation"],
    queryFn: () => api.getGlobalExplanation(),
    enabled: showGlobalPlot,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4 shadow-sm" data-testid="explanation-loading">
        <LoadingSpinner message="Decomposing prediction features via Ridge Linear Explainer..." />
      </div>
    );
  }

  if (error || !explainData) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4 shadow-sm" data-testid="explanation-error">
        <ErrorAlert
          message={error?.message || "Failed to calculate prediction explanation."}
          onRetry={refetch}
        />
      </div>
    );
  }

  const top6 = explainData.top_contributions || [];

  // Chart data formatted for Recharts
  const chartData = top6.map((item) => ({
    name: item.feature,
    contribution: item.contribution,
    direction: item.direction,
    plainEnglish: item.plain_english,
  }));

  return (
    <div
      className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-sm"
      data-testid="explanation-panel"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-blue-600" />
            <h3 className="text-lg font-bold text-slate-900">
              Explain this Prediction (Ridge SHAP Decomposition)
            </h3>
            <ProvenanceBadge tag="ESTIMATED" />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Exact feature contributions ($\beta_j \cdot z_j$) explaining the Ridge model's point casualty prediction.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowGlobalPlot(!showGlobalPlot)}
            className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 shadow-sm transition-colors"
          >
            <ImageIcon className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
            {showGlobalPlot ? "Hide Global Summary" : "View Global SHAP"}
          </button>
        </div>
      </div>

      {/* Model Overview Callout */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-50 rounded-xl p-4 border border-slate-200 text-xs">
        <div>
          <span className="text-slate-500">Evaluated Hazard:</span>
          <p className="font-bold text-slate-800 text-sm mt-0.5">{explainData.hazard}</p>
        </div>
        <div>
          <span className="text-slate-500">Predicted Log Impact:</span>
          <p className="font-bold text-blue-600 text-sm mt-0.5">
            {explainData.predicted_log} <span className="text-slate-400 font-normal">log units</span>
          </p>
        </div>
        <div>
          <span className="text-slate-500">Estimated Median Casualties:</span>
          <p className="font-bold text-slate-900 text-sm mt-0.5">
            ~{explainData.predicted_median.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Summary Narrative */}
      <div className="text-xs text-slate-700 bg-blue-50/60 border border-blue-200/60 rounded-xl p-3.5 flex items-start gap-2.5">
        <HelpCircle className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
        <div>
          <span className="font-semibold text-blue-900">Feature Attribution Summary: </span>
          <span>{explainData.summary_sentence}</span>
        </div>
      </div>

      {/* Top 6 Contributions Bar Chart */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Top 6 Feature Contributions (Log Units)
          </h4>
          <span className="text-[11px] text-slate-400">
            Red = Increases Casualties &bull; Blue = Decreases Casualties
          </span>
        </div>

        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={chartData}
              margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
              <XAxis
                type="number"
                domain={["auto", "auto"]}
                tick={{ fontSize: 11, fill: "#64748b" }}
                unit=" log"
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11, fill: "#334155", fontWeight: 500 }}
                width={120}
              />
              <Tooltip
                formatter={(val: any) => [`${Number(val) > 0 ? "+" : ""}${Number(val).toFixed(2)} log units`, "Contribution"]}
                contentStyle={{ borderRadius: "8px", fontSize: "12px", border: "1px solid #cbd5e1" }}
              />
              <ReferenceLine x={0} stroke="#94a3b8" />
              <Bar dataKey="contribution" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.contribution >= 0 ? "#ef4444" : "#3b82f6"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* One Plain-English Sentence Per Feature */}
      <div className="space-y-3 pt-2">
        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
          Plain-English Interpretability (One Sentence Per Feature)
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="plain-english-list">
          {top6.map((item, idx) => (
            <div
              key={idx}
              className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5 transition-all hover:bg-slate-100/70"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  {item.contribution >= 0 ? (
                    <TrendingUp className="w-3.5 h-3.5 text-red-500" />
                  ) : (
                    <TrendingDown className="w-3.5 h-3.5 text-blue-500" />
                  )}
                  {item.feature}
                </span>
                <span
                  className={`text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full ${
                    item.contribution >= 0
                      ? "bg-red-100 text-red-700"
                      : "bg-blue-100 text-blue-700"
                  }`}
                >
                  {item.contribution >= 0 ? `+${item.contribution.toFixed(2)}` : item.contribution.toFixed(2)} log
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{item.plain_english}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Comparison with XGBoost Tree-SHAP (Optional Toggle) */}
      {explainData.xgboost_comparison && explainData.xgboost_comparison.length > 0 && (
        <div className="border-t border-slate-200 pt-4">
          <button
            type="button"
            onClick={() => setShowTreeShapCompare(!showTreeShapCompare)}
            className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1"
          >
            {showTreeShapCompare ? "Hide" : "Show"} Tree-SHAP Comparison (XGBoost Non-linear Interaction Baseline)
          </button>

          {showTreeShapCompare && (
            <div className="mt-3 p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <p className="text-xs text-slate-500 mb-2">
                While the linear Ridge model governs point estimates, Tree-SHAP on XGBoost captures non-linear interactions across historical events:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {explainData.xgboost_comparison.map((item, idx) => (
                  <div key={idx} className="flex justify-between items-center text-xs p-2 bg-white rounded-lg border border-slate-200">
                    <span className="font-medium text-slate-700">{item.feature}</span>
                    <span className={`font-mono font-semibold ${item.contribution >= 0 ? "text-amber-600" : "text-blue-600"}`}>
                      {item.contribution >= 0 ? `+${item.contribution.toFixed(2)}` : item.contribution.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Global SHAP Summary Plot Modal / Section */}
      {showGlobalPlot && (
        <div className="border-t border-slate-200 pt-4 space-y-3" data-testid="global-shap-section">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Saved Global SHAP Summary Plot (reports/shap_summary.png)
            </h4>
          </div>
          <p className="text-xs text-slate-500">
            Global distribution of impact features across CRED EM-DAT training data:
          </p>

          <div className="bg-slate-900 rounded-xl p-3 flex justify-center">
            {globalData?.summary_plot_base64 ? (
              <img
                src={globalData.summary_plot_base64}
                alt="Global SHAP Summary Plot"
                className="max-h-96 rounded-lg object-contain bg-white"
              />
            ) : (
              <img
                src="/api/explain/summary-plot"
                alt="Global SHAP Summary Plot"
                className="max-h-96 rounded-lg object-contain bg-white"
                onError={(e) => {
                  (e.target as any).style.display = "none";
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
