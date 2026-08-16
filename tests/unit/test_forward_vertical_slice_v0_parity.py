"""Shared parity fixture driven by the existing Python reference pipeline.

For the constrained convex vertical prism v0, the portable projection fixture
uses the existing Python point-projection/convex-hull semantics. This is not a
replacement for the Revit-native formal projection path.
"""
import json
from pathlib import Path

import pytest
from shadow_contours import build_equal_time_contours
from shadow_duration import build_shadow_duration
from shadow_projection import _build_convex_shadow_envelope_v0, _project_point
from shadow_sun import _sun_position_for_true_solar_minutes

FIXTURE = Path(__file__).parents[1] / "fixtures" / "parity" / "forward_vertical_slice_v0.json"


def test_forward_vertical_slice_v0_fixture_is_python_reference_output():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8")); data = fixture["input"]; expected = fixture["expected"]
    times = [data["true_solar_start_minutes"]]; current = times[0] + data["sun_time_step_minutes"]
    while current < data["true_solar_end_minutes"] - 1e-9: times.append(current); current += data["sun_time_step_minutes"]
    if abs(times[-1] - data["true_solar_end_minutes"]) > 1e-9: times.append(data["true_solar_end_minutes"])
    samples=[]; slices=[]
    for index, minute in enumerate(times):
        solar=_sun_position_for_true_solar_minutes(minute,data["latitude_deg"],data["solar_declination_deg"],data["true_north_deg"]); samples.append(solar); points=[]
        for point in data["caster"]["footprint_points_m"]:
            points.append({"x_m":point["x"],"y_m":point["y"],"z_m":data["measurement_plane_elevation_m"]})
            points.append(_project_point({"x_m":point["x"],"y_m":point["y"],"z_m":data["caster"]["top_z_m"]},data["measurement_plane_elevation_m"],solar["shadow_direction_vector"],solar["shadow_length_factor"])["projected_point_m"])
        hull=_build_convex_shadow_envelope_v0(points,data["measurement_plane_elevation_m"])["hull_points_m"]
        slices.append({"complete":True,"true_solar_time":"{:02d}:{:02d}".format(int(minute//60),int(minute%60)),"polygons":[{"component_index":0,"role":"outer","closed":True,"points_m":[{"x":p["x_m"],"y":p["y_m"]} for p in hull]}]})
    duration=build_shadow_duration({"complete":True,"slices":slices},{"grid_resolution_m":data["grid_resolution_m"],"analysis_margin_m":data["analysis_margin_m"],"max_duration_grid_points":data["max_grid_points"],"sun_time_step_minutes":data["sun_time_step_minutes"]},sparse_tiles=False)
    contours=build_equal_time_contours(duration,{"equal_time_contour_levels_minutes":data["contour_levels_minutes"]})
    assert times == expected["sample_times_minutes"]
    assert samples[1]["solar_altitude_deg"] == pytest.approx(expected["representative_solar"]["solar_altitude_deg"],abs=1e-6)
    assert slices[1]["polygons"][0]["points_m"] == expected["representative_polygon"]["points_m"]
    assert duration["grid_spec"] == expected["grid_spec"]
    assert duration["maximum_shadow_duration_minutes"] == expected["maximum_shadow_duration_minutes"]
    assert duration["shadowed_point_count"] == expected["shadowed_point_count"]
    assert contours["generated_levels_minutes"] == expected["generated_contour_levels_minutes"]
    assert contours["contours"][0] == expected["representative_contour"]
