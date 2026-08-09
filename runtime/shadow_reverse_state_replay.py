"""Measurement-specific inverse replay of Forward-equivalent shadow states."""
import math

from shadow_forward_equivalent_validator import build_prismatic_shadow_states
from shadow_reverse_allowance_patterns import build_trapezoidal_sample_ownership_cells
from shadow_reverse_envelope_evaluation import evaluate_prism_against_reverse_envelope
from shadow_reverse_low_rise import _compile_sun_fan, _constraint, _inside, _quantize_height
from shadow_sun import build_true_solar_sun_ray_fan_for_minutes

METHOD = "measurement_specific_shadow_state_inverse_replay_v2"
RECONSTRUCTION_METHOD = "ownership_cell_atomic_facet_measurement_specific_v1"


def build_shadow_state_replay(fixture, resolved_preset, measurement_points,
                              site_boundary_geometry, settings_normalized,
                              maximum_height_m=31.0, temporal_step_minutes=15,
                              grid_resolution_m=1.0, vertical_height_step_m=0.5,
                              zone_common_v2_or_v3_excess_m=None):
    result = {"method": METHOD, "fixture_id": fixture.get("fixture_id"),
        "maximum_height_m": maximum_height_m, "measurement_point_count": 0,
        "sample_minutes": [], "forward_shadow_state_count": 0,
        "reconstruction_method": RECONSTRUCTION_METHOD,
        "inverse_reconstruction_complete": False,
        "original_building_fits_reconstructed_envelope": None,
        "maximum_height_excess_m": None,
        "zone_common_v2_or_v3_excess_m": zone_common_v2_or_v3_excess_m,
        "measurement_specific_excess_m": None,
        "zone_common_pattern_sufficient_explanation": None,
        "temporal_pattern_limitation_only": None, "blockers": [], "warnings": []}
    try:
        cap, resolution, vertical_step, temporal_step = map(
            float, (maximum_height_m, grid_resolution_m, vertical_height_step_m,
                    temporal_step_minutes))
        if not all(math.isfinite(v) and v > 0
                   for v in (cap, resolution, vertical_step, temporal_step)):
            raise ValueError()
        polygon = [(float(p["x_m"]), float(p["y_m"]))
                   for p in site_boundary_geometry["outer_loop"]]
        points = [dict(p) for p in measurement_points]
        if len(polygon) < 3 or not points: raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_shadow_state_replay_input"})
        return result

    coordinates = [(float(p["x_m"]), float(p["y_m"])) for p in points]
    forward = build_prismatic_shadow_states(fixture, resolved_preset, coordinates,
                                             temporal_step)
    states = forward["shadow_states"]
    cells = build_trapezoidal_sample_ownership_cells(forward["sample_minutes"])
    boundaries = [cells[0]["start_minutes"]] + [cell["end_minutes"] for cell in cells]
    fan = build_true_solar_sun_ray_fan_for_minutes(settings_normalized, boundaries)
    if not fan.get("complete"):
        result["blockers"].extend(fan.get("blockers") or [])
        return result
    compiled = _compile_sun_fan(fan)
    ox = math.floor(min(p[0] for p in polygon)/resolution)*resolution
    oy = math.floor(min(p[1] for p in polygon)/resolution)*resolution
    nx = int(round((math.ceil(max(p[0] for p in polygon)/resolution)*resolution-ox)/resolution))+1
    ny = int(round((math.ceil(max(p[1] for p in polygon)/resolution)*resolution-oy)/resolution))+1
    measurement_height = float(fixture["measurement_height_m"])
    grid = []
    for index in range(nx*ny):
        x, y = ox+(index%nx)*resolution, oy+(index//nx)*resolution
        inside = _inside((x,y),polygon,1e-8) is not False
        limit = cap if inside else None
        if inside:
            for q, measurement in enumerate(points):
                value = _constraint((x,y), measurement, fan, measurement_height, compiled)
                if value is not None and not states[q][value["facet"]]:
                    limit = min(limit, _quantize_height(value["height"], vertical_step))
        grid.append({"grid_index":index,"ix":index%nx,"iy":index//nx,"x_m":x,"y_m":y,
                     "inside_site":inside,"bounded":inside,"height_limit_m":limit})
    triangles=[]
    for iy in range(ny-1):
        for ix in range(nx-1):
            ids=(iy*nx+ix,iy*nx+ix+1,(iy+1)*nx+ix+1,(iy+1)*nx+ix)
            if all(grid[i]["inside_site"] for i in ids):
                for vertices in ((ids[0],ids[1],ids[2]),(ids[0],ids[2],ids[3])):
                    triangles.append({"triangle_index":len(triangles),
                                      "vertex_grid_indices":list(vertices)})
    envelope={"height_field":{"grid_spec":{"x_count":nx,"y_count":ny,
        "origin_x_m":ox,"origin_y_m":oy,"resolution_m":resolution},"grid_points":grid},
        "top_surface_mesh":{"triangles":triangles}}
    fit=evaluate_prism_against_reverse_envelope(fixture["building_footprint"],
                                                fixture["building_height_m"],envelope)
    excess=fit["maximum_height_excess_m"]
    result.update({"maximum_height_m":cap,"measurement_point_count":len(points),
        "sample_minutes":forward["sample_minutes"],"shadow_states":states,
        "forward_shadow_state_count":sum(sum(bool(value) for value in row) for row in states),
        "inverse_reconstruction_complete":bool(triangles) and fit["unbounded_point_count"] == 0,
        "measurement_points": points,
        "original_building_fits_reconstructed_envelope":fit["fully_inside"],
        "maximum_height_excess_m":excess,"measurement_specific_excess_m":excess,
        "height_field":envelope["height_field"],"top_surface_mesh":envelope["top_surface_mesh"],
        "envelope_fit":fit})
    if result["inverse_reconstruction_complete"]:
        baseline=zone_common_v2_or_v3_excess_m
        if baseline is not None:
            result["zone_common_pattern_sufficient_explanation"] = bool(
                excess <= 1e-9 and float(baseline) > 1e-9)
    else:
        result["blockers"].append({"failure_code":"measurement_specific_inverse_reconstruction_incomplete"})
    result["warnings"].append(
        "A Forward sample state is mapped to its full trapezoidal ownership cell; sample-instant and full-cell no-shadow semantics are not identical.")
    return result
