import React, { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { LoadingSpinner } from "./LoadingSpinner";
import { ErrorAlert } from "./ErrorAlert";
import {
  Package,
  Save,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Filter,
  Search,
  Upload,
} from "lucide-react";

const MEDICINES = [
  { id: "antibiotics", label: "Antibiotics (courses)" },
  { id: "ors", label: "ORS (sachets)" },
  { id: "iv_fluids", label: "IV Fluids (L)" },
  { id: "analgesics", label: "Analgesics (doses)" },
  { id: "blood_units", label: "Blood Units (units)" },
];

const DEFAULT_DISTRICTS = [
  "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
  "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
  "Kolhapur", "Latur", "Mumbai", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar",
  "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri",
  "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"
];

// Baseline proxy values if unedited
const getEstimatedBaselineStock = (district: string, medicine: string): number => {
  const seed = (district.charCodeAt(0) * 1000 + district.charCodeAt(district.length - 1) * 50) % 25000;
  switch (medicine) {
    case "antibiotics": return 25000 + seed * 2;
    case "ors": return 60000 + seed * 4;
    case "iv_fluids": return 12000 + seed;
    case "analgesics": return 30000 + seed * 2;
    case "blood_units": return 2500 + Math.floor(seed / 10);
    default: return 10000;
  }
};

interface StockEditingTableProps {
  onStockSaved?: () => void;
}

export const StockEditingTable: React.FC<StockEditingTableProps> = ({ onStockSaved }) => {
  let isOfficerOrAbove = false;
  try {
    const auth = useAuth();
    isOfficerOrAbove = auth.isOfficerOrAbove;
  } catch {
    isOfficerOrAbove = false;
  }
  const [districtFilter, setDistrictFilter] = useState<string>("All");
  const [medicineFilter, setMedicineFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [editedStocks, setEditedStocks] = useState<Record<string, Record<string, number>>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch existing user custom stock from backend
  const { data: stockData, isLoading, refetch } = useQuery({
    queryKey: ["userCustomStock"],
    queryFn: () => api.getStock(),
    retry: false,
  });

  // Sync loaded custom stocks into local editing state
  useEffect(() => {
    if (stockData?.stocks) {
      setEditedStocks(stockData.stocks);
    }
  }, [stockData]);

  // Save stock mutation
  const saveMutation = useMutation({
    mutationFn: (stocksToSave: Record<string, Record<string, number>>) =>
      api.updateStock({ stocks: stocksToSave }),
    onSuccess: (res) => {
      setSuccessMessage(res.message || "Custom stock saved successfully with USER-PROVIDED provenance tag.");
      setErrorMessage(null);
      refetch();
      if (onStockSaved) onStockSaved();
      setTimeout(() => setSuccessMessage(null), 6000);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to save custom stock.");
      setSuccessMessage(null);
    },
  });

  // Reset stock mutation
  const resetMutation = useMutation({
    mutationFn: () => api.resetStock(),
    onSuccess: (res) => {
      setEditedStocks({});
      setSuccessMessage("Stock records cleared. Reverted to estimated baseline stock.");
      setErrorMessage(null);
      refetch();
      if (onStockSaved) onStockSaved();
      setTimeout(() => setSuccessMessage(null), 6000);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to reset stock.");
      setSuccessMessage(null);
    },
  });

  const handleStockChange = (district: string, medicine: string, value: string) => {
    const num = Math.max(0, parseFloat(value) || 0);
    setEditedStocks((prev) => ({
      ...prev,
      [district]: {
        ...(prev[district] || {}),
        [medicine]: num,
      },
    }));
  };

  const handleSaveAll = () => {
    if (!isOfficerOrAbove) {
      setErrorMessage("Officer, Coordinator, or Admin role required to update stock.");
      return;
    }
    saveMutation.mutate(editedStocks);
  };

  const handleReset = () => {
    if (!isOfficerOrAbove) {
      setErrorMessage("Officer, Coordinator, or Admin role required to reset stock.");
      return;
    }
    if (window.confirm("Are you sure you want to reset all custom stocks and revert to estimated baseline?")) {
      resetMutation.mutate();
    }
  };

  const hasCustomEntries = Object.keys(editedStocks).length > 0;
  const filteredDistricts = DEFAULT_DISTRICTS.filter((d) => {
    if (districtFilter !== "All" && d !== districtFilter) return false;
    if (searchQuery && !d.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const displayedMedicines = medicineFilter === "All"
    ? MEDICINES
    : MEDICINES.filter((m) => m.id === medicineFilter);

  return (
    <div
      className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6 shadow-sm"
      data-testid="stock-editing-table"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Package className="w-5 h-5 text-emerald-600" />
            <h3 className="text-lg font-bold text-slate-900">
              District Inventory & Custom Stock Override
            </h3>
            <ProvenanceBadge tag="USER-PROVIDED" />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Authorised officers may adjust or upload district-by-medicine physical inventory.
            Simulations and optimizations automatically prioritize user-provided stocks over estimated anchors.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={resetMutation.isPending || (!hasCustomEntries && !stockData?.total_records)}
            data-testid="reset-stock-button"
            className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition-colors shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
            {resetMutation.isPending ? "Resetting..." : "Reset to Estimated Baseline"}
          </button>

          <button
            type="button"
            onClick={handleSaveAll}
            disabled={saveMutation.isPending || !hasCustomEntries}
            data-testid="save-stock-button"
            className="inline-flex items-center px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 transition-colors shadow-sm"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            {saveMutation.isPending ? "Saving..." : "Save Custom Stock"}
          </button>
        </div>
      </div>

      {/* Role Notice */}
      {!isOfficerOrAbove && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            You are currently signed in with viewer permissions. An <strong>Officer</strong> or <strong>Admin</strong> account is required to persist custom stock records.
          </span>
        </div>
      )}

      {/* Alerts */}
      {successMessage && (
        <div
          className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2"
          data-testid="stock-success-alert"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div
          className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center gap-2"
          data-testid="stock-error-alert"
        >
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-60">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search district..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <select
            value={medicineFilter}
            onChange={(e) => setMedicineFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-medium"
          >
            <option value="All">All Medicines</option>
            {MEDICINES.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div className="text-[11px] text-slate-500 flex items-center gap-3">
          <span>Showing {filteredDistricts.length} districts</span>
          {stockData?.total_records ? (
            <span className="font-semibold text-emerald-600">
              &bull; {stockData.total_records} Active Overrides (USER-PROVIDED)
            </span>
          ) : (
            <span className="text-slate-400">&bull; Baseline Estimated Inventory</span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-slate-200 rounded-xl max-h-96 overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100 text-slate-700 font-semibold sticky top-0 z-10 border-b border-slate-200">
            <tr>
              <th className="py-2.5 px-3">District</th>
              {displayedMedicines.map((m) => (
                <th key={m.id} className="py-2.5 px-3">
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {filteredDistricts.map((district) => (
              <tr key={district} className="hover:bg-slate-50/80 transition-colors">
                <td className="py-2 px-3 font-semibold text-slate-900 whitespace-nowrap">
                  {district}
                </td>
                {displayedMedicines.map((m) => {
                  const customVal = editedStocks[district]?.[m.id];
                  const isCustom = customVal !== undefined;
                  const displayVal = isCustom
                    ? customVal
                    : getEstimatedBaselineStock(district, m.id);

                  return (
                    <td key={m.id} className="py-1.5 px-3">
                      <div className="relative flex items-center">
                        <input
                          type="number"
                          min="0"
                          step="100"
                          value={displayVal}
                          onChange={(e) => handleStockChange(district, m.id, e.target.value)}
                          className={`w-28 px-2 py-1 text-xs rounded border transition-colors ${
                            isCustom
                              ? "bg-emerald-50 border-emerald-400 text-emerald-900 font-semibold"
                              : "bg-slate-50 border-slate-200 text-slate-700"
                          } focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none`}
                        />
                        {isCustom && (
                          <span
                            title="USER-PROVIDED custom stock"
                            className="ml-1.5 inline-block w-2 h-2 rounded-full bg-emerald-500"
                          />
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
