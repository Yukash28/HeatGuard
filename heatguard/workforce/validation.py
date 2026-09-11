"""
Validation rules and constraints for workforce profiles and site configurations.
"""

import re
from numbers import Integral, Real
from typing import Any, Tuple


class WorkforceValidationError(ValueError):
    """Raised when workforce profile or site attributes fail validation checks."""


def validate_worker_count(count: Any) -> int:
    """
    Validate the number of exposed workers in a cohort.
    Must be an integer between 1 and 50,000.
    """
    if not isinstance(count, Integral) or isinstance(count, bool):
        raise TypeError(f"Worker count must be an integer, got {type(count).__name__}")

    int_count = int(count)
    if int_count < 1:
        raise WorkforceValidationError(f"Worker count must be at least 1, got {int_count}")
    if int_count > 50000:
        raise WorkforceValidationError(f"Worker count exceeds reasonable single-site maximum of 50,000, got {int_count}")

    return int_count


def validate_shift_time(time_str: str) -> str:
    """
    Validate shift time string format (24-hour 'HH:MM').
    Returns canonical 'HH:MM' string.
    """
    if not isinstance(time_str, str):
        raise TypeError(f"Shift time must be a string, got {type(time_str).__name__}")

    stripped = time_str.strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", stripped)
    if not match:
        raise WorkforceValidationError(f"Shift time must be in 'HH:MM' (24-hour) format, got '{time_str}'")

    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours <= 23):
        raise WorkforceValidationError(f"Shift hour must be between 00 and 23, got {hours}")
    if not (0 <= minutes <= 59):
        raise WorkforceValidationError(f"Shift minute must be between 00 and 59, got {minutes}")

    return f"{hours:02d}:{minutes:02d}"


def validate_coordinates(latitude: Any, longitude: Any) -> Tuple[float, float]:
    """
    Validate geographical coordinates for a work site.
    """
    if not isinstance(latitude, Real) or not isinstance(longitude, Real):
        raise TypeError("Latitude and longitude must be numeric")

    lat = float(latitude)
    lon = float(longitude)

    if not (-90.0 <= lat <= 90.0):
        raise WorkforceValidationError(f"Latitude must be between -90 and 90, got {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise WorkforceValidationError(f"Longitude must be between -180 and 180, got {lon}")

    return lat, lon


def validate_non_empty_string(value: Any, field_name: str) -> str:
    """
    Validate that a string attribute is non-empty after trimming whitespace.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")

    cleaned = value.strip()
    if not cleaned:
        raise WorkforceValidationError(f"{field_name} cannot be empty")

    return cleaned
