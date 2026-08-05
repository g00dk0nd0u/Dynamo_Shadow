import copy
import math

import pytest

from shadow_regulatory_comparison import build_legal_judgement_skeleton, build_selected_limit_comparison
from shadow_regulatory_presets import resolve_regulatory_shadow_preset


def masks(near=225.0, far=140.0):
    return {"available": True, "complete": True, "boundary_dependent_ready": True,
            "near": {"available": True, "maximum_shadow_duration_minutes": near, "point": {"x_m": 10.0, "y_m": 20.0, "distance_from_site_boundary_m": 7.2}},
            "far": {"available": True, "maximum_shadow_duration_minutes": far, "point": {"x_m": 10.0, "y_m": 30.0, "distance_from_site_boundary_m": 14.5}},
            "blockers": [], "warnings": []}


def duration(complete=True, coverage=True):
    return {"complete": complete, "boundary_evaluation_coverage_complete": coverage,
            "method": "grid_trapezoidal_time_integration_v1", "spatial_resolution_m": 0.5,
            "temporal_step_minutes": 15.0}


@pytest.mark.parametrize("preset_id,ready,near,far", [
    ("standard_all", False, None, None), ("hokkaido_all", False, None, None),
    ("standard_3_2", True, 180.0, 120.0), ("standard_4_2_5", True, 240.0, 150.0),
    ("standard_5_3", True, 300.0, 180.0), ("hokkaido_2_1_5", True, 120.0, 90.0),
    ("hokkaido_3_2", True, 180.0, 120.0), ("hokkaido_4_2_5", True, 240.0, 150.0),
])
def test_preset_resolution_comparison_metadata(preset_id, ready, near, far):
    p = resolve_regulatory_shadow_preset(preset_id)
    assert p["comparison_ready"] is ready
    assert p["near_limit_minutes"] == near
    assert p["far_limit_minutes"] == far
    assert p["selection_source"] == "dynamo_player_user_selection"
    assert p["ordinance_applicability_confirmed"] is False


def test_invalid_preset_metadata():
    p = resolve_regulatory_shadow_preset("bad")
    assert p["valid"] is False
    assert p["comparison_ready"] is False


@pytest.mark.parametrize("near,far,overall,near_status,far_status", [
    (225, 140, "within_selected_limits", "within_selected_limit", "within_selected_limit"),
    (240, 140, "within_selected_limits", "within_selected_limit", "within_selected_limit"),
    (225, 150, "within_selected_limits", "within_selected_limit", "within_selected_limit"),
    (240.0000005, 140, "within_selected_limits", "within_selected_limit", "within_selected_limit"),
    (225, 150.0000005, "within_selected_limits", "within_selected_limit", "within_selected_limit"),
    (241, 140, "exceeds_selected_limits", "exceeds_selected_limit", "within_selected_limit"),
    (225, 151, "exceeds_selected_limits", "within_selected_limit", "exceeds_selected_limit"),
    (241, 151, "exceeds_selected_limits", "exceeds_selected_limit", "exceeds_selected_limit"),
])
def test_zone_comparison_statuses(near, far, overall, near_status, far_status):
    result = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), masks(near, far), duration())
    assert result["complete"] is True
    assert result["status"] == overall
    assert result["near"]["status"] == near_status
    assert result["far"]["status"] == far_status


def test_difference_excess_margin_and_point_contract():
    result = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), masks(245, 130), duration())
    assert result["near"]["difference_minutes"] == 5.0
    assert result["near"]["excess_minutes"] == 5.0
    assert result["near"]["remaining_margin_minutes"] == -5.0
    assert result["far"]["difference_minutes"] == -20.0
    assert result["far"]["excess_minutes"] == 0.0
    assert result["far"]["remaining_margin_minutes"] == 20.0
    assert result["near"]["point"]["distance_from_site_boundary_m"] == 7.2


@pytest.mark.parametrize("near,far", [(math.nan, 140), (math.inf, 140), (225, math.nan), (225, math.inf)])
def test_non_finite_observed_is_undetermined(near, far):
    result = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), masks(near, far), duration())
    assert result["status"] == "undetermined"
    assert result["complete"] is False


def test_nan_limit_is_undetermined():
    p = resolve_regulatory_shadow_preset("standard_4_2_5")
    p["near_limit_minutes"] = math.nan
    assert build_selected_limit_comparison(p, masks(), duration())["status"] == "undetermined"


@pytest.mark.parametrize("epsilon", [math.nan, -1.0])
def test_invalid_epsilon(epsilon):
    r = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), masks(), duration(), comparison_epsilon_minutes=epsilon)
    assert r["blockers"][0]["failure_code"] == "invalid_comparison_epsilon_minutes"


@pytest.mark.parametrize("edit,code", [
    (lambda m: m.__setitem__("near", {"available": False}), "near_measurement_mask_required"),
    (lambda m: m.__setitem__("far", {"available": False}), "far_measurement_mask_required"),
    (lambda m: m.__setitem__("complete", False), "complete_measurement_masks_required"),
    (lambda m: m.__setitem__("boundary_dependent_ready", False), "complete_measurement_masks_required"),
])
def test_mask_preconditions(edit, code):
    m = masks(); edit(m)
    r = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), m, duration())
    assert r["status"] == "undetermined"
    assert r["blockers"][0]["failure_code"] == code


@pytest.mark.parametrize("d,code", [(duration(False, True), "complete_shadow_duration_required"), (duration(True, False), "boundary_evaluation_coverage_complete_required")])
def test_duration_preconditions(d, code):
    r = build_selected_limit_comparison(resolve_regulatory_shadow_preset("standard_4_2_5"), masks(), d)
    assert r["blockers"][0]["failure_code"] == code


@pytest.mark.parametrize("preset_id", ["standard_all", "hokkaido_all"])
def test_all_preset_is_undetermined_not_failure(preset_id):
    r = build_selected_limit_comparison(resolve_regulatory_shadow_preset(preset_id), masks(), duration())
    assert r["status"] == "undetermined"
    assert r["blockers"][0]["failure_code"] == "regulatory_limit_pair_not_selected"


def test_invalid_preset_is_undetermined():
    assert build_selected_limit_comparison(resolve_regulatory_shadow_preset("bad"), masks(), duration())["status"] == "undetermined"


def test_inputs_are_not_mutated():
    p = resolve_regulatory_shadow_preset("standard_4_2_5"); m = masks(); d = duration()
    before = copy.deepcopy((p, m, d))
    build_selected_limit_comparison(p, m, d)
    assert (p, m, d) == before


@pytest.mark.parametrize("status", ["within_selected_limits", "exceeds_selected_limits"])
def test_legal_skeleton_always_undetermined(status):
    legal = build_legal_judgement_skeleton({"status": status})
    assert legal["status"] == "undetermined"
    assert legal["selected_limit_comparison_status"] == status
    assert legal["blockers"][0]["failure_code"] == "ordinance_applicability_not_certified"
    assert legal["legal_judgement_generated"] is False
    assert legal["ordinance_selection_certified"] is False
    assert legal["permit_ready_certified"] is False
