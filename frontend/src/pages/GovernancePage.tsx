import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import {
  ShieldCheck,
  ShieldAlert,
  CheckCircle,
  XCircle,
  RefreshCw,
  Lock,
  Eye,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  X,
  AlertTriangle,
  Info,
} from "lucide-react";

export const GovernancePage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user, isCoordinatorOrAdmin } = useAuth();

  // Pending Queue Pagination
  const [page, setPage] = useState(0);
  const pageSize = 10;

  // Selected Allocation for Detailed Review Modal
  const [selectedAllocationId, setSelectedAllocationId] = useState<string | null>(null);

  // Decision Form State
  const [action, setAction] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [reasonCode, setReasonCode] = useState("OPERATIONAL_SURGE_MET");
  const [confidence, setConfidence] = useState(0.85);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [formMsg, setFormMsg] = useState<{ type: "success" | "error" | "warning"; text: string } | null>(null);

  // 1. Fetch Pending Allocations Queue
  const {
    data: pendingAllocations,
    isLoading: isLoadingPending,
    error: errorPending,
    refetch: refetchPending,
  } = useQuery({
    queryKey: ["pendingAllocations", page, pageSize],
    queryFn: () => api.getPendingAllocations(pageSize, page * pageSize),
  });

  // 2. Fetch Selected Allocation Detail
  const {
    data: allocationDetail,
    isLoading: isLoadingDetail,
    error: errorDetail,
  } = useQuery({
    queryKey: ["allocationDetail", selectedAllocationId],
    queryFn: () => (selectedAllocationId ? api.getAllocationById(selectedAllocationId) : null),
    enabled: !!selectedAllocationId,
  });

  // 3. Fetch Audit Log
  const {
    data: auditData,
    isLoading: isLoadingLog,
    error: errorLog,
  } = useQuery({
    queryKey: ["auditLog"],
    queryFn: () => api.getAuditLog(1, 50),
  });

  // 4. Verify Audit Chain
  const {
    data: verifyData,
    isLoading: isVerifying,
    refetch: triggerVerify,
  } = useQuery({
    queryKey: ["auditVerify"],
    queryFn: () => api.verifyAuditChain(),
    enabled: true,
  });

  // 5. Decision Mutation
  const decisionMutation = useMutation({
    mutationFn: (payload: {
      allocation_id: string;
      simulation_id?: string | null;
      plan_hash: string;
      action: "APPROVE" | "REJECT";
      reason_code: string;
      confidence: number;
    }) => api.recordAuditDecision(payload),
    onSuccess: (data) => {
      setFormMsg({
        type: "success",
        text: `Action '${data.action}' recorded! Block #${data.id} appended to audit ledger. Allocation finalized.`,
      });
      setIsConfirmOpen(false);
      setSelectedAllocationId(null);
      queryClient.invalidateQueries({ queryKey: ["pendingAllocations"] });
      queryClient.invalidateQueries({ queryKey: ["auditLog"] });
      queryClient.invalidateQueries({ queryKey: ["auditVerify"] });
    },
    onError: (err: any) => {
      setIsConfirmOpen(false);
      const msg = err.message || "Failed to record decision.";
      if (msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("finalized") || msg.toLowerCase().includes("threshold")) {
        setFormMsg({
          type: "warning",
          text: `Decision Conflict (HTTP 409): ${msg}`,
        });
        queryClient.invalidateQueries({ queryKey: ["pendingAllocations"] });
      } else if (msg.includes("400") || msg.toLowerCase().includes("unlinked")) {
        setFormMsg({
          type: "error",
          text: `Validation Error (HTTP 400): ${msg}`,
        });
      } else {
        setFormMsg({
          type: "error",
          text: msg,
        });
      }
    },
  });

  const handleOpenReview = (allocationId: string) => {
    setFormMsg(null);
    setSelectedAllocationId(allocationId);
    setAction("APPROVE");
    setReasonCode("OPERATIONAL_SURGE_MET");
    setConfidence(0.85);
  };

  const handleConfirmDecision = () => {
    if (!allocationDetail) return;
    decisionMutation.mutate({
      allocation_id: allocationDetail.allocation_id,
      simulation_id: allocationDetail.simulation_id,
      plan_hash: allocationDetail.plan_hash,
      action,
      reason_code: reasonCode,
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

      {/* Feedback Alert */}
      {formMsg && (
        <div
          className={`p-4 rounded-xl text-xs font-medium border flex items-start gap-2.5 ${
            formMsg.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : formMsg.type === "warning"
              ? "bg-amber-50 text-amber-800 border-amber-200"
              : "bg-red-50 text-red-800 border-red-200"
          }`}
        >
          {formMsg.type === "success" ? (
            <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          )}
          <span>{formMsg.text}</span>
        </div>
      )}

      {/* Human-in-the-Loop Pending Allocations Governance Queue */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Human-in-the-Loop Officer Review
            </h2>
            <p className="text-xs text-slate-500">
              Pending allocation plans awaiting formal state coordinator or administrator determination.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!isCoordinatorOrAdmin && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
                <Lock className="w-3.5 h-3.5 mr-1" /> Read-Only Mode (Coordinator Required)
              </span>
            )}
            <button
              onClick={() => refetchPending()}
              disabled={isLoadingPending}
              className="inline-flex items-center px-3 py-1.5 bg-slate-50 border border-slate-200 hover:bg-slate-100 text-slate-700 font-semibold rounded-lg text-xs transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1 ${isLoadingPending ? "animate-spin" : ""}`} />
              Refresh Queue
            </button>
          </div>
        </div>

        {/* Loading / Error States for Pending Queue */}
        {isLoadingPending && <LoadingSpinner message="Fetching pending allocation queue..." />}
        {errorPending && (
          <div className="space-y-2">
            <ErrorAlert message={(errorPending as any).message || "Failed to load pending allocations."} />
            <button
              onClick={() => refetchPending()}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline"
            >
              Retry fetching queue
            </button>
          </div>
        )}

        {/* Pending Queue Table */}
        {!isLoadingPending && !errorPending && pendingAllocations && (
          <>
            {pendingAllocations.length === 0 ? (
              <div className="text-center py-10 px-4 bg-slate-50 rounded-xl border border-slate-100 space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-700">Governance Queue Cleared</h4>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  No allocation plans are currently in PENDING_REVIEW status. New plans generated from the Simulator will appear here for officer formalization.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-3">Allocation ID</th>
                      <th className="py-3 px-3">Simulation ID</th>
                      <th className="py-3 px-3">Creator</th>
                      <th className="py-3 px-3">Submitted (UTC)</th>
                      <th className="py-3 px-3">Cost Index</th>
                      <th className="py-3 px-3">Unmet Demand</th>
                      <th className="py-3 px-3">Routes / Units</th>
                      <th className="py-3 px-3">Status</th>
                      <th className="py-3 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {pendingAllocations.map((item) => (
                      <tr key={item.allocation_id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-3 font-mono text-[11px] font-semibold text-slate-800" title={item.allocation_id}>
                          {item.allocation_id.substring(0, 8)}...
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-600" title={item.simulation_id || "Unlinked"}>
                          {item.simulation_id ? `${item.simulation_id.substring(0, 8)}...` : "None"}
                        </td>
                        <td className="py-3 px-3 text-slate-700">
                          {item.creator ? (
                            <div>
                              <span className="font-medium text-slate-900">{item.creator.email}</span>
                              <span className="block text-[10px] text-slate-400 capitalize">({item.creator.role})</span>
                            </div>
                          ) : (
                            <span className="text-slate-400">Anonymous</span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-slate-600">
                          {item.created_at.substring(0, 19).replace("T", " ")}
                        </td>
                        <td className="py-3 px-3 font-mono font-medium text-slate-800">
                          {item.cost_index !== null && item.cost_index !== undefined ? item.cost_index.toLocaleString() : "N/A"}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-800">
                          {item.unmet_demand_after !== null && item.unmet_demand_after !== undefined ? item.unmet_demand_after.toLocaleString() : "N/A"}
                        </td>
                        <td className="py-3 px-3 text-slate-600">
                          {item.transfers_count ?? 0} routes ({(item.total_transferred_units ?? 0).toLocaleString()} units)
                        </td>
                        <td className="py-3 px-3">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                            {item.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => handleOpenReview(item.allocation_id)}
                            className="inline-flex items-center px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors"
                          >
                            <Eye className="w-3.5 h-3.5 mr-1" />
                            Review Plan
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Controls */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs text-slate-500">
              <span>
                Page {page + 1} &bull; Showing {pendingAllocations.length} records
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="inline-flex items-center px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 disabled:opacity-40"
                >
                  <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={pendingAllocations.length < pageSize}
                  className="inline-flex items-center px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 disabled:opacity-40"
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Allocation Review & Decision Modal */}
      {selectedAllocationId && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Allocation Plan Review & Determination
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  ID: {selectedAllocationId}
                </p>
              </div>
              <button
                onClick={() => {
                  setSelectedAllocationId(null);
                  setIsConfirmOpen(false);
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
              {isLoadingDetail && <LoadingSpinner message="Retrieving persisted allocation record and shipments..." />}
              {errorDetail && (
                <ErrorAlert message={(errorDetail as any).message || "Failed to load allocation details."} />
              )}

              {allocationDetail && (
                <>
                  {/* Plan Identification Metadata */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <div>
                      <span className="text-[11px] text-slate-500 block">Status</span>
                      <span className="font-bold text-amber-800 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded text-[11px]">
                        {allocationDetail.status}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-slate-500 block">Linked Simulation</span>
                      <span className="font-mono text-slate-800 font-medium truncate block" title={allocationDetail.simulation_id || "Unlinked"}>
                        {allocationDetail.simulation_id || "Unlinked"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-slate-500 block">Cost Index</span>
                      <span className="font-mono font-bold text-slate-900">
                        {allocationDetail.cost_index?.toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-slate-500 block">Remaining Unmet</span>
                      <span className="font-mono font-bold text-blue-600">
                        {allocationDetail.unmet_demand_after?.toLocaleString()} units
                      </span>
                    </div>
                  </div>

                  {/* Cryptographic Plan Hash */}
                  <div className="p-3 bg-slate-900 text-slate-200 rounded-xl space-y-1">
                    <span className="text-[10px] uppercase font-bold text-slate-400">
                      Persisted SHA-256 Plan Hash (Canonical Transfer Representation)
                    </span>
                    <p className="font-mono text-[11px] text-emerald-400 break-all select-all">
                      {allocationDetail.plan_hash}
                    </p>
                  </div>

                  {/* Constituent Shipments Table */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-slate-900 text-sm">
                        Constituent Inter-District Shipments ({allocationDetail.shipments.length})
                      </h4>
                      <span className="text-slate-500 font-medium">
                        Total {allocationDetail.total_transferred_units.toLocaleString()} units
                      </span>
                    </div>
                    <div className="overflow-x-auto border border-slate-200 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-2.5 px-3">Source Region</th>
                            <th className="py-2.5 px-3">Destination Region</th>
                            <th className="py-2.5 px-3">Medicine</th>
                            <th className="py-2.5 px-3">Quantity</th>
                            <th className="py-2.5 px-3">Distance (km)</th>
                            <th className="py-2.5 px-3">Priority</th>
                            <th className="py-2.5 px-3">Confidence</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {allocationDetail.shipments.map((s, idx) => (
                            <tr key={idx} className="hover:bg-slate-50">
                              <td className="py-2 px-3 font-semibold text-slate-800">{s.source_region}</td>
                              <td className="py-2 px-3 font-semibold text-blue-700">{s.dest_region}</td>
                              <td className="py-2 px-3 capitalize text-slate-700">{s.medicine}</td>
                              <td className="py-2 px-3 font-bold font-mono text-slate-900">{s.quantity.toLocaleString()}</td>
                              <td className="py-2 px-3 text-slate-600 font-mono">{s.distance_km}</td>
                              <td className="py-2 px-3">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  s.priority === "CRITICAL" ? "bg-red-100 text-red-800" : s.priority === "HIGH" ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700"
                                }`}>
                                  {s.priority}
                                </span>
                              </td>
                              <td className="py-2 px-3 font-mono font-medium text-slate-700">
                                {(s.confidence * 100).toFixed(0)}%
                              </td>
                            </tr>
                          ))}
                          {allocationDetail.shipments.length === 0 && (
                            <tr>
                              <td colSpan={7} className="py-4 text-center text-slate-400">
                                No transfers required; existing stocks meet demand.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Decision Controls Box */}
                  <div className="pt-4 border-t border-slate-200 space-y-4">
                    <h4 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-blue-600" />
                      Officer Decision Authority
                    </h4>

                    {!isCoordinatorOrAdmin ? (
                      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-1">
                        <p className="font-bold">Read-Only Observer Access</p>
                        <p className="text-xs">
                          You are currently signed in as <span className="font-semibold">{user?.role}</span>. Only State Coordinators and Administrators are authorized to formalize allocation plans and append cryptographically signed blocks to the ledger.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label htmlFor="action-decision" className="block text-xs font-semibold text-slate-700 mb-1">
                              Action Decision
                            </label>
                            <select
                              id="action-decision"
                              value={action}
                              onChange={(e) => setAction(e.target.value as "APPROVE" | "REJECT")}
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500"
                            >
                              <option value="APPROVE">APPROVE Allocation Plan</option>
                              <option value="REJECT">REJECT Allocation Plan</option>
                            </select>
                          </div>

                          <div>
                            <label htmlFor="reason-code" className="block text-xs font-semibold text-slate-700 mb-1">
                              Reason Code
                            </label>
                            <select
                              id="reason-code"
                              value={reasonCode}
                              onChange={(e) => setReasonCode(e.target.value)}
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-blue-500"
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
                              Evaluated Confidence:{" "}
                              <span className={`font-bold ${confidence < 0.6 ? "text-red-600" : "text-emerald-600"}`}>
                                {(confidence * 100).toFixed(0)}%
                              </span>
                            </label>
                            <input
                              type="range"
                              min="0.30"
                              max="0.95"
                              step="0.05"
                              value={confidence}
                              onChange={(e) => setConfidence(Number(e.target.value))}
                              className="w-full accent-blue-600 cursor-pointer mt-2"
                            />
                            {confidence < 0.6 && action === "APPROVE" && (
                              <p className="text-[10px] text-red-600 mt-1 font-semibold">
                                ⚠️ Confidence below 60% threshold; APPROVE will be blocked with HTTP 409.
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Confirmation Dialog / Action Button */}
                        {isConfirmOpen ? (
                          <div className="p-4 bg-amber-50 border border-amber-300 rounded-xl space-y-3">
                            <div className="flex items-start gap-2">
                              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                              <div className="text-xs text-amber-900 space-y-1">
                                <p className="font-bold">
                                  Confirm {action} Decision on Allocation {allocationDetail.allocation_id.substring(0, 8)}...
                                </p>
                                <p>
                                  This action will transition the allocation to <strong>{action}D</strong> and append an immutable block to the SHA-256 audit ledger. Terminal decisions cannot be undone.
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center justify-end gap-3 pt-1">
                              <button
                                type="button"
                                onClick={() => setIsConfirmOpen(false)}
                                disabled={decisionMutation.isPending}
                                className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold rounded-lg text-xs"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={handleConfirmDecision}
                                disabled={decisionMutation.isPending}
                                className={`inline-flex items-center px-4 py-2 text-white font-semibold rounded-lg text-xs shadow-sm transition-colors ${
                                  action === "APPROVE" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-red-600 hover:bg-red-700"
                                } disabled:opacity-50`}
                              >
                                {decisionMutation.isPending ? "Recording to Ledger..." : `Confirm ${action}`}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex justify-end pt-2">
                            <button
                              type="button"
                              onClick={() => setIsConfirmOpen(true)}
                              disabled={decisionMutation.isPending}
                              className={`inline-flex items-center px-5 py-2.5 rounded-lg text-xs font-semibold shadow-sm transition-colors text-white ${
                                action === "APPROVE" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-red-600 hover:bg-red-700"
                              } disabled:opacity-50`}
                            >
                              {action === "APPROVE" ? (
                                <CheckCircle className="w-4 h-4 mr-1.5" />
                              ) : (
                                <XCircle className="w-4 h-4 mr-1.5" />
                              )}
                              Submit {action} Decision
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setSelectedAllocationId(null);
                  setIsConfirmOpen(false);
                }}
                className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold rounded-lg text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Immutable Audit Ledger Table */}
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
