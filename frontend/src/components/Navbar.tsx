import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Map,
  Activity,
  GitBranch,
  History,
  ShieldCheck,
  FileText,
  LogIn,
  LogOut,
  User as UserIcon,
} from "lucide-react";

export const Navbar: React.FC = () => {
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuth();

  const navItems = [
    { name: "Overview", path: "/", icon: <Map className="w-4 h-4 mr-1.5" /> },
    { name: "Simulator", path: "/simulator", icon: <Activity className="w-4 h-4 mr-1.5" /> },
    { name: "Allocation Plan", path: "/allocation", icon: <GitBranch className="w-4 h-4 mr-1.5" /> },
    { name: "Backtest", path: "/backtest", icon: <History className="w-4 h-4 mr-1.5" /> },
    { name: "Governance", path: "/governance", icon: <ShieldCheck className="w-4 h-4 mr-1.5" /> },
    { name: "Limitations", path: "/limitations", icon: <FileText className="w-4 h-4 mr-1.5" /> },
  ];

  return (
    <header className="bg-slate-900 text-white sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 font-bold text-lg text-white hover:text-blue-300 transition-colors">
              <span className="p-1.5 bg-blue-600 rounded-lg text-white">
                <ShieldCheck className="w-5 h-5" />
              </span>
              <span>Disaster Healthcare AI</span>
            </Link>
            <span className="hidden md:inline-block px-2 py-0.5 text-xs font-medium bg-slate-800 text-slate-300 rounded border border-slate-700">
              Maharashtra (35 Districts)
            </span>
          </div>

          <nav className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const active = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`inline-flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    active
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  {item.icon}
                  {item.name}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <div className="flex items-center gap-3">
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-semibold text-slate-200">{user?.email}</span>
                  <span className="text-[10px] text-blue-400 capitalize font-medium">{user?.role}</span>
                </div>
                <button
                  onClick={logout}
                  className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 text-slate-300 hover:bg-red-600 hover:text-white transition-colors border border-slate-700"
                >
                  <LogOut className="w-3.5 h-3.5 mr-1" />
                  Logout
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center px-3.5 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-500 transition-colors"
              >
                <LogIn className="w-3.5 h-3.5 mr-1.5" />
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
