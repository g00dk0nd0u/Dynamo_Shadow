import math

from shadow_measurement_plane import _construct_measurement_plane
from shadow_settings import _normalize_settings
from shadow_level_adapter import resolve_average_ground_level


class FakeLevel(object):
    def __init__(self, elevation):
        self.Elevation = elevation


class FakeWrapper(object):
    def __init__(self, elevation):
        self.InternalElement = FakeLevel(elevation)


class UnreadableLevel(object):
    @property
    def Elevation(self):
        raise RuntimeError("unreadable")


def test_level_internal_feet_are_converted_to_meters():
    adapter_result = resolve_average_ground_level(FakeLevel(10.0))
    assert math.isclose(adapter_result["level_elevation_m"], 3.048)
    assert _normalize_settings({}, resolve_average_ground_level(FakeLevel(0.0)))["normalized"]["average_ground_level_elevation_m"] == 0.0
    result = _normalize_settings({}, adapter_result)
    assert math.isclose(result["normalized"]["average_ground_level_elevation_m"], 3.048)
    assert result["average_ground_level_source"] == "revit_level"


def test_wrapper_internal_element_elevation_is_supported():
    result = _normalize_settings({}, resolve_average_ground_level(FakeWrapper(10.0)))
    assert math.isclose(result["normalized"]["average_ground_level_elevation_m"], 3.048)
    assert result["level_used_as_average_ground_level"] is True


def test_valid_level_takes_precedence_over_settings_and_builds_plane():
    result = _normalize_settings({"average_ground_level_elevation_m": 99.0, "measurement_height_m": 4.0}, resolve_average_ground_level(FakeLevel(10.0)))
    assert math.isclose(result["normalized"]["average_ground_level_elevation_m"], 3.048)
    plane = _construct_measurement_plane(result)
    assert math.isclose(plane["elevation_m"], 7.048)
    assert plane["level_used_as_average_ground_level"] is True
    assert plane["level_used_as_measurement_plane"] is False


def test_missing_level_preserves_settings_fallback():
    result = _normalize_settings({"average_ground_level_elevation_m": 12.5}, None)
    assert result["normalized"]["average_ground_level_elevation_m"] == 12.5
    assert result["average_ground_level_source"] == "settings"


def test_missing_level_and_setting_reports_unavailable():
    result = _normalize_settings({}, None)
    assert result["normalized"]["average_ground_level_elevation_m"] is None
    assert result["average_ground_level_source"] == "unavailable"
    assert "average_ground_level_elevation_m" in result["readiness"]["missing_for_measurement_plane"]


def test_invalid_selected_level_does_not_silently_fall_back_to_settings():
    result = _normalize_settings({"average_ground_level_elevation_m": 12.5}, resolve_average_ground_level(UnreadableLevel()))
    assert result["normalized"]["average_ground_level_elevation_m"] is None
    assert result["average_ground_level_source"] == "unavailable_invalid_revit_level"
    assert "average_ground_level_elevation_m" in result["readiness"]["invalid_for_measurement_plane"]
    assert any("not used as a silent fallback" in warning for warning in result["warnings"])
