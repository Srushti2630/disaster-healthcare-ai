import React from "react";
import { Loader2 } from "lucide-react";

export const LoadingSpinner: React.FC<{ message?: string }> = ({
  message = "Loading data from backend...",
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 space-y-3">
      <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      <span className="text-sm font-medium text-slate-600">{message}</span>
    </div>
  );
};
