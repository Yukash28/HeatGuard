"""
Occupational workforce profiling module for HeatGuard.
Manages exposed worker cohorts, shift schedules, and operational parameters.
"""

from heatguard.workforce.models import (
    AcclimatizationStatus,
    ClothingPPE,
    Organization,
    Site,
    WorkforceProfile,
    WorkIntensity,
    WorkType,
)
from heatguard.workforce.validation import (
    WorkforceValidationError,
    validate_coordinates,
    validate_shift_time,
    validate_worker_count,
)

__all__ = [
    "Organization",
    "Site",
    "WorkforceProfile",
    "WorkType",
    "WorkIntensity",
    "AcclimatizationStatus",
    "ClothingPPE",
    "WorkforceValidationError",
    "validate_worker_count",
    "validate_shift_time",
    "validate_coordinates",
]
