"""
Master Pipeline:
1. Ingest / Load Raw Datasets
2. Clean and Validate Quality
3. Apply IMD Official Heat-Wave Target Labels
4. Engineer YoY, Lags, and Multi-Horizon Targets
5. Output final processed CSVs to data/processed/, data/labels/, data/features/
"""

import logging
import sys
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from heatguard.ml.data_cleaning import clean_and_validate_dataset
from heatguard.ml.imd_labeler import apply_imd_heatwave_labels
from heatguard.ml.features import build_yoy_and_lag_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def process_all_datasets(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    labels_dir: str = "data/labels",
    features_dir: str = "data/features",
):
    raw_path = Path(raw_dir)
    proc_path = Path(processed_dir)
    lbl_path = Path(labels_dir)
    feat_path = Path(features_dir)

    proc_path.mkdir(parents=True, exist_ok=True)
    lbl_path.mkdir(parents=True, exist_ok=True)
    feat_path.mkdir(parents=True, exist_ok=True)

    raw_files = list(raw_path.glob("historical_*.csv"))
    if not raw_files:
        logger.warning("No raw files found in %s", raw_dir)
        return

    all_features_dfs = []

    for f in raw_files:
        logger.info("Processing %s...", f.name)
        df_raw = pd.read_csv(f)
        loc_name = df_raw["location"].iloc[0]

        # 1. Clean & Validate
        clean_df, report = clean_and_validate_dataset(df_raw, location_name=loc_name)
        clean_file = proc_path / f"cleaned_{f.name}"
        clean_df.to_csv(clean_file, index=False)
        logger.info("Cleaned dataset saved: %s (%d rows)", clean_file, len(clean_df))

        # Save audit report markdown
        audit_file = proc_path / f"audit_{loc_name.lower().replace(' ', '_')}.md"
        audit_file.write_text(report.to_markdown(), encoding="utf-8")

        # 2. Apply IMD Ground Truth Labels
        labeled_df = apply_imd_heatwave_labels(clean_df)
        label_file = lbl_path / f"labeled_{f.name}"
        labeled_df.to_csv(label_file, index=False)
        hw_count = int(labeled_df["is_heatwave"].sum())
        logger.info("Applied IMD labels to %s: %d total heat-wave days identified", loc_name, hw_count)

        # 3. Engineer YoY & Lag Features
        features_df = build_yoy_and_lag_features(labeled_df)
        feat_file = feat_path / f"features_{f.name}"
        features_df.to_csv(feat_file, index=False)
        all_features_dfs.append(features_df)
        logger.info("Features engineered and saved: %s (Features: %d columns)", feat_file, len(features_df.columns))

    if all_features_dfs:
        combined = pd.concat(all_features_dfs, ignore_index=True)
        combined_file = feat_path / "combined_india_features_2018_2025.csv"
        combined.to_csv(combined_file, index=False)
        logger.info("Combined pan-India dataset saved: %s (Total rows: %d)", combined_file, len(combined))


if __name__ == "__main__":
    process_all_datasets()
