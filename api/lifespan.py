"""Lifespan event handler for FastAPI: loads models, data, and boundary artifacts once."""
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI

from api.config import settings
from src.optimise import load_or_compute_distance_matrix

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing API application lifespan: loading artifacts...")

    app.state.ready = False

    # 0. Initialize Database Tables
    try:
        from api.database import init_db
        init_db()
        logger.info("Initialized database tables (users, simulations, audit_events).")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    # 1. Load Processed Datasets
    try:
        app.state.pop_df = pd.read_csv(settings.PROCESSED_DIR / "district_population.csv")
        app.state.cap_df = pd.read_csv(settings.PROCESSED_DIR / "district_capacity.csv")
        app.state.fac_df = pd.read_csv(settings.PROCESSED_DIR / "district_facilities.csv")
        cleaned_fac_file = settings.PROCESSED_DIR / "cleaned_facilities.csv"
        if cleaned_fac_file.exists():
            app.state.cleaned_facilities_df = pd.read_csv(cleaned_fac_file)
            logger.info(f"Loaded cleaned hospital facilities ({len(app.state.cleaned_facilities_df)} facilities).")
        else:
            app.state.cleaned_facilities_df = pd.DataFrame()
        logger.info(f"Loaded district population ({len(app.state.pop_df)} rows), capacity, and facilities.")
    except Exception as e:
        logger.error(f"Error loading processed CSV data: {e}")
        app.state.pop_df = pd.DataFrame()
        app.state.cap_df = pd.DataFrame()
        app.state.fac_df = pd.DataFrame()
        app.state.cleaned_facilities_df = pd.DataFrame()

    # 2. Load GeoJSON Boundaries and Normalise via Canonical Boundaries Module
    try:
        from src.data.boundaries import load_or_create_district_boundaries
        boundaries_gdf = load_or_create_district_boundaries()
        geojson_obj = json.loads(boundaries_gdf.to_json())
        app.state.geojson = geojson_obj
        logger.info(f"Loaded and normalised {len(geojson_obj.get('features', []))} Maharashtra GeoJSON boundaries (canonical 35 districts with Palghar integration).")
    except Exception as e:
        logger.error(f"Error loading GeoJSON via boundaries module: {e}")
        app.state.geojson = {"type": "FeatureCollection", "features": []}

    # 3. Load Reports & Metrics
    try:
        metrics_file = settings.REPORTS_DIR / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                app.state.metrics_data = json.load(f)
        else:
            app.state.metrics_data = {}

        backtest_file = settings.REPORTS_DIR / "historical_backtest.csv"
        if backtest_file.exists():
            app.state.backtest_df = pd.read_csv(backtest_file)
        else:
            app.state.backtest_df = pd.DataFrame()

        baselines_file = settings.REPORTS_DIR / "baseline_comparison.csv"
        if baselines_file.exists():
            app.state.baselines_df = pd.read_csv(baselines_file)
        else:
            app.state.baselines_df = pd.DataFrame()

        alloc_summary_file = settings.REPORTS_DIR / "allocation_summary.json"
        if alloc_summary_file.exists():
            with open(alloc_summary_file, "r", encoding="utf-8") as f:
                app.state.allocation_summary = json.load(f)
        else:
            app.state.allocation_summary = {}

        logger.info("Loaded reports: metrics.json, historical_backtest.csv, baseline_comparison.csv, allocation_summary.json.")
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        app.state.metrics_data = {}
        app.state.backtest_df = pd.DataFrame()
        app.state.baselines_df = pd.DataFrame()
        app.state.allocation_summary = {}

    # 4. Load Models & Pipelines
    try:
        impact_path = settings.MODELS_DIR / "impact_models.joblib"
        if impact_path.exists():
            imp_bundle = joblib.load(impact_path)
            # Model schema validation
            if isinstance(imp_bundle, dict) and "preprocessor" in imp_bundle and "impact_model" in imp_bundle:
                app.state.impact_bundle = imp_bundle
                logger.info("Loaded impact models and CQR bundle.")
            else:
                logger.error("impact_models.joblib missing required 'preprocessor' or 'impact_model' keys.")
                app.state.impact_bundle = None
        else:
            app.state.impact_bundle = None
            logger.warning(f"Impact models not found at {impact_path}")

        surrogate_path = settings.MODELS_DIR / "shortage_classifier.joblib"
        if surrogate_path.exists():
            app.state.surrogate_bundle = joblib.load(surrogate_path)
            logger.info("Loaded surrogate shortage classifier.")
        else:
            app.state.surrogate_bundle = None

        shap_path = settings.MODELS_DIR / "shap_explainer.joblib"
        if shap_path.exists():
            app.state.shap_explainer = joblib.load(shap_path)
            logger.info("Loaded Tree-SHAP explainer for XGBoost impact model.")
        else:
            app.state.shap_explainer = None

        # DEF-01 Safety Check: Refuse synthetic test fixtures in production / staging
        if settings.ENVIRONMENT in ("production", "staging"):
            for m_name, bundle_obj in [("impact_bundle", app.state.impact_bundle), ("surrogate_bundle", app.state.surrogate_bundle)]:
                if bundle_obj is not None:
                    is_synth = getattr(bundle_obj, "is_synthetic", False) if not isinstance(bundle_obj, dict) else bundle_obj.get("is_synthetic", False)
                    if is_synth:
                        logger.critical(f"FATAL: Synthetic test fixture detected in production environment for {m_name}. Refusing to load.")
                        app.state.ready = False
                        raise RuntimeError(f"Production environment rejects synthetic model fixture for {m_name}.")
    except Exception as e:
        logger.error(f"Error loading ML models: {e}")
        app.state.impact_bundle = None
        app.state.surrogate_bundle = None
        app.state.shap_explainer = None

    # 4b. Load Clinical Forecaster (Hybrid Seasonal Ridge)
    try:
        from src.forecast import load_clinical_forecaster
        clinical_path = Path("final_model.joblib")
        if clinical_path.exists():
            app.state.clinical_model = load_clinical_forecaster(clinical_path)
            logger.info("Loaded certified Clinical Forecasting model (Hybrid Seasonal Ridge).")
        else:
            app.state.clinical_model = None
            logger.warning(f"Clinical forecasting model not found at {clinical_path}")
    except Exception as e:
        logger.error(f"Error loading clinical forecasting model: {e}")
        app.state.clinical_model = None

    # 5. Distance Matrix
    try:
        app.state.distances_df = load_or_compute_distance_matrix()
        logger.info("Loaded Haversine x 1.3 circuity distance matrix.")
    except Exception as e:
        logger.error(f"Error computing distance matrix: {e}")
        app.state.distances_df = None

    app.state.ready = True
    logger.info("FastAPI lifespan setup completed: server is READY.")

    yield

    logger.info("Shutting down API server...")
