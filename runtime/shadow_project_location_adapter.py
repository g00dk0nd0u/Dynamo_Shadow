"""Read-only Revit Project Location adapter for the shared site orientation."""
import math

from shadow_revit_api import REVIT_API_CAPABILITIES, XYZ


_SOURCE_REVIT = "revit_active_project_location"
_SOURCE_EXPLICIT = "explicit_pure_python"
_UNAVAILABLE_WARNING = (
    "Revit ActiveProjectLocation True North could not be resolved; no silent "
    "zero-degree fallback was applied."
)


def _finite_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _current_document():
    try:
        import clr
        clr.AddReference("RevitServices")
        from RevitServices.Persistence import DocumentManager
        return DocumentManager.Instance.CurrentDBDocument
    except Exception:
        return None


def _result(available=False, radians=None, source="unavailable", warnings=None):
    degrees = math.degrees(radians) if available else None
    return {
        "true_north_available": bool(available),
        "true_north_source": source,
        "true_north_rotation_rad": radians if available else None,
        "true_north_rotation_deg": degrees if available else None,
        "true_north_applied_to_shadow_direction": False,
        "angle_contract": (
            "ProjectPosition.Angle radians, positive clockwise from Project "
            "North/model +Y to True North; used directly by the core's "
            "clockwise model-azimuth rotation"
        ),
        "warnings": list(warnings or []),
    }


def resolve_true_north_rotation(document=None, explicit_rotation_rad=None,
                                revit_runtime=None):
    """Resolve JSON-safe orientation without exposing Project Location identity.

    Autodesk's ProjectPosition.Angle contract is radians measured clockwise from
    Project North to True North. Revit model +Y is therefore the zero Project
    North axis used by Shadow Core, and the API value is not sign-inverted.
    ``explicit_rotation_rad`` exists only for pure-Python callers and tests.
    """
    if explicit_rotation_rad is not None:
        angle = _finite_float(explicit_rotation_rad)
        if angle is None:
            return _result(warnings=["Explicit pure-Python True North rotation is not finite."])
        return _result(True, angle, _SOURCE_EXPLICIT)

    if revit_runtime is None:
        revit_runtime = bool(REVIT_API_CAPABILITIES.get("revit_api_loaded"))
    if document is None and revit_runtime:
        document = _current_document()
    if document is None:
        return _result(warnings=[_UNAVAILABLE_WARNING])

    try:
        location = document.ActiveProjectLocation
        if location is None or XYZ is None:
            raise ValueError("active project location or XYZ unavailable")
        position = location.GetProjectPosition(XYZ.Zero)
        angle = _finite_float(position.Angle if position is not None else None)
        if angle is None:
            raise ValueError("ProjectPosition.Angle unavailable")
        return _result(True, angle, _SOURCE_REVIT)
    except Exception:
        return _result(warnings=[_UNAVAILABLE_WARNING])


def apply_true_north_to_settings(settings, resolution):
    """Return a settings copy containing only the resolved common orientation."""
    copied = dict(settings) if isinstance(settings, dict) else {}
    if resolution.get("true_north_available"):
        copied["true_north_deg"] = resolution["true_north_rotation_deg"]
    else:
        copied.pop("true_north_deg", None)
    return copied


def resolve_runtime_true_north(settings, document=None):
    """Use Revit as authority in Revit; preserve explicit SI core input in Python."""
    revit_runtime = bool(REVIT_API_CAPABILITIES.get("revit_api_loaded"))
    if revit_runtime:
        return resolve_true_north_rotation(document=document, revit_runtime=True)
    explicit_deg = settings.get("true_north_deg") if isinstance(settings, dict) else None
    explicit_deg = _finite_float(explicit_deg)
    return resolve_true_north_rotation(
        explicit_rotation_rad=(None if explicit_deg is None else math.radians(explicit_deg)),
        revit_runtime=False)


def mark_true_north_applied(resolution, solar_calculation):
    """Attach compact 08:00/12:00/16:00 direction evidence to diagnostics."""
    result = dict(resolution)
    slices = (solar_calculation or {}).get("slices") or []
    result["true_north_applied_to_shadow_direction"] = bool(
        result.get("true_north_available") and
        any(item.get("shadow_direction_model") is not None or
            item.get("ray_vector_model") is not None for item in slices))
    wanted = {"08:00", "12:00", "16:00"}
    result["shadow_direction_check_samples"] = [
        {"input_time": item.get("input_time"),
         "shadow_direction_model": item.get("shadow_direction_model")}
        for item in slices if item.get("input_time") in wanted
    ]
    return result
