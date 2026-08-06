import json

import script
import shadow_inputs


class FatalBoundaryError(BaseException):
    pass


def _set_inputs(monkeypatch, site_boundary=None):
    inputs = {
        "building_elements": None,
        "site_boundary": site_boundary,
        "level": None,
        "settings": None,
    }
    monkeypatch.setattr(script, "INPUTS", inputs, raising=False)
    monkeypatch.setattr(script._shadow_utils, "INPUTS", inputs, raising=False)


def test_optional_boundary_base_exception_degrades_without_stopping_pipeline(monkeypatch):
    _set_inputs(monkeypatch, [object()])

    def crash(_value):
        raise FatalBoundaryError("C:/Users/private/project.rvt")

    monkeypatch.setattr(script, "_diagnose_site_boundary", crash)
    result = script._build_success()

    assert result["success"] is True
    assert result["partial_success"] is True
    assert result["degraded_components"] == ["site_boundary", "site_boundary_area"]
    assert result["shadow_calculation_completed"] is True
    assert result["boundary_dependent_steps_completed"] is False
    assert result["site_boundary"]["error_code"] == "optional_site_boundary_diagnostic_failure"
    assert "Users/private" not in result["site_boundary"]["sanitized_error_message"]
    assert result["footprint_extraction"] is not None
    assert result["sun_position_diagnostics"] is not None
    assert result["shadow_projection_diagnostics"] is not None


def test_no_boundary_is_successful_and_area_player_input(monkeypatch):
    _set_inputs(monkeypatch)
    result = script._build_success()
    graph = json.loads(open("runtime/Shadow.dyn", encoding="utf-8").read())

    assert result["success"] is True
    assert result["partial_success"] is False
    assert result["site_boundary"]["boundary_dependent_steps_available"] is False
    assert any(item["Id"] == "70c7bb6dbe3647b180c23c419e57cc9c" for item in graph["Inputs"])


def test_malformed_boundary_item_does_not_stop_remaining_items(monkeypatch):
    original = shadow_inputs._diagnose_site_boundary_unsafe

    def fail_one(value):
        if value and value[0] == "bad":
            raise FatalBoundaryError("bad boundary")
        return original(value)

    monkeypatch.setattr(shadow_inputs, "_diagnose_site_boundary_unsafe", fail_one)
    result = shadow_inputs._diagnose_site_boundary(["bad", None])

    assert result["count"] == 2
    assert result["rejected_count"] == 2
    assert result["items"][0]["diagnostic_failed"] is True
    assert result["items"][1]["index"] == 1
