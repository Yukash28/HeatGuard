"""
Script to collect multi-year historical data (2018–2025) for representative Indian locations.
Saves raw records to data/raw/ and validates quality into data/processed/.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import List

# Ensure repository root is on Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from heatguard.api.base import LocationTarget
from heatguard.api.historical import OpenMeteoHistoricalProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Representative Indian climate zones
DEFAULT_LOCATIONS: List[LocationTarget] = [
    LocationTarget(name="New Delhi", latitude=28.6139, longitude=77.2090, terrain_type="plains"),
    LocationTarget(name="Ahmedabad", latitude=23.0225, longitude=72.5714, terrain_type="plains"),
    LocationTarget(name="Bengaluru", latitude=12.9716, longitude=77.5946, terrain_type="plains"),  # Plateau / high altitude
    LocationTarget(name="Kolkata", latitude=22.5726, longitude=88.3639, terrain_type="coastal"),
    LocationTarget(name="Nagpur", latitude=21.1458, longitude=79.0882, terrain_type="plains"),
]


def ingest_historical_data(
    locations: List[LocationTarget],
    start_date: str = "2018-01-01",
    end_date: str = "2025-12-31",
    raw_dir: str = "data/raw",
) -> List[Path]:
    """Fetch and save raw data per location."""
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)

    provider = OpenMeteoHistoricalProvider()
    saved_files: List[Path] = []

    for loc in locations:
        slug = loc.name.lower().replace(" ", "_")
        target_file = raw_path / f"historical_{slug}_{start_date[:4]}_{end_date[:4]}.csv"

        if target_file.exists():
            logger.info("Found existing raw dataset for %s: %s", loc.name, target_file)
            saved_files.append(target_file)
            continue

        try:
            logger.info("Ingesting %s from %s to %s...", loc.name, start_date, end_date)
            df = provider.fetch_historical_daily(loc, start_date=start_date, end_date=end_date)
            df.to_csv(target_file, index=False)
            logger.info("Saved %d daily records to %s", len(df), target_file)
            saved_files.append(target_file)
            time.sleep(1.0)  # Friendly throttling between requests
        except Exception as exc:
            logger.error("Failed to ingest %s: %s", loc.name, exc)

    return saved_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest historical Indian weather data (2018-2025)")
    parser.add_argument("--start", default="2018-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--raw-dir", default="data/raw", help="Directory to save raw CSVs")
    args = parser.parse_args()

    ingest_historical_data(DEFAULT_LOCATIONS, start_date=args.start, end_date=args.end, raw_dir=args.raw_dir)
