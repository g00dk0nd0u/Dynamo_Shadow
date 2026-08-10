"""Non-fatal write/readback diagnostics for Revit element overrides."""
import re


def _safe_message(exc):
    # API binding errors are useful by type; avoid serializing arbitrary object
    # representations or environment-specific paths into debug output.
    text = " ".join(str(exc).split())
    text = re.sub(r"[A-Za-z]:[\\/][^ ]+|/(?:Users|home)/[^ ]+",
                  "<redacted_path>", text)
    return text[:240]


def _rgb(value):
    if value is None:
        return None
    try:
        valid = getattr(value, "IsValid", True)
        if callable(valid):
            valid = valid()
        if not bool(valid):
            return None
        return {"r": int(value.Red), "g": int(value.Green), "b": int(value.Blue)}
    except BaseException:
        return None


def apply_and_readback(view, element_id, rgb, line_weight,
                       override_type, color_type):
    """Set an override and immediately read it back without failing geometry."""
    requested_color = {"r": int(rgb[0]), "g": int(rgb[1]), "b": int(rgb[2])}
    result = {
        "attempted": True, "set_succeeded": False,
        "requested_projection_line_color": requested_color,
        "requested_projection_line_weight": int(line_weight),
        "readback_attempted": False, "readback_succeeded": False,
        "actual_projection_line_color": None,
        "actual_projection_line_weight": None,
        "color_matches_requested": False,
        "line_weight_matches_requested": False,
        "verified": False,
    }
    if view is None or override_type is None or color_type is None:
        result.update({"set_failure_type": "ApiUnavailable",
                       "set_failure_message": "Projection-line graphical override API is unavailable."})
        return result
    try:
        override = override_type()
        override.SetProjectionLineColor(color_type(*rgb))
        override.SetProjectionLineWeight(int(line_weight))
        view.SetElementOverrides(element_id, override)
        result["set_succeeded"] = True
    except BaseException as exc:
        result.update({"set_failure_type": type(exc).__name__,
                       "set_failure_message": _safe_message(exc)})
        return result
    result["readback_attempted"] = True
    try:
        actual = view.GetElementOverrides(element_id)
        result["actual_projection_line_color"] = _rgb(
            getattr(actual, "ProjectionLineColor"))
        # Revit uses a negative special value for an unset projection weight.
        # Preserve it verbatim so diagnostics do not misreport it as configured.
        result["actual_projection_line_weight"] = int(
            getattr(actual, "ProjectionLineWeight"))
        result["readback_succeeded"] = True
        result["color_matches_requested"] = (
            result["actual_projection_line_color"] == requested_color)
        result["line_weight_matches_requested"] = (
            result["actual_projection_line_weight"] == int(line_weight))
        result["verified"] = (result["color_matches_requested"] and
                              result["line_weight_matches_requested"])
    except BaseException as exc:
        result.update({"readback_failure_type": type(exc).__name__,
                       "readback_failure_message": _safe_message(exc)})
    return result


def empty_readback_summary():
    return {"attempted_element_count": 0, "successful_element_count": 0,
            "write_failure_count": 0,
            "color_match_count": 0, "color_mismatch_count": 0,
            "line_weight_match_count": 0, "line_weight_mismatch_count": 0,
            "readback_failure_count": 0, "verified_element_count": 0}


def add_to_readback_summary(summary, diagnostic):
    if not diagnostic or not diagnostic.get("attempted"):
        return
    summary["attempted_element_count"] += 1
    if not diagnostic.get("set_succeeded"):
        summary["write_failure_count"] += 1
        return
    # Readback is only meaningful after a successful write.
    if not diagnostic.get("readback_attempted"):
        summary["readback_failure_count"] += 1
        return
    if not diagnostic.get("readback_succeeded"):
        summary["readback_failure_count"] += 1
        return
    summary["successful_element_count"] += 1
    summary["color_match_count" if diagnostic.get("color_matches_requested")
            else "color_mismatch_count"] += 1
    summary["line_weight_match_count" if diagnostic.get("line_weight_matches_requested")
            else "line_weight_mismatch_count"] += 1
    if diagnostic.get("verified"):
        summary["verified_element_count"] += 1


def all_writes_succeeded(summary):
    return (summary["attempted_element_count"] > 0 and
            summary["write_failure_count"] == 0)


def all_readbacks_succeeded(summary):
    return (all_writes_succeeded(summary) and
            summary["successful_element_count"] ==
            summary["attempted_element_count"])


def all_overrides_verified(summary):
    return (all_readbacks_succeeded(summary) and
            summary["verified_element_count"] ==
            summary["attempted_element_count"])


def aggregate_status(summary):
    return {
        "graphical_overrides_write_succeeded": all_writes_succeeded(summary),
        "graphical_overrides_readback_succeeded": all_readbacks_succeeded(summary),
        "graphical_overrides_verified": all_overrides_verified(summary),
    }
