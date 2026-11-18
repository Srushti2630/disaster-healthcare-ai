import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { KPICard } from "../components/KPICard";
import { DistrictMap } from "../components/DistrictMap";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorAlert } from "../components/ErrorAlert";
import { Users, Building2, Bed, HeartPulse, Search } from "lucide-react";

export const OverviewPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");

  const {
    data: districtsData,
    isLoading: isLoadingDistricts,
    error: errorDistricts,
    refetch: refetchDistricts,
  } = useQuery({
    queryKey: ["districts"],
    queryFn: () => api.getDistricts(),
  });

  const {
    data: geoJsonData,
    isLoading: isLoadingGeo,
    error: errorGeo,
  } = useQuery({
    queryKey: ["geoDistricts"],
    queryFn: () => api.getGeoDistricts(),
  });

  if (isLoadingDistricts || isLoadingGeo) {
    return <LoadingSpinner message="Loading Maharashtra district registry and real spatial geometries..." />;
  }

  if (errorDistricts || errorGeo) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <ErrorAlert
          message={errorDistricts?.message || errorGeo?.message || "Failed to load district data."}
          onRetry={refetchDistricts}
        />
      </div>
    );
  }

  const districts = districtsData?.districts || [];
  const filteredDistricts = districts.filter((d) =>
    d.district.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Regional Healthcare Overview & Spatial Geometry
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Statewide administrative infrastructure across Maharashtra's 35 district nodes.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="State Population"
          value={districtsData?.total_state_population || 131936179}
          subtitle="WorldPop 2020, about 100 m (3 arc-second)"
          tag="REAL"
          icon={<Users className="w-5 h-5" />}
        />
        <KPICard
          title="Cleaned Facilities"
          value={districtsData?.total_cleaned_facilities ?? districtsData?.total_facilities ?? (districts.length > 0 ? districts.reduce((acc, d) => acc + (d.facilities?.total_facilities ?? d.total_facilities ?? 0), 0) : 4767)}
          subtitle="National Health Portal Directory"
          tag="REAL"
          icon={<Building2 className="w-5 h-5" />}
        />
        <KPICard
          title="Hospital Beds Anchor"
          value={districtsData?.state_hospital_beds_anchor || 144983}
          subtitle="Statewide Bed Allocation Baseline"
          tag="ESTIMATED"
          icon={<Bed className="w-5 h-5" />}
        />
        <KPICard
          title="State ICU Beds Anchor"
          value={districtsData?.state_icu_beds_anchor || 11587}
          subtitle="State ICU audit (provided dataset; original publisher not stated)"
          tag="REAL"
          icon={<HeartPulse className="w-5 h-5" />}
        />
      </div>

      {/* Real Boundary Leaflet Map */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Maharashtra 35-District Polygon Map
            </h2>
            <p className="text-xs text-slate-500">
              Real high-resolution administrative boundaries from official GIS shapefiles.
            </p>
          </div>
          <ProvenanceBadge tag="REAL" />
        </div>

        {geoJsonData && <DistrictMap geoJsonData={geoJsonData} />}
      </div>

      {/* District Data Registry Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              District Healthcare & Capacity Registry
            </h2>
            <p className="text-xs text-slate-500">
              Verified population, facility counts, and bed capacity ranges per district.
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search district..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">District</th>
                <th className="py-3 px-3">
                  Population <ProvenanceBadge tag="REAL" className="ml-1" />
                </th>
                <th className="py-3 px-3">
                  Facilities <ProvenanceBadge tag="REAL" className="ml-1" />
                </th>
                <th className="py-3 px-3">
                  Beds (Mid) <ProvenanceBadge tag="ESTIMATED" className="ml-1" />
                </th>
                <th className="py-3 px-3">
                  ICU Beds <ProvenanceBadge tag="ESTIMATED" className="ml-1" />
                </th>
                <th className="py-3 px-3">Density (pop/km²)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredDistricts.map((d) => (
                <tr key={d.district} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-3 font-semibold text-slate-900">{d.district}</td>
                  <td className="py-3 px-3 text-slate-700">{d.population.toLocaleString()}</td>
                  <td className="py-3 px-3 text-slate-700">{d.facilities.total_facilities}</td>
                  <td className="py-3 px-3 text-slate-700">{d.capacity.beds_mid.toLocaleString()}</td>
                  <td className="py-3 px-3 text-slate-700">{d.capacity.icu_beds_mid.toLocaleString()}</td>
                  <td className="py-3 px-3 text-slate-500">{d.pop_density_sqkm.toFixed(1)}</td>
                </tr>
              ))}
              {filteredDistricts.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-6 text-slate-400">
                    No districts found matching "{searchTerm}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
