"""Revit/Dynamo Level adapter for JSON-safe average-ground elevation data."""
from shadow_units import _internal_length_to_meters
from shadow_utils import _safe_attr, _try_unwrap


def resolve_average_ground_level(level):
    """Read a selected Level and cross the adapter boundary in SI meters."""
    result = {
        "level_reference_present": level is not None,
        "level_elevation_internal": None,
        "level_elevation_m": None,
        "level_elevation_readable": False,
        "warnings": [],
    }
    if level is None:
        return result

    candidates = [level]
    native = _try_unwrap(level)
    if native is not None and native is not level:
        candidates.insert(0, native)
    internal = _safe_attr(level, "InternalElement")
    if internal is not None and internal not in candidates:
        candidates.append(internal)

    elevation = None
    for candidate in candidates:
        elevation = _safe_attr(candidate, "Elevation")
        if elevation is not None:
            break
    try:
        elevation_internal = float(elevation)
        if elevation_internal != elevation_internal or abs(elevation_internal) == float("inf"):
            raise ValueError("non-finite Elevation")
    except Exception:
        result["warnings"].append(
            "Selected Revit Level Elevation could not be read; settings.average_ground_level_elevation_m was not used as a silent fallback."
        )
        return result

    elevation_m, conversion_warnings = _internal_length_to_meters(elevation_internal)
    result.update({
        "level_elevation_internal": elevation_internal,
        "level_elevation_m": elevation_m,
        "level_elevation_readable": elevation_m is not None,
    })
    result["warnings"].extend(conversion_warnings)
    if elevation_m is None:
        result["warnings"].append("Selected Revit Level Elevation could not be converted to meters.")
    return result
