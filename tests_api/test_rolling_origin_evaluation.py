import numpy as np
import pandas as pd
import pytest

import src.models.train_impact_model as impact_training


@pytest.fixture(scope="module")
def labeled_events():
    return impact_training.prepare_impact_data()


def test_rolling_origin_splits_match_approved_periods_and_are_disjoint(labeled_events):
    splits = impact_training.build_rolling_origin_splits(
        labeled_events,
        verify_expected_counts=True,
        print_event_ids=False,
    )
    assert len(splits) == 5

    all_evaluation_ids = []
    for fold in splits:
        spec = fold["spec"]
        frames = [fold[name] for name in impact_training.ROLLING_ORIGIN_SPLIT_NAMES]
        assert tuple(len(frame) for frame in frames) == spec["expected_counts"]
        assert all(not frame.empty for frame in frames)

        id_sets = [set(frame["DisNo."]) for frame in frames]
        assert all(
            id_sets[left].isdisjoint(id_sets[right])
            for left in range(len(id_sets))
            for right in range(left + 1, len(id_sets))
        )
        assert frames[0]["start_year"].max() < frames[1]["start_year"].min()
        assert frames[1]["start_year"].max() < frames[2]["start_year"].min()
        assert frames[2]["start_year"].max() < frames[3]["start_year"].min()
        assert frames[3]["start_year"].max() <= 2018
        all_evaluation_ids.extend(fold["evaluation"]["DisNo."])

    assert len(all_evaluation_ids) == 176
    assert len(set(all_evaluation_ids)) == len(all_evaluation_ids)


def test_rolling_origin_splits_are_deterministic_and_exclude_post_2018_rows(labeled_events):
    first = impact_training.build_rolling_origin_splits(
        labeled_events,
        verify_expected_counts=True,
        print_event_ids=False,
    )
    second = impact_training.build_rolling_origin_splits(
        labeled_events,
        verify_expected_counts=True,
        print_event_ids=False,
    )
    assert [
        tuple(fold[name]["DisNo."].tolist() for name in impact_training.ROLLING_ORIGIN_SPLIT_NAMES)
        for fold in first
    ] == [
        tuple(fold[name]["DisNo."].tolist() for name in impact_training.ROLLING_ORIGIN_SPLIT_NAMES)
        for fold in second
    ]

    post_2018 = labeled_events.iloc[[0]].copy()
    post_2018.loc[:, "DisNo."] = "2099-0001-IND"
    post_2018.loc[:, "start_year"] = 2019
    with_post_2018 = pd.concat([labeled_events, post_2018], ignore_index=True)
    splits = impact_training.build_rolling_origin_splits(
        with_post_2018,
        print_event_ids=False,
    )
    assert all(
        (frame["start_year"] < 2019).all()
        for fold in splits
        for name in impact_training.ROLLING_ORIGIN_SPLIT_NAMES
        for frame in [fold[name]]
    )
    assert all(
        "2099-0001-IND" not in set(fold[name]["DisNo."])
        for fold in splits
        for name in impact_training.ROLLING_ORIGIN_SPLIT_NAMES
    )


def test_rolling_origin_preflight_rejects_changed_counts_before_fitting(labeled_events):
    changed = labeled_events.drop(index=labeled_events.index[0]).reset_index(drop=True)
    with pytest.raises(ValueError, match="differ from approved counts"):
        impact_training.build_rolling_origin_splits(changed, print_event_ids=False)


