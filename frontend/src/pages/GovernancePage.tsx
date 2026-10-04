import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import {
  ShieldCheck,
  ShieldAlert,
  CheckCircle,
  XCircle,
  RefreshCw,
  Lock,
} from "lucide-react";

export const GovernancePage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user, isCoordinatorOrAdmin } = useAuth();

  const [action, setAction] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [reasonCode, setReasonCode] = useState("OPERATIONAL_SURGE_MET");
  const [planHash, setPlanHash] = useState("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  const [confidence, setConfidence] = useState(0.85);
  const [formMsg, setFormMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // 1. Fetch Audit Log
  const {
    data: auditData,
    isLoading: isLoadingLog,
    error: errorLog,
  } = useQuery({
    queryKey: ["auditLog"],
    queryFn: () => api.getAuditLog(1, 50),
  });

  // 2. Verify Audit Chain
  const {
    data: verifyData,
    isLoading: isVerifying,
    refetch: triggerVerify,
  } = useQuery({
    queryKey: ["auditVerify"],
    queryFn: () => api.verifyAuditChain(),
    enabled: true,
  });

  // 3. Mutation to Record Decision
  const decisionMutation = useMutation({
    mutationFn: (payload: any) => api.recordAuditDecision(payload),
    onSuccess: (data) => {
      setFormMsg({
        type: "success",
        text: `Action '${data.action}' recorded! Block #${data.id} appended with hash ${data.current_hash.substring(0, 12)}...`,
      });
      queryClient.invalidateQueries({ queryKey: ["auditLog"] });
      queryClient.invalidateQueries({ queryKey: ["auditVerify"] });
    },
    onError: (err: any) => {
      setFormMsg({
        type: "error",
        text: err.message || "Failed to record decision.",
      });
    },
  });

  const handleDecisionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormMsg(null);
    decisionMutation.mutate({
      action,
      reason_code: reasonCode,
      plan_hash: planHash,
      confidence: Number(confidence),
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Governance & Cryptographic Audit Ledger
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          SHA-256 hash-chained tamper-evident decision ledger for human-in-the-loop allocation approvals.
        </p>
      </div>

      {/* Verification Banner */}
      <div
        className={`rounded-2xl border p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 ${
          verifyData?.is_valid
            ? "bg-emerald-50 border-emerald-200 text-emerald-950"
            : "bg-red-50 border-red-200 text-red-950"
        }`}
      >
        <div className="flex items-start gap-4">
          <div className="p-2.5 rounded-xl bg-white shadow-sm shrink-0">
            {verifyData?.is_valid ? (
              <ShieldCheck className="w-8 h-8 text-emerald-600" />
            ) : (
              <ShieldAlert className="w-8 h-8 text-red-600" />
            )}
          </div>
          <div>
            <h3 className="text-base font-bold">
              {verifyData?.is_valid
                ? "Cryptographic Audit Ledger: Intact & Verified"
                : "TAMPERING DETECTED in Audit Chain!"}
            </h3>
            <p className="text-xs text-slate-600 mt-1">
              {verifyData?.message || "Recomputing SHA-256 block hashes from Genesis Block..."}
            </p>
            {verifyData?.broken_block && (
              <p className="text-xs font-mono text-red-700 mt-1">
                Broken Block #{verifyData.broken_block.broken_row_id} (Reason: {verifyData.broken_block.error_type})
              </p>
            )}
          </div>
        </div>

        <button
          aria-label="Re-Verify Chain"
          onClick={() => triggerVerify()}
          disabled={isVerifying}
          className="inline-flex items-center px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 font-semibold rounded-lg text-xs shadow-sm transition-colors shrink-0 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isVerifying ? "animate-spin" : ""}`} />
          {isVerifying ? "Recomputing Hashes..." : "Re-Verify Chain"}
        </button>
      </div>

      {/* Human-in-the-Loop Review Form (Coordinators & Admins) */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Human-in-the-Loop Officer Review
            </h2>
            <p className="text-xs text-slate-500">
              Only State Coordinators and Administrators are authorized to formalize allocation plans.
            </p>
          </div>
          {!isCoordinatorOrAdmin && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
              <Lock className="w-3.5 h-3.5 mr-1" /> Requires Coordinator Role
            </span>
          )}
        </div>

        {formMsg && (
          <div
            className={`p-4 rounded-xl text-xs font-medium border ${
              formMsg.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-red-50 text-red-800 border-red-200"
            }`}
          >
            {formMsg.text}
          </div>
        )}

        <form onSubmit={handleDecisionSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Action Decision
              </label>
              <select
                disabled={!isCoordinatorOrAdmin}
                value={action}
                onChange={(e) => setAction(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="APPROVE">APPROVE Plan</option>
                <option value="REJECT">REJECT Plan</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason Code
              </label>
              <select
                disabled={!isCoordinatorOrAdmin}
                value={reasonCode}
                onChange={(e) => setReasonCode(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="OPERATIONAL_SURGE_MET">OPERATIONAL_SURGE_MET</option>
                <option value="SAFETY_RESERVES_ADEQUATE">SAFETY_RESERVES_ADEQUATE</option>
                <option value="PERISHABLES_COMPLIANT">PERISHABLES_COMPLIANT</option>
                <option value="CONFIDENCE_BELOW_THRESHOLD">CONFIDENCE_BELOW_THRESHOLD</option>
                <option value="MANUAL_REVIEW_REQUIRED">MANUAL_REVIEW_REQUIRED</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Evaluated Plan Confidence:{" "}
                <span className={`font-bold ${confidence < 0.6 ? "text-red-600" : "text-emerald-600"}`}>
                  {(confidence * 100).toFixed(0)}%
                </span>
              </label>
              <input
                type="range"
                min="0.30"
                max="0.95"
                step="0.05"
                disabled={!isCoordinatorOrAdmin}
                value={confidence}
                onChange={(e) => setConfidence(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer disabled:opacity-50 mt-2"
              />
              {confidence < 0.6 && action === "APPROVE" && (
                <p className="text-[10px] text-red-600 mt-1 font-semibold">
                  ⚠️ Confidence below 60% threshold in config.yaml; APPROVE will be blocked with HTTP 409.
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Plan SHA-256 Hash
              </label>
              <input
                type="text"
                disabled={!isCoordinatorOrAdmin}
                value={planHash}
                onChange={(e) => setPlanHash(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs font-mono focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={!isCoordinatorOrAdmin || decisionMutation.isPending}
              className={`inline-flex items-center px-5 py-2.5 rounded-lg text-xs font-semibold shadow-sm transition-colors text-white ${
                action === "APPROVE"
                  ? "bg-emerald-600 hover:bg-emerald-700"
                  : "bg-red-600 hover:bg-red-700"
              } disabled:opacity-40`}
            >
              {action === "APPROVE" ? (
                <CheckCircle className="w-4 h-4 mr-1.5" />
              ) : (
                <XCircle className="w-4 h-4 mr-1.5" />
              )}
              {decisionMutation.isPending ? "Recording to Ledger..." : `Submit ${action} Decision`}
            </button>
          </div>
        </form>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">
            Immutable Audit Ledger ({auditData?.total_count || 0} Blocks)
          </h2>
          <span className="text-xs text-slate-500 font-mono">
            Genesis Hash: 000000000000...
          </span>
        </div>

        {isLoadingLog && <LoadingSpinner message="Fetching audit events..." />}
        {errorLog && <ErrorAlert message={(errorLog as any).message || "Failed to load audit ledger."} />}

        {auditData && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-3">Block #</th>
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Action</th>
                  <th className="py-3 px-3">Reason Code</th>
                  <th className="py-3 px-3">Confidence</th>
                  <th className="py-3 px-3">Previous Block Hash</th>
                  <th className="py-3 px-3">Current Block Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {auditData.items.map((event) => {
                  const isApprove = event.action === "APPROVE";
                  return (
                    <tr key={event.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2.5 px-3 font-bold text-slate-900 font-sans">#{event.id}</td>
                      <td className="py-2.5 px-3 text-slate-600 font-sans">{event.created_at.substring(0, 19).replace("T", " ")}</td>
                      <td className="py-2.5 px-3 font-sans">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold ${
                            isApprove
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : "bg-red-100 text-red-800 border border-red-300"
                          }`}
                        >
                          {event.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-700 font-sans">{event.reason_code}</td>
                      <td className="py-2.5 px-3 text-slate-800 font-sans font-semibold">
                        {(event.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 truncate max-w-[130px]" title={event.prev_hash}>
                        {event.prev_hash.substring(0, 16)}...
                      </td>
                      <td className="py-2.5 px-3 text-blue-700 font-semibold truncate max-w-[130px]" title={event.current_hash}>
                        {event.current_hash.substring(0, 16)}...
                      </td>
                    </tr>
                  );
                })}
                {auditData.items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400 font-sans">
                      No decisions recorded yet. The genesis block is ready.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
