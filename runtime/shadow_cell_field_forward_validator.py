"""Forward-equivalent validation for an authoritative finite column field."""
import math

from shadow_duration import integrate_shadow_states_trapezoidal
from shadow_forward_equivalent_validator import build_forward_solar_samples
from shadow_regulatory_comparison import build_selected_limit_comparison
from shadow_site_masks import _classify

METHOD = "finite_cell_field_forward_equivalent_validator_v1"


def cell_footprint(cell):
    return [(cell["min_x_m"], cell["min_y_m"]), (cell["max_x_m"], cell["min_y_m"]),
            (cell["max_x_m"], cell["max_y_m"]), (cell["min_x_m"], cell["max_y_m"])]


def is_cell_shadowed(point, cell, building_height_m, measurement_height_m, solar):
    """Exact segment/AABB form of ``is_prism_shadowed`` for a square cell."""
    delta = float(building_height_m)-float(measurement_height_m)
    direction = (solar or {}).get("shadow_direction_model"); factor = (solar or {}).get("shadow_length_factor")
    if delta <= 0.0 or direction is None or factor is None: return False
    end = (point[0]-float(direction["x"])*delta*float(factor),
           point[1]-float(direction["y"])*delta*float(factor))
    t0, t1 = 0.0, 1.0
    for start, finish, low, high in ((point[0], end[0], cell["min_x_m"], cell["max_x_m"]),
                                      (point[1], end[1], cell["min_y_m"], cell["max_y_m"])):
        d = finish-start
        if abs(d) <= 1e-15:
            if start < low-1e-9 or start > high+1e-9: return False
            continue
        a, b = (low-start)/d, (high-start)/d
        if a > b: a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1+1e-9: return False
    return True


def build_cell_field_shadow_states(points, cells, measurement_height_m, solar_samples):
    """Return whole-building states using OR, never per-column addition."""
    return [[any(is_cell_shadowed((float(point[0]), float(point[1])), cells[index],
                    cells[index]["height_m"], measurement_height_m, solar)
                 for index in range(len(cells))) for solar in solar_samples] for point in points]


def _validation_grid(cells, site, measurement_height, samples, solar, resolution, maximum_grid_points):
    polygon = [(float(p["x_m"]), float(p["y_m"])) for p in site["outer_loop"]]
    xs = [p[0] for p in polygon]; ys = [p[1] for p in polygon]
    shadow_x = [value for cell in cells for s in solar for value in (
        cell["min_x_m"], cell["max_x_m"],
        cell["min_x_m"]+(s.get("shadow_direction_model") or {"x": 0.0})["x"]*max(0.0, cell["height_m"]-measurement_height)*float(s.get("shadow_length_factor") or 0.0),
        cell["max_x_m"]+(s.get("shadow_direction_model") or {"x": 0.0})["x"]*max(0.0, cell["height_m"]-measurement_height)*float(s.get("shadow_length_factor") or 0.0))]
    shadow_y = [value for cell in cells for s in solar for value in (
        cell["min_y_m"], cell["max_y_m"],
        cell["min_y_m"]+(s.get("shadow_direction_model") or {"y": 0.0})["y"]*max(0.0, cell["height_m"]-measurement_height)*float(s.get("shadow_length_factor") or 0.0),
        cell["max_y_m"]+(s.get("shadow_direction_model") or {"y": 0.0})["y"]*max(0.0, cell["height_m"]-measurement_height)*float(s.get("shadow_length_factor") or 0.0))]
    # The union of the actual swept-column bounds is the complete non-zero-shadow
    # domain. Site + 10 m is retained so both regulatory bands exist even when zero.
    min_x = math.floor(min(min(xs)-10.0, min(shadow_x)-resolution)/resolution)*resolution
    min_y = math.floor(min(min(ys)-10.0, min(shadow_y)-resolution)/resolution)*resolution
    max_x = math.ceil(max(max(xs)+10.0, max(shadow_x)+resolution)/resolution)*resolution
    max_y = math.ceil(max(max(ys)+10.0, max(shadow_y)+resolution)/resolution)*resolution
    nx = int(round((max_x-min_x)/resolution))+1; ny = int(round((max_y-min_y)/resolution))+1
    count = nx*ny
    if count > maximum_grid_points:
        return None, {"x_count": nx, "y_count": ny, "origin_x_m": min_x, "origin_y_m": min_y,
            "resolution_m": resolution, "ordering": "row_major_y_then_x"}, count
    swept = []
    for s in solar:
        direction = s.get("shadow_direction_model") or {"x": 0.0, "y": 0.0}
        boxes = []
        for cell in cells:
            reach = max(0.0, cell["height_m"]-measurement_height)*float(s.get("shadow_length_factor") or 0.0)
            dx, dy = direction["x"]*reach, direction["y"]*reach
            boxes.append((min(cell["min_x_m"], cell["min_x_m"]+dx), max(cell["max_x_m"], cell["max_x_m"]+dx),
                          min(cell["min_y_m"], cell["min_y_m"]+dy), max(cell["max_y_m"], cell["max_y_m"]+dy)))
        swept.append(boxes)
    near = far = None
    for iy in range(ny):
        y = min_y+iy*resolution
        for ix in range(nx):
            x = min_x+ix*resolution
            zone, distance = _classify((x, y), polygon, 1e-6)
            if zone not in ("near_5_to_10m", "far_over_10m"):
                continue
            states = [any(box[0]-1e-9 <= x <= box[1]+1e-9 and box[2]-1e-9 <= y <= box[3]+1e-9 and
                          is_cell_shadowed((x, y), cells[j], cells[j]["height_m"], measurement_height, s)
                          for j, box in enumerate(swept[k])) for k, s in enumerate(solar)]
            duration = integrate_shadow_states_trapezoidal(states, samples)
            candidate = {"available": True, "maximum_shadow_duration_minutes": duration,
                "point": {"x_m": x, "y_m": y, "distance_from_site_boundary_m": distance}}
            if zone == "near_5_to_10m" and (near is None or (-duration, x, y) <
                    (-near["maximum_shadow_duration_minutes"], near["point"]["x_m"], near["point"]["y_m"])): near = candidate
            if zone == "far_over_10m" and (far is None or (-duration, x, y) <
                    (-far["maximum_shadow_duration_minutes"], far["point"]["x_m"], far["point"]["y_m"])): far = candidate
    return {"near": near or {"available": False}, "far": far or {"available": False}}, {
        "x_count": nx, "y_count": ny, "origin_x_m": min_x, "origin_y_m": min_y,
        "resolution_m": resolution, "ordering": "row_major_y_then_x"}, count


