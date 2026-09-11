"""
Storage data models and domain mapping utilities for HeatGuard persistence.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid

from heatguard.risk.models import OccupationalRiskLevel, RecommendedControl, RiskAssessmentResult, RiskFactor
from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    Organization,
    Site,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)


@dataclass
class OrganizationRecord:
    id: str
    name: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_domain(self) -> Organization:
        return Organization(id=self.id, name=self.name)

    @classmethod
    def from_domain(cls, org: Organization, created_at: Optional[str] = None) -> "OrganizationRecord":
        return cls(
            id=org.id,
            name=org.name,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class SiteRecord:
    id: str
    organization_id: str
    name: str
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now_iso
        if not self.updated_at:
            self.updated_at = now_iso

    def to_domain(self) -> Site:
        return Site(
            id=self.id,
            organization_id=self.organization_id,
            name=self.name,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
        )

    @classmethod
    def from_domain(
        cls,
        site: Site,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> "SiteRecord":
        now_iso = datetime.now(timezone.utc).isoformat()
        return cls(
            id=site.id,
            organization_id=site.organization_id,
            name=site.name,
            latitude=site.latitude,
            longitude=site.longitude,
            timezone=site.timezone,
            created_at=created_at or now_iso,
            updated_at=updated_at or now_iso,
        )


@dataclass
class WorkforceProfileRecord:
    id: str
    site_id: str
    workers: int
    work_type: str
    work_intensity: str
    ppe: str
    acclimatization: str
    shift_start: str
    shift_end: str
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_domain(self) -> WorkforceProfile:
        return WorkforceProfile(
            id=self.id,
            site_id=self.site_id,
            number_of_workers=self.workers,
            work_type=WorkType.from_str(self.work_type),
            work_intensity=WorkIntensity.from_str(self.work_intensity),
            shift_start=self.shift_start,
            shift_end=self.shift_end,
            clothing_or_ppe=self.ppe,
            acclimatization_status=AcclimatizationStatus.from_str(self.acclimatization),
        )

    @classmethod
    def from_domain(
        cls,
        profile: WorkforceProfile,
        updated_at: Optional[str] = None,
    ) -> "WorkforceProfileRecord":
        return cls(
            id=profile.id,
            site_id=profile.site_id,
            workers=profile.number_of_workers,
            work_type=profile.work_type.value,
            work_intensity=profile.work_intensity.value,
            ppe=profile.clothing_or_ppe,
            acclimatization=profile.acclimatization_status.value,
            shift_start=profile.shift_start,
            shift_end=profile.shift_end,
            updated_at=updated_at or datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class WeatherSnapshotRecord:
    id: str
    site_id: str
    timestamp: str
    temperature_c: float
    relative_humidity: float
    wind_speed_kmh: float
    solar_radiation: float = 0.0
    data_source: str = "Open-Meteo"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class WbgtCalculationRecord:
    id: str
    site_id: str
    timestamp: str
    wbgt_c: float
    effective_wbgt_c: float
    heat_index_c: float
    method: str = "Liljegren"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class RiskAssessmentRecord:
    id: str
    site_id: str
    timestamp: str
    wbgt: float
    risk_level: str
    risk_score: float
    explanation: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_domain(
        cls,
        site_id: str,
        result: RiskAssessmentResult,
        record_id: Optional[str] = None,
    ) -> "RiskAssessmentRecord":
        return cls(
            id=record_id or f"risk-{uuid.uuid4().hex[:10]}",
            site_id=site_id,
            timestamp=result.timestamp,
            wbgt=result.effective_wbgt_c,
            risk_level=result.risk_level.value,
            risk_score=result.risk_score,
            explanation=result.explanation,
        )


@dataclass
class ActionPlanRecord:
    id: str
    site_id: str
    timestamp: str
    risk_tier: str
    peak_period: str
    action_summary: str
    controls_json: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def controls_list(self) -> List[Dict[str, str]]:
        try:
            return json.loads(self.controls_json)
        except Exception:
            return []


