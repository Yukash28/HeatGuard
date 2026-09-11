"""
Tests for Organization, Site, and WorkforceProfile models and validations.
"""

import pytest

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


# --- Organization & Site Tests -----------------------------------------------

def test_create_organization_valid():
    org = Organization(id="org-1", name="Apex Infrastructure")
    assert org.id == "org-1"
    assert org.name == "Apex Infrastructure"
    d = org.to_dict()
    assert d["id"] == "org-1"
    reconstructed = Organization.from_dict(d)
    assert reconstructed.name == org.name


def test_organization_empty_name_raises():
    with pytest.raises(WorkforceValidationError, match="cannot be empty"):
        Organization(id="org-1", name="   ")


def test_create_site_valid():
    site = Site(
        id="site-blr-1",
        organization_id="org-1",
        name="Bengaluru Metro Line 4 Site",
        latitude=12.9716,
        longitude=77.5946,
    )
    assert site.latitude == 12.9716
    assert site.timezone == "Asia/Kolkata"
    d = site.to_dict()
    reconstructed = Site.from_dict(d)
    assert reconstructed.name == site.name


def test_site_invalid_coordinates():
    with pytest.raises(WorkforceValidationError, match="Latitude must be between -90 and 90"):
        Site(id="s1", organization_id="o1", name="Polar", latitude=95.0, longitude=0.0)

    with pytest.raises(WorkforceValidationError, match="Longitude must be between -180 and 180"):
        Site(id="s1", organization_id="o1", name="FarEast", latitude=0.0, longitude=185.0)


# --- WorkforceProfile Validation Tests ---------------------------------------

def test_workforce_profile_creation_valid():
    profile = WorkforceProfile(
        id="wf-1",
        site_id="site-blr-1",
        number_of_workers=35,
        work_type=WorkType.CONSTRUCTION,
        work_intensity=WorkIntensity.HEAVY,
        shift_start="08:00",
        shift_end="17:00",
        clothing_or_ppe=ClothingPPE.HI_VIS_VEST_HELMET.value,
        acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    assert profile.number_of_workers == 35
    assert profile.work_type == WorkType.CONSTRUCTION
    assert profile.work_intensity == WorkIntensity.HEAVY
    assert profile.shift_duration_hours() == 9.0


def test_workforce_profile_from_string_enums():
    profile = WorkforceProfile(
        id="wf-2",
        site_id="site-blr-1",
        number_of_workers=10,
        work_type="Delivery/Gig Work",  # string converted to Enum
        work_intensity="moderate",      # case-insensitive
        shift_start="09:00",
        shift_end="18:00",
        clothing_or_ppe="Standard Workwear",
        acclimatization_status="mixed",
    )
    assert profile.work_type == WorkType.DELIVERY_GIG
    assert profile.work_intensity == WorkIntensity.MODERATE
    assert profile.acclimatization_status == AcclimatizationStatus.MIXED


def test_invalid_worker_count():
    with pytest.raises(WorkforceValidationError, match="at least 1"):
        validate_worker_count(0)

    with pytest.raises(WorkforceValidationError, match="at least 1"):
        validate_worker_count(-5)

    with pytest.raises(WorkforceValidationError, match="exceeds reasonable"):
        validate_worker_count(60000)

    with pytest.raises(TypeError, match="integer"):
        validate_worker_count("25")  # type: ignore


def test_invalid_shift_time():
    assert validate_shift_time("8:30") == "08:30"
    assert validate_shift_time("23:59") == "23:59"

    with pytest.raises(WorkforceValidationError, match="between 00 and 23"):
        validate_shift_time("25:00")

    with pytest.raises(WorkforceValidationError, match="between 00 and 59"):
        validate_shift_time("12:65")

    with pytest.raises(WorkforceValidationError, match="24-hour"):
        validate_shift_time("invalid")


def test_invalid_enums():
    with pytest.raises(WorkforceValidationError, match="Invalid work_type"):
        WorkType.from_str("Underwater Welding")

    with pytest.raises(WorkforceValidationError, match="Invalid work_intensity"):
        WorkIntensity.from_str("Extreme")

    with pytest.raises(WorkforceValidationError, match="Invalid acclimatization_status"):
        AcclimatizationStatus.from_str("Immune")


# --- Shift Hours & Active Checks --------------------------------------------

def test_shift_duration_normal_and_overnight():
    day_profile = WorkforceProfile(
        id="w1", site_id="s1", number_of_workers=5,
        work_type=WorkType.UTILITIES, work_intensity=WorkIntensity.LIGHT,
        shift_start="07:30", shift_end="16:00",
        clothing_or_ppe="Standard", acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    assert day_profile.shift_duration_hours() == 8.5

    night_profile = WorkforceProfile(
        id="w2", site_id="s1", number_of_workers=5,
        work_type=WorkType.ROAD_HIGHWAY, work_intensity=WorkIntensity.HEAVY,
        shift_start="22:00", shift_end="06:00",
        clothing_or_ppe="Hi-Vis", acclimatization_status=AcclimatizationStatus.UNACCLIMATIZED,
    )
    assert night_profile.shift_duration_hours() == 8.0


def test_is_shift_active_normal():
    profile = WorkforceProfile(
        id="w1", site_id="s1", number_of_workers=10,
        work_type=WorkType.CONSTRUCTION, work_intensity=WorkIntensity.HEAVY,
        shift_start="08:00", shift_end="17:00",
        clothing_or_ppe="Standard", acclimatization_status=AcclimatizationStatus.ACCLIMATIZED,
    )
    assert profile.is_shift_active(8) is True
    assert profile.is_shift_active(12) is True
    assert profile.is_shift_active(17) is True
    assert profile.is_shift_active(7) is False
    assert profile.is_shift_active(18) is False
    assert profile.is_shift_active(23) is False


def test_is_shift_active_overnight():
    profile = WorkforceProfile(
        id="w2", site_id="s1", number_of_workers=8,
        work_type=WorkType.ROAD_HIGHWAY, work_intensity=WorkIntensity.HEAVY,
        shift_start="21:00", shift_end="05:00",
        clothing_or_ppe="Standard", acclimatization_status=AcclimatizationStatus.UNACCLIMATIZED,
    )
    assert profile.is_shift_active(21) is True
    assert profile.is_shift_active(23) is True
    assert profile.is_shift_active(0) is True
    assert profile.is_shift_active(4) is True
    assert profile.is_shift_active(5) is True
    assert profile.is_shift_active(6) is False
    assert profile.is_shift_active(14) is False
    assert profile.is_shift_active(20) is False


# --- Serialization Roundtrip ------------------------------------------------

def test_workforce_profile_serialization():
    original = WorkforceProfile(
        id="wf-99",
        site_id="site-blr-1",
        number_of_workers=42,
        work_type=WorkType.WAREHOUSE_LOGISTICS,
        work_intensity=WorkIntensity.MODERATE,
        shift_start="06:00",
        shift_end="14:30",
        clothing_or_ppe=ClothingPPE.COVERALLS_DOUBLE_LAYER.value,
        acclimatization_status=AcclimatizationStatus.MIXED,
    )
    data = original.to_dict()
    assert data["number_of_workers"] == 42
    assert data["work_type"] == "Warehouse/Outdoor Logistics"

    restored = WorkforceProfile.from_dict(data)
    assert restored.id == original.id
    assert restored.number_of_workers == original.number_of_workers
    assert restored.work_type == original.work_type
    assert restored.work_intensity == original.work_intensity
    assert restored.shift_start == original.shift_start
    assert restored.shift_end == original.shift_end
    assert restored.acclimatization_status == original.acclimatization_status
