"""
Conformalized Quantile Regression (CQR) module.
Defines CQRRegressor for calibrated prediction interval estimation.
"""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

class CQRRegressor:
    """Conformalized Quantile Regression (CQR) for calibrated prediction intervals."""

    def __init__(self, alpha=0.10, n_estimators=100, random_state=42):
        self.alpha = alpha
        self.lower_quantile = alpha / 2.0
        self.upper_quantile = 1.0 - (alpha / 2.0)
        self.q_low_model = GradientBoostingRegressor(
            loss="quantile", alpha=self.lower_quantile, n_estimators=n_estimators, random_state=random_state
        )
        self.q_high_model = GradientBoostingRegressor(
            loss="quantile", alpha=self.upper_quantile, n_estimators=n_estimators, random_state=random_state
        )
        self.conformal_scores = None
        self.conformal_margin = 0.0

    def fit(self, X_train, y_train, X_calib, y_calib):
        self.q_low_model.fit(X_train, y_train)
        self.q_high_model.fit(X_train, y_train)

        q_low_calib = self.q_low_model.predict(X_calib)
        q_high_calib = self.q_high_model.predict(X_calib)

        scores = np.maximum(q_low_calib - y_calib, y_calib - q_high_calib)
        self.conformal_scores = np.sort(scores)
        
        n = len(y_calib)
        q_level = np.ceil((1 - self.alpha) * (n + 1)) / n
        q_level = min(1.0, max(0.0, q_level))
        self.conformal_margin = float(np.quantile(self.conformal_scores, q_level))

    def predict_interval(self, X):
        q_low = self.q_low_model.predict(X)
        q_high = self.q_high_model.predict(X)
        
        lower_bound = q_low - self.conformal_margin
        upper_bound = q_high + self.conformal_margin
        return lower_bound, upper_bound
