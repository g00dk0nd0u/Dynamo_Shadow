"""Pure-Python diagnosis of Reverse sample/cell/mesh reconstruction losses."""
import math

from shadow_forward_equivalent_validator import (
    _orientation, _point_on_segment, build_prismatic_shadow_states,
    is_prism_shadowed, point_in_polygon)
from shadow_reverse_envelope_evaluation import evaluate_prism_against_reverse_envelope
from shadow_reverse_low_rise import _inside


METHOD = "sample_instant_reconstruction_cause_decomposition_v2"
MAXIMUM_DIAGNOSTIC_LEVEL_COUNT = 1000000


def _empty(fixture, maximum_height_m):
    return {"method": METHOD, "fixture_id": fixture.get("fixture_id"),
        "maximum_height_m": maximum_height_m, "forward_v2_v3_excess_m": None,
        "measurement_specific_sample_instant_excess_m": None,
        "measurement_specific_ownership_cell_excess_m": None,
        "ownership_cell_expansion_delta_m": None,
        "combined_temporal_facet_delta_m": None, "ray_facet_delta_m": None,
        "cell_model_excess_m": None, "cell_or_grid_excess_m": None,
        "mesh_evaluated_excess_m": None, "spatial_mesh_delta_m": None,
        "original_building_fits_sample_instant_cell_model": None,
        "original_building_fits_sample_instant_inverse": None,
        "aligned_full_cell_count": 0, "partial_boundary_cell_count": 0,
        "boundary_cell_approximation_used": False,
        "sample_instant_reconstruction_complete": False,
        "ownership_cell_reconstruction_complete": False,
        "cause_decomposition_complete": False, "diagnostic_evaluation_count": 0,
        "diagnostic_level_count": None,
        "blockers": [], "warnings": []}


def _strictly_in_polygon(point, polygon, tolerance=1e-9):
    return point_in_polygon(point, polygon) and not any(
        _point_on_segment(point, polygon[i], polygon[(i+1) % len(polygon)], tolerance)
        for i in range(len(polygon)))


def _proper_segments_intersect(a, b, c, d, tolerance=1e-9):
    values = (_orientation(a, b, c), _orientation(a, b, d),
              _orientation(c, d, a), _orientation(c, d, b))
    return (((values[0] > tolerance and values[1] < -tolerance) or
             (values[0] < -tolerance and values[1] > tolerance)) and
            ((values[2] > tolerance and values[3] < -tolerance) or
             (values[2] < -tolerance and values[3] > tolerance)))


def _building_cell_coverage(cell_polygon, building_polygon, tolerance=1e-9):
    """Classify positive-area building coverage; boundary contact is not partial."""
    if all(point_in_polygon(point, building_polygon) for point in cell_polygon):
        return "full"
    min_x, max_x = cell_polygon[0][0], cell_polygon[2][0]
    min_y, max_y = cell_polygon[0][1], cell_polygon[2][1]
    if any(_strictly_in_polygon(point, building_polygon, tolerance)
           for point in cell_polygon):
        return "partial"
    if any(min_x+tolerance < point[0] < max_x-tolerance and
           min_y+tolerance < point[1] < max_y-tolerance
           for point in building_polygon):
        return "partial"
    return ("partial" if any(_proper_segments_intersect(
        cell_polygon[i], cell_polygon[(i+1) % 4], building_polygon[j],
        building_polygon[(j+1) % len(building_polygon)], tolerance)
        for i in range(4) for j in range(len(building_polygon))) else "none")


