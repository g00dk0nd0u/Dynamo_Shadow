import types

from shadow_graphical_override import (apply_and_readback, _safe_message,
    empty_readback_summary, add_to_readback_summary, aggregate_status)
import shadow_contour_preview
import shadow_preview
import shadow_site_result_preview


class FakeColor:
    def __init__(self, r, g, b):
        self.Red, self.Green, self.Blue = r, g, b
        self.IsValid = True


class FakeOverride:
    def __init__(self):
        self.ProjectionLineColor = None
        self.ProjectionLineWeight = -1

    def SetProjectionLineColor(self, color):
        self.ProjectionLineColor = color

    def SetProjectionLineWeight(self, weight):
        self.ProjectionLineWeight = weight


class FakeView:
    def __init__(self, readback_color=None, readback_weight=None, fail=False):
        self.actual = None
        self.readback_color = readback_color
        self.readback_weight = readback_weight
        self.fail = fail

    def SetElementOverrides(self, element_id, override):
        self.actual = override

    def GetElementOverrides(self, element_id):
        if self.fail:
            raise RuntimeError("readback unavailable")
        return types.SimpleNamespace(
            ProjectionLineColor=self.readback_color or self.actual.ProjectionLineColor,
            ProjectionLineWeight=(self.actual.ProjectionLineWeight if self.readback_weight is None
                                  else self.readback_weight))


def test_matching_red_readback_is_verified():
    result = apply_and_readback(FakeView(), 1, (220, 30, 30), 5,
                                FakeOverride, FakeColor)
    assert result["color_matches_requested"] is True
    assert result["line_weight_matches_requested"] is True
    assert result["verified"] is True


def test_blue_color_mismatch_is_reported():
    view = FakeView(readback_color=FakeColor(0, 0, 0))
    result = apply_and_readback(view, 1, (30, 90, 220), 5,
                                FakeOverride, FakeColor)
    assert result["color_matches_requested"] is False
    assert result["actual_projection_line_color"] == {"r": 0, "g": 0, "b": 0}


def test_line_weight_mismatch_is_reported_without_normalization():
    result = apply_and_readback(FakeView(readback_weight=-1), 1,
                                (0, 0, 0), 2, FakeOverride, FakeColor)
    assert result["actual_projection_line_weight"] == -1
    assert result["line_weight_matches_requested"] is False


def test_readback_exception_is_nonfatal_diagnostic():
    result = apply_and_readback(FakeView(fail=True), 1, (0, 0, 0), 2,
                                FakeOverride, FakeColor)
    assert result["set_succeeded"] is True
    assert result["readback_succeeded"] is False
    assert result["readback_failure_type"] == "RuntimeError"


def test_failure_message_redacts_personal_path():
    assert "/home/person" not in _safe_message(
        RuntimeError("binding failed at /home/person/model.rvt"))


def test_existing_preview_color_and_weight_mapping_is_unchanged():
    assert shadow_preview.HOURLY_SHADOW_COLOR == (0, 0, 0)
    assert shadow_preview.HOURLY_SHADOW_LINE_WEIGHT == 2
    assert shadow_contour_preview.HIGH_DURATION_CONTOUR_COLOR == (220, 30, 30)
    assert shadow_contour_preview.LOW_DURATION_CONTOUR_COLOR == (30, 90, 220)
    assert shadow_contour_preview.CONTOUR_LINE_WEIGHT == 8
    assert shadow_site_result_preview._DISTANCE_STYLES == {
        5.0: ((220, 30, 30), 5), 10.0: ((30, 90, 220), 5)}


def test_write_failure_remains_in_aggregate_verification_denominator():
    summary = empty_readback_summary()
    write_failure = apply_and_readback(
        None, 1, (220, 30, 30), 5, FakeOverride, FakeColor)
    verified = apply_and_readback(
        FakeView(), 2, (220, 30, 30), 5, FakeOverride, FakeColor)
    add_to_readback_summary(summary, write_failure)
    add_to_readback_summary(summary, verified)

    assert summary["attempted_element_count"] == 2
    assert summary["write_failure_count"] == 1
    assert summary["verified_element_count"] == 1
    status = aggregate_status(summary)
    assert status["graphical_overrides_write_succeeded"] is False
    assert status["graphical_overrides_verified"] is False
