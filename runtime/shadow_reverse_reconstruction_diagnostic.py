"""Pure-Python diagnosis of Reverse sample/cell/mesh reconstruction losses."""
import math

from shadow_forward_equivalent_validator import (
    build_prismatic_shadow_states, is_prism_shadowed)
from shadow_reverse_envelope_evaluation import (
    _sample_polygon, evaluate_prism_against_reverse_envelope)
from shadow_reverse_low_rise import _inside


METHOD = "sample_instant_reconstruction_cause_decomposition_v1"


def _empty(fixture, maximum_height_m):
    return {"method": METHOD, "fixture_id": fixture.get("fixture_id"),
        "maximum_height_m": maximum_height_m, "forward_v2_v3_excess_m": None,
        "measurement_specific_sample_instant_excess_m": None,
        "measurement_specific_ownership_cell_excess_m": None,
        "ownership_cell_expansion_delta_m": None,
        "combined_temporal_facet_delta_m": None, "ray_facet_delta_m": None,
        "cell_or_grid_excess_m": None, "mesh_evaluated_excess_m": None,
        "spatial_mesh_delta_m": None,
        "original_building_fits_sample_instant_inverse": None,
        "sample_instant_reconstruction_complete": False,
        "ownership_cell_reconstruction_complete": False,
        "cause_decomposition_complete": False, "diagnostic_evaluation_count": 0,
        "blockers": [], "warnings": []}


