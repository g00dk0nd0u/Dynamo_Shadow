"""Pure-Python prismatic Forward-equivalent validator (not formal Forward)."""
import math

from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_sun import REGULATORY_DECLINATION_DEG, _sun_position_for_true_solar_minutes

METHOD = "pure_python_prismatic_forward_equivalent_validator_v1"


def _point_on_segment(point, a, b, tolerance=1e-9):
    cross = (point[0] - a[0]) * (b[1] - a[1]) - (point[1] - a[1]) * (b[0] - a[0])
    return (abs(cross) <= tolerance and min(a[0], b[0]) - tolerance <= point[0] <= max(a[0], b[0]) + tolerance
            and min(a[1], b[1]) - tolerance <= point[1] <= max(a[1], b[1]) + tolerance)


def point_in_polygon(point, polygon):
    inside = False
    for index, a in enumerate(polygon):
        b = polygon[(index + 1) % len(polygon)]
        if _point_on_segment(point, a, b):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            crossing_x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < crossing_x:
                inside = not inside
    return inside


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d, tolerance=1e-9):
    values = (_orientation(a, b, c), _orientation(a, b, d),
              _orientation(c, d, a), _orientation(c, d, b))
    if ((values[0] > tolerance and values[1] < -tolerance) or (values[0] < -tolerance and values[1] > tolerance)) and \
       ((values[2] > tolerance and values[3] < -tolerance) or (values[2] < -tolerance and values[3] > tolerance)):
        return True
    return any(abs(value) <= tolerance and _point_on_segment(point, start, end, tolerance)
               for value, point, start, end in ((values[0], c, a, b), (values[1], d, a, b),
                                                  (values[2], a, c, d), (values[3], b, c, d)))


def segment_intersects_polygon(start, end, polygon):
    if point_in_polygon(start, polygon) or point_in_polygon(end, polygon):
        return True
    return any(_segments_intersect(start, end, polygon[i], polygon[(i + 1) % len(polygon)])
               for i in range(len(polygon)))


def is_prism_shadowed(point, footprint, building_height_m, measurement_height_m, solar):
    delta = float(building_height_m) - float(measurement_height_m)
    direction = (solar or {}).get("shadow_direction_model")
    factor = (solar or {}).get("shadow_length_factor")
    if delta <= 0.0 or direction is None or factor is None:
        return False
    reach = delta * float(factor)
    toward_sun = (point[0] - float(direction["x"]) * reach,
                  point[1] - float(direction["y"]) * reach)
    return segment_intersects_polygon(point, toward_sun, footprint)


def _times(start, end, step):
    values = []
    current = float(start)
    while current < float(end) - 1e-9:
        values.append(current); current += step
    values.append(float(end))
    return values


def build_prismatic_shadow_states(fixture, resolved_preset, points,
                                  temporal_step_minutes=15, building_height_m=None,
                                  footprint=None):
    """Return the q-by-k states used by the Forward-equivalent validator.

    This deliberately exposes states without changing their duration semantics; callers
    must continue to use :func:`integrate_shadow_states_trapezoidal`.
    """
    polygon = [(float(p[0]), float(p[1])) for p in (footprint or fixture["building_footprint"])]
    height = float(fixture["building_height_m"] if building_height_m is None else building_height_m)
    measurement = float(fixture["measurement_height_m"])
    parse = lambda value: int(value[:2]) * 60 + int(value[3:5])
    samples = _times(parse(resolved_preset["true_solar_start_time"]),
                     parse(resolved_preset["true_solar_end_time"]), temporal_step_minutes)
    solar = [_sun_position_for_true_solar_minutes(value, float(fixture["site_latitude_deg"]),
             REGULATORY_DECLINATION_DEG, float(fixture["true_north_deg"])) for value in samples]
    states = [[is_prism_shadowed((float(point[0]), float(point[1])), polygon, height,
                                 measurement, item) for item in solar] for point in points]
    return {"sample_minutes": samples, "solar_samples": solar, "shadow_states": states}


def build_prismatic_forward_equivalent_duration(fixture, resolved_preset,
                                                 spatial_resolution_m=0.5, temporal_step_minutes=15):
    footprint = [(float(p[0]), float(p[1])) for p in fixture["building_footprint"]]
    site = [(float(p[0]), float(p[1])) for p in fixture["site_boundary"]]
    height = float(fixture["building_height_m"])
    measurement = float(fixture["measurement_height_m"])
    state_data = build_prismatic_shadow_states(fixture, resolved_preset, [], temporal_step_minutes)
    sample_minutes, solar = state_data["sample_minutes"], state_data["solar_samples"]
    reach = max([max(0.0, height - measurement) * float(item.get("shadow_length_factor") or 0.0)
                 for item in solar] or [0.0])
    xs = [p[0] for p in footprint + site]; ys = [p[1] for p in footprint + site]
    # Site + 10 m zones, plus full prismatic shadow reach and one grid cell.
    pad = max(10.0, reach) + spatial_resolution_m
    min_x = math.floor((min(xs) - pad) / spatial_resolution_m) * spatial_resolution_m
    min_y = math.floor((min(ys) - pad) / spatial_resolution_m) * spatial_resolution_m
    max_x = math.ceil((max(xs) + pad) / spatial_resolution_m) * spatial_resolution_m
    max_y = math.ceil((max(ys) + pad) / spatial_resolution_m) * spatial_resolution_m
    nx = int(round((max_x - min_x) / spatial_resolution_m)) + 1
    ny = int(round((max_y - min_y) / spatial_resolution_m)) + 1
    grid = []
    for iy in range(ny):
        y = min_y + iy * spatial_resolution_m
        for ix in range(nx):
            x = min_x + ix * spatial_resolution_m
            states = [is_prism_shadowed((x, y), footprint, height, measurement, item) for item in solar]
            grid.append({"x_m": x, "y_m": y,
                         "shadow_duration_minutes": integrate_shadow_states_trapezoidal(states, sample_minutes)})
    return {"available": True, "complete": True, "method": METHOD,
            "spatial_resolution_m": spatial_resolution_m, "temporal_step_minutes": temporal_step_minutes,
            "duration_grid": grid, "grid_point_count": len(grid),
            "grid_spec": {"x_count": nx, "y_count": ny, "origin_x_m": min_x, "origin_y_m": min_y,
                          "resolution_m": spatial_resolution_m, "ordering": "row_major_y_then_x"},
            "bounds_m": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
            "bounds_sources": ["building_shadow_reach", "site_boundary_expanded_10m"],
            "site_boundary_bounds_included": True, "boundary_evaluation_coverage_complete": True,
            "legal_judgement_generated": False, "ordinance_selection_certified": False,
            "permit_ready_certified": False, "blockers": [], "warnings": [
                "Pure-Python ray/prism validation only; not Revit-native production Forward geometry."]}
