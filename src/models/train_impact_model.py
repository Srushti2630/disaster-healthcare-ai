from pathlib import Path
import argparse
import hashlib
import json
import math
import platform
import joblib
import re
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from scipy.stats import spearmanr, pearsonr
import xgboost as xgb
import shap
import sklearn

from src.models.cqr import CQRRegressor

PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
CONFIG_PATH = Path("config.yaml")
ROLLING_ORIGIN_SEED = 42
ROLLING_ORIGIN_FOLDS = (
    {
        "name": "A",
        "fit_end_year": 1999,
        "point_calibration_years": (2000, 2001),
        "interval_calibration_years": (2002, 2003),
        "evaluation_years": (2004, 2006),
        "expected_counts": (205, 29, 24, 47),
    },
    {
        "name": "B",
        "fit_end_year": 2002,
        "point_calibration_years": (2003, 2004),
        "interval_calibration_years": (2005, 2006),
        "evaluation_years": (2007, 2009),
        "expected_counts": (245, 19, 41, 32),
    },
    {
        "name": "C",
        "fit_end_year": 2005,
        "point_calibration_years": (2006, 2007),
        "interval_calibration_years": (2008, 2009),
        "evaluation_years": (2010, 2012),
        "expected_counts": (291, 29, 17, 26),
    },
    {
        "name": "D",
        "fit_end_year": 2008,
        "point_calibration_years": (2009, 2010),
        "interval_calibration_years": (2011, 2012),
        "evaluation_years": (2013, 2015),
        "expected_counts": (328, 19, 16, 34),
    },
    {
        "name": "E",
        "fit_end_year": 2011,
        "point_calibration_years": (2012, 2013),
        "interval_calibration_years": (2014, 2015),
        "evaluation_years": (2016, 2018),
        "expected_counts": (356, 15, 26, 37),
    },
)
ROLLING_ORIGIN_SPLIT_NAMES = (
    "fit",
    "point_calibration",
    "interval_calibration",
    "evaluation",
)

FEATURE_COLS_NUM = [
    "magnitude", "start_year", "start_month", "decade"
]
FEATURE_COLS_CAT = ["disaster_type", "disaster_subtype", "scope"]

INDIAN_STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 
    'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 
    'Maharashtra', 'Maharastra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Orissa', 
    'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 
    'Uttarakhand', 'West Bengal', 'Jammu and Kashmir', 'Delhi'
]

def parse_provinces_and_scope(loc_str):
    loc_str = str(loc_str)
    found = set()
    for s in INDIAN_STATES:
        if re.search(r'\b' + re.escape(s) + r'\b', loc_str, re.IGNORECASE):
            norm = 'Odisha' if s in ['Odisha', 'Orissa'] else ('Maharashtra' if s == 'Maharastra' else s)
            found.add(norm)
    prov_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:province|state)', loc_str)
    for p in prov_matches:
        if p not in ['India', 'State', 'District']:
            found.add(p)
    cnt = max(1, len(found))
    scope = "multi-state" if cnt > 1 else "single-state"
    return cnt, scope


def prepare_impact_data():
    """Load EM-DAT disaster events catalogue (without weather features)."""
    events_path = PROCESSED_DIR / "emdat_events.csv"
    if not events_path.exists():
        raise FileNotFoundError(f"Missing {events_path}")

    df = pd.read_csv(events_path)

    # Filter non-null total_affected for training target
    valid_df = df[df["total_affected"].notna() & (df["total_affected"] > 0)].copy().reset_index(drop=True)
    valid_df["target"] = np.log1p(valid_df["total_affected"])

    for col in FEATURE_COLS_CAT:
        valid_df[col] = valid_df[col].fillna("Unknown").astype(str)

    return valid_df