def build_reverse_reconstruction_diagnostic(
        fixture, resolved_preset, measurement_points, site_boundary_geometry,
        ownership_cell_replay, maximum_height_m=31.0, temporal_step_minutes=15,
        grid_resolution_m=1.0, vertical_height_step_m=0.5,
        maximum_diagnostic_evaluations=5000000):
    """Replay exact sample states against finite site-cell prisms.

    A cell is constrained only when the original prism did not shadow the same
    measurement point at the same Forward sample instant.  No temporal ownership
    expansion or adjacent-ray facet is used.
    """
    result = _empty(fixture, maximum_height_m)
    try:
        cap, resolution, step, temporal = map(float, (maximum_height_m,
            grid_resolution_m, vertical_height_step_m, temporal_step_minutes))
        guard = int(maximum_diagnostic_evaluations)
        if (not all(math.isfinite(v) and v > 0 for v in (cap, resolution, step, temporal))
                or guard <= 0 or guard != maximum_diagnostic_evaluations):
            raise ValueError()
        polygon = [(float(p["x_m"]), float(p["y_m"]))
                   for p in site_boundary_geometry["outer_loop"]]
        points = [(float(p["x_m"]), float(p["y_m"])) for p in measurement_points]
        if len(polygon) < 3 or not points:
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_reconstruction_diagnostic_input"})
        return result

    forward = build_prismatic_shadow_states(fixture, resolved_preset, points, temporal)
    states, solar = forward["shadow_states"], forward["solar_samples"]
    ox = math.floor(min(p[0] for p in polygon) / resolution) * resolution
    oy = math.floor(min(p[1] for p in polygon) / resolution) * resolution
    nx = int(round((math.ceil(max(p[0] for p in polygon) / resolution) * resolution-ox)/resolution))+1
    ny = int(round((math.ceil(max(p[1] for p in polygon) / resolution) * resolution-oy)/resolution))+1
    levels = [min(cap, index * step) for index in range(int(math.ceil(cap / step))+1)]
    levels = sorted(set(levels))
    grid = []
    evaluations = 0
    measurement_height = float(fixture["measurement_height_m"])
    for index in range(nx * ny):
        x, y = ox+(index % nx)*resolution, oy+(index // nx)*resolution
        inside = _inside((x, y), polygon, 1e-8) is not False
        limit = cap if inside else None
        if inside:
            half = resolution / 2.0
            cell = [(x-half, y-half), (x+half, y-half),
                    (x+half, y+half), (x-half, y+half)]
            for q, point in enumerate(points):
                for k, sample_solar in enumerate(solar):
                    if states[q][k]:
                        continue
                    # Monotonicity permits an exact cap precheck: when the cap
                    # casts no shadow, no lower enumerated level can constrain.
                    evaluations += 1
                    if evaluations > guard:
                        result["diagnostic_evaluation_count"] = evaluations
                        result["blockers"].append({"failure_code":
                            "maximum_diagnostic_evaluations_exceeded",
                            "maximum_diagnostic_evaluations": guard})
                        return result
                    if not is_prism_shadowed(point, cell, cap,
                                             measurement_height, sample_solar):
                        continue
                    candidates = [value for value in levels if value > measurement_height]
                    low, high = 0, len(candidates)-1
                    first_shadow = high
                    while low <= high:
                        candidate_index = (low+high)//2
                        height = candidates[candidate_index]
                        evaluations += 1
                        if evaluations > guard:
                            result["diagnostic_evaluation_count"] = evaluations
                            result["blockers"].append({"failure_code":
                                "maximum_diagnostic_evaluations_exceeded",
                                "maximum_diagnostic_evaluations": guard})
                            return result
                        if is_prism_shadowed(point, cell, height,
                                             measurement_height, sample_solar):
                            first_shadow = candidate_index
                            high = candidate_index-1
                        else:
                            low = candidate_index+1
                    previous = (max([value for value in levels
                                     if value <= measurement_height] or [0.0])
                                if first_shadow == 0 else candidates[first_shadow-1])
                    limit = min(limit, previous)
        grid.append({"grid_index": index, "ix": index % nx, "iy": index // nx,
                     "x_m": x, "y_m": y, "inside_site": inside,
                     "bounded": inside, "height_limit_m": limit})
    triangles = []
    for iy in range(ny-1):
        for ix in range(nx-1):
            ids = (iy*nx+ix, iy*nx+ix+1, (iy+1)*nx+ix+1, (iy+1)*nx+ix)
            if all(grid[i]["inside_site"] for i in ids):
                for vertices in ((ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])):
                    triangles.append({"triangle_index": len(triangles),
                                      "vertex_grid_indices": list(vertices)})
    envelope = {"height_field": {"grid_spec": {"x_count": nx, "y_count": ny,
        "origin_x_m": ox, "origin_y_m": oy, "resolution_m": resolution},
        "grid_points": grid}, "top_surface_mesh": {"triangles": triangles}}
    footprint = [(float(p[0]), float(p[1])) for p in fixture["building_footprint"]]
    validation = _sample_polygon(footprint, 0.5)
    cell_excess = 0.0
    cell_unbounded = 0
    for x, y in validation:
        ix, iy = int(math.floor((x-ox)/resolution+0.5)), int(math.floor((y-oy)/resolution+0.5))
        if not (0 <= ix < nx and 0 <= iy < ny):
            cell_unbounded += 1
            continue
        limit = grid[iy*nx+ix]["height_limit_m"]
        if limit is None:
            cell_unbounded += 1
        else:
            cell_excess = max(cell_excess, float(fixture["building_height_m"])-limit)
    mesh_fit = evaluate_prism_against_reverse_envelope(
        fixture["building_footprint"], fixture["building_height_m"], envelope)
    mesh_excess = mesh_fit["maximum_height_excess_m"]
    sample_complete = bool(triangles) and not cell_unbounded and mesh_fit["unbounded_point_count"] == 0
    ownership_excess = ownership_cell_replay.get("measurement_specific_excess_m")
    ownership_complete = bool(ownership_cell_replay.get("inverse_reconstruction_complete"))
    baseline = ownership_cell_replay.get("zone_common_v2_or_v3_excess_m")
    combined = (float(ownership_excess)-mesh_excess
                if ownership_excess is not None and sample_complete else None)
    result.update({"maximum_height_m": cap, "forward_v2_v3_excess_m": baseline,
        "measurement_specific_sample_instant_excess_m": mesh_excess,
        "measurement_specific_ownership_cell_excess_m": ownership_excess,
        # The representations differ, so this must not be labelled temporal-only.
        "combined_temporal_facet_delta_m": combined,
        "cell_or_grid_excess_m": cell_excess,
        "mesh_evaluated_excess_m": mesh_excess,
        "spatial_mesh_delta_m": mesh_excess-cell_excess if sample_complete else None,
        "original_building_fits_sample_instant_inverse": bool(sample_complete and mesh_excess <= 1e-9),
        "sample_instant_reconstruction_complete": sample_complete,
        "ownership_cell_reconstruction_complete": ownership_complete,
        # Ray/facet has no common finite-cell representation yet, so the full
        # causal decomposition is deliberately incomplete even when both
        # reconstructions themselves complete.
        "cause_decomposition_complete": False,
        "diagnostic_evaluation_count": evaluations,
        "height_field": envelope["height_field"], "top_surface_mesh": envelope["top_surface_mesh"],
        "sample_instant_envelope_fit": mesh_fit})
    result["warnings"].extend([
        "ownership_cell_expansion_delta_m is null because ownership-cell facets and finite-cell sample predicates are not the same spatial representation.",
        "ray_facet_delta_m is null because an apple-to-apple finite-cell adjacent-ray-facet reconstruction is unavailable.",
        "combined_temporal_facet_delta_m combines temporal ownership expansion, ray/facet geometry, and representation differences; it is not an ownership-cell-only cause.",
        "Boundary cells use their full finite square footprint; cell/grid and triangulated-mesh results are reported separately."])
    if not sample_complete:
        result["blockers"].append({"failure_code": "sample_instant_reconstruction_incomplete"})
    return result
