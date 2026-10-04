import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./context/AuthContext";
import { Navbar } from "./components/Navbar";
import { OverviewPage } from "./pages/OverviewPage";
import { SimulatorPage } from "./pages/SimulatorPage";
import { AllocationPage } from "./pages/AllocationPage";
import { BacktestPage } from "./pages/BacktestPage";
import { GovernancePage } from "./pages/GovernancePage";
import { LimitationsPage } from "./pages/LimitationsPage";
import { LoginPage } from "./pages/LoginPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
            <Navbar />
            <main className="flex-1">
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/simulator" element={<SimulatorPage />} />
                <Route path="/allocation" element={<AllocationPage />} />
                <Route path="/backtest" element={<BacktestPage />} />
                <Route path="/governance" element={<GovernancePage />} />
                <Route path="/limitations" element={<LimitationsPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
              <div className="max-w-7xl mx-auto px-4 space-y-1">
                <p>Disaster Healthcare AI Decision-Support Framework &bull; Maharashtra (35 Districts)</p>
                <p className="text-[11px] text-slate-400">
                  CRED EM-DAT &bull; WorldPop 2020 &bull; National Health Portal &bull; Kapoor et al. (2020) &bull; Google OR-Tools SCIP
                </p>
              </div>
            </footer>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
