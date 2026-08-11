import math

import pytest

import shadow_project_location_adapter as adapter
from shadow_sun import _model_direction_from_true_north_azimuth


class _Position:
    def __init__(self, angle):
        self.Angle = angle


class _Location:
    def __init__(self, angle):
        self.angle = angle

    def GetProjectPosition(self, _origin):
        return _Position(self.angle)


class _Document:
    def __init__(self, angle):
        self.ActiveProjectLocation = _Location(angle)


class _XYZ:
    Zero = object()


@pytest.mark.parametrize("rotation_deg", [0.0, 90.0, -90.0, 30.0])
def test_project_position_angle_is_clockwise_project_north_to_true_north(
        monkeypatch, rotation_deg):
    """Revit's positive clockwise PN->TN angle is used without sign inversion."""
    monkeypatch.setattr(adapter, "XYZ", _XYZ)
    result = adapter.resolve_true_north_rotation(
        document=_Document(math.radians(rotation_deg)), revit_runtime=True)
    assert result["true_north_available"] is True
    assert result["true_north_rotation_deg"] == pytest.approx(rotation_deg)
    assert result["true_north_source"] == "revit_active_project_location"


def test_zero_angle_preserves_existing_shadow_direction_exactly():
    _, before = _model_direction_from_true_north_azimuth(217.0, 0.0)
    resolved = adapter.resolve_true_north_rotation(explicit_rotation_rad=0.0)
    _, after = _model_direction_from_true_north_azimuth(
        217.0, resolved["true_north_rotation_deg"])
    assert after == before


@pytest.mark.parametrize("rotation_deg", [90.0, -90.0, 30.0])
def test_clockwise_true_north_rotation_matches_independent_xy_matrix(rotation_deg):
    azimuth = 37.0
    _, base = _model_direction_from_true_north_azimuth(azimuth, 0.0)
    _, actual = _model_direction_from_true_north_azimuth(azimuth, rotation_deg)
    angle = math.radians(rotation_deg)
    expected = {
        "x": base["x"] * math.cos(angle) + base["y"] * math.sin(angle),
        "y": -base["x"] * math.sin(angle) + base["y"] * math.cos(angle),
    }
    assert actual["x"] == pytest.approx(expected["x"])
    assert actual["y"] == pytest.approx(expected["y"])


def test_forward_and_reverse_share_one_resolved_settings_contract():
    resolved = adapter.resolve_true_north_rotation(
        explicit_rotation_rad=math.radians(30.0))
    forward = adapter.apply_true_north_to_settings({}, resolved)
    reverse = adapter.apply_true_north_to_settings({}, resolved)
    assert forward["true_north_deg"] == reverse["true_north_deg"] == pytest.approx(30.0)


def test_unavailable_does_not_silently_apply_zero():
    result = adapter.resolve_true_north_rotation(document=None, revit_runtime=True)
    settings = adapter.apply_true_north_to_settings({"true_north_deg": 0.0}, result)
    assert result["true_north_available"] is False
    assert result["true_north_source"] == "unavailable"
    assert result["true_north_rotation_deg"] is None
    assert "true_north_deg" not in settings
    assert result["warnings"]