def build_cell_field_forward_validation(cells, site_boundary_geometry, resolved_preset,
                                        settings_normalized, measurement_height_m,
                                        spatial_resolution_m=0.5, temporal_step_minutes=15,
                                        maximum_grid_points=1000000):
    fixture = {"site_latitude_deg": settings_normalized["normalized"]["site_latitude_deg"],
               "true_north_deg": settings_normalized["normalized"]["true_north_deg"]}
    sample_data = build_forward_solar_samples(fixture, resolved_preset, temporal_step_minutes)
    samples, solar = sample_data["sample_minutes"], sample_data["solar_samples"]
    masks, spec, grid_count = _validation_grid(cells, site_boundary_geometry, float(measurement_height_m), samples, solar,
                                               float(spatial_resolution_m), maximum_grid_points)
    if masks is None:
        return {"method": METHOD, "available": False, "complete": False,
                "grid_point_count": grid_count, "blockers": [{"failure_code": "reverse_expansion_complexity_limit_exceeded",
                "limit_type": "full_validation_grid_points"}]}
    masks.update({"complete": True, "boundary_dependent_ready": True})
    duration = {"method": METHOD, "complete": True,
                "boundary_evaluation_coverage_complete": True, "spatial_resolution_m": spatial_resolution_m,
                "temporal_step_minutes": temporal_step_minutes}
    comparison = build_selected_limit_comparison(resolved_preset, masks, duration, settings_normalized)
    near = masks.get("near", {}); far = masks.get("far", {})
    return {"method": METHOD, "available": True, "complete": comparison.get("complete", False),
            "sample_minutes": samples, "solar_samples": solar,
            "grid_spec": spec, "grid_point_count": grid_count, "measurement_masks": masks,
            "near_max_minutes": near.get("maximum_shadow_duration_minutes"),
            "far_max_minutes": far.get("maximum_shadow_duration_minutes"),
            "near_limit_minutes": resolved_preset.get("near_limit_minutes"),
            "far_limit_minutes": resolved_preset.get("far_limit_minutes"),
            "worst_near_point": near.get("point"), "worst_far_point": far.get("point"),
            "overall_status": comparison.get("status"), "comparison": comparison,
            "blockers": list(comparison.get("blockers") or [])}