def test_fold_fits_preprocessor_and_models_only_on_training_rows(
    labeled_events, monkeypatch
):
    fold = impact_training.build_rolling_origin_splits(
        labeled_events,
        print_event_ids=False,
    )[0]
    fitted_indices = []
    transformed_indices = []
    estimator_fit_sizes = []
    point_calibration_fit_sizes = []
    cqr_fit_sizes = []

    class PreprocessorSpy:
        def fit_transform(self, frame):
            fitted_indices.append(set(frame.index))
            return np.arange(len(frame), dtype=float).reshape(-1, 1)

        def transform(self, frame):
            transformed_indices.append(set(frame.index))
            return np.arange(len(frame), dtype=float).reshape(-1, 1)

    class EstimatorSpy:
        def fit(self, features, target):
            estimator_fit_sizes.append((len(features), len(target)))
            self.value = float(np.mean(target))
            return self

        def predict(self, features):
            return np.full(len(features), self.value)

    class CalibratorSpy:
        def fit(self, features, target):
            point_calibration_fit_sizes.append((len(features), len(target)))
            self.coef_ = np.array([1.0])
            self.intercept_ = 0.0
            return self

    class CQRSpy:
        def __init__(self, alpha, n_estimators, random_state):
            self.init_args = (alpha, n_estimators, random_state)

        def fit(self, x_train, y_train, x_calib, y_calib):
            cqr_fit_sizes.append((len(x_train), len(y_train), len(x_calib), len(y_calib)))

        def predict_interval(self, features):
            return np.full(len(features), -1.0), np.full(len(features), 30.0)

    monkeypatch.setattr(impact_training, "LinearRegression", CalibratorSpy)
    point_rows, interval_rows, _, id_sets = impact_training._run_rolling_origin_fold(
        fold,
        estimator_factory=lambda: {
            "Ridge": EstimatorSpy(),
            "Random_Forest": EstimatorSpy(),
            "XGBoost": EstimatorSpy(),
        },
        preprocessor_factory=PreprocessorSpy,
        cqr_factory=CQRSpy,
    )

    expected_fit_indices = set(fold["fit"].index)
    assert fitted_indices == [expected_fit_indices]
    assert transformed_indices == [
        set(fold["point_calibration"].index),
        set(fold["interval_calibration"].index),
        set(fold["evaluation"].index),
    ]
    assert estimator_fit_sizes == [(205, 205)] * 3
    assert point_calibration_fit_sizes == [(29, 29)] * 3
    assert cqr_fit_sizes == [(205, 205, 24, 24)]
    assert id_sets["fit_ids"].isdisjoint(id_sets["point_calibration_ids"])
    assert id_sets["fit_ids"].isdisjoint(id_sets["interval_calibration_ids"])
    assert id_sets["fit_ids"].isdisjoint(id_sets["evaluation_ids"])
    assert len(interval_rows) == 47
    assert {row["prediction_variant"] for row in point_rows} == {
        "raw",
        "affine_calibrated",
    }


def test_estimator_random_seeds_and_parameters_are_fixed():
    first = impact_training._build_rolling_origin_estimators(seed=42)
    second = impact_training._build_rolling_origin_estimators(seed=42)
    assert first["Ridge"].get_params()["alpha"] == 1.0
    assert first["Random_Forest"].get_params()["n_estimators"] == 100
    assert first["Random_Forest"].get_params()["random_state"] == 42
    assert first["XGBoost"].get_params()["random_state"] == 42
    assert first["XGBoost"].get_params()["n_jobs"] == 1
    for name in first:
        assert first[name].get_params() == second[name].get_params()


def test_invalid_point_predictions_are_counted_not_silently_dropped():
    rows = pd.DataFrame({
        "target": [1.0, 2.0],
        "prediction_log": [1.1, np.nan],
        "total_affected": [1.7, 6.4],
    })
    summary = impact_training._summarize_point_predictions(rows)
    assert summary["n"] == 2
    assert summary["invalid_prediction_count"] == 1
    assert summary["log_mae"] is None


def test_crossed_intervals_are_counted_and_not_used_as_valid_widths():
    rows = pd.DataFrame({
        "target": [1.0, 2.0],
        "lower_log": [0.0, 3.0],
        "upper_log": [2.0, 2.0],
    })
    summary = impact_training._summarize_intervals(rows)
    assert summary["n"] == 2
    assert summary["valid_interval_count"] == 1
    assert summary["invalid_or_crossed_interval_count"] == 1
    assert summary["coverage_pct_all_events"] == 50.0
