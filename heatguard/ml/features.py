"""
Year-Over-Year (YoY) and Multi-Horizon Feature Engineering Pipeline.
Strictly eliminates data leakage by ensuring every feature for date T
only utilizes information strictly available prior to T (or for forecasting horizon H, <= T).

Features Created:
1. Multi-Day Moving Averages: rolling 3d, 7d, 14d, 30d means
2. Multi-Day Extremes: rolling 3d, 7d, 14d maximum temperatures
3. Cumulative Heat: consecutive days above 40°C
4. Hydrological / Moisture Lags: rolling 7d, 14d, 30d cumulative rainfall
5. Humidity / Pressure Trends: 3d and 7d deltas
6. Year-Over-Year Signals:
   - Same date previous year (T - 365)
   - Same week previous year (7-day window around T - 365)
   - Previous 2-year and 3-year temperatures for the same calendar date
   - Temperature anomaly relative to historical baseline
7. Calendar Seasonality: Day of year sine and cosine cyclical encodings
"""

from typing import List, Optional
import numpy as np
import pandas as pd


def build_yoy_and_lag_features(
    df: pd.DataFrame,
    date_col: str = "date",
    location_col: str = "location",
    horizons: List[int] = [1, 3, 5, 7],
) -> pd.DataFrame:
    """
    Construct causal feature set for a single continuous location time series.
    """
    feat = df.copy()
    feat[date_col] = pd.to_datetime(feat[date_col])
    feat = feat.sort_values(date_col).reset_index(drop=True)

    # 1. Cyclical Seasonality
    doy = feat[date_col].dt.dayofyear
    feat["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    feat["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    feat["month"] = feat[date_col].dt.month

    # 2. Rolling Lags (strictly backward-looking, shifted by 1 to prevent lookahead at t)
    # lag1 = yesterday's value
    feat["tmax_lag1"] = feat["tmax"].shift(1)
    feat["tmin_lag1"] = feat["tmin"].shift(1)
    feat["humidity_lag1"] = feat["humidity"].shift(1)
    feat["pressure_lag1"] = feat["pressure"].shift(1)
    feat["solar_lag1"] = feat["solar_radiation"].shift(1)

    # Rolling averages over past 3, 7, 14, 30 days (shift 1 so today's tmax is excluded)
    feat["tmax_roll_mean_3d"] = feat["tmax"].shift(1).rolling(3, min_periods=1).mean()
    feat["tmax_roll_mean_7d"] = feat["tmax"].shift(1).rolling(7, min_periods=1).mean()
    feat["tmax_roll_mean_14d"] = feat["tmax"].shift(1).rolling(14, min_periods=1).mean()
    feat["tmax_roll_mean_30d"] = feat["tmax"].shift(1).rolling(30, min_periods=1).mean()

    # Rolling max over past 3, 7, 14 days
    feat["tmax_roll_max_3d"] = feat["tmax"].shift(1).rolling(3, min_periods=1).max()
    feat["tmax_roll_max_7d"] = feat["tmax"].shift(1).rolling(7, min_periods=1).max()
    feat["tmax_roll_max_14d"] = feat["tmax"].shift(1).rolling(14, min_periods=1).max()

    # Temperature trends (momentum)
    feat["tmax_trend_3d"] = feat["tmax_lag1"] - feat["tmax"].shift(4)
    feat["tmax_trend_7d"] = feat["tmax_lag1"] - feat["tmax"].shift(8)

    # Cumulative rainfall in prior 7, 14, 30 days
    feat["rainfall_roll_sum_7d"] = feat["rainfall"].shift(1).rolling(7, min_periods=1).sum()
    feat["rainfall_roll_sum_14d"] = feat["rainfall"].shift(1).rolling(14, min_periods=1).sum()
    feat["rainfall_roll_sum_30d"] = feat["rainfall"].shift(1).rolling(30, min_periods=1).sum()

    # Consecutive hot days (tmax >= 40.0 in previous days)
    hot_flag = (feat["tmax"].shift(1) >= 40.0).astype(int)
    consec = []
    curr = 0
    for val in hot_flag:
        if val == 1:
            curr += 1
        else:
            curr = 0
        consec.append(curr)
    feat["consecutive_hot_days"] = consec

    # 3. Year-Over-Year (YoY) Patterns
    # Map by (month, day) for past years
    feat_indexed = feat.set_index(date_col)

    yoy_1y = []
    yoy_1y_week = []
    yoy_2y = []
    yoy_3y = []

    for curr_date in feat[date_col]:
        # Date 1 year prior
        d_1y = curr_date - pd.DateOffset(years=1)
        d_2y = curr_date - pd.DateOffset(years=2)
        d_3y = curr_date - pd.DateOffset(years=3)

        # Same date 1y prior
        v_1y = feat_indexed.loc[d_1y]["tmax"] if d_1y in feat_indexed.index else np.nan
        # Same week 1y prior (+/- 3 days window around d_1y)
        w_start = d_1y - pd.Timedelta(days=3)
        w_end = d_1y + pd.Timedelta(days=3)
        w_sub = feat_indexed.loc[(feat_indexed.index >= w_start) & (feat_indexed.index <= w_end)]
        v_1y_week = w_sub["tmax"].mean() if len(w_sub) > 0 else np.nan

        v_2y = feat_indexed.loc[d_2y]["tmax"] if d_2y in feat_indexed.index else np.nan
        v_3y = feat_indexed.loc[d_3y]["tmax"] if d_3y in feat_indexed.index else np.nan

        yoy_1y.append(v_1y)
        yoy_1y_week.append(v_1y_week)
        yoy_2y.append(v_2y)
        yoy_3y.append(v_3y)

    feat["tmax_yoy_1y"] = yoy_1y
    feat["tmax_yoy_1y_week_mean"] = yoy_1y_week
    feat["tmax_yoy_2y"] = yoy_2y
    feat["tmax_yoy_3y"] = yoy_3y

    # Multi-year historical average for same calendar date
    # Fallback to smoothed normal if multi-year previous isn't yet available
    feat["hist_3y_mean"] = feat[["tmax_yoy_1y", "tmax_yoy_2y", "tmax_yoy_3y"]].mean(axis=1)
    if "smoothed_normal" in feat.columns:
        feat["hist_3y_mean"] = feat["hist_3y_mean"].fillna(feat["smoothed_normal"])
        feat["temp_anomaly_hist"] = feat["tmax_lag1"] - feat["smoothed_normal"]

    # 4. Multi-Horizon Future Targets (for training and backtesting)
    # Target Tmax at t + H days
    for h in horizons:
        feat[f"target_tmax_{h}d"] = feat["tmax"].shift(-h)
        if "is_heatwave" in feat.columns:
            feat[f"target_heatwave_{h}d"] = feat["is_heatwave"].shift(-h)
        if "heatwave_label" in feat.columns:
            feat[f"target_hw_label_{h}d"] = feat["heatwave_label"].shift(-h)

    # Convert date back to string
    feat[date_col] = feat[date_col].dt.strftime("%Y-%m-%d")
    return feat
