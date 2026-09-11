"""
Official India Meteorological Department (IMD) Heat-Wave Label Generator.
Implements authoritative rules strictly without fabricated labels:

1. Terrain Thresholds:
   - Plains: Tmax >= 40.0°C
   - Coastal: Tmax >= 37.0°C
   - Hills: Tmax >= 30.0°C

2. Departure from Normal Climatology:
   - Normal <= 40°C:
     - Heat Wave: Departure +4.5°C to +6.4°C
     - Severe Heat Wave: Departure >= +6.5°C
   - Normal > 40°C:
     - Heat Wave: Departure +4.0°C to +5.9°C
     - Severe Heat Wave: Departure >= +6.0°C

3. Absolute Threshold Override (Plains):
   - Tmax >= 45.0°C -> Heat Wave
   - Tmax >= 47.0°C -> Severe Heat Wave

Labels Produced:
  0 = No Heat Wave
  1 = Heat Wave
  2 = Severe Heat Wave
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


def compute_climatological_normals(
    df: pd.DataFrame,
    date_col: str = "date",
    tmax_col: str = "tmax",
    window_days: int = 15,
) -> pd.DataFrame:
    """
    Compute daily climatological normal maximum temperature for each day-of-year (1..366)
    using a rolling window over available multi-year records.
    """
    work = df.copy()
    work["dt"] = pd.to_datetime(work[date_col])
    work["doy"] = work["dt"].dt.dayofyear

    # Mean Tmax for each day of year across all years
    doy_means = work.groupby("doy")[tmax_col].mean().reset_index()
    doy_means.rename(columns={tmax_col: "normal_tmax"}, inplace=True)

    # Smooth normals with rolling circular window
    # Duplicate boundary to wrap December into January smoothly
    wrapped = pd.concat([doy_means, doy_means, doy_means], ignore_index=True)
    wrapped["smoothed_normal"] = wrapped["normal_tmax"].rolling(window=window_days, center=True, min_periods=1).mean()

    n = len(doy_means)
    smoothed = wrapped.iloc[n:2*n][["doy", "smoothed_normal"]].reset_index(drop=True)

    work = work.merge(smoothed, on="doy", how="left")
    work.drop(columns=["dt", "doy"], inplace=True)
    return work


def apply_imd_heatwave_labels(
    df: pd.DataFrame,
    tmax_col: str = "tmax",
    normal_col: str = "smoothed_normal",
    terrain_col: str = "terrain_type",
) -> pd.DataFrame:
    """
    Apply strict IMD criteria to produce authoritative heat-wave targets.
    Adds:
      - 'normal_tmax': climatological normal for that day of year
      - 'departure_from_normal': Tmax - normal_tmax
      - 'heatwave_label': 0 (No), 1 (Heat Wave), 2 (Severe Heat Wave)
      - 'is_heatwave': binary 0 or 1 (1 = Heat Wave or Severe)
      - 'heatwave_category': Human-readable string
    """
    out = df.copy()

    if normal_col not in out.columns:
        out = compute_climatological_normals(out, tmax_col=tmax_col)

    out["departure_from_normal"] = out[tmax_col] - out[normal_col]

    labels = []
    categories = []

    for _, row in out.iterrows():
        tmax = float(row[tmax_col])
        normal = float(row[normal_col])
        departure = float(row["departure_from_normal"])
        terrain = str(row.get(terrain_col, "plains")).lower()

        # Step 1: Minimum threshold requirement based on terrain
        if terrain == "coastal":
            min_qualify = tmax >= 37.0
        elif terrain in ("hills", "hilly"):
            min_qualify = tmax >= 30.0
        else:
            min_qualify = tmax >= 40.0

        label = 0
        cat = "No Heat Wave"

        # Step 2: Absolute temperature override for plains
        if terrain == "plains":
            if tmax >= 47.0:
                label = 2
                cat = "Severe Heat Wave"
            elif tmax >= 45.0:
                label = 1
                cat = "Heat Wave"

        # Step 3: Departure-based criteria if qualified
        if label == 0 and min_qualify:
            if normal <= 40.0:
                if departure >= 6.5:
                    label = 2
                    cat = "Severe Heat Wave"
                elif departure >= 4.5:
                    label = 1
                    cat = "Heat Wave"
            else:
                if departure >= 6.0:
                    label = 2
                    cat = "Severe Heat Wave"
                elif departure >= 4.0:
                    label = 1
                    cat = "Heat Wave"

        labels.append(label)
        categories.append(cat)

    out["heatwave_label"] = labels
    out["is_heatwave"] = [1 if l > 0 else 0 for l in labels]
    out["heatwave_category"] = categories

    return out
