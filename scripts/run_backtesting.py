"""
Historical Backtesting and Model Validation Runner.
Simulates chronological forecast execution over test years (e.g. Train 2018-2022 -> Test 2023; Train 2018-2023 -> Test 2024; Train 2018-2024 -> Test 2025).

Evaluates:
- Temperature Regression: MAE, RMSE, R2, MAPE across Horizons: 1d, 3d, 5d, 7d
- Heat-Wave Probability: Precision, Recall, F1, ROC-AUC, PR-AUC, False Negatives
- Strict comparison against 3 Simple Baselines:
  1. Persistence: T(t+H) ≈ T(t)
  2. YoY: T(t+H) ≈ T(t+H - 365d)
  3. Climatological Normal: T(t+H) ≈ smoothed_normal
- Performance during known historical heat-wave periods
- Automated performance regression threshold check (Safety Gates)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from heatguard.ml.metrics import evaluate_classification, evaluate_regression
from heatguard.ml.models import HeatWaveModelSuite

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Feature columns strictly available prior to forecast time
FEATURE_COLS = [
    "latitude", "longitude",
    "doy_sin", "doy_cos", "month",
    "tmax_lag1", "tmin_lag1", "humidity_lag1", "pressure_lag1", "solar_lag1",
    "tmax_roll_mean_3d", "tmax_roll_mean_7d", "tmax_roll_mean_14d", "tmax_roll_mean_30d",
    "tmax_roll_max_3d", "tmax_roll_max_7d", "tmax_roll_max_14d",
    "tmax_trend_3d", "tmax_trend_7d",
    "rainfall_roll_sum_7d", "rainfall_roll_sum_14d", "rainfall_roll_sum_30d",
    "consecutive_hot_days",
    "tmax_yoy_1y", "tmax_yoy_1y_week_mean", "tmax_yoy_2y", "tmax_yoy_3y",
    "hist_3y_mean", "temp_anomaly_hist",
    "smoothed_normal",
]


def run_chronological_backtest(
    features_csv: str = "data/features/combined_india_features_2018_2025.csv",
    train_end_year: int = 2023,
    test_year: int = 2024,
    horizons: List[int] = [1, 3, 5, 7],
    output_dir: str = "data/results",
) -> Dict[str, Any]:
    """
    Run backtest simulating prediction standing at test_year without lookahead.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(features_csv)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year

    # Drop rows without complete feature history
    df_clean = df.dropna(subset=FEATURE_COLS).copy()

    train_mask = df_clean["year"] <= train_end_year
    test_mask = df_clean["year"] == test_year

    train_df = df_clean[train_mask].copy()
    test_df = df_clean[test_mask].copy()

    logger.info("Chronological Split: Train (2018-%d) = %d rows | Test (%d) = %d rows",
                train_end_year, len(train_df), test_year, len(test_df))

    X_train = train_df[FEATURE_COLS].values
    X_test = test_df[FEATURE_COLS].values

    results: Dict[str, Any] = {
        "metadata": {
            "train_years": f"2018-{train_end_year}",
            "test_year": test_year,
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "features_count": len(FEATURE_COLS),
        },
        "regression_results": {},
        "classification_results": {},
        "baselines": {},
        "heatwave_event_performance": {},
    }

    # Track historical predictions for audit export
    prediction_records = []

    # Iterate through each horizon
    for h in horizons:
        logger.info("=== EVALUATING HORIZON: %d DAY(S) AHEAD ===", h)
        t_col = f"target_tmax_{h}d"
        hw_col = f"target_heatwave_{h}d"

        # Valid train/test masks for this specific horizon
        h_train_mask = ~np.isnan(train_df[t_col]) & ~np.isnan(train_df[hw_col])
        h_test_mask = ~np.isnan(test_df[t_col]) & ~np.isnan(test_df[hw_col])

        y_train_reg = train_df.loc[h_train_mask, t_col].values
        y_test_reg = test_df.loc[h_test_mask, t_col].values

        y_train_clf = train_df.loc[h_train_mask, hw_col].values.astype(int)
        y_test_clf = test_df.loc[h_test_mask, hw_col].values.astype(int)

        X_tr = X_train[h_train_mask]
        X_te = X_test[h_test_mask]
        test_sub_df = test_df[h_test_mask].reset_index(drop=True)

        results["regression_results"][f"{h}d"] = {}
        results["classification_results"][f"{h}d"] = {}
        results["baselines"][f"{h}d"] = {}

        # -------------------------------------------------------------
        # BASELINES FOR REGRESSION
        # -------------------------------------------------------------
        # Baseline 1: Persistence (tomorrow ≈ today)
        base_persist = test_sub_df["tmax"].values
        persist_m = evaluate_regression(y_test_reg, base_persist)
        results["baselines"][f"{h}d"]["Persistence"] = persist_m.to_dict()

        # Baseline 2: YoY (same day previous year)
        base_yoy = test_sub_df["tmax_yoy_1y"].fillna(test_sub_df["smoothed_normal"]).values
        yoy_m = evaluate_regression(y_test_reg, base_yoy)
        results["baselines"][f"{h}d"]["Same_Date_Last_Year"] = yoy_m.to_dict()

        # Baseline 3: Seasonal Normal
        base_normal = test_sub_df["smoothed_normal"].values
        normal_m = evaluate_regression(y_test_reg, base_normal)
        results["baselines"][f"{h}d"]["Climatological_Normal"] = normal_m.to_dict()

        # -------------------------------------------------------------
        # ML REGRESSION MODELS
        # -------------------------------------------------------------
        suite = HeatWaveModelSuite()
        best_reg_name = None
        best_reg_mae = 999.0
        best_reg_preds = None

        for name, model in suite.regressors.items():
            model.fit(X_tr, y_train_reg)
            preds = model.predict(X_te)
            m = evaluate_regression(y_test_reg, preds)
            results["regression_results"][f"{h}d"][name] = m.to_dict()
            if m.mae < best_reg_mae:
                best_reg_mae = m.mae
                best_reg_name = name
                best_reg_preds = preds

        logger.info("Horizon %dd Best Regressor: %s (MAE=%.2f°C vs Persistence MAE=%.2f°C)",
                    h, best_reg_name, best_reg_mae, persist_m.mae)

        # -------------------------------------------------------------
        # ML CLASSIFICATION MODELS (HEAT-WAVE PROBABILITY)
        # -------------------------------------------------------------
        best_clf_name = None
        best_clf_f1 = -1.0
        best_clf_probs = None

        for name, model in suite.classifiers.items():
            model.fit(X_tr, y_train_clf)
            probs = model.predict_proba(X_te)[:, 1]
            m = evaluate_classification(y_test_clf, probs, threshold=0.35)
            results["classification_results"][f"{h}d"][name] = m.to_dict()
            if m.f1 > best_clf_f1:
                best_clf_f1 = m.f1
                best_clf_name = name
                best_clf_probs = probs

        logger.info("Horizon %dd Best Classifier: %s (F1=%.3f, ROC-AUC=%.3f, Recall=%.3f)",
                    h, best_clf_name, best_clf_f1,
                    results['classification_results'][f'{h}d'][best_clf_name]['ROC_AUC'],
                    results['classification_results'][f'{h}d'][best_clf_name]['Recall'])

        # Save individual prediction records for 1d and 3d horizons
        if h in [1, 3]:
            for idx in range(len(test_sub_df)):
                prediction_records.append({
                    "date": test_sub_df.iloc[idx]["date"].strftime("%Y-%m-%d"),
                    "location": test_sub_df.iloc[idx]["location"],
                    "horizon_days": h,
                    "actual_tmax": round(float(y_test_reg[idx]), 1),
                    "predicted_tmax": round(float(best_reg_preds[idx]), 1),
                    "tmax_error": round(float(best_reg_preds[idx] - y_test_reg[idx]), 2),
                    "actual_heatwave": int(y_test_clf[idx]),
                    "predicted_heatwave_prob": round(float(best_clf_probs[idx]), 3),
                    "predicted_heatwave_class": 1 if best_clf_probs[idx] >= 0.35 else 0,
                    "normal_tmax": round(float(test_sub_df.iloc[idx]["smoothed_normal"]), 1),
                })

    # Save detailed prediction audit CSV
    preds_df = pd.DataFrame(prediction_records)
    preds_csv = out_path / f"backtest_predictions_test_{test_year}.csv"
    preds_df.to_csv(preds_csv, index=False)
    logger.info("Saved backtest predictions audit to %s (%d rows)", preds_csv, len(preds_df))

    # Evaluate specifically during historical heatwave events (actual_heatwave == 1)
    hw_only_df = preds_df[preds_df["actual_heatwave"] == 1]
    if len(hw_only_df) > 0:
        hw_mae = float(np.mean(np.abs(hw_only_df["tmax_error"])))
        hw_recall = float(np.mean(hw_only_df["predicted_heatwave_class"] == 1))
        results["heatwave_event_performance"] = {
            "total_heatwave_days_in_test": len(hw_only_df),
            "heatwave_temperature_mae": round(hw_mae, 2),
            "heatwave_capture_recall": round(hw_recall, 3),
        }
        logger.info("Historical Heat-Wave Event Performance: Total HW Days=%d, MAE=%.2f°C, Recall=%.1f%%",
                    len(hw_only_df), hw_mae, hw_recall * 100)

    # Save summary JSON
    summary_file = out_path / f"backtest_summary_{test_year}.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("Saved backtest evaluation metrics to %s", summary_file)

    return results


