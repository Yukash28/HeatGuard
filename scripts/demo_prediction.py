"""
HeatGuard Live Terminal Demo:
Demonstrates:
1. Multi-Horizon ML Heat-Wave Prediction with Year-Over-Year Context
2. Occupational Thermal Physics & Clothing Adjustment Value (CAV) Correction Factor
3. Effective WBGT & Action Threshold calculation (ISO 7243 / ACGIH)
"""

import argparse
import datetime
import sys
import time
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from heatguard.ml.predictor import HeatWavePredictor
from heatguard.risk.engine import get_clothing_adjustment_value, get_action_threshold_wbgt
from heatguard.workforce.models import WorkIntensity, AcclimatizationStatus


def print_banner(title: str):
    width = 72
    print("\n" + "=" * width)
    print(f"  {title.center(width - 4)}")
    print("=" * width)


def run_demo(
    city: str = "New Delhi",
    date: str = "2026-05-18",
    horizon: int = 3,
    ambient_temp: float = 41.5,
    humidity: float = 48.0,
    outdoor_wbgt: float = 30.2,
    ppe_type: str = "Coveralls / Double Layer",
    intensity: str = "Heavy",
    acclimatization: str = "Unacclimatized",
):
    print_banner("HEATGUARD — PREDICTIVE HEAT SAFETY & CORRECTION DEMO")
    time.sleep(0.3)

    # ---------------------------------------------------------
    # PART 1: ML HEAT-WAVE PREDICTION & YoY CONTEXT
    # ---------------------------------------------------------
    print("\n[PART 1: ML HEAT-WAVE PREDICTION (8-YEAR MULTI-YEAR REANALYSIS)]")
    print(f" • Monitored Target Location:  {city}")
    print(f" • Prediction Target Date:     {date} ({horizon} Days Ahead Horizon)")
    print(f" • Pre-calculated Model Baseline: Trained on ECMWF ERA5-Land (2018–2023)")

    predictor = HeatWavePredictor()

    # Contextual climatological normals & historical signals
    normal_map = {"New Delhi": 37.5, "Ahmedabad": 38.8, "Bengaluru": 32.5, "Kolkata": 35.2}
    exp_normal = normal_map.get(city, 37.0)

    city_coords = {
        "New Delhi": (28.6139, 77.2090),
        "Ahmedabad": (23.0225, 72.5714),
        "Bengaluru": (12.9716, 77.5946),
        "Kolkata": (22.5726, 88.3639),
    }
    lat, lon = city_coords.get(city, (28.6139, 77.2090))

    import datetime
    dt_obj = datetime.date.fromisoformat(date)
    doy = dt_obj.timetuple().tm_yday

    # Realistic inference feature payload
    feature_payload = {
        "latitude": lat,
        "longitude": lon,
        "doy_sin": np.sin(2 * np.pi * doy / 365.25),
        "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        "month": dt_obj.month,
        "tmax_lag1": ambient_temp,
        "tmin_lag1": ambient_temp - 12.0,
        "humidity_lag1": humidity,
        "pressure_lag1": 1004.0,
        "solar_lag1": 25.0,
        "tmax_roll_mean_3d": ambient_temp - 0.5,
        "tmax_roll_mean_7d": ambient_temp - 1.0,
        "tmax_roll_mean_14d": ambient_temp - 1.8,
        "tmax_roll_mean_30d": ambient_temp - 2.5,
        "tmax_roll_max_3d": ambient_temp,
        "tmax_roll_max_7d": ambient_temp,
        "tmax_roll_max_14d": ambient_temp,
        "tmax_trend_3d": 1.8,
        "tmax_trend_7d": 2.5,
        "rainfall_roll_sum_7d": 0.0,
        "rainfall_roll_sum_14d": 1.5,
        "rainfall_roll_sum_30d": 4.0,
        "consecutive_hot_days": 4,
        "tmax_yoy_1y": exp_normal + 1.2,
        "tmax_yoy_1y_week_mean": exp_normal + 1.0,
        "tmax_yoy_2y": exp_normal + 2.0,
        "tmax_yoy_3y": exp_normal + 0.8,
        "hist_3y_mean": exp_normal + 1.33,
        "temp_anomaly_hist": ambient_temp - exp_normal,
        "smoothed_normal": exp_normal,
    }

    print(" • Evaluating Year-Over-Year patterns and rolling atmospheric lags...")
    output = predictor.predict(
        location=city,
        target_date=date,
        horizon_days=horizon,
        feature_dict=feature_payload,
    )

    print("\n  >>> ML PREDICTION VERDICT <<<")
    print(f"  +----------------------------------------------------------------+")
    print(f"  | Predicted Maximum Temp (Tmax):   {output.predicted_tmax:.1f}°C  (±{output.uncertainty_margin:.1f}°C band)         |")
    print(f"  | Historical Climatological Normal:{output.historical_expected_tmax:.1f}°C                          |")
    print(f"  | Temperature Departure / Anomaly: +{output.temperature_anomaly:.1f}°C above normal              |")
    print(f"  | Calibrated Heat-Wave Probability:{output.heatwave_probability:.1f}%                            |")
    print(f"  | Risk Classification Verdict:     {output.risk_level}                    |")
    print(f"  | Prediction Confidence:           {output.confidence} (Horizon-decay calibrated)       |")
    print(f"  +----------------------------------------------------------------+")
    print("  Key Contributing Drivers:")
    for factor in output.contributing_factors:
        print(f"    - {factor}")

    time.sleep(0.4)

    # ---------------------------------------------------------
    # PART 2: CORRECTION FACTORS & EFFECTIVE WBGT
    # ---------------------------------------------------------
    print_banner("PART 2: WORKFORCE CORRECTION FACTORS & EFFECTIVE WBGT")
    print(f"Scenario: Outdoor industrial workforce during forecasted peak period.")
    print(f" • Measured/Forecasted Outdoor WBGT:  {outdoor_wbgt:.1f}°C")
    print(f" • Ambient Dry-Bulb Air Temp:          {ambient_temp:.1f}°C (RH: {humidity:.0f}%)")
    print(f" • Workforce PPE Equipment:           {ppe_type}")
    print(f" • Work Metabolic Load:               {intensity}")
    print(f" • Acclimatization Status:            {acclimatization}")

    # 1. Clothing Adjustment Value (CAV)
    cav_correction = get_clothing_adjustment_value(ppe_type)
    effective_wbgt = outdoor_wbgt + cav_correction

    # 2. Action Threshold
    w_intensity = WorkIntensity.from_str(intensity)
    w_acclim = AcclimatizationStatus.from_str(acclimatization)
    action_threshold = get_action_threshold_wbgt(w_intensity, w_acclim)

    net_margin = effective_wbgt - action_threshold

    print("\n  >>> THERMAL CORRECTION CALCULATIONS <<<")
    print(f"  Formula: Effective WBGT = Outdoor WBGT + Clothing Adjustment Value (CAV)")
    print(f"           Effective WBGT = {outdoor_wbgt:.1f}°C + {cav_correction:.1f}°C (PPE penalty)")
    print(f"           Effective WBGT = {effective_wbgt:.1f}°C")
    print()
    print(f"  Action Threshold (ISO 7243 / ACGIH): {action_threshold:.1f}°C (Baseline for {intensity} / {acclimatization})")
    print(f"  Exceedance Margin:                   +{net_margin:.1f}°C above safety limit!")

    # Mandatory controls
    if effective_wbgt >= 32.0 or net_margin >= 4.0:
        protocol = "CRITICAL: 15-min work / 45-min rest in cooled shade. Halt non-essential heavy work."
    elif effective_wbgt >= 30.0 or net_margin >= 2.0:
        protocol = "HIGH: 30-min work / 30-min rest cycles. Mandatory 1000 mL/hr electrolyte hydration."
    elif effective_wbgt >= action_threshold:
        protocol = "MODERATE: 45-min work / 15-min rest cycles. Increase shaded water stations."
    else:
        protocol = "LOW: Normal work pace permitted with standard rest breaks."

    print(f"\n  Mandated Operational Control Protocol:")
    print(f"  >>> {protocol}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HeatGuard Prediction & Correction Factor Terminal Demo")
    parser.add_argument("--city", default="New Delhi", help="City name (New Delhi, Ahmedabad, Bengaluru, Kolkata)")
    parser.add_argument("--date", default="2026-05-18", help="Target prediction date")
    parser.add_argument("--horizon", type=int, default=3, help="Horizon days ahead (1-7)")
    parser.add_argument("--temp", type=float, default=41.5, help="Ambient temperature in °C")
    parser.add_argument("--wbgt", type=float, default=30.2, help="Raw outdoor WBGT in °C")
    parser.add_argument("--ppe", default="Coveralls / Double Layer", help="PPE type")
    parser.add_argument("--intensity", default="Heavy", help="Metabolic intensity (Light, Moderate, Heavy)")
    parser.add_argument("--acclim", default="Unacclimatized", help="Acclimatization status")
    args = parser.parse_args()

    run_demo(
        city=args.city,
        date=args.date,
        horizon=args.horizon,
        ambient_temp=args.temp,
        outdoor_wbgt=args.wbgt,
        ppe_type=args.ppe,
        intensity=args.intensity,
        acclimatization=args.acclim,
    )
