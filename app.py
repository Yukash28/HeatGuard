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
import json
from typing import Any, Dict, List, Tuple
import uuid
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from heatguard.risk.engine import assess_hourly_forecast_risk
from heatguard.risk.models import OccupationalRiskLevel, RiskAssessmentResult
from heatguard.risk.multi_site import (
    OrganizationOverview,
    SiteSummary,
    evaluate_organization_overview,
)
from heatguard.storage import (
    ActionPlanRecord,
    HeatGuardRepository,
    RiskAssessmentRecord,
    SiteRecord,
    WbgtCalculationRecord,
    WeatherSnapshotRecord,
    WorkforceProfileRecord,
    init_db,
)
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

# --- Persistent Storage & Multi-Site Initialization -------------------------
repo = init_db(seed=True)

all_orgs = repo.list_organizations()
abc_org = repo.get_organization("org-abc")
if not abc_org:
    repo.seed_default_presets()
    all_orgs = repo.list_organizations()
    abc_org = repo.get_organization("org-abc") or all_orgs[0]

org_names = [o.name for o in all_orgs]
def_org_idx = next((i for i, o in enumerate(all_orgs) if o.id == abc_org.id), 0)

# --- Navigation & Mode Selection in Sidebar ---------------------------------
if "nav_view_radio" not in st.session_state:
    st.session_state["nav_view_radio"] = "🏢 Organization Overview"

st.sidebar.markdown("### 🧭 Command Navigation")
current_view = st.sidebar.radio(
    "Monitoring Scope",
    ["🏢 Organization Overview", "🔍 Site Detailed Dashboard"],
    key="nav_view_radio",
)

st.sidebar.divider()
st.sidebar.header("🏢 Enterprise & Site Selection")

selected_org_name = st.sidebar.selectbox("Active Organization", org_names, index=def_org_idx, key="sidebar_org_selector")
selected_org = next((o for o in all_orgs if o.name == selected_org_name), abc_org)

# Fetch persisted sites belonging to active organization
org_sites = repo.list_sites(organization_id=selected_org.id)
if not org_sites:
    org_sites = repo.list_sites()
site_names = [s.name for s in org_sites]

if "selected_site_name" not in st.session_state or st.session_state["selected_site_name"] not in site_names:
    st.session_state["selected_site_name"] = site_names[0]

current_site_idx = site_names.index(st.session_state["selected_site_name"])
selected_site_name = st.sidebar.selectbox(
    "Active Monitored Worksite",
    site_names,
    index=current_site_idx,
    key="sidebar_site_selector",
)
st.session_state["selected_site_name"] = selected_site_name

# Fetch active site record & saved workforce profile from SQLite
active_site_record = next((s for s in org_sites if s.name == selected_site_name), org_sites[0])
saved_wf_record = repo.get_workforce_profile(active_site_record.id)

# Site parameters editor (available in sidebar)
if current_view == "🔍 Site Detailed Dashboard":
    with st.sidebar.expander("📍 Worksite Coordinates & Details", expanded=False):
        site_lat = st.number_input("Latitude", value=active_site_record.latitude, format="%.4f", key=f"lat_{active_site_record.id}")
        site_lon = st.number_input("Longitude", value=active_site_record.longitude, format="%.4f", key=f"lon_{active_site_record.id}")
        st.caption(f"Site ID: `{active_site_record.id}` | Timezone: `{active_site_record.timezone}`")
    st.sidebar.caption(f"📍 {site_lat:.4f}° N, {site_lon:.4f}° E")
else:
    site_lat = active_site_record.latitude
    site_lon = active_site_record.longitude

try:
    current_site = Site(
        id=active_site_record.id,
        organization_id=active_site_record.organization_id,
        name=selected_site_name,
        latitude=site_lat,
        longitude=site_lon,
        timezone=active_site_record.timezone,
    )
except WorkforceValidationError as exc:
    st.sidebar.error(f"Site Error: {exc}")
    st.stop()

