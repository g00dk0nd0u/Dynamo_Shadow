"""Pure-Python selected regulatory shadow-limit comparison helpers."""
import copy
import math

METHOD = "selected_regulatory_limit_comparison_v1"
BASIS = "user_selected_dynamo_player_preset"
WARNING = "This is a numerical comparison against the user-selected preset, not a certified legal judgement."
ALL_PRESET_REASON = "Select a specific near/far limit pair instead of an All preset. All / 全候補ではなく、個別の規制時間を選択してください。"


def _finite(value):
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _blocker(code, reason=None):
    item = {"failure_code": code}
    if reason:
        item["reason"] = reason
    return item


def _base(status="undetermined", blockers=None, warnings=None):
    return {
        "available": False,
        "complete": False,
        "method": METHOD,
        "status": status,
        "comparison_basis": BASIS,
        "preset": None,
        "near": {"zone": "5m_to_10m", "status": "undetermined"},
        "far": {"zone": "over_10m", "status": "undetermined"},
        "numerical_context": {},
        "ordinance_applicability_confirmed": False,
        "ordinance_selection_certified": False,
        "legal_judgement_generated": False,
        "permit_ready_certified": False,
        "blockers": list(blockers or []),
        "warnings": list(warnings or [WARNING]),
    }


def _preset_summary(preset):
    preset = preset if isinstance(preset, dict) else {}
    return {
        "preset_id": preset.get("preset_id"),
        "profile": preset.get("profile"),
        "true_solar_start_time": preset.get("true_solar_start_time"),
        "true_solar_end_time": preset.get("true_solar_end_time"),
        "near_limit_minutes": preset.get("near_limit_minutes"),
        "far_limit_minutes": preset.get("far_limit_minutes"),
    }


def _context(shadow_duration, settings_normalized, epsilon):
    duration = shadow_duration if isinstance(shadow_duration, dict) else {}
    normalized = ((settings_normalized or {}).get("normalized") or {}) if isinstance(settings_normalized, dict) else {}
    return {
        "spatial_resolution_m": duration.get("spatial_resolution_m", normalized.get("grid_resolution_m")),
        "temporal_step_minutes": duration.get("temporal_step_minutes", normalized.get("sun_time_step_minutes")),
        "duration_method": duration.get("method", "grid_trapezoidal_time_integration_v1"),
        "comparison_epsilon_minutes": epsilon,
        "boundary_evaluation_coverage_complete": duration.get("boundary_evaluation_coverage_complete"),
    }


def _compare_zone(zone, source, allowed, epsilon):
    observed = _finite((source or {}).get("maximum_shadow_duration_minutes"))
    if observed is None or allowed is None or not (source or {}).get("available"):
        return {"zone": zone, "status": "undetermined"}
    difference = observed - allowed
    status = "within_selected_limit" if observed <= allowed + epsilon else "exceeds_selected_limit"
    return {
        "zone": zone,
        "status": status,
        "observed_maximum_minutes": observed,
        "selected_limit_minutes": allowed,
        "difference_minutes": difference,
        "excess_minutes": max(0.0, difference),
        "remaining_margin_minutes": allowed - observed,
        "point": copy.deepcopy((source or {}).get("point")),
    }


def build_selected_limit_comparison(resolved_regulatory_preset, measurement_masks, shadow_duration=None, settings_normalized=None, comparison_epsilon_minutes=1e-6):
    """Compare measured near/far maximum durations with the user-selected preset."""
    epsilon = _finite(comparison_epsilon_minutes)
    if epsilon is None or epsilon < 0.0:
        result = _base(blockers=[_blocker("invalid_comparison_epsilon_minutes")])
        result["numerical_context"] = _context(shadow_duration, settings_normalized, comparison_epsilon_minutes)
        return result

    preset = resolved_regulatory_preset if isinstance(resolved_regulatory_preset, dict) else {}
    masks = measurement_masks if isinstance(measurement_masks, dict) else {}
    result = _base()
    result["preset"] = _preset_summary(preset)
    result["numerical_context"] = _context(shadow_duration, settings_normalized, epsilon)

    if preset.get("valid") is not True:
        result["blockers"].append(_blocker("valid_regulatory_preset_required"))
        return result
    if preset.get("comparison_ready") is False or preset.get("preset_purpose") == "contour_candidate_set":
        result["blockers"].append(_blocker("regulatory_limit_pair_not_selected", ALL_PRESET_REASON))
        result["reason"] = ALL_PRESET_REASON
        return result
    near_allowed = _finite(preset.get("near_limit_minutes"))
    far_allowed = _finite(preset.get("far_limit_minutes"))
    if near_allowed is None or far_allowed is None:
        result["blockers"].append(_blocker("finite_selected_limit_minutes_required"))
        return result
    if masks.get("complete") is not True or masks.get("boundary_dependent_ready") is not True:
        result["blockers"].append(_blocker("complete_measurement_masks_required"))
        return result
    if not (masks.get("near") or {}).get("available"):
        result["blockers"].append(_blocker("near_measurement_mask_required"))
        return result
    if not (masks.get("far") or {}).get("available"):
        result["blockers"].append(_blocker("far_measurement_mask_required"))
        return result
    if shadow_duration is not None:
        if (shadow_duration or {}).get("complete") is not True:
            result["blockers"].append(_blocker("complete_shadow_duration_required"))
            return result
        if (shadow_duration or {}).get("boundary_evaluation_coverage_complete") is not True:
            result["blockers"].append(_blocker("boundary_evaluation_coverage_complete_required"))
            return result

    near = _compare_zone("5m_to_10m", masks.get("near"), near_allowed, epsilon)
    far = _compare_zone("over_10m", masks.get("far"), far_allowed, epsilon)
    result["near"] = near
    result["far"] = far
    if near["status"] == "undetermined" or far["status"] == "undetermined":
        result["blockers"].append(_blocker("finite_zone_maximum_duration_required"))
        return result
    result["available"] = True
    result["complete"] = True
    result["status"] = "exceeds_selected_limits" if "exceeds_selected_limit" in (near["status"], far["status"]) else "within_selected_limits"
    return result


def build_legal_judgement_skeleton(selected_limit_comparison):
    comparison = selected_limit_comparison if isinstance(selected_limit_comparison, dict) else {}
    return {
        "available": False,
        "complete": False,
        "status": "undetermined",
        "reason": "ordinance_applicability_not_certified",
        "selected_limit_comparison_status": comparison.get("status"),
        "blockers": [{"failure_code": "ordinance_applicability_not_certified"}],
        "legal_judgement_generated": False,
        "ordinance_selection_certified": False,
        "permit_ready_certified": False,
    }
