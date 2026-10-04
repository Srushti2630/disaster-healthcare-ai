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
        logger.info(f"Loaded district population ({len(app.state.pop_df)} rows), capacity, and facilities.")
    except Exception as e:
        logger.error(f"Error loading processed CSV data: {e}")
        app.state.pop_df = pd.DataFrame()
        app.state.cap_df = pd.DataFrame()
        app.state.fac_df = pd.DataFrame()

    # 2. Load GeoJSON Boundaries and Normalise
    try:
        if settings.BOUNDARIES_FILE.exists():
            with open(settings.BOUNDARIES_FILE, "r", encoding="utf-8") as f:
                geojson_obj = json.load(f)

            # Normalise district property name across features
            for feature in geojson_obj.get("features", []):
                props = feature.get("properties", {})
                # Ensure 'district' key exists
                d_name = props.get("district") or props.get("District") or props.get("DISTRICT") or props.get("NAME_2")
                if d_name:
                    props["district"] = d_name.strip()
            app.state.geojson = geojson_obj
            logger.info("Loaded and normalised Maharashtra GeoJSON boundaries.")
        else:
            app.state.geojson = {"type": "FeatureCollection", "features": []}
            logger.warning(f"Boundaries file not found at {settings.BOUNDARIES_FILE}")
    except Exception as e:
        logger.error(f"Error loading GeoJSON: {e}")
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

        logger.info("Loaded reports: metrics.json, historical_backtest.csv, baseline_comparison.csv.")
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        app.state.metrics_data = {}
        app.state.backtest_df = pd.DataFrame()
        app.state.baselines_df = pd.DataFrame()

    # 4. Load Models & Pipelines
    try:
        impact_path = settings.MODELS_DIR / "impact_models.joblib"
        if impact_path.exists():
            app.state.impact_bundle = joblib.load(impact_path)
            logger.info("Loaded impact models and CQR bundle.")
        else:
            app.state.impact_bundle = None
            logger.warning(f"Impact models not found at {impact_path}")

        surrogate_path = settings.MODELS_DIR / "shortage_classifier.joblib"
        if surrogate_path.exists():
            app.state.surrogate_bundle = joblib.load(surrogate_path)
            logger.info("Loaded surrogate shortage classifier.")
        else:
            app.state.surrogate_bundle = None
    except Exception as e:
        logger.error(f"Error loading ML models: {e}")
        app.state.impact_bundle = None
        app.state.surrogate_bundle = None

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