def build_rolling_origin_splits(df, verify_expected_counts=True, print_event_ids=True):
    """Create and verify the approved chronological folds before any model fitting."""
    required = {"DisNo.", "start_year", "target"}
    missing_columns = required.difference(df.columns)
    if missing_columns:
        raise ValueError(f"Rolling-origin input is missing columns: {sorted(missing_columns)}")
    if df["DisNo."].isna().any() or df["DisNo."].astype(str).duplicated().any():
        raise ValueError("Rolling-origin input must have a unique, non-null DisNo. per event.")
    if df["start_year"].isna().any() or not np.isfinite(df["start_year"]).all():
        raise ValueError("Rolling-origin input contains missing or non-finite start_year values.")
    splits = []
    all_evaluation_ids = set()
    for spec in ROLLING_ORIGIN_FOLDS:
        point_start, point_end = spec["point_calibration_years"]
        interval_start, interval_end = spec["interval_calibration_years"]
        evaluation_start, evaluation_end = spec["evaluation_years"]
        fold_frames = {
            "fit": df[df["start_year"] <= spec["fit_end_year"]].copy(),
            "point_calibration": df[df["start_year"].between(point_start, point_end)].copy(),
            "interval_calibration": df[df["start_year"].between(interval_start, interval_end)].copy(),
            "evaluation": df[df["start_year"].between(evaluation_start, evaluation_end)].copy(),
        }
        counts = tuple(len(fold_frames[name]) for name in ROLLING_ORIGIN_SPLIT_NAMES)
        if verify_expected_counts and counts != spec["expected_counts"]:
            raise ValueError(
                f"Fold {spec['name']} counts {counts} differ from approved "
                f"counts {spec['expected_counts']}; no models were fitted."
            )
        if any(count == 0 for count in counts):
            raise ValueError(f"Fold {spec['name']} contains an empty split: {counts}.")

        ids = {
            name: set(frame["DisNo."].astype(str))
            for name, frame in fold_frames.items()
        }
        for index, name in enumerate(ROLLING_ORIGIN_SPLIT_NAMES):
            for other_name in ROLLING_ORIGIN_SPLIT_NAMES[index + 1:]:
                overlap = ids[name] & ids[other_name]
                if overlap:
                    raise ValueError(
                        f"Fold {spec['name']} has overlapping {name}/{other_name} "
                        f"event IDs: {sorted(overlap)}"
                    )
        if any((frame["start_year"] >= 2019).any() for frame in fold_frames.values()):
            raise ValueError(
                f"Fold {spec['name']} unexpectedly includes events from 2019 or later."
            )

        evaluation_overlap = all_evaluation_ids & ids["evaluation"]
        if evaluation_overlap:
            raise ValueError(
                f"Evaluation IDs overlap across folds: {sorted(evaluation_overlap)}"
            )
        all_evaluation_ids.update(ids["evaluation"])

        chronological = (
            fold_frames["fit"]["start_year"].max()
            < fold_frames["point_calibration"]["start_year"].min()
            and fold_frames["point_calibration"]["start_year"].max()
            < fold_frames["interval_calibration"]["start_year"].min()
            and fold_frames["interval_calibration"]["start_year"].max()
            < fold_frames["evaluation"]["start_year"].min()
        )
        if not chronological or fold_frames["evaluation"]["start_year"].max() > 2018:
            raise ValueError(f"Fold {spec['name']} violates chronological boundaries.")

        if print_event_ids:
            year_ranges = {
                name: (
                    int(frame["start_year"].min()),
                    int(frame["start_year"].max()),
                )
                for name, frame in fold_frames.items()
            }
            print(
                f"Fold {spec['name']}: counts={dict(zip(ROLLING_ORIGIN_SPLIT_NAMES, counts))}; "
                f"years={year_ranges}; chronological/disjoint=verified"
            )
            for name in ROLLING_ORIGIN_SPLIT_NAMES:
                print(f"  {name}_DisNo={','.join(sorted(ids[name]))}")

        splits.append({"spec": spec, **fold_frames})

    print(
        f"Rolling-origin preflight passed: {len(all_evaluation_ids)} unique "
        "evaluation events; all years <= 2018."
    )
    return splits


def _build_impact_preprocessor():
    return ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler())
        ]), FEATURE_COLS_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURE_COLS_CAT)
    ])


def _build_rolling_origin_estimators(seed=ROLLING_ORIGIN_SEED):
    """Use the existing model families and fixed hyperparameters for every fold."""
    return {
        "Ridge": Ridge(alpha=1.0),
        "Random_Forest": RandomForestRegressor(n_estimators=100, random_state=seed),
        "XGBoost": xgb.XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            random_state=seed,
            n_jobs=1,
        ),
    }


def _fit_affine_calibrator(model, X_point_cal, y_point_cal):
    predictions = model.predict(X_point_cal)
    calibrator = LinearRegression().fit(
        np.asarray(predictions).reshape(-1, 1),
        y_point_cal,
    )
    slope = float(calibrator.coef_[0])
    intercept = float(calibrator.intercept_)
    if slope <= 0:
        return 1.0, 0.0
    return slope, intercept


def _safe_exp(value):
    if value > math.log(np.finfo(float).max):
        return None
    return float(np.exp(value))


def _summarize_point_predictions(rows):
    y_true = rows["target"].to_numpy(dtype=float)
    y_pred = rows["prediction_log"].to_numpy(dtype=float)
    actual = rows["total_affected"].to_numpy(dtype=float)
    invalid = ~np.isfinite(y_pred)
    n = len(rows)
    summary = {
        "n": n,
        "invalid_prediction_count": int(invalid.sum()),
        "valid_prediction_count": int((~invalid).sum()),
    }
    if n == 0:
        summary.update({
            "log_mae": None,
            "log_rmse": None,
            "r2": None,
            "spearman": None,
            "signed_log_bias": None,
            "accuracy_within_half_order_pct": None,
            "underprediction_rate_pct": None,
            "overprediction_rate_pct": None,
            "median_predicted_to_actual_ratio": None,
            "p90_absolute_multiplicative_error": None,
            "ratio_valid_count": 0,
            "ratio_invalid_count": 0,
            "multiplicative_error_overflow_count": 0,
        })
        return summary
    if invalid.any():
        summary.update({
            "log_mae": None,
            "log_rmse": None,
            "r2": None,
            "spearman": None,
            "signed_log_bias": None,
            "accuracy_within_half_order_pct": None,
            "underprediction_rate_pct": None,
            "overprediction_rate_pct": None,
            "median_predicted_to_actual_ratio": None,
            "p90_absolute_multiplicative_error": None,
            "ratio_valid_count": 0,
            "ratio_invalid_count": int(invalid.sum()),
            "multiplicative_error_overflow_count": 0,
        })
        return summary

    residual = y_pred - y_true
    log10_abs_error = np.abs(residual / np.log(10))
    with np.errstate(over="ignore", invalid="ignore"):
        predicted_affected = np.expm1(y_pred)
    ratio_valid = np.isfinite(predicted_affected) & (predicted_affected > 0) & (actual > 0)
    log_ratio = np.full(n, np.nan, dtype=float)
    log_ratio[ratio_valid] = (
        np.log(predicted_affected[ratio_valid]) - np.log(actual[ratio_valid])
    )
    abs_log_ratio = np.abs(log_ratio[ratio_valid])
    multiplicative = [_safe_exp(value) for value in abs_log_ratio]
    finite_multiplicative = [value for value in multiplicative if value is not None]
    rho = spearmanr(y_true, y_pred).statistic if n > 1 else np.nan
    summary.update({
        "log_mae": float(mean_absolute_error(y_true, y_pred)),
        "log_rmse": float(root_mean_squared_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)) if n > 1 else None,
        "spearman": float(rho) if np.isfinite(rho) else None,
        "signed_log_bias": float(np.mean(residual)),
        "accuracy_within_half_order_pct": float(np.mean(log10_abs_error <= 0.5) * 100),
        "underprediction_rate_pct": float(np.mean(residual < 0) * 100),
        "overprediction_rate_pct": float(np.mean(residual > 0) * 100),
        "median_predicted_to_actual_ratio": (
            _safe_exp(float(np.median(log_ratio[ratio_valid])))
            if ratio_valid.any() else None
        ),
        "p90_absolute_multiplicative_error": (
            float(np.quantile(finite_multiplicative, 0.9))
            if finite_multiplicative else None
        ),
        "ratio_valid_count": int(ratio_valid.sum()),
        "ratio_invalid_count": int((~ratio_valid).sum()),
        "multiplicative_error_overflow_count": int(
            len(multiplicative) - len(finite_multiplicative)
        ),
    })
    return summary


