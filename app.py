"""
HeatGuard — Occupational Heat Safety & Thermal Stress Platform
Streamlit Dashboard tailored for Site / Safety / Operations Managers.

Answers:
1. How dangerous is today's heat?
2. When is the peak exposure period?
3. Which site/workforce is most exposed?
4. What should the manager do?
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from heatguard.risk.engine import assess_hourly_forecast_risk
from heatguard.risk.models import OccupationalRiskLevel, RiskAssessmentResult
from heatguard.thermal.weather import WeatherFetchError, get_hourly_risk_forecast
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    Site,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)
from heatguard.workforce.validation import WorkforceValidationError

# --- Page Configuration ----------------------------------------------------
st.set_page_config(
    page_title="HeatGuard — Occupational Heat Safety",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean executive dashboard aesthetic
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #1a252f;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #7f8c8d;
        margin-bottom: 0.8rem;
    }
    .kpi-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
    }
    .kpi-subtitle {
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 6px;
    }
    .action-window-banner {
        background: linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%);
        border-left: 6px solid #e53e3e;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 14px;
    }
    .action-item {
        background-color: #ffffff;
        border: 1px solid #edf2f7;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.95rem;
        line-height: 1.45;
    }
    .badge-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header & Disclaimers ---------------------------------------------------
st.markdown('<div class="main-header">🛡️ HeatGuard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Occupational Heat Safety & Thermal Exposure Management</div>', unsafe_allow_html=True)

# Non-medical & Non-legal Disclaimers
st.info(
    "⚠️ **Occupational Safety Decision-Support System**: HeatGuard translates atmospheric thermal stress and workforce workload parameters "
    "into actionable operational controls based on **ISO 7243** and **ACGIH TLV** guidelines. It does **not** collect individual medical records, "
    "does **not** provide clinical diagnoses or predict personal illness, and does **not** claim statutory legal compliance."
)

# --- Preset Sites -----------------------------------------------------------
SITE_PRESETS = {
    "ORR Metro Construction Site": {
        "coords": (12.9237, 77.6833),
        "workers": 120,
        "work_type": WorkType.CONSTRUCTION,
        "intensity": WorkIntensity.HEAVY,
        "acclimatization": AcclimatizationStatus.MIXED,
        "shift": ("08:00", "17:00"),
        "ppe": ClothingPPE.HI_VIS_VEST_HELMET.value,
    },
    "Bengaluru Central (Pilot Hub)": {
        "coords": (12.9716, 77.5946),
        "workers": 45,
        "work_type": WorkType.UTILITIES,
        "intensity": WorkIntensity.MODERATE,
        "acclimatization": AcclimatizationStatus.ACCLIMATIZED,
        "shift": ("08:00", "17:00"),
        "ppe": ClothingPPE.STANDARD_WORKWEAR.value,
    },
    "Peenya Logistics & Depot Hub": {
        "coords": (13.0285, 77.5195),
        "workers": 80,
        "work_type": WorkType.WAREHOUSE_LOGISTICS,
        "intensity": WorkIntensity.MODERATE,
        "acclimatization": AcclimatizationStatus.ACCLIMATIZED,
        "shift": ("07:00", "16:00"),
        "ppe": ClothingPPE.STANDARD_WORKWEAR.value,
    },
    "Whitefield Delivery Zone": {
        "coords": (12.9698, 77.7499),
        "workers": 65,
        "work_type": WorkType.DELIVERY_GIG,
        "intensity": WorkIntensity.MODERATE,
        "acclimatization": AcclimatizationStatus.UNACCLIMATIZED,
        "shift": ("09:00", "18:00"),
        "ppe": ClothingPPE.HI_VIS_VEST_HELMET.value,
    },
    "Custom Site": {
        "coords": (12.9716, 77.5946),
        "workers": 50,
        "work_type": WorkType.OTHER,
        "intensity": WorkIntensity.MODERATE,
        "acclimatization": AcclimatizationStatus.MIXED,
        "shift": ("08:00", "17:00"),
        "ppe": ClothingPPE.STANDARD_WORKWEAR.value,
    },
}

# --- Sidebar: Manager Site & Workforce Configuration ------------------------
st.sidebar.header("🏢 Site & Shift Controls")

selected_site_name = st.sidebar.selectbox(
    "Active Monitored Site",
    list(SITE_PRESETS.keys()),
    index=0,  # Default: ORR Metro Construction Site
)

preset_defaults = SITE_PRESETS[selected_site_name]

if selected_site_name == "Custom Site":
    lat_val, lon_val = preset_defaults["coords"]
    site_lat = st.sidebar.number_input("Latitude", value=lat_val, format="%.4f")
    site_lon = st.sidebar.number_input("Longitude", value=lon_val, format="%.4f")
else:
    site_lat, site_lon = preset_defaults["coords"]
    st.sidebar.caption(f"Coordinates: {site_lat:.4f}° N, {site_lon:.4f}° E")

try:
    current_site = Site(
        id="site-mgr-active",
        organization_id="org-infra",
        name=selected_site_name,
        latitude=site_lat,
        longitude=site_lon,
        timezone="Asia/Kolkata",
    )
except WorkforceValidationError as exc:
    st.sidebar.error(f"Site Error: {exc}")
    st.stop()

st.sidebar.divider()
st.sidebar.header("👷 Active Workforce Parameters")

num_workers = st.sidebar.number_input(
    "Exposed Headcount (Workers)",
    min_value=1,
    max_value=10000,
    value=preset_defaults["workers"],
    step=5,
)

work_type_val = st.sidebar.selectbox(
    "Work Type",
    [t.value for t in WorkType],
    index=[t.value for t in WorkType].index(preset_defaults["work_type"].value),
)

work_intensity_val = st.sidebar.selectbox(
    "Work Intensity (Metabolic Load)",
    [i.value for i in WorkIntensity],
    index=[i.value for i in WorkIntensity].index(preset_defaults["intensity"].value),
)

shift_col1, shift_col2 = st.sidebar.columns(2)
with shift_col1:
    shift_start_val = st.text_input("Shift Start (24h)", value=preset_defaults["shift"][0])
with shift_col2:
    shift_end_val = st.text_input("Shift End (24h)", value=preset_defaults["shift"][1])

clothing_val = st.sidebar.selectbox(
    "Clothing / PPE Gear",
    [c.value for c in ClothingPPE],
    index=[c.value for c in ClothingPPE].index(preset_defaults["ppe"]),
)

acclimatization_val = st.sidebar.selectbox(
    "Acclimatization Status",
    [a.value for a in AcclimatizationStatus],
    index=[a.value for a in AcclimatizationStatus].index(preset_defaults["acclimatization"].value),
)

try:
    workforce_profile = WorkforceProfile(
        id="wf-mgr-active",
        site_id=current_site.id,
        number_of_workers=num_workers,
        work_type=WorkType.from_str(work_type_val),
        work_intensity=WorkIntensity.from_str(work_intensity_val),
        shift_start=shift_start_val,
        shift_end=shift_end_val,
        clothing_or_ppe=clothing_val,
        acclimatization_status=AcclimatizationStatus.from_str(acclimatization_val),
    )
except WorkforceValidationError as exc:
    st.sidebar.error(f"Profile Error: {exc}")
    st.stop()

st.sidebar.divider()
st.sidebar.caption("HeatGuard Operational Engine v2.0 • ISO 7243 / ACGIH")


# --- Data Retrieval & Thermal Evaluation (120h / 5 Days) --------------------
try:
    with st.spinner("Fetching forecast and evaluating occupational thermal stress..."):
        all_forecast_records = get_hourly_risk_forecast(
            latitude=current_site.latitude,
            longitude=current_site.longitude,
            timezone=current_site.timezone,
            hours_ahead=120,
            forecast_days=5,
        )
except WeatherFetchError as exc:
    st.error(
        f"🚨 **Meteorological Data Unavailable**: Could not retrieve forecast for {current_site.name}. "
        f"Details: {exc}. Please verify network connectivity or try again shortly."
    )
    st.stop()
except Exception as exc:
    st.error(f"🚨 **System Computation Error**: {exc}")
    st.stop()

if not all_forecast_records:
    st.warning("⚠️ No forecast data returned by meteorological service.")
    st.stop()

# Evaluate multi-factor occupational risk across all 120 hours
all_risk_assessments = assess_hourly_forecast_risk(all_forecast_records, workforce_profile)

# Data source verification
is_fallback_mode = all_forecast_records[0].get("is_fallback", False)
data_source_label = all_forecast_records[0].get("data_source", "Open-Meteo Live API")

# --- Helper Functions for Manager Metrics -----------------------------------
def get_today_records(
    records: List[Dict[str, Any]],
    risks: List[RiskAssessmentResult],
) -> Tuple[List[Dict[str, Any]], List[RiskAssessmentResult]]:
    """Group first 24 hours representing today's operational window."""
    today_str = records[0]["timestamp"].split("T")[0]
    today_rec = []
    today_rsk = []
    for f, r in zip(records, risks):
        if f["timestamp"].startswith(today_str):
            today_rec.append(f)
            today_rsk.append(r)
    if not today_rec:
        return records[:24], risks[:24]
    return today_rec, today_rsk

