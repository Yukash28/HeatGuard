"""
Domain models for organizations, sites, and occupational workforce profiles.
Designed for cohort thermal exposure decision-support without collecting medical data.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from heatguard.workforce.validation import (
    WorkforceValidationError,
    validate_coordinates,
    validate_non_empty_string,
    validate_shift_time,
    validate_worker_count,
)


class WorkType(str, Enum):
    """Occupational activity category."""
    CONSTRUCTION = "Construction"
    ROAD_HIGHWAY = "Road/Highway"
    DELIVERY_GIG = "Delivery/Gig Work"
    UTILITIES = "Utilities"
    WAREHOUSE_LOGISTICS = "Warehouse/Outdoor Logistics"
    OTHER = "Other"

    @classmethod
    def from_str(cls, value: str) -> "WorkType":
        for member in cls:
            if member.value.lower() == value.strip().lower() or member.name.lower() == value.strip().lower():
                return member
        valid_options = [m.value for m in cls]
        raise WorkforceValidationError(f"Invalid work_type '{value}'. Valid options: {valid_options}")


class WorkIntensity(str, Enum):
    """Metabolic work intensity level."""
    LIGHT = "Light"
    MODERATE = "Moderate"
    HEAVY = "Heavy"

    @classmethod
    def from_str(cls, value: str) -> "WorkIntensity":
        for member in cls:
            if member.value.lower() == value.strip().lower() or member.name.lower() == value.strip().lower():
                return member
        valid_options = [m.value for m in cls]
        raise WorkforceValidationError(f"Invalid work_intensity '{value}'. Valid options: {valid_options}")


class AcclimatizationStatus(str, Enum):
    """Cohort heat acclimatization status."""
    ACCLIMATIZED = "Acclimatized"
    UNACCLIMATIZED = "Unacclimatized"
    MIXED = "Mixed"

    @classmethod
    def from_str(cls, value: str) -> "AcclimatizationStatus":
        for member in cls:
            if member.value.lower() == value.strip().lower() or member.name.lower() == value.strip().lower():
                return member
        valid_options = [m.value for m in cls]
        raise WorkforceValidationError(f"Invalid acclimatization_status '{value}'. Valid options: {valid_options}")


class ClothingPPE(str, Enum):
    """Typical occupational clothing or protective equipment."""
    STANDARD_WORKWEAR = "Standard Workwear"
    COVERALLS_DOUBLE_LAYER = "Coveralls / Double Layer"
    IMPERMEABLE_PPE = "Impermeable / Chemical PPE"
    HI_VIS_VEST_HELMET = "Hi-Vis Vest + Safety Helmet"

    @classmethod
    def from_str(cls, value: str) -> "ClothingPPE":
        for member in cls:
            if member.value.lower() == value.strip().lower() or member.name.lower() == value.strip().lower():
                return member
        # Return fallback string if custom PPE description
        return cls.STANDARD_WORKWEAR


@dataclass
class Organization:
    """Enterprise, contractor, or government body managing work sites."""
    id: str
    name: str

    def __post_init__(self):
        self.id = validate_non_empty_string(str(self.id), "Organization ID")
        self.name = validate_non_empty_string(str(self.name), "Organization Name")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Organization":
        return cls(id=data["id"], name=data["name"])


@dataclass
class Site:
    """Geographic facility or project zone where workers are deployed."""
    id: str
    organization_id: str
    name: str
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"

    def __post_init__(self):
        self.id = validate_non_empty_string(str(self.id), "Site ID")
        self.organization_id = validate_non_empty_string(str(self.organization_id), "Organization ID")
        self.name = validate_non_empty_string(str(self.name), "Site Name")
        self.latitude, self.longitude = validate_coordinates(self.latitude, self.longitude)
        self.timezone = validate_non_empty_string(str(self.timezone), "Timezone")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Site":
        return cls(
            id=data["id"],
            organization_id=data["organization_id"],
            name=data["name"],
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            timezone=data.get("timezone", "Asia/Kolkata"),
        )


@dataclass
class WorkforceProfile:
    """
    Occupational cohort profile describing an exposed group of workers.
    Strictly cohort-level operational data: no personal or medical records.
    """
    id: str
    site_id: str
    number_of_workers: int
    work_type: WorkType
    work_intensity: WorkIntensity
    shift_start: str
    shift_end: str
    clothing_or_ppe: str
    acclimatization_status: AcclimatizationStatus

    def __post_init__(self):
        self.id = validate_non_empty_string(str(self.id), "WorkforceProfile ID")
        self.site_id = validate_non_empty_string(str(self.site_id), "Site ID")
        self.number_of_workers = validate_worker_count(self.number_of_workers)

        if not isinstance(self.work_type, WorkType):
            self.work_type = WorkType.from_str(str(self.work_type))

        if not isinstance(self.work_intensity, WorkIntensity):
            self.work_intensity = WorkIntensity.from_str(str(self.work_intensity))

        self.shift_start = validate_shift_time(self.shift_start)
        self.shift_end = validate_shift_time(self.shift_end)

        self.clothing_or_ppe = validate_non_empty_string(str(self.clothing_or_ppe), "Clothing/PPE")

        if not isinstance(self.acclimatization_status, AcclimatizationStatus):
            self.acclimatization_status = AcclimatizationStatus.from_str(str(self.acclimatization_status))

    def shift_duration_hours(self) -> float:
        """Calculate the total duration of the shift in hours."""
        start_h, start_m = map(int, self.shift_start.split(":"))
        end_h, end_m = map(int, self.shift_end.split(":"))
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        if end_minutes >= start_minutes:
            duration_minutes = end_minutes - start_minutes
        else:
            # Overnight shift (e.g. 22:00 to 06:00)
            duration_minutes = (24 * 60 - start_minutes) + end_minutes

        return round(duration_minutes / 60.0, 2)

    def is_shift_active(self, hour: int) -> bool:
        """
        Determine whether a given hour (0-23) falls within the shift window.
        Correctly accounts for daytime and overnight shifts.
        """
        start_h = int(self.shift_start.split(":")[0])
        end_h = int(self.shift_end.split(":")[0])

        if start_h <= end_h:
            # Standard daytime shift (e.g. 08:00 to 17:00)
            return start_h <= hour <= end_h
        else:
            # Overnight shift (e.g. 21:00 to 05:00)
            return hour >= start_h or hour <= end_h

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "site_id": self.site_id,
            "number_of_workers": self.number_of_workers,
            "work_type": self.work_type.value,
            "work_intensity": self.work_intensity.value,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
            "clothing_or_ppe": self.clothing_or_ppe,
            "acclimatization_status": self.acclimatization_status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkforceProfile":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            site_id=data["site_id"],
            number_of_workers=int(data["number_of_workers"]),
            work_type=WorkType.from_str(data["work_type"]),
            work_intensity=WorkIntensity.from_str(data["work_intensity"]),
            shift_start=data["shift_start"],
            shift_end=data["shift_end"],
            clothing_or_ppe=data.get("clothing_or_ppe", ClothingPPE.STANDARD_WORKWEAR.value),
            acclimatization_status=AcclimatizationStatus.from_str(data["acclimatization_status"]),
        )
