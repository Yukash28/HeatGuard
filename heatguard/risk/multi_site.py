"""
Multi-site aggregation and evaluation engine for HeatGuard.
Computes organization-level metrics and rolled-up site exposure summaries.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Callable, Dict, List, Optional

from heatguard.risk.engine import assess_hourly_forecast_risk
from heatguard.risk.models import OccupationalRiskLevel, RiskAssessmentResult
from heatguard.storage.models import SiteRecord, WorkforceProfileRecord
from heatguard.storage.repository import HeatGuardRepository
from heatguard.thermal.weather import get_hourly_risk_forecast
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    Site,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)

logger = logging.getLogger(__name__)


@dataclass
class SiteSummary:
    """Summary of thermal conditions and risk exposure for a single site."""
    site_id: str
    name: str
    location_str: str
    latitude: float
    longitude: float
    workers: int
    work_type: str
    work_intensity: str
    current_wbgt: float
    peak_wbgt: float
    peak_wbgt_time: str
    current_risk_level: OccupationalRiskLevel
    current_risk_score: float
    peak_risk_level: OccupationalRiskLevel
    peak_risk_score: float
    peak_risk_period: str
    is_fallback: bool
    data_source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "name": self.name,
            "location": self.location_str,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "workers": self.workers,
            "work_type": self.work_type,
            "work_intensity": self.work_intensity,
            "current_wbgt": round(self.current_wbgt, 1),
            "peak_wbgt": round(self.peak_wbgt, 1),
            "peak_wbgt_time": self.peak_wbgt_time,
            "current_risk": self.current_risk_level.value,
            "current_risk_score": round(self.current_risk_score, 1),
            "peak_risk": self.peak_risk_level.value,
            "peak_risk_score": round(self.peak_risk_score, 1),
            "peak_risk_period": self.peak_risk_period,
            "is_fallback": self.is_fallback,
        }


@dataclass
class OrganizationOverview:
    """Enterprise-level aggregated heat exposure rollup across multiple worksites."""
    org_id: str
    org_name: str
    total_sites: int
    total_workers: int
    high_risk_sites_count: int
    critical_risk_sites_count: int
    moderate_risk_sites_count: int
    low_risk_sites_count: int
    sites: List[SiteSummary]


def evaluate_site_summary(
    site_record: SiteRecord,
    wf_record: Optional[WorkforceProfileRecord],
    forecast_fetcher: Optional[Callable[..., List[Dict[str, Any]]]] = None,
) -> SiteSummary:
    """
    Evaluate 24h thermal exposure and risk metrics for a single site.
    """
    fetch_fn = forecast_fetcher or get_hourly_risk_forecast

    # Construct domain site
    domain_site = site_record.to_domain()

    # Construct or default workforce profile
    if wf_record:
        wf_profile = wf_record.to_domain()
    else:
        wf_profile = WorkforceProfile(
            id=f"wf-{site_record.id}",
            site_id=site_record.id,
            number_of_workers=50,
            work_type=WorkType.CONSTRUCTION,
            work_intensity=WorkIntensity.HEAVY,
            shift_start="08:00",
            shift_end="17:00",
            clothing_or_ppe=ClothingPPE.STANDARD_WORKWEAR.value,
            acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
        )

    # Fetch 24-hour forecast
    try:
        records = fetch_fn(
            latitude=domain_site.latitude,
            longitude=domain_site.longitude,
            timezone=domain_site.timezone,
            hours_ahead=24,
            forecast_days=1,
        )
    except Exception as exc:
        logger.warning("Forecast fetch failed for site %s: %s", site_record.name, exc)
        records = []

    if not records:
        # Fallback dummy record if no data available
        records = [{
            "timestamp": datetime.now().strftime("%Y-%m-%dT12:00:00"),
            "temp_c": 30.0,
            "humidity": 65.0,
            "wind_kmh": 10.0,
            "radiation": 400.0,
            "wbgt_c": 27.5,
            "is_fallback": True,
            "data_source": "Offline Baseline",
        }]

    # Assess hourly risk
    risks = assess_hourly_forecast_risk(records, wf_profile)

    # Calculate metrics
    current_weather = records[0]
    current_risk = risks[0]
    current_wbgt = float(current_weather["wbgt_c"])

    # Peak WBGT
    peak_idx = max(range(len(records)), key=lambda i: float(records[i]["wbgt_c"]))
    peak_wbgt = float(records[peak_idx]["wbgt_c"])
    peak_time = records[peak_idx]["timestamp"].split("T")[1][:5]

    # Peak Risk
    shift_risks = [r for r in risks if r.is_during_shift]
    eval_risks = shift_risks if shift_risks else risks
    max_risk = max(eval_risks, key=lambda r: r.risk_score)

    # Peak Risk Period
    elevated_hours = [
        records[i]["timestamp"].split("T")[1][:5]
        for i, r in enumerate(risks)
        if r.risk_level in (OccupationalRiskLevel.HIGH, OccupationalRiskLevel.CRITICAL)
    ]

    if elevated_hours:
        peak_period = f"{elevated_hours[0]} – {elevated_hours[-1]}"
    else:
        p_dt = datetime.fromisoformat(records[peak_idx]["timestamp"])
        start_str = p_dt.replace(hour=max(0, p_dt.hour - 1)).strftime("%H:00")
        end_str = p_dt.replace(hour=min(23, p_dt.hour + 2)).strftime("%H:00")
        peak_period = f"{start_str} – {end_str}"

    loc_str = f"{domain_site.latitude:.4f}° N, {domain_site.longitude:.4f}° E"

    return SiteSummary(
        site_id=domain_site.id,
        name=domain_site.name,
        location_str=loc_str,
        latitude=domain_site.latitude,
        longitude=domain_site.longitude,
        workers=wf_profile.number_of_workers,
        work_type=wf_profile.work_type.value,
        work_intensity=wf_profile.work_intensity.value,
        current_wbgt=current_wbgt,
        peak_wbgt=peak_wbgt,
        peak_wbgt_time=peak_time,
        current_risk_level=current_risk.risk_level,
        current_risk_score=current_risk.risk_score,
        peak_risk_level=max_risk.risk_level,
        peak_risk_score=max_risk.risk_score,
        peak_risk_period=peak_period,
        is_fallback=records[0].get("is_fallback", False),
        data_source=records[0].get("data_source", "Open-Meteo"),
    )


def evaluate_organization_overview(
    repo: HeatGuardRepository,
    org_id: Optional[str] = None,
    forecast_fetcher: Optional[Callable[..., List[Dict[str, Any]]]] = None,
) -> OrganizationOverview:
    """
    Aggregate and compute multi-site metrics for an organization.
    """
    all_orgs = repo.list_organizations()
    if not all_orgs:
        repo.seed_default_presets()
        all_orgs = repo.list_organizations()

    target_org = None
    if org_id:
        target_org = repo.get_organization(org_id)

    if not target_org:
        # Default to first organization (e.g. ABC Construction)
        target_org = all_orgs[0]

    sites = repo.list_sites(organization_id=target_org.id)
    if not sites:
        # If no sites under target org, check all sites
        sites = repo.list_sites()

    summaries: List[SiteSummary] = []
    total_workers = 0
    high_risk_count = 0
    critical_risk_count = 0
    moderate_risk_count = 0
    low_risk_count = 0

    for site in sites:
        wf = repo.get_workforce_profile(site.id)
        summary = evaluate_site_summary(site, wf, forecast_fetcher=forecast_fetcher)
        summaries.append(summary)

        total_workers += summary.workers

        # Count by peak risk level
        if summary.peak_risk_level == OccupationalRiskLevel.CRITICAL:
            critical_risk_count += 1
        elif summary.peak_risk_level == OccupationalRiskLevel.HIGH:
            high_risk_count += 1
        elif summary.peak_risk_level == OccupationalRiskLevel.MODERATE:
            moderate_risk_count += 1
        else:
            low_risk_count += 1

    return OrganizationOverview(
        org_id=target_org.id,
        org_name=target_org.name,
        total_sites=len(summaries),
        total_workers=total_workers,
        high_risk_sites_count=high_risk_count,
        critical_risk_sites_count=critical_risk_count,
        moderate_risk_sites_count=moderate_risk_count,
        low_risk_sites_count=low_risk_count,
        sites=summaries,
    )