def _summarize_intervals(rows, alpha=0.10):
    y_true = rows["target"].to_numpy(dtype=float)
    lower = rows["lower_log"].to_numpy(dtype=float)
    upper = rows["upper_log"].to_numpy(dtype=float)
    n = len(rows)
    finite = np.isfinite(lower) & np.isfinite(upper)
    ordered = finite & (lower <= upper)
    invalid_count = int((~ordered).sum())
    covered = ordered & (y_true >= lower) & (y_true <= upper)
    width = upper[ordered] - lower[ordered]
    scores = np.full(n, np.inf, dtype=float)
    scores[ordered] = width
    below = ordered & (y_true < lower)
    above = ordered & (y_true > upper)
    scores[below] += (2.0 / alpha) * (lower[below] - y_true[below])
    scores[above] += (2.0 / alpha) * (y_true[above] - upper[above])
    valid_scores = scores[ordered]
    multiplicative_width = [_safe_exp(value) for value in width]
    finite_factors = [value for value in multiplicative_width if value is not None]
    return {
        "n": n,
        "valid_interval_count": int(ordered.sum()),
        "invalid_or_crossed_interval_count": invalid_count,
        "coverage_pct_all_events": float(covered.sum() / n * 100) if n else None,
        "covered_count": int(covered.sum()),
        "lower_miss_count": int(below.sum()),
        "upper_miss_count": int(above.sum()),
        "mean_log_width_valid_intervals": float(np.mean(width)) if len(width) else None,
        "median_log_width_valid_intervals": float(np.median(width)) if len(width) else None,
        "mean_multiplicative_width_valid_intervals": (
            float(np.mean(finite_factors)) if finite_factors else None
        ),
        "median_multiplicative_width_valid_intervals": (
            float(np.median(finite_factors)) if finite_factors else None
        ),
        "multiplicative_width_overflow_count": int(
            len(multiplicative_width) - len(finite_factors)
        ),
        "interval_score_mean_valid_intervals": (
            float(np.mean(valid_scores)) if len(valid_scores) else None
        ),
        "interval_score_infinite_count": invalid_count,
    }


def _run_rolling_origin_fold(
    fold,
    estimator_factory=_build_rolling_origin_estimators,
    preprocessor_factory=_build_impact_preprocessor,
    cqr_factory=CQRRegressor,
):
    spec = fold["spec"]
    feature_columns = FEATURE_COLS_NUM + FEATURE_COLS_CAT
    fit_df = fold["fit"]
    point_df = fold["point_calibration"]
    interval_df = fold["interval_calibration"]
    evaluation_df = fold["evaluation"]

    preprocessor = preprocessor_factory()
    X_fit = preprocessor.fit_transform(fit_df[feature_columns])
    X_point = preprocessor.transform(point_df[feature_columns])
    X_interval = preprocessor.transform(interval_df[feature_columns])
    X_evaluation = preprocessor.transform(evaluation_df[feature_columns])
    y_fit = fit_df["target"].to_numpy(dtype=float)
    y_point = point_df["target"].to_numpy(dtype=float)
    y_interval = interval_df["target"].to_numpy(dtype=float)
    y_evaluation = evaluation_df["target"].to_numpy(dtype=float)

    point_rows = []
    calibration = {}
    models = estimator_factory()
    for model_name, model in models.items():
        model.fit(X_fit, y_fit)
        raw_point = np.asarray(model.predict(X_evaluation), dtype=float).reshape(-1)
        slope, intercept = _fit_affine_calibrator(model, X_point, y_point)
        calibration[model_name] = {"slope": slope, "intercept": intercept}
        calibrated = slope * raw_point + intercept
        for index, (_, event) in enumerate(evaluation_df.iterrows()):
            common = {
                "fold": spec["name"],
                "DisNo.": str(event["DisNo."]),
                "year": int(event["start_year"]),
                "disaster_type": str(event["disaster_type"]),
                "target": float(y_evaluation[index]),
                "total_affected": float(event["total_affected"]),
            }
            point_rows.append({
                **common,
                "model": model_name,
                "prediction_variant": "raw",
                "prediction_log": float(raw_point[index]),
            })
            point_rows.append({
                **common,
                "model": model_name,
                "prediction_variant": "affine_calibrated",
                "prediction_log": float(calibrated[index]),
            })

    training_median = float(np.median(y_fit))
    type_medians = fit_df.groupby("disaster_type")["target"].median().to_dict()
    for model_name, predictions in (
        ("Training_Median", np.full(len(evaluation_df), training_median)),
        (
            "Disaster_Type_Training_Median",
            evaluation_df["disaster_type"].map(type_medians)
            .fillna(training_median).to_numpy(dtype=float),
        ),
    ):
        for index, (_, event) in enumerate(evaluation_df.iterrows()):
            point_rows.append({
                "fold": spec["name"],
                "DisNo.": str(event["DisNo."]),
                "year": int(event["start_year"]),
                "disaster_type": str(event["disaster_type"]),
                "target": float(y_evaluation[index]),
                "total_affected": float(event["total_affected"]),
                "model": model_name,
                "prediction_variant": "raw",
                "prediction_log": float(predictions[index]),
            })

    cqr = cqr_factory(alpha=0.10, n_estimators=100, random_state=ROLLING_ORIGIN_SEED)
    cqr.fit(X_fit, y_fit, X_interval, y_interval)
    lower, upper = cqr.predict_interval(X_evaluation)
    interval_rows = evaluation_df[["DisNo.", "start_year", "disaster_type", "total_affected"]].copy()
    interval_rows["fold"] = spec["name"]
    interval_rows["target"] = y_evaluation
    interval_rows["lower_log"] = np.asarray(lower, dtype=float).reshape(-1)
    interval_rows["upper_log"] = np.asarray(upper, dtype=float).reshape(-1)
    return point_rows, interval_rows, calibration, {
        "fit_ids": set(fit_df["DisNo."].astype(str)),
        "point_calibration_ids": set(point_df["DisNo."].astype(str)),
        "interval_calibration_ids": set(interval_df["DisNo."].astype(str)),
        "evaluation_ids": set(evaluation_df["DisNo."].astype(str)),
    }


