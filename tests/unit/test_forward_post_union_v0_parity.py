"""Python-authoritative post-union duration and contour parity fixture."""
import json
from pathlib import Path

import pytest
from shadow_contours import build_equal_time_contours
from shadow_duration import build_shadow_duration, integrate_shadow_states_trapezoidal

FIXTURE = Path(__file__).parents[1] / "fixtures" / "parity" / "forward_post_union_v0.json"


def test_python_reference_matches_post_union_parity_fixture():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = fixture["input"]
    expected = fixture["expected"]
    tolerance = fixture["tolerances"]

    duration = build_shadow_duration(source["unified_shadow_slices"], source["duration_settings"])
    contours = build_equal_time_contours(duration, source["contour_settings"])

    assert duration["complete"] and contours["complete"]
    assert duration["temporal_step_minutes"] is expected["temporal_step_minutes"]
    assert duration["grid_spec"] == expected["grid_spec"]
    assert len(duration["duration_grid"]) == expected["logical_grid_point_count"]
    assert duration["maximum_shadow_duration_minutes"] == pytest.approx(
        expected["maximum_shadow_duration_minutes"], abs=tolerance["duration_minutes"])
    assert duration["shadowed_point_count"] == expected["shadowed_point_count"]
    assert [point["shadow_duration_minutes"] for point in duration["duration_grid"]] == pytest.approx(
        expected["duration_values_minutes"], abs=tolerance["duration_minutes"])
    for key in ("requested_levels_minutes", "generated_levels_minutes", "contour_count",
                "closed_contour_count", "open_contour_count", "contours", "permit_ready_certified"):
        assert contours[key] == expected[key]

    changing = expected["changing_state_point"]
    assert len(set(changing["states"])) > 1
    assert integrate_shadow_states_trapezoidal(
        changing["states"], [item["true_solar_minutes"] for item in source["unified_shadow_slices"]["slices"]]
    ) == pytest.approx(changing["duration_minutes"], abs=tolerance["duration_minutes"])
