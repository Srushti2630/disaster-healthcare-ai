import React from "react";
import { AlertCircle } from "lucide-react";

export const ErrorAlert: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => {
  return (
    <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl p-4 flex items-start gap-3 my-4">
      <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
      <div className="flex-1">
        <h4 className="font-semibold text-sm">Error Loading Information</h4>
        <p className="text-xs mt-1 text-red-700">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 text-xs font-semibold text-red-700 underline hover:text-red-900"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};