def build_reverse_reconstruction_diagnostic(
        fixture, resolved_preset, measurement_points, site_boundary_geometry,
        ownership_cell_replay, maximum_height_m=31.0, temporal_step_minutes=15,
        grid_resolution_m=1.0, vertical_height_step_m=0.5,
        maximum_diagnostic_evaluations=5000000):
    """Replay exact sample states against independent finite site-cell prisms."""
    result = _empty(fixture, maximum_height_m)
    try:
        cap, resolution, step, temporal = map(float, (maximum_height_m,
            grid_resolution_m, vertical_height_step_m, temporal_step_minutes))
        guard = int(maximum_diagnostic_evaluations)
        if (not all(math.isfinite(v) and v > 0 for v in (cap, resolution, step, temporal))
                or guard <= 0 or guard != maximum_diagnostic_evaluations):
            raise ValueError()
        site = [(float(p["x_m"]), float(p["y_m"]))
                for p in site_boundary_geometry["outer_loop"]]
        points = [(float(p["x_m"]), float(p["y_m"])) for p in measurement_points]
        building = [(float(p[0]), float(p[1])) for p in fixture["building_footprint"]]
        coordinates = site + points + building
        if (len(site) < 3 or len(building) < 3 or not points or
                not all(math.isfinite(value) for point in coordinates for value in point)):
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_reconstruction_diagnostic_input"})
        return result

    level_count = int(math.ceil(cap/step))+1
    result["diagnostic_level_count"] = level_count
    if level_count > MAXIMUM_DIAGNOSTIC_LEVEL_COUNT:
        result["blockers"].append({"failure_code":
            "maximum_diagnostic_level_count_exceeded",
            "maximum_diagnostic_level_count": MAXIMUM_DIAGNOSTIC_LEVEL_COUNT,
            "diagnostic_level_count": level_count})
        return result

    forward = build_prismatic_shadow_states(fixture, resolved_preset, points, temporal)
    states, solar = forward["shadow_states"], forward["solar_samples"]
    ox = math.floor(min(p[0] for p in site) / resolution) * resolution
    oy = math.floor(min(p[1] for p in site) / resolution) * resolution
    nx = int(round((math.ceil(max(p[0] for p in site)/resolution)*resolution-ox)/resolution))
    ny = int(round((math.ceil(max(p[1] for p in site)/resolution)*resolution-oy)/resolution))
    levels = sorted(set(min(cap, index*step) for index in range(level_count)))
    candidates = [value for value in levels if value > float(fixture["measurement_height_m"])]
    evaluations = 0
    cells = []
    for iy in range(ny):
        for ix in range(nx):
            min_x, min_y = ox+ix*resolution, oy+iy*resolution
            footprint = [(min_x, min_y), (min_x+resolution, min_y),
                         (min_x+resolution, min_y+resolution), (min_x, min_y+resolution)]
            if not all(_inside(point, site, 1e-8) is not False for point in footprint):
                continue
            limit = cap
            for q, point in enumerate(points):
                for k, sample_solar in enumerate(solar):
                    if states[q][k]:
                        continue
                    evaluations += 1
                    if evaluations > guard:
                        result["diagnostic_evaluation_count"] = evaluations
                        result["blockers"].append({"failure_code":
                            "maximum_diagnostic_evaluations_exceeded",
                            "maximum_diagnostic_evaluations": guard})
                        return result
                    if not is_prism_shadowed(point, footprint, cap,
                                             fixture["measurement_height_m"], sample_solar):
                        continue
                    low, high, first_shadow = 0, len(candidates)-1, len(candidates)-1
                    while low <= high:
                        candidate_index = (low+high)//2
                        evaluations += 1
                        if evaluations > guard:
                            result["diagnostic_evaluation_count"] = evaluations
                            result["blockers"].append({"failure_code":
                                "maximum_diagnostic_evaluations_exceeded",
                                "maximum_diagnostic_evaluations": guard})
                            return result
                        if is_prism_shadowed(point, footprint, candidates[candidate_index],
                                             fixture["measurement_height_m"], sample_solar):
                            first_shadow, high = candidate_index, candidate_index-1
                        else:
                            low = candidate_index+1
                    previous = (max([value for value in levels
                                     if value <= fixture["measurement_height_m"]] or [0.0])
                                if first_shadow == 0 else candidates[first_shadow-1])
                    limit = min(limit, previous)
            coverage = _building_cell_coverage(footprint, building)
            cells.append({"cell_index": len(cells), "ix": ix, "iy": iy,
                "min_x_m": min_x, "max_x_m": min_x+resolution,
                "min_y_m": min_y, "max_y_m": min_y+resolution,
                "center_x_m": min_x+resolution/2.0,
                "center_y_m": min_y+resolution/2.0,
                "building_coverage": coverage, "height_limit_m": limit})

    occupied = [cell for cell in cells if cell["building_coverage"] != "none"]
    full = [cell for cell in occupied if cell["building_coverage"] == "full"]
    partial = [cell for cell in occupied if cell["building_coverage"] == "partial"]
    height = float(fixture["building_height_m"])
    cell_excess = max([max(0.0, height-cell["height_limit_m"]) for cell in occupied] or [0.0])
    cell_fit = bool(occupied) and cell_excess <= 1e-9

    # Convert cell limits to a separate vertex field.  A shared vertex receives
    # the strictest adjacent cell limit; this conversion is intentionally measured.
    cell_by_index = {(cell["ix"], cell["iy"]): cell for cell in cells}
    grid = []
    for iy in range(ny+1):
        for ix in range(nx+1):
            adjacent = [cell_by_index[key] for key in
                        ((ix-1, iy-1), (ix, iy-1), (ix-1, iy), (ix, iy))
                        if key in cell_by_index]
            limit = min([cell["height_limit_m"] for cell in adjacent] or [cap])
            grid.append({"grid_index": len(grid), "ix": ix, "iy": iy,
                "x_m": ox+ix*resolution, "y_m": oy+iy*resolution,
                "inside_site": bool(adjacent), "bounded": bool(adjacent),
                "height_limit_m": limit if adjacent else None})
    triangles = []
    width = nx+1
    for cell in cells:
        ix, iy = cell["ix"], cell["iy"]
        ids = (iy*width+ix, iy*width+ix+1, (iy+1)*width+ix+1, (iy+1)*width+ix)
        for vertices in ((ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])):
            triangles.append({"triangle_index": len(triangles),
                              "vertex_grid_indices": list(vertices)})
    envelope = {"height_field": {"grid_spec": {"x_count": nx+1, "y_count": ny+1,
        "origin_x_m": ox, "origin_y_m": oy, "resolution_m": resolution},
        "grid_points": grid}, "top_surface_mesh": {"triangles": triangles}}
    mesh_fit = evaluate_prism_against_reverse_envelope(
        fixture["building_footprint"], height, envelope)
    mesh_excess = mesh_fit["maximum_height_excess_m"]
    exact_cell_model = not partial and bool(full)
    subset_invariant_failed = bool(exact_cell_model and cap >= height and not cell_fit)
    sample_complete = (bool(cells) and bool(triangles) and bool(occupied)
                       and not subset_invariant_failed)
    ownership_excess = ownership_cell_replay.get("measurement_specific_excess_m")
    ownership_complete = bool(ownership_cell_replay.get("inverse_reconstruction_complete"))
    combined = (float(ownership_excess)-cell_excess
                if (ownership_complete and exact_cell_model and
                    ownership_excess is not None) else None)
    result.update({"maximum_height_m": cap,
        "forward_v2_v3_excess_m": ownership_cell_replay.get("zone_common_v2_or_v3_excess_m"),
        "measurement_specific_sample_instant_excess_m": cell_excess,
        "measurement_specific_ownership_cell_excess_m": ownership_excess,
        "combined_temporal_facet_delta_m": combined,
        "cell_model_excess_m": cell_excess, "cell_or_grid_excess_m": cell_excess,
        "mesh_evaluated_excess_m": mesh_excess,
        "spatial_mesh_delta_m": mesh_excess-cell_excess if exact_cell_model else None,
        "original_building_fits_sample_instant_cell_model": cell_fit if exact_cell_model else None,
        "original_building_fits_sample_instant_inverse": cell_fit if exact_cell_model else None,
        "aligned_full_cell_count": len(full),
        "partial_boundary_cell_count": len(partial),
        "boundary_cell_approximation_used": bool(partial),
        "sample_instant_reconstruction_complete": sample_complete,
        "ownership_cell_reconstruction_complete": ownership_complete,
        "cause_decomposition_complete": False,
        "diagnostic_evaluation_count": evaluations, "finite_cells": cells,
        "height_field": envelope["height_field"], "top_surface_mesh": envelope["top_surface_mesh"],
        "sample_instant_envelope_fit": mesh_fit})
    result["warnings"].extend([
        "ownership_cell_expansion_delta_m is null because ownership-cell facets and finite-cell sample predicates are not the same representation.",
        "ray_facet_delta_m is null because a common finite-cell adjacent-ray-facet reconstruction is unavailable.",
        "combined_temporal_facet_delta_m is not an ownership-cell-only attribution."])
    if partial:
        result["warnings"].append(
            "Partial building boundary cells use full-square footprints; the sample-instant cell result is approximate, not exact.")
    if subset_invariant_failed:
        result["blockers"].append({"failure_code":
            "sample_instant_cell_subset_invariant_failed"})
    if not sample_complete:
        result["blockers"].append({"failure_code": "sample_instant_reconstruction_incomplete"})
    return result
