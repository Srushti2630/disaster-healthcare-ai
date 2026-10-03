# Data Directory Structure and Setup

This directory contains raw, interim, and processed data for the **Explainable & Uncertainty-Aware Disaster Healthcare AI Framework**.

## Structure
- `data/raw/`: Read-only source datasets.
  - `emdat.xlsx`: EM-DAT International Disaster Database (India subset).
  - `hospital_directory (1).csv`: National Health Portal hospital directory.
  - `ICU beds count in India - Statewise.csv`: State-level ICU capacity numbers.
  - `ind_ppp_2020_constrained (1).tif.zip`: WorldPop 2020 1km population raster for India.
  - `Medical-Inventory-Optimization-and-Forecasting-main.zip`: Methodology reference code repository.
- `data/interim/`: Intermediate cached transformations (e.g. Open-Meteo event weather parquet).
- `data/processed/`: Standardized output tables for training and optimization:
  - `district_population.csv`: WorldPop zonal sum population per Maharashtra district.
  - `district_capacity.csv`: Estimated hospital and ICU bed capacity per district.
  - `emdat_events.csv`: Standardized historical EM-DAT event records.
  - `weather_events.parquet`: Event-window weather features from Open-Meteo.
  - `hazard_priors.csv`: District-level historical hazard frequency distributions.
  - `provenance.yaml`: Machine-readable data provenance catalog.

## Instructions to Obtain Missing Raw Data
See [docs/DATA_NEEDED.md](../docs/DATA_NEEDED.md) for full instructions, source URLs, and expected schemas.
