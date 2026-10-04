"""
Real Open-Meteo weather fetching module for interactive What-If simulation.
Fetches historical/real-time weather archive data from Open-Meteo API.
Failed fetches remain NaN (no random generation).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import requests

PROCESSED_DIR = Path("data/processed")
INTERIM_DIR = Path("data/interim")

def fetch_open_meteo_archive(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """
    Fetch real historical weather telemetry from Open-Meteo Archive API.
    Returns weather indicators dict or NaNs if fetch fails/offline. Failed fetches stay NaN, NEVER random.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ["precipitation_sum", "wind_speed_10m_max", "temperature_2m_max", "temperature_2m_min"],
        "timezone": "Asia/Kolkata"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json().get("daily", {})
            precip = data.get("precipitation_sum", [np.nan])
            wind = data.get("wind_speed_10m_max", [np.nan])
            temp_max = data.get("temperature_2m_max", [np.nan])
            temp_min = data.get("temperature_2m_min", [np.nan])

            precip_clean = [p for p in precip if p is not None and not np.isnan(p)]
            wind_clean = [w for w in wind if w is not None and not np.isnan(w)]
            tmax_clean = [t for t in temp_max if t is not None and not np.isnan(t)]
            tmin_clean = [t for t in temp_min if t is not None and not np.isnan(t)]

            return {
                "precip_sum_mm": float(np.sum(precip_clean)) if precip_clean else np.nan,
                "wind_max_kmh": float(np.max(wind_clean)) if wind_clean else np.nan,
                "temp_max_c": float(np.max(tmax_clean)) if tmax_clean else np.nan,
                "temp_min_c": float(np.min(tmin_clean)) if tmin_clean else np.nan,
                "status": "SUCCESS_OPEN_METEO"
            }
    except Exception as e:
        pass

    # Failed fetches stay NaN
    return {
        "precip_sum_mm": np.nan,
        "wind_max_kmh": np.nan,
        "temp_max_c": np.nan,
        "temp_min_c": np.nan,
        "status": "FAILED_FETCH_STAYS_NAN"
    }

if __name__ == "__main__":
    res = fetch_open_meteo_archive(18.52, 73.85, "2024-07-01", "2024-07-07")
    print("Open-Meteo Fetch Test Result:", res)
