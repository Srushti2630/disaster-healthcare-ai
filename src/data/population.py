"""
WorldPop 2020 population raster extraction module.
Computes zonal sum population per Maharashtra district using windowed GeoTIFF reads.
Outputs data/processed/district_population.csv.
"""
from pathlib import Path
import os
import zipfile
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
import geopandas as gpd

from src.data.boundaries import load_or_create_district_boundaries, MAHARASHTRA_DISTRICTS

PROCESSED_DIR = Path("data/processed")
INTERIM_DIR = Path("data/interim")
RAW_ZIP = Path("data/raw/ind_ppp_2020_constrained (1).tif.zip")
TARGET_TIF = INTERIM_DIR / "ind_ppp_2020_constrained.tif"

# Total 2020 projected Maharashtra population reference anchor (Census 2011 = 112.37M, 2020 projected = 124.5M)
TARGET_MAHARASHTRA_POP_2020 = 124_500_000

def get_geotiff_path() -> Path:
    """Ensure WorldPop GeoTIFF is unzipped in data/interim and return its path."""
    if TARGET_TIF.exists():
        return TARGET_TIF
    
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_ZIP.exists():
        raise FileNotFoundError(f"WorldPop zip missing at {RAW_ZIP}")
    
    print(f"Extracting {RAW_ZIP.name}...")
    with zipfile.ZipFile(RAW_ZIP) as z:
        tif_name = [name for name in z.namelist() if name.endswith(".tif")][0]
        z.extract(tif_name, INTERIM_DIR)
        extracted = INTERIM_DIR / tif_name
        if extracted != TARGET_TIF:
            extracted.rename(TARGET_TIF)
    return TARGET_TIF

from rasterio.mask import mask

def compute_district_populations() -> pd.DataFrame:
    """Compute raw zonal sum population for each district from WorldPop raster using rasterio.mask."""
    tif_path = get_geotiff_path()
    gdf = load_or_create_district_boundaries()
    is_real = gdf.attrs.get("is_real", True)

    records = []
    with rasterio.open(tif_path) as src:
        gdf_src = gdf.to_crs(src.crs)
        for idx, row in gdf_src.iterrows():
            d_name = row["district"]
            geom = [row["geometry"]]
            try:
                out_img, _ = mask(src, geom, crop=True)
                arr = np.where(out_img < 0, 0, out_img)
                arr = np.nan_to_num(arr, nan=0.0)
                raw_pop = float(np.sum(arr))
            except Exception as e:
                print(f"Warning: rasterio.mask failed for {d_name}: {e}")
                raw_pop = 0.0

            area_sqkm = float(row["area_sqkm"]) if ("area_sqkm" in row and not pd.isna(row["area_sqkm"])) else round(row["geometry"].area * (111.0 ** 2), 1)

            records.append({
                "district": d_name,
                "population": int(round(raw_pop)),
                "area_sqkm": area_sqkm,
            })

    df = pd.DataFrame(records)
    total_raw = df["population"].sum()
    gap_pct = abs(total_raw - TARGET_MAHARASHTRA_POP_2020) / TARGET_MAHARASHTRA_POP_2020 * 100.0
    print(f"Raw WorldPop zonal sum total: {total_raw:,.0f} (Official MH 2020 projection: {TARGET_MAHARASHTRA_POP_2020:,.0f}, gap: {gap_pct:.2f}%)")

    df["pop_density_sqkm"] = (df["population"] / df["area_sqkm"]).round(2)
    df["provenance"] = "REAL" if is_real else "ESTIMATED"

    out_csv = PROCESSED_DIR / "district_population.csv"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df[["district", "population", "area_sqkm", "pop_density_sqkm", "provenance"]].to_csv(out_csv, index=False)
    print(f"Successfully wrote {len(df)} district populations to {out_csv} (Provenance: {df['provenance'].iloc[0]})")
    return df

if __name__ == "__main__":
    compute_district_populations()
