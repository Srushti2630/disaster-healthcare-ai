import React, { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import type { Layer } from "leaflet";
import { DistrictMedicineDemand } from "../types";

interface DistrictMapProps {
  geoJsonData: any;
  simulationResults?: DistrictMedicineDemand[];
  selectedMedicine?: string;
  onDistrictSelect?: (districtName: string) => void;
}

export const DistrictMap: React.FC<DistrictMapProps> = ({
  geoJsonData,
  simulationResults,
  selectedMedicine = "antibiotics",
  onDistrictSelect,
}) => {
  // Map of district name to risk probability
  const riskMap = useMemo(() => {
    const map = new Map<string, { prob: number; risk: string }>();
    if (simulationResults) {
      for (const item of simulationResults) {
        if (item.medicine === selectedMedicine) {
          map.set(item.district.toLowerCase(), {
            prob: item.shortage_probability,
            risk: item.risk_level,
          });
        }
      }
    }
    return map;
  }, [simulationResults, selectedMedicine]);

  const getColor = (prob: number | undefined) => {
    if (prob === undefined) return "#94a3b8"; // slate-400 default
    if (prob > 0.40) return "#dc2626"; // red-600 High Risk
    if (prob >= 0.10) return "#f59e0b"; // amber-500 Medium Risk
    return "#10b981"; // emerald-500 Low Risk
  };

  const styleFeature = (feature: any) => {
    const dName = (feature.properties?.district || "").toLowerCase();
    const riskInfo = riskMap.get(dName);
    const prob = riskInfo?.prob;

    return {
      fillColor: getColor(prob),
      weight: 1.5,
      opacity: 1,
      color: "#ffffff",
      dashArray: "",
      fillOpacity: 0.75,
    };
  };

  const onEachFeature = (feature: any, layer: Layer) => {
    const dName = feature.properties?.district || "Unknown District";
    const riskInfo = riskMap.get(dName.toLowerCase());

    const tooltipContent = `
      <div style="font-family: sans-serif; font-size: 12px; padding: 4px;">
        <strong style="font-size: 13px;">${dName}</strong><br/>
        ${
          riskInfo
            ? `<span>Shortage Probability: <b>${(riskInfo.prob * 100).toFixed(1)}%</b></span><br/>
               <span>Risk Level: <b>${riskInfo.risk}</b></span>`
            : `<span>Maharashtra Node</span>`
        }
      </div>
    `;
    layer.bindTooltip(tooltipContent, { sticky: true });

    layer.on({
      click: () => {
        if (onDistrictSelect) {
          onDistrictSelect(dName);
        }
      },
      mouseover: (e) => {
        const l = e.target;
        l.setStyle({ weight: 3, color: "#1e3a8a", fillOpacity: 0.9 });
      },
      mouseout: (e) => {
        const l = e.target;
        l.setStyle(styleFeature(feature));
      },
    });
  };

  return (
    <div className="w-full h-[520px] rounded-xl overflow-hidden shadow-sm border border-slate-200 z-0">
      <MapContainer
        center={[19.7515, 75.7139]} // Maharashtra centroid
        zoom={7}
        scrollWheelZoom={false}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geoJsonData && (
          <GeoJSON
            key={selectedMedicine + "-" + (simulationResults?.length || 0)}
            data={geoJsonData}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>
    </div>
  );
};
