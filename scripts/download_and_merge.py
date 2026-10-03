#!/usr/bin/env python3
"""
download_and_merge.py
Downloads the public datasets for the disaster-healthcare project and merges
them into unified tables under data/processed/.

Usage examples
  python download_and_merge.py                          # default steps, 2000-2025
  python download_and_merge.py --years 2010-2024
  python download_and_merge.py --steps noaa,ibtracs     # only some steps
  python download_and_merge.py --steps worldpop,osm,hhs # the big optional files

Steps: noaa, ibtracs, usgs, emdat, weather, merge       (default)
       worldpop (~500 MB), osm (~1 GB+), hhs (large)    (optional)

EM-DAT requires a free login, so it cannot be auto-downloaded. Register at
https://public.emdat.be, export the India records as .xlsx and save it as
data/raw/emdat.xlsx. The 'emdat' step will pick it up.

Outputs (data/processed/)
  noaa_events.csv, ibtracs_storms.csv, usgs_quakes.csv, emdat_events.csv
  weather_daily.csv
  disaster_events.csv   <- unified schema (see UNIFIED_COLS)
"""
import argparse
import datetime as dt
import re
import time
from pathlib import Path

import pandas as pd
import requests

RAW = Path("data/raw")
OUT = Path("data/processed")
UA = {"User-Agent": "disaster-healthcare-project/1.0 (student research)"}

NOAA_DIR = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
IBTRACS_NI = ("https://www.ncei.noaa.gov/data/international-best-track-archive-"
              "for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv")
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
WORLDPOP_IND = ("https://worldpop-public-data.soton.ac.uk/GIS/Population/"
                "Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_constrained.tif")
OSM_INDIA = "https://download.geofabrik.de/asia/india-latest.osm.pbf"
HHS_FACILITY = "https://healthdata.gov/api/v3/views/anag-cw7u/export.csv?accessType=DOWNLOAD"

# Illustrative regional centroids for weather download. Edit freely.
REGIONS = {
    "Pune": (18.52, 73.86), "Mumbai": (19.08, 72.88), "Nashik": (20.00, 73.79),
    "Nagpur": (21.15, 79.09), "Kolhapur": (16.70, 74.24), "Satara": (17.69, 74.00),
    "Ratnagiri": (16.99, 73.30), "Sangli": (16.85, 74.58),
    "Aurangabad": (19.88, 75.34), "Solapur": (17.66, 75.91),
}

UNIFIED_COLS = ["source", "event_id", "date", "type", "lat", "lon", "region",
                "deaths", "injuries", "affected", "damage_usd", "intensity"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def get(url, dest, retries=3):
    """Stream a file to disk; skip if already present."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest}")
        return dest
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=120, headers=UA) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
                print(f"  [ok]   {dest}")
                return dest
        except Exception as e:  # noqa: BLE001
            print(f"  [retry {attempt + 1}/{retries}] {url}: {e}")
            time.sleep(2 * (attempt + 1))
    print(f"  [FAILED] {url}")
    return None


def money(s):
    """NOAA damage strings like '10.00K', '1.5M' -> float USD."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return 0.0
    s = str(s).strip().upper()
    if not s:
        return 0.0
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1], 1.0)
    core = s[:-1] if s[-1] in "KMB" else s
    try:
        return float(core) * mult
    except ValueError:
        return 0.0


