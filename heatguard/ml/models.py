"""
Model Suite for India Heat-Wave Prediction:
1. Baseline Models (Persistence, YoY, Seasonal Normal)
2. Ridge / Linear Regression
3. Random Forest (Regressor & Classifier)
4. XGBoost (Regressor & Classifier with class imbalance scaling)
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb


class HeatWaveModelSuite:
    """Encapsulates regression and classification models for heat-wave prediction."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

        # Regression Models (predict future Tmax)
        self.regressors = {
            "Linear_Ridge": Pipeline([
                ("scaler", StandardScaler()),
                ("model", Ridge(alpha=10.0, random_state=random_state))
            ]),
            "Random_Forest": RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_leaf=4,
                n_jobs=-1,
                random_state=random_state,
            ),
            "XGBoost": xgb.XGBRegressor(
                n_estimators=120,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=random_state,
                n_jobs=-1,
            ),
        }

        # Classification Models (predict Heat-Wave Probability)
        self.classifiers = {
            "Logistic_Regression": Pipeline([
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(class_weight="balanced", random_state=random_state, max_iter=1000))
            ]),
            "Random_Forest": RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_leaf=4,
                class_weight="balanced",
                n_jobs=-1,
                random_state=random_state,
            ),
            "XGBoost": xgb.XGBClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.05,
                scale_pos_weight=10.0,  # accounts for heatwave sparsity (~2-5% of days)
                subsample=0.8,
                colsample_bytree=0.8,
                eval_metric="logloss",
                random_state=random_state,
                n_jobs=-1,
            ),
        }