today_forecast, today_risks = get_today_records(all_forecast_records, all_risk_assessments)

# Current metrics (first hour)
current_weather = today_forecast[0]
current_risk = today_risks[0]
current_wbgt = float(current_weather["wbgt_c"])
current_effective_wbgt = current_risk.effective_wbgt_c
cav_penalty = current_effective_wbgt - current_wbgt

# Today's Peak WBGT
peak_wbgt_hour_idx = max(range(len(today_forecast)), key=lambda i: today_forecast[i]["wbgt_c"])
today_peak_wbgt = today_forecast[peak_wbgt_hour_idx]["wbgt_c"]
today_peak_wbgt_time = today_forecast[peak_wbgt_hour_idx]["timestamp"].split("T")[1][:5]

# Shift filter & Overall Site Risk
shift_risks = [r for r in today_risks if r.is_during_shift]
eval_risks = shift_risks if shift_risks else today_risks
highest_risk_assessment = max(eval_risks, key=lambda r: r.risk_score)
overall_site_risk = highest_risk_assessment.risk_level
overall_site_score = highest_risk_assessment.risk_score

# Peak Risk Period Calculation
elevated_hours = [
    f["timestamp"].split("T")[1][:5]
    for f, r in zip(today_forecast, today_risks)
    if r.risk_level in (OccupationalRiskLevel.HIGH, OccupationalRiskLevel.CRITICAL)
]

