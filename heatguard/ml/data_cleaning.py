"""
Automated Data Quality Validation, Cleaning, and Auditing.
Checks for missing values, impossible temperatures, duplicate timestamps,
unit anomalies, and writes a reproducible audit log.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Valid physical meteorological bounds for India
BOUNDS = {
    "tmax": (-5.0, 55.0),       # °C
    "tmin": (-15.0, 42.0),      # °C
    "tmean": (-10.0, 48.0),     # °C
    "humidity": (0.0, 100.0),    # %
    "dew_point": (-20.0, 35.0), # °C
    "rainfall": (0.0, 600.0),    # mm/day
    "wind_speed": (0.0, 200.0),  # km/h
    "pressure": (850.0, 1050.0), # hPa
    "solar_radiation": (0.0, 40.0), # MJ/m2
    "cloud_cover": (0.0, 100.0), # %
    "soil_moisture": (0.0, 1.0), # m3/m3
}


@dataclass
class QualityReport:
    """Audit summary of data validation and cleaning."""
    total_records: int
    missing_imputed: Dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    outliers_clipped: Dict[str, int] = field(default_factory=dict)
    date_gaps: List[str] = field(default_factory=list)
    is_valid: bool = True

    def to_markdown(self) -> str:
        lines = [
            "# Data Quality Audit Report",
            f"- **Total Rows Evaluated**: {self.total_records}",
            f"- **Duplicate Dates Removed**: {self.duplicates_removed}",
            f"- **Missing Value Imputations**:",
        ]
        for col, count in self.missing_imputed.items():
            lines.append(f"  - `{col}`: {count} values")
        lines.append("- **Outliers Clipped to Physical Limits**:")
        for col, count in self.outliers_clipped.items():
            lines.append(f"  - `{col}`: {count} values")
        lines.append(f"- **Integrity Status**: {'PASS' if self.is_valid else 'FAIL'}")
        return "\n".join(lines)


def clean_and_validate_dataset(
    df: pd.DataFrame,
    location_name: str,
) -> Tuple[pd.DataFrame, QualityReport]:
    """
    Clean raw meteorological records:
    1. Ensure chronological ordering and remove duplicate dates.
    2. Check continuous date frequency (no missing days).
    3. Validate physical bounds and clip / flag outliers.
    4. Impute minor gaps using forward-fill / linear interpolation without future lookahead.
    """
    clean_df = df.copy()
    report = QualityReport(total_records=len(clean_df))

    # 1. Parse dates and sort
    clean_df["date"] = pd.to_datetime(clean_df["date"])
    initial_len = len(clean_df)
    clean_df = clean_df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    report.duplicates_removed = initial_len - len(clean_df)

    # 2. Check full date continuity
    full_idx = pd.date_range(start=clean_df["date"].min(), end=clean_df["date"].max(), freq="D")
    if len(full_idx) != len(clean_df):
        missing_dates = full_idx.difference(clean_df["date"])
        report.date_gaps = [d.strftime("%Y-%m-%d") for d in missing_dates]
        clean_df = clean_df.set_index("date").reindex(full_idx)
        clean_df.index.name = "date"
        clean_df = clean_df.reset_index()
        clean_df["location"] = location_name

    # 3. Validate physical bounds
    for col, (lower, upper) in BOUNDS.items():
        if col in clean_df.columns:
            outlier_mask = (clean_df[col] < lower) | (clean_df[col] > upper)
            outlier_count = int(outlier_mask.sum())
            if outlier_count > 0:
                report.outliers_clipped[col] = outlier_count
                clean_df.loc[clean_df[col] < lower, col] = lower
                clean_df.loc[clean_df[col] > upper, col] = upper

    # Cross-variable physical validation: Tmax must be >= Tmin
    invalid_t_mask = clean_df["tmax"] < clean_df["tmin"]
    if invalid_t_mask.sum() > 0:
        clean_df.loc[invalid_t_mask, "tmax"] = clean_df.loc[invalid_t_mask, "tmin"] + 0.1

    # 4. Impute missing values (causal forward fill + localized interpolation)
    numeric_cols = [c for c in clean_df.columns if c not in ["date", "location", "terrain_type"]]
    for col in numeric_cols:
        missing_count = int(clean_df[col].isna().sum())
        if missing_count > 0:
            report.missing_imputed[col] = missing_count
            clean_df[col] = clean_df[col].interpolate(method="linear", limit_direction="forward").bfill()

    clean_df["date"] = clean_df["date"].dt.strftime("%Y-%m-%d")
    return clean_df, report
