# Data Requirements & Acquisition Guide

This document lists all public datasets used in the pipeline, their sources, expected schemas, and instructions for providing additional or updated files.

---

## 1. Verified Raw Datasets Currently Present in `data/raw/`

### A. EM-DAT International Disaster Database (`emdat.xlsx`)
- **Source**: Centre for Research on the Epidemiology of Disasters (CRED) — [public.emdat.be](https://public.emdat.be/)
- **License**: Free for academic research / non-commercial use.
- **Expected Columns**: `Disaster Type`, `Disaster Subtype`, `Start Year`, `Start Month`, `Start Day`, `Total Deaths`, `No. Injured`, `Total Affected`, `Latitude`, `Longitude`, `Location`, `Admin Units`, `GADM Admin Units`.
- **Purpose**: Core real-world disaster impact training dataset (`REAL`).

### B. National Hospital Directory (`hospital_directory (1).csv`)
- **Source**: Open Government Data Portal India — [data.gov.in](https://data.gov.in/)
- **Expected Columns**: `State`, `District`, `Hospital_Category`, `Hospital_Care_Type`, `Total_Num_Beds`, `Location_Coordinates`.
- **Purpose**: Real healthcare facility counts, public/private proportion, and spatial distribution across districts (`REAL`).

### C. Statewise ICU Beds Audit (`ICU beds count in India - Statewise.csv`)
- **Source**: National Health Profile / Kapoor et al. (2020) ICU Capacity Study.
- **Expected Columns**: `State/UT`, `Public ICU Beds`, `Private ICU Beds`, `Total ICU Beds`.
- **Purpose**: Hard state-level anchor for hospital capacity scaling (`REAL`).

### D. WorldPop High-Resolution Population Raster (`ind_ppp_2020_constrained (1).tif.zip`)
- **Source**: WorldPop Project, University of Southampton — [worldpop.org](https://www.worldpop.org/)
- **Expected File**: `ind_ppp_2020_constrained.tif` (100m/1km unconstrained/constrained GeoTIFF).
- **Purpose**: High-fidelity zonal sum population extraction per district (`REAL`).

---

## 2. Missing or Optional Datasets (`DATA_NEEDED`)

If you wish to provide higher-resolution or custom local data, place them in `data/raw/` using the specified file names:

### 1. Maharashtra District GeoJSON Polygon (`data/raw/boundaries/maharashtra_districts.geojson`)
- **Source**: GADM Level 2 or geoBoundaries ADM2 ([geoboundaries.org](https://www.geoboundaries.org/)).
- **Expected Properties**: `district_name` or `NAME_2` matching Maharashtra's 35 official districts.
- **Fallback**: If not provided, the code uses exact district centroids and bounding envelopes generated from census coordinates.

### 2. Historical Pharmaceutical Consumption (`data/raw/pharma_data.csv`)
- **Source**: Hospital ERP / Pharmacy Bill Records.
- **Expected Columns**: `Dateofbill`, `DrugName`, `SubCat`, `Quantity`, `ReturnQuantity`, `Final_Cost`, `Patient_ID`, `Dept`.
- **Purpose**: Calibrating baseline daily consumption rates per bed/patient.
- **Fallback**: If absent, parameters are derived directly from WHO Interagency Emergency Health Kit (IEHK 2017) and Sphere Handbook standards (tagged `ASSUMED`).

### 3. Road Distance & Travel Time Matrix (`data/raw/road_distances.csv`)
- **Source**: OSRM / Google Maps Distance Matrix API export.
- **Expected Columns**: `source_district`, `dest_district`, `distance_km`, `travel_time_hours`.
- **Fallback**: If absent, calculated using Haversine distance $\times$ circuity factor $1.3$ (tagged `ASSUMED`).