def pick(df, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([None] * len(df), index=df.index)


def unify(df):
    for c in UNIFIED_COLS:
        if c not in df.columns:
            df[c] = None
    return df[UNIFIED_COLS]


# --------------------------------------------------------------------------
# NOAA Storm Events (US)
# --------------------------------------------------------------------------
NOAA_TYPE_MAP = {
    "Flood": "flood", "Flash Flood": "flood", "Coastal Flood": "flood",
    "Hurricane": "cyclone", "Hurricane (Typhoon)": "cyclone",
    "Tropical Storm": "cyclone", "Tropical Depression": "cyclone",
    "Storm Surge/Tide": "cyclone",
    "Excessive Heat": "heatwave", "Heat": "heatwave",
    "Tornado": "tornado", "Wildfire": "wildfire",
    "Winter Storm": "winter_storm", "Blizzard": "winter_storm",
}


def normalize_noaa(df):
    df = df[df["EVENT_TYPE"].isin(NOAA_TYPE_MAP)].copy()
    day = df["BEGIN_DAY"].astype(int).astype(str).str.zfill(2)
    date = pd.to_datetime(df["BEGIN_YEARMONTH"].astype(int).astype(str) + day,
                          format="%Y%m%d", errors="coerce")
    out = pd.DataFrame({
        "source": "NOAA",
        "event_id": "NOAA-" + df["EVENT_ID"].astype(str),
        "date": date,
        "type": df["EVENT_TYPE"].map(NOAA_TYPE_MAP),
        "lat": pd.to_numeric(df.get("BEGIN_LAT"), errors="coerce"),
        "lon": pd.to_numeric(df.get("BEGIN_LON"), errors="coerce"),
        "region": df["STATE"],
        "deaths": pd.to_numeric(df["DEATHS_DIRECT"], errors="coerce").fillna(0)
                  + pd.to_numeric(df["DEATHS_INDIRECT"], errors="coerce").fillna(0),
        "injuries": pd.to_numeric(df["INJURIES_DIRECT"], errors="coerce").fillna(0)
                    + pd.to_numeric(df["INJURIES_INDIRECT"], errors="coerce").fillna(0),
        "damage_usd": df["DAMAGE_PROPERTY"].map(money) + df["DAMAGE_CROPS"].map(money),
    })
    return unify(out)


def step_noaa(y0, y1):
    print("NOAA Storm Events")
    html = requests.get(NOAA_DIR, timeout=60, headers=UA).text
    files = {}
    for m in re.finditer(r"StormEvents_details-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz", html):
        y, c = int(m.group(1)), m.group(2)
        if y0 <= y <= y1 and (y not in files or c > files[y][0]):
            files[y] = (c, m.group(0))
    frames = []
    for y, (_, name) in sorted(files.items()):
        p = get(NOAA_DIR + name, RAW / "noaa" / name)
        if p:
            df = pd.read_csv(p, compression="gzip", low_memory=False)
            frames.append(normalize_noaa(df))
    if frames:
        OUT.mkdir(parents=True, exist_ok=True)
        pd.concat(frames).to_csv(OUT / "noaa_events.csv", index=False)
        print(f"  -> {OUT / 'noaa_events.csv'}")


# --------------------------------------------------------------------------
# IBTrACS North Indian basin
# --------------------------------------------------------------------------
def normalize_ibtracs(df):
    for c in ["LAT", "LON", "WMO_WIND", "USA_WIND", "WMO_PRES"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], errors="coerce")
    df["wind"] = df[["WMO_WIND", "USA_WIND"]].max(axis=1)  # knots
    rows = []
    for sid, g in df.groupby("SID"):
        g = g.sort_values("ISO_TIME")
        peak = g.loc[g["wind"].idxmax()] if g["wind"].notna().any() else g.iloc[0]
        rows.append({
            "source": "IBTrACS", "event_id": f"IBTRACS-{sid}",
            "date": g["ISO_TIME"].min(), "type": "cyclone",
            "lat": peak["LAT"], "lon": peak["LON"], "region": "North Indian Ocean",
            "intensity": g["wind"].max(),
            "min_pressure_hpa": g["WMO_PRES"].min(),
            "name": g["NAME"].iloc[0],
        })
    return pd.DataFrame(rows)


def step_ibtracs():
    print("IBTrACS (North Indian)")
    p = get(IBTRACS_NI, RAW / "ibtracs" / "ibtracs.NI.list.v04r01.csv")
    if not p:
        return
    df = pd.read_csv(p, skiprows=[1], low_memory=False,
                     usecols=["SID", "NAME", "ISO_TIME", "LAT", "LON",
                              "WMO_WIND", "WMO_PRES", "USA_WIND"])
    out = normalize_ibtracs(df)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "ibtracs_storms.csv", index=False)
    print(f"  -> {OUT / 'ibtracs_storms.csv'} ({len(out)} storms)")


# --------------------------------------------------------------------------
# USGS earthquakes (India bounding box)
# --------------------------------------------------------------------------
def step_usgs(y0, y1, minmag=4.5):
    print("USGS earthquakes")
    frames = []
    for y in range(y0, y1 + 1):
        dest = RAW / "usgs" / f"quakes_{y}.csv"
        if not dest.exists():
            params = dict(format="csv", starttime=f"{y}-01-01", endtime=f"{y + 1}-01-01",
                          minmagnitude=minmag, minlatitude=6, maxlatitude=37,
                          minlongitude=68, maxlongitude=98, orderby="time-asc",
                          limit=20000)
            try:
                r = requests.get(USGS_URL, params=params, timeout=120, headers=UA)
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(r.text)
            except Exception as e:  # noqa: BLE001
                print(f"  [FAILED] {y}: {e}")
                continue
        try:
            frames.append(pd.read_csv(dest))
        except pd.errors.EmptyDataError:
            pass
    if not frames:
        return
    df = pd.concat(frames)
    out = unify(pd.DataFrame({
        "source": "USGS", "event_id": "USGS-" + df["id"].astype(str),
        "date": pd.to_datetime(df["time"], errors="coerce").dt.tz_localize(None),
        "type": "earthquake", "lat": df["latitude"], "lon": df["longitude"],
        "region": df["place"], "intensity": df["mag"],
    }))
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "usgs_quakes.csv", index=False)
    print(f"  -> {OUT / 'usgs_quakes.csv'} ({len(out)} quakes)")