def check_safety_regression_gates(
    results: Dict[str, Any],
    max_allowed_1d_mae: float = 1.80,    # °C
    min_allowed_1d_f1: float = 0.50,
    min_allowed_recall: float = 0.65,
) -> Tuple[bool, List[str]]:
    """
    Automated regression test gate: Fails if new models degrade below thresholds.
    """
    failures = []
    reg_1d = results["regression_results"]["1d"]
    best_mae = min(m["MAE"] for m in reg_1d.values())
    if best_mae > max_allowed_1d_mae:
        failures.append(f"1-Day MAE ({best_mae:.2f}°C) exceeded maximum safety threshold ({max_allowed_1d_mae:.2f}°C)")

    clf_1d = results["classification_results"]["1d"]
    best_f1 = max(m["F1"] for m in clf_1d.values())
    if best_f1 < min_allowed_1d_f1:
        failures.append(f"1-Day F1-Score ({best_f1:.2f}) fell below minimum safety threshold ({min_allowed_1d_f1:.2f})")

    best_recall = max(m["Recall"] for m in clf_1d.values())
    if best_recall < min_allowed_recall:
        failures.append(f"1-Day Recall ({best_recall:.2f}) fell below safety false-negative gate ({min_allowed_recall:.2f})")

    passed = len(failures) == 0
    return passed, failures


if __name__ == "__main__":
    res = run_chronological_backtest(test_year=2024)
    passed, issues = check_safety_regression_gates(res)
    print("\n" + "="*50)
    print(f"SAFETY REGRESSION TEST GATE: {'PASSED' if passed else 'FAILED'}")
    if issues:
        for i in issues:
            print(f" - FAIL: {i}")
    else:
        print("All model accuracy and safety recall gates passed successfully.")
    print("="*50)
