"""
Visualizations for India Heat-Wave Prediction Model:
Generates:
1. Actual vs Predicted Temperature Scatter / Time-series
2. Prediction Error by Horizon (1d, 3d, 5d, 7d)
3. Model Comparison Table (Baselines vs Ridge vs RF vs XGBoost)
4. Heat-Wave ROC-AUC and PR-AUC curves
5. Heat-Wave Confusion Matrix and False Negative Breakdown
6. Historical Heat-Wave Events vs Predicted Probabilities
"""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def generate_all_plots(
    results_json_path: str = "data/results/backtest_summary_2024.json",
    predictions_csv_path: str = "data/results/backtest_predictions_test_2024.csv",
    output_dir: str = "data/results/plots",
):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(results_json_path, "r", encoding="utf-8") as f:
        res = json.load(f)

    preds_df = pd.read_csv(predictions_csv_path)

    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"

    # 1. Horizon Degradation Plot (MAE vs Horizon)
    horizons = ["1d", "3d", "5d", "7d"]
    persist_maes = [res["baselines"][h]["Persistence"]["MAE"] for h in horizons]
    normal_maes = [res["baselines"][h]["Climatological_Normal"]["MAE"] for h in horizons]
    yoy_maes = [res["baselines"][h]["Same_Date_Last_Year"]["MAE"] for h in horizons]
    xgb_maes = [res["regression_results"][h]["XGBoost"]["MAE"] for h in horizons]
    rf_maes = [res["regression_results"][h]["Random_Forest"]["MAE"] for h in horizons]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(horizons, persist_maes, "o--", label="Baseline: Persistence (T_today)", color="#64748b")
    ax.plot(horizons, normal_maes, "^--", label="Baseline: Climatological Normal", color="#d97706")
    ax.plot(horizons, yoy_maes, "s--", label="Baseline: Same Date Last Year", color="#8b5cf6")
    ax.plot(horizons, rf_maes, "D-", label="ML: Random Forest", color="#059669")
    ax.plot(horizons, xgb_maes, "*-", label="ML: XGBoost", color="#2563eb", linewidth=2.5, markersize=8)

    ax.set_title("Forecast Accuracy Degradation Across Horizons (Test Year 2024)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Prediction Horizon", fontsize=11)
    ax.set_ylabel("Mean Absolute Error (°C)", fontsize=11)
    ax.legend(loc="upper left")
    plt.tight_layout()
    fig.savefig(out_path / "mae_horizon_degradation.png", dpi=150)
    plt.close()

    # 2. Actual vs Predicted Tmax Scatter Plot (1-Day Horizon)
    sub1d = preds_df[preds_df["horizon_days"] == 1]
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.scatterplot(
        data=sub1d,
        x="actual_tmax",
        y="predicted_tmax",
        hue="actual_heatwave",
        palette={0: "#3b82f6", 1: "#ef4444"},
        alpha=0.6,
        ax=ax,
    )
    # 1:1 reference line
    min_val = min(sub1d["actual_tmax"].min(), sub1d["predicted_tmax"].min())
    max_val = max(sub1d["actual_tmax"].max(), sub1d["predicted_tmax"].max())
    ax.plot([min_val, max_val], [min_val, max_val], "k--", alpha=0.5, label="1:1 Perfect Prediction")
    ax.set_title("Actual vs Predicted Tmax (1-Day Horizon, Test 2024)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Actual Tmax (°C)")
    ax.set_ylabel("Predicted Tmax (°C)")
    ax.legend(title="IMD Heat Wave", labels=["No Heat Wave (0)", "Heat Wave (1)"])
    plt.tight_layout()
    fig.savefig(out_path / "actual_vs_predicted_tmax_1d.png", dpi=150)
    plt.close()

    # 3. New Delhi Extreme Heat Wave Period (May-June 2024) Time Series
    delhi_df = sub1d[sub1d["location"] == "New Delhi"].copy()
    delhi_df["date"] = pd.to_datetime(delhi_df["date"])
    summer_delhi = delhi_df[(delhi_df["date"].dt.month.isin([4, 5, 6]))].sort_values("date")

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(summer_delhi["date"], summer_delhi["actual_tmax"], "r-", label="Actual Tmax (°C)", linewidth=2)
    ax1.plot(summer_delhi["date"], summer_delhi["predicted_tmax"], "b--", label="Predicted Tmax (°C)", linewidth=1.8)
    ax1.plot(summer_delhi["date"], summer_delhi["normal_tmax"], "k:", label="Normal Climatology", alpha=0.6)
    ax1.axhline(40.0, color="orange", linestyle="--", alpha=0.5, label="IMD Plains Threshold (40°C)")
    ax1.axhline(45.0, color="red", linestyle="--", alpha=0.5, label="IMD Extreme Override (45°C)")
    ax1.set_ylabel("Maximum Temperature (°C)", color="#1e293b", fontsize=11)
    ax1.set_title("New Delhi Summer 2024: Actual vs Predicted Tmax & Heat-Wave Probabilities", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.fill_between(
        summer_delhi["date"], 0, summer_delhi["predicted_heatwave_prob"],
        color="#dc2626", alpha=0.2, label="Heat-Wave Probability"
    )
    ax2.set_ylabel("Heat-Wave Probability (0-1)", color="#dc2626", fontsize=11)
    ax2.set_ylim(0, 1.05)
    plt.tight_layout()
    fig.savefig(out_path / "delhi_summer_2024_timeseries.png", dpi=150)
    plt.close()

    # 4. Confusion Matrix Plot
    from sklearn.metrics import confusion_matrix
    y_true = sub1d["actual_heatwave"]
    y_pred = sub1d["predicted_heatwave_class"]
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["Predicted No HW", "Predicted HW"],
                yticklabels=["Actual No HW", "Actual HW"], ax=ax)
    ax.set_title("Heat-Wave Detection Confusion Matrix (1-Day Horizon)", fontsize=12, fontweight="bold")
    plt.tight_layout()
    fig.savefig(out_path / "confusion_matrix_1d.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    generate_all_plots()