# --------------------------------------------------------------------------
# EM-DAT (manual download)
# --------------------------------------------------------------------------
def step_emdat():
    print("EM-DAT")
    cands = sorted(RAW.glob("emdat*.xlsx"))
    if not cands:
        print("  [manual] No data/raw/emdat*.xlsx found. Register at "
              "https://public.emdat.be, export India records, save as data/raw/emdat.xlsx")
        return
    df = pd.read_excel(cands[0])
    date = pd.to_datetime(dict(year=pick(df, "Start Year"),
                               month=pick(df, "Start Month").fillna(1),
                               day=pick(df, "Start Day").fillna(1)), errors="coerce")
    affected = pick(df, "Total Affected", "No. Affected")
    out = unify(pd.DataFrame({
        "source": "EM-DAT",
        "event_id": "EMDAT-" + pick(df, "DisNo.", "Dis No").astype(str),
        "date": date,
        "type": pick(df, "Disaster Type").str.lower(),
        "lat": pd.to_numeric(pick(df, "Latitude"), errors="coerce"),
        "lon": pd.to_numeric(pick(df, "Longitude"), errors="coerce"),
        "region": pick(df, "Location", "Country"),
        "deaths": pd.to_numeric(pick(df, "Total Deaths"), errors="coerce"),
        "injuries": pd.to_numeric(pick(df, "No. Injured"), errors="coerce"),
        "affected": pd.to_numeric(affected, errors="coerce"),
        # EM-DAT reports damages in thousand USD
        "damage_usd": pd.to_numeric(pick(df, "Total Damage ('000 US$)",
                                         "Total Damage, Adjusted ('000 US$)"),
                                    errors="coerce") * 1000,
        "intensity": pd.to_numeric(pick(df, "Magnitude"), errors="coerce"),
    }))
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "emdat_events.csv", index=False)
    print(f"  -> {OUT / 'emdat_events.csv'} ({len(out)} events)")


# --------------------------------------------------------------------------
# Weather (Open-Meteo archive)
# --------------------------------------------------------------------------
def step_weather(y0, y1):
    print("Open-Meteo weather")
    frames = []
    for name, (lat, lon) in REGIONS.items():
        dest = RAW / "weather" / f"{name}_{y0}_{y1}.csv"
        if dest.exists():
            frames.append(pd.read_csv(dest))
            continue
        params = dict(latitude=lat, longitude=lon, start_date=f"{y0}-01-01",
                      end_date=f"{y1}-12-31", timezone="Asia/Kolkata",
                      daily="precipitation_sum,temperature_2m_max,temperature_2m_min,"
                            "wind_speed_10m_max")
        try:
            r = requests.get(OPENMETEO_URL, params=params, timeout=120, headers=UA)
            r.raise_for_status()
            d = pd.DataFrame(r.json()["daily"]).rename(columns={"time": "date"})
            d.insert(0, "region", name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            d.to_csv(dest, index=False)
            frames.append(d)
            print(f"  [ok]   {name}")
            time.sleep(1)  # be polite to the free API
        except Exception as e:  # noqa: BLE001
            print(f"  [FAILED] {name}: {e}")
    if frames:
        OUT.mkdir(parents=True, exist_ok=True)
        pd.concat(frames).to_csv(OUT / "weather_daily.csv", index=False)
        print(f"  -> {OUT / 'weather_daily.csv'}")


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------
def step_merge():
    print("Merging")
    parts = []
    for fn in ["noaa_events.csv", "ibtracs_storms.csv", "usgs_quakes.csv", "emdat_events.csv"]:
        p = OUT / fn
        if p.exists():
            parts.append(unify(pd.read_csv(p, parse_dates=["date"])))
            print(f"  + {fn} ({len(parts[-1])} rows)")
    if not parts:
        print("  nothing to merge")
        return
    df = pd.concat(parts, ignore_index=True)
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.month
    df.to_csv(OUT / "disaster_events.csv", index=False)
    print(f"  -> {OUT / 'disaster_events.csv'} ({len(df)} rows)")
    print(df.groupby(["source", "type"]).size().to_string())


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default=f"2000-{dt.date.today().year - 1}")
    ap.add_argument("--steps", default="noaa,ibtracs,usgs,emdat,weather,merge")
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-"))
    steps = [s.strip() for s in a.steps.split(",")]

    if "noaa" in steps: step_noaa(y0, y1)
    if "ibtracs" in steps: step_ibtracs()
    if "usgs" in steps: step_usgs(y0, y1)
    if "emdat" in steps: step_emdat()
    if "weather" in steps: step_weather(y0, y1)
    if "worldpop" in steps: get(WORLDPOP_IND, RAW / "worldpop" / "ind_ppp_2020_constrained.tif")
    if "osm" in steps: get(OSM_INDIA, RAW / "osm" / "india-latest.osm.pbf")
    if "hhs" in steps: get(HHS_FACILITY, RAW / "hhs" / "hospital_capacity_by_facility.csv")
    if "merge" in steps: step_merge()


if __name__ == "__main__":
    main()
