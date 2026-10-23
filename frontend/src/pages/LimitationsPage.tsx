import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { AlertCircle, Database, CheckCircle2, ShieldAlert } from "lucide-react";

export const LimitationsPage: React.FC = () => {
  const { data: metricsData, isLoading, error } = useQuery({
    queryKey: ["metrics"],
    queryFn: () => api.getMetrics(),
  });

  if (isLoading) {
    return <LoadingSpinner message="Loading dataset provenance and methodological limitations..." />;
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <ErrorAlert message={(error as any).message || "Failed to load limitations."} />
      </div>
    );
  }

  const limitations = metricsData?.limitations || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Data Sources, Provenance & Methodological Limitations
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Strict, machine-readable data provenance classification and transparent scientific constraints.
        </p>
      </div>

      {/* Provenance Hierarchy Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">
            Data Asset Provenance Registry
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">Asset / Dataset</th>
                <th className="py-3 px-3">Provenance Tag</th>
                <th className="py-3 px-3">Primary Source</th>
                <th className="py-3 px-3">Records & Methodological Treatment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">EM-DAT Disaster Catalogue</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="REAL" /></td>
                <td className="py-3 px-3 text-slate-700">CRED EM-DAT International Disaster Database</td>
                <td className="py-3 px-3 text-slate-600">810 India disaster events (512 with recorded targets); casualty targets never imputed.</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">WorldPop Population Raster</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="REAL" /></td>
                <td className="py-3 px-3 text-slate-700">WorldPop 2020, about 100 m (3 arc-second)</td>
                <td className="py-3 px-3 text-slate-600">Raw zonal sum per district; 131.9M total vs 124.5M projection (5.97% gap reported unscaled).</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">National Hospital Directory</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="REAL" /></td>
                <td className="py-3 px-3 text-slate-700">Open Government Data Portal India (data.gov.in)</td>
                <td className="py-3 px-3 text-slate-600">4,767 Maharashtra health facilities classified by public/private mix and coordinates.</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">State ICU Beds Audit</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="REAL" /></td>
                <td className="py-3 px-3 text-slate-700">State ICU audit (provided dataset; original publisher not stated)</td>
                <td className="py-3 px-3 text-slate-600">11,587 total state ICU beds (2,572 public / 9,015 private).</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">District Hospital Bed Capacity</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="ESTIMATED" /></td>
                <td className="py-3 px-3 text-slate-700">Derived from State Bed Anchor + Facility Counts</td>
                <td className="py-3 px-3 text-slate-600">Allocated from 144,983 state total hospital bed anchor across 35 districts.</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">Epidemiological Demand Rates</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="ASSUMED" /></td>
                <td className="py-3 px-3 text-slate-700">WHO IEHK 2017 & Sphere Handbook Norms</td>
                <td className="py-3 px-3 text-slate-600">Per-patient daily medicine consumption rates and epidemic durations.</td>
              </tr>
              <tr>
                <td className="py-3 px-3 font-semibold text-slate-900">Distance Matrix</td>
                <td className="py-3 px-3"><ProvenanceBadge tag="ASSUMED" /></td>
                <td className="py-3 px-3 text-slate-700">Haversine Distance × 1.3 Circuity Factor</td>
                <td className="py-3 px-3 text-slate-600">Road transport circuity matrix across 35 district centroids.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Model Benchmark Performance */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <h2 className="text-lg font-bold text-slate-900">
          Impact Model Performance & Bootstrap Confidence Intervals
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-xs text-slate-500 font-semibold">Ridge Test R² (95% CI)</span>
            <p className="text-xl font-bold text-slate-900 mt-1">
              {metricsData?.models_benchmarked?.Ridge?.test_r2 || 0.278}
            </p>
            <p className="text-[11px] text-slate-500 mt-1 font-mono">
              95% CI: [{metricsData?.ridge_bootstrap_ci?.r2_95_ci?.[0]}, {metricsData?.ridge_bootstrap_ci?.r2_95_ci?.[1]}]
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-xs text-slate-500 font-semibold">Spearman Rank Correlation ρ</span>
            <p className="text-xl font-bold text-slate-900 mt-1">
              {metricsData?.models_benchmarked?.Ridge?.test_spearman_rho || 0.52}
            </p>
            <p className="text-[11px] text-slate-500 mt-1 font-mono">
              95% CI: [{metricsData?.ridge_bootstrap_ci?.spearman_rho_95_ci?.[0]}, {metricsData?.ridge_bootstrap_ci?.spearman_rho_95_ci?.[1]}]
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-xs text-slate-500 font-semibold">Surrogate Classifier Fidelity</span>
            <p className="text-xl font-bold text-emerald-600 mt-1">
              {(metricsData?.surrogate_fidelity?.held_out_accuracy ? metricsData.surrogate_fidelity.held_out_accuracy * 100 : 91.3).toFixed(1)}%
            </p>
            <p className="text-[11px] text-slate-500 mt-1">
              Held-out scenario accuracy across 500 Monte-Carlo scenarios
            </p>
          </div>
        </div>

        {/* Ensemble & Model Comparison Table */}
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-800">
              Heterogeneous Ensemble Model Benchmark Comparison
            </h3>
            <span className="text-[11px] bg-emerald-50 text-emerald-700 px-2.5 py-0.5 rounded-full border border-emerald-200 font-semibold">
              Time-Split Test Set (N=78)
            </span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead>
                <tr className="bg-slate-100 text-slate-700 font-semibold">
                  <th className="py-2.5 px-3 text-left">Model Architecture</th>
                  <th className="py-2.5 px-3 text-left">Technique</th>
                  <th className="py-2.5 px-3 text-right">Test MAE (Log)</th>
                  <th className="py-2.5 px-3 text-right">Test R²</th>
                  <th className="py-2.5 px-3 text-right">Spearman ρ</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <tr className="hover:bg-slate-50">
                  <td className="py-2 px-3 font-semibold text-slate-800">Ridge Regression</td>
                  <td className="py-2 px-3 text-slate-600">L2 Regularized Linear</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Ridge?.test_mae_log ?? "2.8812"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Ridge?.test_r2 ?? "0.2780"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Ridge?.test_spearman_rho ?? "0.5199"}</td>
                  <td className="py-2 px-3 text-center"><span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">Base Estimator</span></td>
                </tr>
                <tr className="hover:bg-slate-50">
                  <td className="py-2 px-3 font-semibold text-slate-800">Random Forest</td>
                  <td className="py-2 px-3 text-slate-600">Bagging Ensemble (100 Trees)</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Random_Forest?.test_mae_log ?? "3.3398"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Random_Forest?.test_r2 ?? "-0.0289"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.Random_Forest?.test_spearman_rho ?? "0.2933"}</td>
                  <td className="py-2 px-3 text-center"><span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">Base Estimator</span></td>
                </tr>
                <tr className="hover:bg-slate-50">
                  <td className="py-2 px-3 font-semibold text-slate-800">XGBoost Regressor</td>
                  <td className="py-2 px-3 text-slate-600">Gradient Boosting (Trees)</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.XGBoost?.test_mae_log ?? "3.0908"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.XGBoost?.test_r2 ?? "0.1403"}</td>
                  <td className="py-2 px-3 text-right font-mono">{metricsData?.models_benchmarked?.XGBoost?.test_spearman_rho ?? "0.4454"}</td>
                  <td className="py-2 px-3 text-center"><span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">Base Estimator</span></td>
                </tr>
                <tr className="bg-emerald-50/70 border-t-2 border-emerald-300 font-semibold">
                  <td className="py-2.5 px-3 font-bold text-emerald-950 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
                    Voting Ensemble (Fused)
                  </td>
                  <td className="py-2.5 px-3 text-emerald-800">Heterogeneous Voting (Ridge + RF + XGB)</td>
                  <td className="py-2.5 px-3 text-right font-mono text-emerald-950 font-bold">{metricsData?.models_benchmarked?.Voting_Ensemble?.test_mae_log ?? "2.9961"}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-emerald-950 font-bold">{metricsData?.models_benchmarked?.Voting_Ensemble?.test_r2 ?? "0.2159"}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-emerald-950 font-bold">{metricsData?.models_benchmarked?.Voting_Ensemble?.test_spearman_rho ?? "0.5026"}</td>
                  <td className="py-2.5 px-3 text-center"><span className="px-2 py-0.5 bg-emerald-600 text-white font-bold rounded text-[10px]">ACTIVE PROD</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Honest Scientific Limitations List */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-amber-600" />
          <h2 className="text-lg font-bold text-slate-900">
            Documented Scientific Limitations
          </h2>
        </div>

        <ul className="space-y-3">
          {limitations.map((item, idx) => (
            <li key={idx} className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 text-xs text-slate-700 border border-slate-200">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