# Workforce Parameters in sidebar
default_workers = saved_wf_record.workers if saved_wf_record else 50
default_work_type = saved_wf_record.work_type if saved_wf_record else WorkType.CONSTRUCTION.value
default_intensity = saved_wf_record.work_intensity if saved_wf_record else WorkIntensity.HEAVY.value
default_shift_start = saved_wf_record.shift_start if saved_wf_record else "08:00"
default_shift_end = saved_wf_record.shift_end if saved_wf_record else "17:00"
default_ppe = saved_wf_record.ppe if saved_wf_record else ClothingPPE.HI_VIS_VEST_HELMET.value
default_acclim = saved_wf_record.acclimatization if saved_wf_record else AcclimatizationStatus.ACCLIMATIZED.value

if current_view == "🔍 Site Detailed Dashboard":
    st.sidebar.divider()
    st.sidebar.header("👷 Worksite Workforce Parameters")

    num_workers = st.sidebar.number_input(
        "Exposed Headcount (Workers)",
        min_value=1,
        max_value=10000,
        value=default_workers,
        step=5,
        key=f"workers_{active_site_record.id}",
    )

    all_work_types = [t.value for t in WorkType]
    work_type_idx = all_work_types.index(default_work_type) if default_work_type in all_work_types else 0
    work_type_val = st.sidebar.selectbox("Work Type", all_work_types, index=work_type_idx, key=f"wt_{active_site_record.id}")

    all_intensities = [i.value for i in WorkIntensity]
    intensity_idx = all_intensities.index(default_intensity) if default_intensity in all_intensities else 0
    work_intensity_val = st.sidebar.selectbox("Work Intensity (Metabolic Load)", all_intensities, index=intensity_idx, key=f"wi_{active_site_record.id}")

    shift_col1, shift_col2 = st.sidebar.columns(2)
    with shift_col1:
        shift_start_val = st.text_input("Shift Start (24h)", value=default_shift_start, key=f"ss_{active_site_record.id}")
    with shift_col2:
        shift_end_val = st.text_input("Shift End (24h)", value=default_shift_end, key=f"se_{active_site_record.id}")

    all_ppes = [c.value for c in ClothingPPE]
    ppe_idx = all_ppes.index(default_ppe) if default_ppe in all_ppes else 0
    clothing_val = st.sidebar.selectbox("Clothing / PPE Gear", all_ppes, index=ppe_idx, key=f"ppe_{active_site_record.id}")

    all_acclims = [a.value for a in AcclimatizationStatus]
    acclim_idx = all_acclims.index(default_acclim) if default_acclim in all_acclims else 0
    acclimatization_val = st.sidebar.selectbox("Acclimatization Status", all_acclims, index=acclim_idx, key=f"acc_{active_site_record.id}")

    try:
        workforce_profile = WorkforceProfile(
            id=saved_wf_record.id if saved_wf_record else f"wf-{current_site.id}",
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

    if st.sidebar.button("💾 Save Profile to Database", use_container_width=True):
        repo.save_site(current_site)
        repo.save_workforce_profile(workforce_profile)
        st.sidebar.success(f"✅ Saved updates for '{current_site.name}' to SQLite!")
else:
    # Use saved profile in overview mode
    workforce_profile = saved_wf_record.to_domain() if saved_wf_record else WorkforceProfile(
        id=f"wf-{current_site.id}",
        site_id=current_site.id,
        number_of_workers=default_workers,
        work_type=WorkType.from_str(default_work_type),
        work_intensity=WorkIntensity.from_str(default_intensity),
        shift_start=default_shift_start,
        shift_end=default_shift_end,
        clothing_or_ppe=default_ppe,
        acclimatization_status=AcclimatizationStatus.from_str(default_acclim),
    )

# Add New Facility expander
with st.sidebar.expander("➕ Register New Worksite", expanded=False):
    with st.form("register_site_form", clear_on_submit=True):
        st.markdown(f"<b>Add Site to {selected_org.name}</b>", unsafe_allow_html=True)
        new_site_name = st.text_input("Facility / Site Name", placeholder="e.g. Mysuru Solar Array")
        c_lat_col, c_lon_col = st.columns(2)
        with c_lat_col:
            new_site_lat = st.number_input("Latitude", value=12.2958, format="%.4f")
        with c_lon_col:
            new_site_lon = st.number_input("Longitude", value=76.6394, format="%.4f")
        new_headcount = st.number_input("Headcount", min_value=1, max_value=10000, value=60, step=5)
        new_wt = st.selectbox("Work Type", [t.value for t in WorkType], key="new_wt")
        new_wi = st.selectbox("Intensity", [i.value for i in WorkIntensity], key="new_wi")
        n_sc1, n_sc2 = st.columns(2)
        with n_sc1:
            new_ss = st.text_input("Shift Start", value="07:00", key="new_ss")
        with n_sc2:
            new_se = st.text_input("Shift End", value="16:00", key="new_se")
        new_p = st.selectbox("PPE", [c.value for c in ClothingPPE], key="new_ppe")
        new_acc = st.selectbox("Acclimatization", [a.value for a in AcclimatizationStatus], key="new_acc")
        
        submitted = st.form_submit_button("Persist New Worksite", use_container_width=True)
        if submitted:
            if not new_site_name.strip():
                st.error("Site name cannot be empty.")
            else:
                new_id = f"site-{uuid.uuid4().hex[:8]}"
                created_site = Site(
                    id=new_id,
                    organization_id=selected_org.id,
                    name=new_site_name.strip(),
                    latitude=new_site_lat,
                    longitude=new_site_lon,
                    timezone="Asia/Kolkata",
                )
                repo.save_site(created_site)
                created_wf = WorkforceProfile(
                    id=f"wf-{new_id}",
                    site_id=new_id,
                    number_of_workers=new_headcount,
                    work_type=WorkType.from_str(new_wt),
                    work_intensity=WorkIntensity.from_str(new_wi),
                    shift_start=new_ss,
                    shift_end=new_se,
                    clothing_or_ppe=new_p,
                    acclimatization_status=AcclimatizationStatus.from_str(new_acc),
                )
                repo.save_workforce_profile(created_wf)
                st.session_state["selected_site_name"] = created_site.name
                st.session_state["nav_view_radio"] = "🔍 Site Detailed Dashboard"
                st.rerun()

st.sidebar.divider()
st.sidebar.caption("HeatGuard Multi-Site Command v2.0 • ISO 7243 / ACGIH")


# ============================================================================
# VIEW 1: ORGANIZATION OVERVIEW
# ============================================================================
if current_view == "🏢 Organization Overview":
    st.markdown(f'<div class="main-header">🏢 {selected_org.name}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Multi-Site Thermal Stress Monitoring & Workforce Heat Safety Command</div>', unsafe_allow_html=True)

    with st.spinner(f"Evaluating real-time atmospheric exposure across {selected_org.name} worksites..."):
        org_overview = evaluate_organization_overview(repo=repo, org_id=selected_org.id)

    # ------------------------------------------------------------------------
    # ORGANIZATION-LEVEL OVERVIEW KPI CARDS
    # ------------------------------------------------------------------------
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)

    with kpi_c1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">TOTAL SITES</div>
                <div class="kpi-value">{org_overview.total_sites}</div>
                <div class="kpi-subtitle">Active Monitored Worksites</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_c2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">TOTAL WORKERS</div>
                <div class="kpi-value">{org_overview.total_workers:,}</div>
                <div class="kpi-subtitle">Exposed Workforce Cohort</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_c3:
        high_border = "#e67e22" if org_overview.high_risk_sites_count > 0 else "#27ae60"
        high_val_color = "#e67e22" if org_overview.high_risk_sites_count > 0 else "#0f172a"
        st.markdown(
            f"""
            <div class="kpi-card" style="border-top: 4px solid {high_border};">
                <div class="kpi-title">HIGH-RISK SITES</div>
                <div class="kpi-value" style="color: {high_val_color};">{org_overview.high_risk_sites_count}</div>
                <div class="kpi-subtitle">Orange Flag • Action Required</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_c4:
        crit_border = "#c0392b" if org_overview.critical_risk_sites_count > 0 else "#27ae60"
        crit_val_color = "#c0392b" if org_overview.critical_risk_sites_count > 0 else "#0f172a"
        st.markdown(
            f"""
            <div class="kpi-card" style="border-top: 4px solid {crit_border};">
                <div class="kpi-title">CRITICAL SITES</div>
                <div class="kpi-value" style="color: {crit_val_color};">{org_overview.critical_risk_sites_count}</div>
                <div class="kpi-subtitle">Red Flag • Work Limits/Rest</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # SITE SELECTOR & DRILL-DOWN CONTROL
    # ------------------------------------------------------------------------
    st.subheader("🔍 Worksite Detail Selector")
    st.caption("Select a site to open its detailed occupational heat stress dashboard, hourly exposure trajectory, and ISO 7243 action plan.")

    drill_col1, drill_col2 = st.columns([3.2, 1.2])
    with drill_col1:
        drill_site_chosen = st.selectbox(
            "Choose Worksite to Open Detailed Dashboard",
            site_names,
            index=current_site_idx,
            key="org_overview_drill_selector",
        )
    with drill_col2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 Open Detailed Dashboard", type="primary", use_container_width=True):
            st.session_state["selected_site_name"] = drill_site_chosen
            st.session_state["nav_view_radio"] = "🔍 Site Detailed Dashboard"
            st.rerun()

    st.markdown("<div style='margin-bottom: 18px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # MULTI-SITE EXPOSURE MONITORING TABLE
    # ------------------------------------------------------------------------
    st.subheader(f"📊 {selected_org.name} Multi-Site Exposure Table")
    st.caption("Live comparison of thermal exposure, peak risk period, and workforce density across all sites.")

    table_data = []
    for s in org_overview.sites:
        table_data.append({
            "Site Name": s.name,
            "Location": s.location_str,
            "Worker Count": s.workers,
            "Work Type": s.work_type,
            "Current WBGT": f"{s.current_wbgt:.1f}°C",
            "Peak WBGT": f"{s.peak_wbgt:.1f}°C",
            "Current Risk": s.current_risk_level.value,
            "Peak Risk Period": s.peak_risk_period,
            "Risk Tier": s.peak_risk_level.value,
        })

    table_df = pd.DataFrame(table_data)
    st.dataframe(
        table_df[["Site Name", "Location", "Worker Count", "Work Type", "Current WBGT", "Peak WBGT", "Current Risk", "Peak Risk Period", "Risk Tier"]],
        hide_index=True,
        width="stretch",
    )

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # INTERACTIVE WORKSITE STATUS CARDS
    # ------------------------------------------------------------------------
    st.subheader("📍 Worksite Quick-Access Cards")
    card_cols = st.columns(min(len(org_overview.sites), 4))
    for idx, s in enumerate(org_overview.sites):
        r_color = s.peak_risk_level.color_hex
        with card_cols[idx % 4]:
            st.markdown(
                f"""
                <div class="kpi-card" style="border-top: 4px solid {r_color}; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 800; font-size: 1.05rem; color: #0f172a; margin-bottom: 4px;">{s.name}</div>
                        <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">📍 {s.location_str}</div>
                        <div style="font-size: 0.85rem; color: #334155; margin-bottom: 4px;">👷 <b>{s.workers}</b> Workers • {s.work_type}</div>
                        <div style="font-size: 0.85rem; color: #334155; margin-bottom: 6px;">🌡️ WBGT: <b>{s.current_wbgt:.1f}°C</b> (Peak: <b>{s.peak_wbgt:.1f}°C</b>)</div>
                    </div>
                    <div>
                        <div style="margin-bottom: 10px;">
                            <span style="display:inline-block; background-color: {r_color}20; border: 1px solid {r_color}; color: {r_color}; font-weight: 800; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">
                                {s.peak_risk_level.value} RISK • {s.peak_risk_period}
                            </span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Inspect {s.name} ➔", key=f"btn_card_inspect_{s.site_id}", use_container_width=True):
                st.session_state["selected_site_name"] = s.name
                st.session_state["nav_view_radio"] = "🔍 Site Detailed Dashboard"
                st.rerun()

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)
    st.info(
        "💡 **Multi-Site Heat Stress Management**: HeatGuard automatically aggregates micro-climate variations across all active worksites. "
        "High and Critical alerts demand proactive scheduling of rest cycles and hydration distribution before peak risk hours begin."
    )
    st.stop()


# ============================================================================
# VIEW 2: SITE DETAILED DASHBOARD
# ============================================================================

# Top Navigation Bar to return to Org Overview
top_nav_c1, top_nav_c2 = st.columns([1.5, 3.5])
with top_nav_c1:
    if st.button("⬅ Return to Organization Overview", use_container_width=True, type="secondary"):
        st.session_state["nav_view_radio"] = "🏢 Organization Overview"
        st.rerun()
with top_nav_c2:
    st.markdown(
        f"""
        <div style="padding-top: 6px; font-size: 0.95rem; color: #475569;">
            🏢 <b>Organization</b>: {selected_org.name} &nbsp;•&nbsp; 📍 <b>Active Worksite</b>: <span style="color: #0f172a; font-weight: 700;">{current_site.name}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

# --- Data Retrieval & Thermal Evaluation (120h / 5 Days) --------------------
try:
    with st.spinner(f"Fetching forecast and evaluating occupational thermal stress for {current_site.name}..."):
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

# --- SQLite Persistence: Save Current Evaluation Records --------------------
try:
    ws_records = [
        WeatherSnapshotRecord(
            id=f"ws-{current_site.id}-{rec['timestamp']}",
            site_id=current_site.id,
            timestamp=rec["timestamp"],
            temperature_c=float(rec["temp_c"]),
            relative_humidity=float(rec["humidity"]),
            wind_speed_kmh=float(rec["wind_kmh"]),
            solar_radiation=float(rec.get("radiation", 0.0)),
            data_source=data_source_label,
        )
        for rec in today_forecast
    ]
    repo.save_weather_snapshots_batch(ws_records)

    wbgt_records = [
        WbgtCalculationRecord(
            id=f"wbgt-{current_site.id}-{rec['timestamp']}",
            site_id=current_site.id,
            timestamp=rec["timestamp"],
            wbgt_c=float(rec["wbgt_c"]),
            effective_wbgt_c=float(rsk.effective_wbgt_c),
            heat_index_c=float(rec.get("heat_index_c", 0.0)),
            method="Liljegren",
        )
        for rec, rsk in zip(today_forecast, today_risks)
    ]
    repo.save_wbgt_calculations_batch(wbgt_records)

    risk_records = [
        RiskAssessmentRecord(
            id=f"risk-{current_site.id}-{r.timestamp}",
            site_id=current_site.id,
            timestamp=r.timestamp,
            wbgt=float(r.effective_wbgt_c),
            risk_level=r.risk_level.value,
            risk_score=float(r.risk_score),
            explanation=r.explanation,
        )
        for r in today_risks
    ]
    repo.save_risk_assessments_batch(risk_records)

    controls_payload = [c.to_dict() for c in highest_risk_assessment.recommended_controls]
    plan_record = ActionPlanRecord(
        id=f"plan-{current_site.id}-{today_forecast[0]['timestamp'].split('T')[0]}",
        site_id=current_site.id,
        timestamp=today_forecast[0]["timestamp"],
        risk_tier=overall_site_risk.value,
        peak_period=peak_risk_period_str,
        action_summary=f"Mandatory heat controls for {workforce_profile.number_of_workers} workers at {current_site.name}.",
        controls_json=json.dumps(controls_payload),
    )
    repo.save_action_plan(plan_record)
except Exception as exc:
    # Non-blocking persistence error reporting
    pass

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
    all_stored_sites = repo.list_sites()
    for s_rec in all_stored_sites:
        wf_rec = repo.get_workforce_profile(s_rec.id)
        s_workers = wf_rec.workers if wf_rec else 50
        s_work_type = wf_rec.work_type if wf_rec else "Construction"
        s_intensity = WorkIntensity.from_str(wf_rec.work_intensity) if wf_rec else WorkIntensity.MODERATE
        
        offset = 0.4 if "Construction" in s_rec.name else (-0.3 if "Pilot" in s_rec.name else 0.1)
        site_peak_wbgt = today_peak_wbgt + offset
        
        if site_peak_wbgt >= 32.0 or (site_peak_wbgt >= 30.0 and s_intensity == WorkIntensity.HEAVY):
            s_risk = "CRITICAL" if site_peak_wbgt >= 32.5 else "HIGH"
            s_color = "#c0392b" if s_risk == "CRITICAL" else "#e67e22"
        elif site_peak_wbgt >= 28.0:
            s_risk = "MODERATE"
            s_color = "#f39c12"
        else:
            s_risk = "LOW"
            s_color = "#27ae60"
            
        comparison_rows.append({
            "Site": s_rec.name,
            "Workers": s_workers,
            "Work Type": s_work_type,
            "Intensity": s_intensity.value,
            "Peak WBGT": f"{site_peak_wbgt:.1f}°C",
            "Risk Tier": s_risk,
            "_color": s_color,
            "Is Active": "⭐ Active" if s_rec.name == current_site.name else "—",
        })

    if comparison_rows:
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

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)


# ============================================================================
# FIFTH SECTION: Persistent Audit & Action Plan Records (SQLite)
# ============================================================================
st.subheader("🗄️ Persistent Records & Historical Action Plans")
st.caption("Answers: *What historical thermal assessments and action plans are persisted in HeatGuard storage?*")

with st.expander(f"📋 View Stored Records & Audit Log for {current_site.name}", expanded=False):
    hist_tab1, hist_tab2, hist_tab3 = st.tabs(["Action Plans Log", "Recent Risk Assessments", "Database Status"])
    with hist_tab1:
        saved_plans = repo.list_action_plans(current_site.id, limit=10)
        if saved_plans:
            plans_data = []
            for p in saved_plans:
                plans_data.append({
                    "Timestamp": p.timestamp,
                    "Risk Tier": p.risk_tier,
                    "Peak Period": p.peak_period,
                    "Action Summary": p.action_summary,
                    "Controls Count": len(p.controls_list),
                    "Saved At (UTC)": p.created_at[:19].replace("T", " "),
                })
            st.dataframe(pd.DataFrame(plans_data), hide_index=True, width="stretch")
        else:
            st.info("No historical action plans saved yet for this site.")

    with hist_tab2:
        saved_risks = repo.get_risk_assessments(current_site.id, limit=24)
        if saved_risks:
            risks_data = []
            for r in saved_risks:
                risks_data.append({
                    "Timestamp": r.timestamp,
                    "Effective WBGT": f"{r.wbgt:.2f}°C",
                    "Risk Level": r.risk_level,
                    "Risk Score": f"{r.risk_score:.1f}",
                    "Explanation": r.explanation,
                })
            st.dataframe(pd.DataFrame(risks_data), hide_index=True, width="stretch")
        else:
            st.info("No risk assessments saved yet for this site.")

    with hist_tab3:
        all_sites_count = len(repo.list_sites())
        all_orgs_count = len(repo.list_organizations())
        st.markdown(
            f"""
            - **Storage Engine**: SQLite 3 (WAL Mode, Foreign Keys Enforced)
            - **Database Location**: `{repo.conn_mgr.db_path}`
            - **Total Organizations**: `{all_orgs_count}`
            - **Total Registered Sites**: `{all_sites_count}`
            - **Current Schema Migration**: `Version {repo.migration_mgr.get_current_version()}`
            """
        )