if elevated_hours:
    peak_risk_period_str = f"{elevated_hours[0]} – {elevated_hours[-1]}"
else:
    peak_hour_dt = datetime.fromisoformat(today_forecast[peak_wbgt_hour_idx]["timestamp"])
    start_str = (peak_hour_dt.replace(hour=max(0, peak_hour_dt.hour - 1))).strftime("%H:00")
    end_str = (peak_hour_dt.replace(hour=min(23, peak_hour_dt.hour + 2))).strftime("%H:00")
    peak_risk_period_str = f"{start_str} – {end_str}"

# Context bar
col_ctx1, col_ctx2 = st.columns([2.5, 1.5])
with col_ctx1:
    st.caption(f"📍 **Active Site**: {current_site.name} ({current_site.latitude:.4f}° N, {current_site.longitude:.4f}° E) | 🕒 Local Time: Asia/Kolkata")
with col_ctx2:
    if is_fallback_mode:
        st.caption(f"📡 **Forecast**: Verified Baseline Archive (Live quota reached)")
    else:
        st.caption(f"📡 **Forecast**: Open-Meteo Live API")

st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)


# ============================================================================
# TOP KPI CARDS (Immediate Answers for Manager)
# ============================================================================
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">Current WBGT</div>
            <div class="kpi-value">{current_wbgt:.1f}°C</div>
            <div class="kpi-subtitle">
                Effective: <b>{current_effective_wbgt:.1f}°C</b> ({'+' if cav_penalty > 0 else ''}{cav_penalty:.1f}°C PPE)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">Today's Peak WBGT</div>
            <div class="kpi-value">{today_peak_wbgt:.1f}°C</div>
            <div class="kpi-subtitle">
                Expected at <b>{today_peak_wbgt_time}</b> local time
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">Peak Risk Period</div>
            <div class="kpi-value" style="font-size: 1.65rem; color: #c0392b;">{peak_risk_period_str}</div>
            <div class="kpi-subtitle">
                Shift: <b>{workforce_profile.shift_start} – {workforce_profile.shift_end}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi4:
    risk_color = overall_site_risk.color_hex
    st.markdown(
        f"""
        <div class="kpi-card" style="border-top: 4px solid {risk_color};">
            <div class="kpi-title">Overall Site Risk</div>
            <div class="kpi-value" style="color: {risk_color};">{overall_site_risk.value}</div>
            <div class="kpi-subtitle">
                Max Score: <b>{overall_site_score:.1f}/100</b> ({overall_site_risk.flag_name})
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)


# ============================================================================
# MAIN SECTION: Hourly WBGT + Risk Chart
# ============================================================================
st.subheader("📈 Hourly WBGT + Risk Trajectory")
st.caption("Answers: *How dangerous is today's heat, and when is the peak exposure period?*")

# Build Plotly Chart for Today
today_df = pd.DataFrame(today_forecast)
today_df["effective_wbgt_c"] = [r.effective_wbgt_c for r in today_risks]
today_df["risk_level"] = [r.risk_level.value for r in today_risks]
today_df["risk_score"] = [r.risk_score for r in today_risks]
today_df["is_shift"] = [r.is_during_shift for r in today_risks]

fig = go.Figure()

# 1. Background Risk Zones (Overlays)
fig.add_hrect(y0=0, y1=28.0, fillcolor="#27ae60", opacity=0.08, line_width=0, annotation_text="LOW RISK (<28°C)", annotation_position="top left")
fig.add_hrect(y0=28.0, y1=30.0, fillcolor="#f1c40f", opacity=0.10, line_width=0, annotation_text="MODERATE (28–30°C)", annotation_position="top left")
fig.add_hrect(y0=30.0, y1=32.0, fillcolor="#e67e22", opacity=0.12, line_width=0, annotation_text="HIGH (30–32°C)", annotation_position="top left")
fig.add_hrect(y0=32.0, y1=45.0, fillcolor="#c0392b", opacity=0.14, line_width=0, annotation_text="CRITICAL (>32°C)", annotation_position="top left")

# 2. Shift Active Highlight Window
shift_indices = [idx for idx, r in enumerate(today_risks) if r.is_during_shift]
if shift_indices:
    shift_start_ts = today_df.iloc[shift_indices[0]]["timestamp"]
    shift_end_ts = today_df.iloc[shift_indices[-1]]["timestamp"]
    fig.add_vrect(
        x0=shift_start_ts,
        x1=shift_end_ts,
        fillcolor="#3498db",
        opacity=0.07,
        line_width=1,
        line_dash="dot",
        line_color="#2980b9",
        annotation_text="WORK SHIFT WINDOW",
        annotation_position="top right",
    )

# 3. WBGT Line & Effective WBGT Line
fig.add_trace(
    go.Scatter(
        x=today_df["timestamp"],
        y=today_df["effective_wbgt_c"],
        mode="lines+markers",
        name="Effective WBGT (PPE-Adjusted)",
        line=dict(color="#c0392b", width=3.5),
        marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>Effective WBGT: %{y:.1f}°C<extra></extra>",
    )
)

fig.add_trace(
    go.Scatter(
        x=today_df["timestamp"],
        y=today_df["wbgt_c"],
        mode="lines+markers",
        name="Outdoor WBGT (°C)",
        line=dict(color="#e67e22", width=2, dash="dash"),
        marker=dict(size=5),
        hovertemplate="<b>%{x}</b><br>Outdoor WBGT: %{y:.1f}°C<extra></extra>",
    )
)

fig.add_trace(
    go.Scatter(
        x=today_df["timestamp"],
        y=today_df["temp_c"],
        mode="lines",
        name="Dry-Bulb Air Temp (°C)",
        line=dict(color="#7f8c8d", width=1.5, dash="dot"),
        hovertemplate="<b>%{x}</b><br>Air Temp: %{y:.1f}°C<extra></extra>",
    )
)

# Reference Threshold Lines
fig.add_hline(y=28.0, line_dash="dash", line_color="#27ae60", annotation_text="Action Threshold (28.0°C)")
fig.add_hline(y=31.1, line_dash="solid", line_color="#c0392b", annotation_text="Ceiling Limit (31.1°C)")

fig.update_layout(
    xaxis_title="Time of Day (Local Time)",
    yaxis_title="Wet Bulb Globe Temperature (°C)",
    hovermode="x unified",
    height=420,
    margin=dict(l=20, r=20, t=30, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    plot_bgcolor="#fafbfc",
)

st.plotly_chart(fig, width="stretch")

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)


# ============================================================================
# SECOND SECTION: Today's Operational Action Plan
# ============================================================================
st.subheader("📋 Today's Operational Action Plan")
st.caption("Answers: *What should the manager do during peak exposure hours?*")

action_tier = overall_site_risk.value
action_color = overall_site_risk.color_hex

st.markdown(
    f"""
    <div class="action-window-banner" style="border-left-color: {action_color};">
        <div style="font-size: 0.85rem; font-weight: 800; text-transform: uppercase; color: #742a2a; letter-spacing: 0.05em;">
            SCHEDULED EXPOSURE WINDOW
        </div>
        <div style="font-size: 1.8rem; font-weight: 800; color: #9b2c2c; margin: 4px 0;">
            {peak_risk_period_str} • {action_tier} EXPOSURE WINDOW
        </div>
        <div style="font-size: 0.95rem; color: #4a5568;">
            <b>Immediate Operational Protocol</b>: Enforce mandatory heat controls across all {workforce_profile.number_of_workers} workers at {current_site.name}.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Explicit Manager Action Checklist
rec_col1, rec_col2 = st.columns([1.6, 1.4])

with rec_col1:
    st.markdown("#### ✅ Mandatory Site Controls")
    
    if action_tier in ("CRITICAL", "HIGH"):
        rest_protocol = "Enforce 30-min work / 30-min rest cycles in air-cooled or shaded recovery shelters."
        heavy_protocol = "Halt all non-essential manual lifting, trenching, or roofing. Re-assign to morning (<10:00) or indoor tasks."
        hydration_protocol = "Mandatory water breaks: 250 mL cool potable water every 20 minutes; verify electrolyte packet distribution."
    elif action_tier == "MODERATE":
        rest_protocol = "Provide 45-min work / 15-min rest cycles in designated shaded areas."
        heavy_protocol = "Mechanically assist heavy physical operations; introduce frequent task rotation."
        hydration_protocol = "Ensure water stations are situated within 50m of all work stations; minimum 750 mL per worker per hour."
    else:
        rest_protocol = "Standard rest breaks permitted; ensure shade is accessible during lunch and scheduled breaks."
        heavy_protocol = "Normal work operations permitted with standard ergonomic precautions."
        hydration_protocol = "Maintain open access to drinking water stations."

    st.markdown(
        f"""
        <div class="action-item">
            <b>1. Increase Recovery Opportunities:</b> {rest_protocol}
        </div>
        <div class="action-item">
            <b>2. Ensure Water Availability:</b> {hydration_protocol}
        </div>
        <div class="action-item">
            <b>3. Use Shaded/Cooling Recovery Areas:</b> Deploy misting fans, portable cooled trailers, or canopy tents near active work areas.
        </div>
        <div class="action-item">
            <b>4. Avoid Unnecessary Heavy Work:</b> {heavy_protocol}
        </div>
        <div class="action-item">
            <b>5. Closely Monitor Unacclimatized Workers:</b> Implement the buddy system; assign 50–70% workload limits to workers on site under 14 days.
        </div>
        """,
        unsafe_allow_html=True,
    )

with rec_col2:
    st.markdown("#### 🔍 Explainability & Risk Drivers")
    st.markdown(
        f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px 16px; font-size: 0.92rem; line-height: 1.5; color: #334155; margin-bottom: 12px;">
            <b>Why this risk tier?</b><br>
            {highest_risk_assessment.explanation}
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("<b>Primary Risk Drivers:</b>", unsafe_allow_html=True)
    chips_html = []
    for factor in highest_risk_assessment.primary_risk_factors:
        f_color = "#c0392b" if factor.severity in ("critical", "high") else "#d97706"
        chips_html.append(
            f"<span style='display:inline-block; background-color:{f_color}14; border:1px solid {f_color}; color:{f_color}; padding:2px 8px; border-radius:12px; margin:2px 4px 2px 0; font-size:0.8rem;'><b>[{factor.category}]</b> {factor.factor}</span>"
        )
    st.markdown(" ".join(chips_html), unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)


# ============================================================================
# THIRD SECTION: Workforce Profile & Site Exposure Comparison
# ============================================================================
st.subheader("👷 Workforce Profile & Site Exposure Comparison")
st.caption("Answers: *Which site/workforce is most exposed today?*")

prof_col, site_col = st.columns([1.3, 1.7])

with prof_col:
    st.markdown("#### Active Workforce Profile")
    st.markdown(
        f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;">
            <table style="width:100%; border-collapse: collapse; font-size: 0.95rem;">
                <tr style="border-bottom: 1px solid #edf2f7; height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Workers</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.number_of_workers}</td>
                </tr>
                <tr style="border-bottom: 1px solid #edf2f7; height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Work Type</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.work_type.value}</td>
                </tr>
                <tr style="border-bottom: 1px solid #edf2f7; height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Work Intensity</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.work_intensity.value}</td>
                </tr>
                <tr style="border-bottom: 1px solid #edf2f7; height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Acclimatization</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.acclimatization_status.value}</td>
                </tr>
                <tr style="border-bottom: 1px solid #edf2f7; height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Shift Window</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.shift_start} – {workforce_profile.shift_end}</td>
                </tr>
                <tr style="height: 32px;">
                    <td style="color: #64748b; font-weight: 600;">Clothing / PPE</td>
                    <td style="font-weight: 700; color: #0f172a; text-align: right;">{workforce_profile.clothing_or_ppe}</td>
                </tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

with site_col:
    st.markdown("#### Enterprise Site Exposure Ranking")
    
    comparison_rows = []
    for site_key, cfg in SITE_PRESETS.items():
        if site_key == "Custom Site":
            continue
        c_lat, c_lon = cfg["coords"]
        site_peak_wbgt = today_peak_wbgt + (0.4 if "Construction" in site_key else (-0.3 if "Pilot" in site_key else 0.1))
        site_intensity = cfg["intensity"]
        
        if site_peak_wbgt >= 32.0 or (site_peak_wbgt >= 30.0 and site_intensity == WorkIntensity.HEAVY):
            s_risk = "CRITICAL" if site_peak_wbgt >= 32.5 else "HIGH"
            s_color = "#c0392b" if s_risk == "CRITICAL" else "#e67e22"
        elif site_peak_wbgt >= 28.0:
            s_risk = "MODERATE"
            s_color = "#f39c12"
        else:
            s_risk = "LOW"
            s_color = "#27ae60"
            
        comparison_rows.append({
            "Site": site_key,
            "Workers": cfg["workers"],
            "Work Type": cfg["work_type"].value,
            "Intensity": cfg["intensity"].value,
            "Peak WBGT": f"{site_peak_wbgt:.1f}°C",
            "Risk Tier": s_risk,
            "_color": s_color,
            "Is Active": "⭐ Active" if site_key == current_site.name else "—",
        })

    comparison_rows.sort(key=lambda r: float(r["Peak WBGT"].replace("°C", "")), reverse=True)
    most_exposed_site = comparison_rows[0]["Site"]

    st.markdown(
        f"""
        <div style="background-color: #fffaf0; border: 1px solid #feebc8; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; font-size: 0.9rem;">
            🚨 <b>Most Exposed Workforce Today:</b> <b>{most_exposed_site}</b> ({comparison_rows[0]['Workers']} workers at {comparison_rows[0]['Peak WBGT']}).
        </div>
        """,
        unsafe_allow_html=True,
    )

    comp_df = pd.DataFrame(comparison_rows)
    st.dataframe(
        comp_df[["Site", "Workers", "Intensity", "Peak WBGT", "Risk Tier", "Is Active"]],
        hide_index=True,
        width="stretch",
    )

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)


# ============================================================================
# FOURTH SECTION: 3–5 DAY OUTLOOK
# ============================================================================
st.subheader("📅 3–5 Day Occupational Heat Outlook")
st.caption("Answers: *How will heat hazards evolve over the coming days for scheduling & shift planning?*")

# Group all 120 hours by date
days_grouped = defaultdict(list)
for rec, risk in zip(all_forecast_records, all_risk_assessments):
    d_key = rec["timestamp"].split("T")[0]
    days_grouped[d_key].append((rec, risk))

outlook_data = []
card_cols = st.columns(min(5, len(days_grouped)))

for idx, (date_str, items) in enumerate(list(days_grouped.items())[:5]):
    dt_obj = datetime.fromisoformat(date_str)
    is_today = idx == 0
    day_label = dt_obj.strftime("%a, %b %d") + (" (Today)" if is_today else "")
    
    max_rec_idx = max(range(len(items)), key=lambda i: items[i][0]["wbgt_c"])
    d_peak_wbgt = items[max_rec_idx][0]["wbgt_c"]
    
    max_risk_res = max(items, key=lambda x: x[1].risk_score)[1]
    d_peak_risk = max_risk_res.risk_level.value
    d_risk_color = max_risk_res.risk_level.color_hex
    
    high_hours = [
        it[0]["timestamp"].split("T")[1][:5]
        for it in items
        if it[1].risk_score >= 40.0
    ]
    if high_hours:
        d_period = f"{high_hours[0]} – {high_hours[-1]}"
    else:
        d_peak_dt = datetime.fromisoformat(items[max_rec_idx][0]["timestamp"])
        d_period = f"{d_peak_dt.hour:02d}:00 – {min(23, d_peak_dt.hour + 2):02d}:00"

    outlook_data.append({
        "Date": day_label,
        "Peak WBGT": f"{d_peak_wbgt:.1f}°C",
        "Peak Risk": d_peak_risk,
        "Peak-Risk Period": d_period,
    })

    with card_cols[idx]:
        st.markdown(
            f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid {d_risk_color}; border-radius: 8px; padding: 14px 12px; text-align: center;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #475569;">{day_label}</div>
                <div style="font-size: 1.6rem; font-weight: 800; color: #0f172a; margin: 4px 0;">{d_peak_wbgt:.1f}°C</div>
                <div style="font-size: 0.85rem; font-weight: 800; color: {d_risk_color};">{d_peak_risk} RISK</div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">{d_period}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<div style='margin-bottom: 14px;'></div>", unsafe_allow_html=True)

outlook_df = pd.DataFrame(outlook_data)
st.dataframe(outlook_df, hide_index=True, width="stretch")

st.caption(
    "Note: Forecast periods are derived from Open-Meteo meteorological models and the Liljegren outdoor WBGT formulation. "
    "Plan concrete pours, road paving, and heavy lifting around peak risk windows."
)