def _print_metric(label, metrics):
    print(f"{label}: {json.dumps(metrics, sort_keys=True, allow_nan=False)}")


def evaluate_rolling_origin_impact_models(print_event_ids=True):
    """Run the approved development-only rolling-origin comparison without writing artifacts."""
    df = prepare_impact_data()
    folds = build_rolling_origin_splits(
        df,
        verify_expected_counts=True,
        print_event_ids=print_event_ids,
    )

    data_path = PROCESSED_DIR / "emdat_events.csv"
    code_path = Path(__file__).resolve()
    manifest = {
        "experiment": "chronological rolling-origin development evaluation",
        "label": "REAL EM-DAT Total Affected; target=log1p(total_affected)",
        "prediction_provenance": "ESTIMATED",
        "rows_with_labeled_target_through_2018": int((df["start_year"] <= 2018).sum()),
        "post_2018_rows_excluded": int((df["start_year"] >= 2019).sum()),
        "feature_columns": FEATURE_COLS_NUM + FEATURE_COLS_CAT,
        "folds": [
            {
                "name": spec["name"],
                "fit_end_year": spec["fit_end_year"],
                "point_calibration_years": spec["point_calibration_years"],
                "interval_calibration_years": spec["interval_calibration_years"],
                "evaluation_years": spec["evaluation_years"],
                "expected_counts": spec["expected_counts"],
                "event_ids": {
                    split_name: sorted(fold[split_name]["DisNo."].astype(str).tolist())
                    for split_name in ROLLING_ORIGIN_SPLIT_NAMES
                },
            }
            for spec, fold in zip(ROLLING_ORIGIN_FOLDS, folds)
        ],
        "seed": ROLLING_ORIGIN_SEED,
        "estimators": {
            "Ridge": {"alpha": 1.0},
            "Random_Forest": {"n_estimators": 100, "random_state": ROLLING_ORIGIN_SEED},
            "XGBoost": {
                "n_estimators": 100,
                "max_depth": 4,
                "learning_rate": 0.05,
                "random_state": ROLLING_ORIGIN_SEED,
                "n_jobs": 1,
            },
            "conformal_method_note": (
                "Uses the existing CQRRegressor unchanged. Its conformal margin uses "
                "interpolated numpy.quantile; empirical coverage here is not presented "
                "as a formal finite-sample guarantee."
            ),
            "CQR": {"alpha": 0.10, "n_estimators": 100, "random_state": ROLLING_ORIGIN_SEED},
        },
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "xgboost_version": xgb.__version__,
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(code_path.read_bytes()).hexdigest(),
    }
    print("ROLLING_ORIGIN_MANIFEST=" + json.dumps(manifest, sort_keys=True))

    all_point_rows = []
    all_interval_rows = []
    all_calibration = {}
    evaluation_ids = set()
    for fold in folds:
        point_rows, interval_rows, calibration, id_sets = _run_rolling_origin_fold(fold)
        if evaluation_ids & id_sets["evaluation_ids"]:
            raise ValueError("Evaluation event IDs overlap between rolling-origin folds.")
        evaluation_ids.update(id_sets["evaluation_ids"])
        all_point_rows.extend(point_rows)
        all_interval_rows.append(interval_rows)
        all_calibration[fold["spec"]["name"]] = calibration

    point_frame = pd.DataFrame(all_point_rows)
    interval_frame = pd.concat(all_interval_rows, ignore_index=True)
    evaluation_frame = folds[0]["evaluation"].iloc[0:0].copy()
    for fold in folds:
        evaluation_frame = pd.concat([evaluation_frame, fold["evaluation"]], axis=0)
    if set(evaluation_frame["DisNo."].astype(str)) != evaluation_ids:
        raise ValueError("Pooled evaluation rows do not match the verified evaluation IDs.")
    if (evaluation_frame["start_year"] >= 2019).any():
        raise ValueError("The experiment unexpectedly included 2019 or later events.")

    print("Point calibration coefficients:")
    print(json.dumps(all_calibration, sort_keys=True))
    groups = (
        ("below_10000", lambda frame: frame["total_affected"] < 10_000),
        ("10000_to_below_1m", lambda frame: (
            (frame["total_affected"] >= 10_000)
            & (frame["total_affected"] < 1_000_000)
        )),
        ("at_least_1m", lambda frame: frame["total_affected"] >= 1_000_000),
        ("at_least_10m", lambda frame: frame["total_affected"] >= 10_000_000),
    )

    model_keys = sorted(point_frame["model"].unique())
    for model_name in model_keys:
        variants = sorted(
            point_frame.loc[point_frame["model"] == model_name, "prediction_variant"].unique()
        )
        for variant in variants:
            selected = point_frame[
                (point_frame["model"] == model_name)
                & (point_frame["prediction_variant"] == variant)
            ]
            _print_metric(
                f"POOLED_POINT model={model_name} variant={variant}",
                _summarize_point_predictions(selected),
            )
            for fold_name in [spec["name"] for spec in ROLLING_ORIGIN_FOLDS]:
                fold_rows = selected[selected["fold"] == fold_name]
                _print_metric(
                    f"FOLD_POINT fold={fold_name} model={model_name} variant={variant}",
                    _summarize_point_predictions(fold_rows),
                )
            for group_name, predicate in groups:
                group_rows = selected[predicate(selected)]
                _print_metric(
                    f"SEVERITY_POINT group={group_name} model={model_name} "
                    f"variant={variant}",
                    _summarize_point_predictions(group_rows),
                )

    _print_metric("POOLED_INTERVAL", _summarize_intervals(interval_frame))
    for fold_name in [spec["name"] for spec in ROLLING_ORIGIN_FOLDS]:
        fold_rows = interval_frame[interval_frame["fold"] == fold_name]
        _print_metric(
            f"FOLD_INTERVAL fold={fold_name}",
            _summarize_intervals(fold_rows),
        )
    for group_name, predicate in groups:
        group_rows = interval_frame[predicate(interval_frame)]
        _print_metric(
            f"SEVERITY_INTERVAL group={group_name}",
            _summarize_intervals(group_rows),
        )
    for fold_name in [spec["name"] for spec in ROLLING_ORIGIN_FOLDS]:
        fold_interval_rows = interval_frame[interval_frame["fold"] == fold_name]
        for group_name, predicate in groups:
            _print_metric(
                f"FOLD_SEVERITY_INTERVAL fold={fold_name} group={group_name}",
                _summarize_intervals(fold_interval_rows[predicate(fold_interval_rows)]),
            )
        for model_name in model_keys:
            variants = sorted(
                point_frame.loc[
                    point_frame["model"] == model_name, "prediction_variant"
                ].unique()
            )
            for variant in variants:
                fold_model_rows = point_frame[
                    (point_frame["fold"] == fold_name)
                    & (point_frame["model"] == model_name)
                    & (point_frame["prediction_variant"] == variant)
                ]
                for group_name, predicate in groups:
                    _print_metric(
                        f"FOLD_SEVERITY_POINT fold={fold_name} group={group_name} "
                        f"model={model_name} variant={variant}",
                        _summarize_point_predictions(fold_model_rows[predicate(fold_model_rows)]),
                    )

    return {
        "manifest": manifest,
        "point_predictions": point_frame,
        "interval_predictions": interval_frame,
        "calibration": all_calibration,
    }


def train_and_evaluate_impact_models():
    """Execute time-split model training, CQR calibration, SHAP feature attribution, and historical back-testing."""
    df = prepare_impact_data()
    print(f"Loaded {len(df)} real disaster events with recorded target casualty figures.")

    # Time-based splitting
    train_mask = df["start_year"] <= 2012
    val_mask = (df["start_year"] > 2012) & (df["start_year"] <= 2018)
    test_mask = df["start_year"] >= 2019

    train_df = df[train_mask].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()

    # Fallback to 70/15/15 time split if any split is too small
    if len(train_df) < 100 or len(test_df) < 30:
        df_sorted = df.sort_values("start_year").reset_index(drop=True)
        n = len(df_sorted)
        train_df = df_sorted.iloc[:int(0.70*n)].copy()
        val_df = df_sorted.iloc[int(0.70*n):int(0.85*n)].copy()
        test_df = df_sorted.iloc[int(0.85*n):].copy()

    print(f"Time splits: Train (N={len(train_df)}), Val (N={len(val_df)}), Test (N={len(test_df)})")

    # Preprocessing pipeline
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler())
        ]), FEATURE_COLS_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURE_COLS_CAT)
    ])

    X_train_raw = train_df[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_train = train_df["target"].values

    point_cal_df = val_df[val_df["start_year"] <= 2015].copy()
    interval_cal_df = val_df[val_df["start_year"] > 2015].copy()
    if len(point_cal_df) < 10 or len(interval_cal_df) < 10:
        raise ValueError("The validation period must provide at least 10 point- and interval-calibration events.")

    X_point_cal_raw = point_cal_df[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_point_cal = point_cal_df["target"].values
    X_interval_cal_raw = interval_cal_df[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_interval_cal = interval_cal_df["target"].values

    X_test_raw = test_df[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_test = test_df["target"].values

    X_train = preprocessor.fit_transform(X_train_raw)
    X_point_cal = preprocessor.transform(X_point_cal_raw)
    X_interval_cal = preprocessor.transform(X_interval_cal_raw)
    X_test = preprocessor.transform(X_test_raw)

    # Individual base models
    ridge_base = Ridge(alpha=1.0)
    rf_base = RandomForestRegressor(n_estimators=100, random_state=42)
    xgb_base = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)

    # Models evaluation with heterogeneous Voting Ensemble
    models = {
        "Median_Baseline": None,
        "Ridge": ridge_base,
        "Random_Forest": rf_base,
        "XGBoost": xgb_base,
        "Voting_Ensemble": VotingRegressor(
            estimators=[
                ("ridge", Ridge(alpha=1.0)),
                ("rf", RandomForestRegressor(n_estimators=100, random_state=42)),
                ("xgb", xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42))
            ]
        )
    }

    metrics = {}
    median_val = float(np.median(y_train))

    for m_name, model in models.items():
        if m_name == "Median_Baseline":
            y_pred_test = np.full_like(y_test, fill_value=median_val)
        else:
            model.fit(X_train, y_train)
            y_pred_test = model.predict(X_test)

        mae = float(mean_absolute_error(y_test, y_pred_test))
        rmse = float(root_mean_squared_error(y_test, y_pred_test))
        r2 = float(r2_score(y_test, y_pred_test))
        rho, _ = spearmanr(y_test, y_pred_test)

        # Order of magnitude accuracy (% predictions within 0.5 log10 units)
        log10_err = np.abs((y_test - y_pred_test) / np.log(10))
        acc_half_log = float(np.mean(log10_err <= 0.5) * 100)

        metrics[m_name] = {
            "test_mae_log": round(mae, 4),
            "test_rmse_log": round(rmse, 4),
            "test_r2": round(r2, 4),
            "test_spearman_rho": round(float(rho) if not np.isnan(rho) else 0.0, 4),
            "accuracy_within_half_order_of_magnitude_pct": round(acc_half_log, 1)
        }

    print("\n--- Model Benchmark Results (Time-Split Test Set) ---")
    for m_name, m_res in metrics.items():
        print(f"  {m_name:18s} | MAE: {m_res['test_mae_log']:.4f} | R²: {m_res['test_r2']:.4f} | Spearman: {m_res['test_spearman_rho']:.4f} | Order-of-Mag Acc: {m_res['accuracy_within_half_order_of_magnitude_pct']}%")

    ridge_model = models["Ridge"]
    point_calibrator = LinearRegression().fit(
        ridge_model.predict(X_point_cal).reshape(-1, 1),
        y_point_cal
    )
    calibration_slope = float(point_calibrator.coef_[0])
    calibration_intercept = float(point_calibrator.intercept_)
    if calibration_slope <= 0:
        calibration_slope = 1.0
        calibration_intercept = 0.0

    raw_ridge_test = ridge_model.predict(X_test)
    calibrated_ridge_test = calibration_slope * raw_ridge_test + calibration_intercept
    metrics["Ridge_Uncalibrated"] = metrics["Ridge"]
    ridge_rho, _ = spearmanr(y_test, calibrated_ridge_test)
    ridge_log10_err = np.abs((y_test - calibrated_ridge_test) / np.log(10))
    metrics["Ridge"] = {
        "test_mae_log": round(float(mean_absolute_error(y_test, calibrated_ridge_test)), 4),
        "test_rmse_log": round(float(root_mean_squared_error(y_test, calibrated_ridge_test)), 4),
        "test_r2": round(float(r2_score(y_test, calibrated_ridge_test)), 4),
        "test_spearman_rho": round(float(ridge_rho) if not np.isnan(ridge_rho) else 0.0, 4),
        "accuracy_within_half_order_of_magnitude_pct": round(float(np.mean(ridge_log10_err <= 0.5) * 100), 1)
    }
    print(
        "\n--- Validation-Calibrated Ridge (Time-Split Test Set) ---"
        f"\n  MAE: {metrics['Ridge']['test_mae_log']:.4f} | "
        f"R²: {metrics['Ridge']['test_r2']:.4f} | "
        f"Spearman: {metrics['Ridge']['test_spearman_rho']:.4f}"
    )

    # Fit Conformalized Quantile Regression (CQR) for calibrated prediction intervals
    cqr = CQRRegressor(alpha=0.10, n_estimators=100, random_state=42)
    cqr.fit(X_train, y_train, X_interval_cal, y_interval_cal)

    lower_test, upper_test = cqr.predict_interval(X_test)
    covered = (y_test >= lower_test) & (y_test <= upper_test)
    empirical_coverage_90 = float(np.mean(covered) * 100)
    
    # CQR Interval Width as Multiplicative Factor
    log_widths = upper_test - lower_test
    mult_factors = np.exp(log_widths)
    med_mult_factor = float(np.median(mult_factors))

    # Per-hazard coverage breakdown
    test_df_cov = test_df.copy()
    test_df_cov["covered"] = covered
    test_df_cov["disaster_type"] = test_df_cov["disaster_type"].astype(str)
    per_hazard_cov = {}
    for h_type, grp in test_df_cov.groupby("disaster_type"):
        per_hazard_cov[h_type] = {
            "sample_count": int(len(grp)),
            "coverage_pct": round(float(grp["covered"].mean() * 100), 1)
        }

    # Coverage breakdown for single-state vs multi-state events
    test_scopes = []
    for _, r in test_df_cov.iterrows():
        loc_txt = str(r.get("Location", ""))
        _, sc = parse_provinces_and_scope(loc_txt)
        test_scopes.append(sc)
    test_df_cov["spatial_scope"] = test_scopes

    scope_cov = {}
    for sc_name, grp in test_df_cov.groupby("spatial_scope"):
        scope_cov[sc_name] = {
            "sample_count": int(len(grp)),
            "coverage_pct": round(float(grp["covered"].mean() * 100), 1)
        }

    # Bootstrap 95% Confidence Intervals (N=78 test set, B=1000)
    y_pred_ridge = calibrated_ridge_test
    n_test = len(y_test)
    rng_bs = np.random.default_rng(42)
    
    boot_covs = []
    boot_r2s = []
    boot_rhos = []
    for _ in range(1000):
        b_idx = rng_bs.choice(n_test, size=n_test, replace=True)
        boot_covs.append(float(np.mean(covered[b_idx]) * 100.0))
        boot_r2s.append(float(r2_score(y_test[b_idx], y_pred_ridge[b_idx])))
        r_b, _ = spearmanr(y_test[b_idx], y_pred_ridge[b_idx])
        boot_rhos.append(float(r_b) if not np.isnan(r_b) else 0.0)

    cov_ci = [round(float(np.percentile(boot_covs, 2.5)), 1), round(float(np.percentile(boot_covs, 97.5)), 1)]
    r2_ci = [round(float(np.percentile(boot_r2s, 2.5)), 4), round(float(np.percentile(boot_r2s, 97.5)), 4)]
    rho_ci = [round(float(np.percentile(boot_rhos, 2.5)), 4), round(float(np.percentile(boot_rhos, 97.5)), 4)]

    print(f"\n[OK] Conformalized Quantile Regression (CQR 90% Nominal) Empirical Test Coverage: {empirical_coverage_90:.1f}% (95% CI: {cov_ci}%)")
    print(f"[OK] CQR Median Interval Multiplicative Factor: x{med_mult_factor:.2f}")
    print(f"[OK] Ridge Test R2: {metrics['Ridge']['test_r2']:.4f} (95% CI: {r2_ci}) | Spearman rho: {metrics['Ridge']['test_spearman_rho']:.4f} (95% CI: {rho_ci})")

    # Keep XGBoost for Tree-SHAP explainability and compare candidate models at runtime.
    best_xgb = models["XGBoost"]
    best_xgb.fit(X_train, y_train)

    ensemble_model = models["Voting_Ensemble"]
    ensemble_model.fit(X_train, y_train)
    ridge_model = models["Ridge"]

    # Estimate uncertainty from the later, independent interval-calibration period.
    val_preds = calibration_slope * ridge_model.predict(X_interval_cal) + calibration_intercept
    val_residuals = y_interval_cal - val_preds
    val_std_log = float(np.std(val_residuals))
    impact_sigma_log = round(val_std_log if val_std_log > 0 else 3.40, 4)

    # SHAP Explainer (Tree-SHAP on XGBoost component for non-linear feature interactions)
    explainer = shap.TreeExplainer(best_xgb)
    shap_values = explainer(X_test)

    # Generate SHAP summary plot
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))
    feature_names = list(preprocessor.get_feature_names_out())
    shap.summary_plot(shap_values.values, X_test, feature_names=feature_names, show=False)
    shap_png = REPORTS_DIR / "shap_summary.png"
    plt.tight_layout()
    plt.savefig(shap_png, dpi=300)
    plt.close()

    # Historical Disaster Back-Test Replay (Leave-One-Event-Out by DisNo.)
    backtest_disno_list = [
        "2005-0409-IND", "2005-0541-IND", "2001-0033-IND", "1993-0074-IND", "2019-0331-IND"
    ]
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f)
            if cfg and "backtest_disno_list" in cfg:
                backtest_disno_list = cfg["backtest_disno_list"]

    backtest_records = []
    for target_disno in backtest_disno_list:
        target_match = df[df["DisNo."] == target_disno]
        if len(target_match) == 0:
            continue
        target_row = target_match.iloc[0]

        # Exclude target event for leave-one-event-out
        df_loo = df[df["DisNo."] != target_disno].copy().reset_index(drop=True)

        loo_train_mask = df_loo["start_year"] <= 2012
        loo_val_mask = (df_loo["start_year"] > 2012) & (df_loo["start_year"] <= 2018)

        loo_train = df_loo[loo_train_mask].copy()
        loo_val = df_loo[loo_val_mask].copy()

        if len(loo_train) < 100:
            loo_train = df_loo.iloc[:int(0.80 * len(df_loo))].copy()
            loo_val = df_loo.iloc[int(0.80 * len(df_loo)):].copy()

        loo_prep = ColumnTransformer([
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler())
            ]), FEATURE_COLS_NUM),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURE_COLS_CAT)
        ])

        X_tr_raw = loo_train[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
        y_tr = loo_train["target"].values
        X_va_raw = loo_val[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
        y_va = loo_val["target"].values

        X_tr = loo_prep.fit_transform(X_tr_raw)
        X_va = loo_prep.transform(X_va_raw)

        loo_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        loo_model.fit(X_tr, y_tr)

        loo_cqr = CQRRegressor(alpha=0.10, n_estimators=100, random_state=42)
        loo_cqr.fit(X_tr, y_tr, X_va, y_va)

        target_raw = pd.DataFrame([target_row[FEATURE_COLS_NUM + FEATURE_COLS_CAT]])
        X_tgt = loo_prep.transform(target_raw)

        pred_log = float(loo_model.predict(X_tgt)[0])
        low_log, high_log = loo_cqr.predict_interval(X_tgt)

        pred_median = int(max(0, np.expm1(pred_log)))
        p10_nominal90 = int(max(0, np.expm1(low_log[0])))
        p90_nominal90 = int(np.expm1(high_log[0]))
        actual_aff = int(target_row["total_affected"])

        loc_text = str(target_row.get("Location", "Unknown"))
        prov_cnt, scope_val = parse_provinces_and_scope(loc_text)
        ratio_val = round(float(pred_median / actual_aff), 4) if actual_aff > 0 else 0.0

        width_orders_of_mag = round(float((high_log[0] - low_log[0]) / np.log(10)), 4)
        in_train = bool(target_row["start_year"] <= 2012)

        backtest_records.append({
            "DisNo.": target_disno,
            "Location": loc_text,
            "provinces_count": prov_cnt,
            "scope": scope_val,
            "predicted_median": pred_median,
            "predicted_p10_nominal90": p10_nominal90,
            "predicted_p90_nominal90": p90_nominal90,
            "actual": actual_aff,
            "ratio": ratio_val,
            "interval_width_orders_of_magnitude": width_orders_of_mag,
            "in_training_period": in_train
        })

    bt_df = pd.DataFrame(backtest_records)
    bt_csv = REPORTS_DIR / "historical_backtest.csv"
    bt_df.to_csv(bt_csv, index=False)

    # Log-Log Plot
    if len(bt_df) > 0:
        plt.figure(figsize=(8, 6))
        actuals = bt_df["actual"].values
        medians = bt_df["predicted_median"].values
        p10s = bt_df["predicted_p10_nominal90"].values
        p90s = bt_df["predicted_p90_nominal90"].values

        yerr_lower = np.maximum(1.0, medians - p10s)
        yerr_upper = np.maximum(1.0, p90s - medians)

        plt.errorbar(actuals, medians, yerr=[yerr_lower, yerr_upper], fmt='o', color='navy', ecolor='gray', capsize=5, label='Disaster Events (90% CQR Interval)')
        for _, r in bt_df.iterrows():
            plt.annotate(r["DisNo."], (r["actual"], r["predicted_median"]), textcoords="offset points", xytext=(5, 5), fontsize=8)

        all_vals = np.concatenate([actuals, medians, p10s, p90s])
        min_v = max(1.0, all_vals.min() / 2)
        max_v = all_vals.max() * 2

        plt.plot([min_v, max_v], [min_v, max_v], 'r--', label='1:1 Perfect Prediction')
        plt.xscale('log')
        plt.yscale('log')
        plt.xlim(min_v, max_v)
        plt.ylim(min_v, max_v)
        plt.xlabel('Actual Total Affected (Log Scale)')
        plt.ylabel('Predicted Total Affected (Log Scale)')
        plt.title('Leave-One-Event-Out Historical Backtest (Log-Log Scale)')
        plt.grid(True, which='both', ls='--', alpha=0.5)
        plt.legend()
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "historical_backtest_loglog.png", dpi=300)
        plt.close()

    print(f"[OK] Leave-one-event-out historical back-test completed for {len(bt_df)} real disaster events.")

    # Save artifacts
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    bundle = {
        "preprocessor": preprocessor,
        "impact_model": ridge_model,
        "ridge_model": ridge_model,
        "point_calibrator": {
            "slope": calibration_slope,
            "intercept": calibration_intercept
        },
        "production_model_name": "Ridge Regression (alpha=1.0)",
        "comparison_models": {
            "ridge": ridge_model,
            "rf": models["Random_Forest"],
            "xgb": best_xgb,
        },
        "cqr_model": cqr,
        "feature_cols_num": FEATURE_COLS_NUM,
        "feature_cols_cat": FEATURE_COLS_CAT,
        "median_baseline": median_val,
        "cqr_margin": float(cqr.conformal_margin),
        "sigma_log": impact_sigma_log
    }
    joblib.dump(bundle, MODELS_DIR / "impact_models.joblib")
    joblib.dump(explainer, MODELS_DIR / "shap_explainer.joblib")

    # Metrics JSON
    metrics_summary = {
        "dataset": "EM-DAT India Historical Disasters (REAL)",
        "sample_size": len(df),
        "split_policy": "Time-based (Train <= 2012, Val 2013-2018, Test 2019+)",
        "production_model": "Ridge Regression (alpha=1.0) with validation-only affine calibration",
        "point_calibration": {
            "fit_period": "2013-2015",
            "interval_calibration_period": "2016-2018",
            "slope": round(calibration_slope, 6),
            "intercept": round(calibration_intercept, 6),
            "method": "Positive-slope linear calibration on validation predictions; separate later period retained for CQR calibration."
        },
        "impact_model_residual_sigma": impact_sigma_log,
        "models_benchmarked": metrics,
        "ridge_bootstrap_ci": {
            "r2_95_ci": r2_ci,
            "spearman_rho_95_ci": rho_ci
        },
        "conformal_quantile_regression": {
            "nominal_confidence": 0.90,
            "empirical_test_coverage_pct": round(empirical_coverage_90, 1),
            "coverage_95_ci_pct": cov_ci,
            "median_interval_multiplicative_factor": round(med_mult_factor, 2),
            "conformal_margin_log_units": round(float(cqr.conformal_margin), 4),
            "calibration_period": "2016-2018",
            "per_hazard_coverage": per_hazard_cov,
            "single_vs_multi_state_coverage": scope_cov,
            "calibration_disclaimer": (
                f"Empirical test coverage of {empirical_coverage_90:.1f}% vs a 90.0% nominal target "
                "describes this held-out sample only; it does not establish future calibration."
            )
        },
        "historical_backtest": backtest_records
    }
    
    with open(REPORTS_DIR / "metrics.json", "w") as f:
        json.dump(metrics_summary, f, indent=2)

    print(f"[OK] Impact model, CQR intervals, SHAP explainer, and metrics saved to {MODELS_DIR} and {REPORTS_DIR}.")
    return metrics_summary

def main(argv=None):
    parser = argparse.ArgumentParser(description="Train or evaluate the impact model.")
    parser.add_argument(
        "--rolling-origin-evaluation",
        action="store_true",
        help="Run the development-only chronological evaluation without writing artifacts.",
    )
    args = parser.parse_args(argv)
    if args.rolling_origin_evaluation:
        evaluate_rolling_origin_impact_models()
    else:
        train_and_evaluate_impact_models()


if __name__ == "__main__":
    main()
