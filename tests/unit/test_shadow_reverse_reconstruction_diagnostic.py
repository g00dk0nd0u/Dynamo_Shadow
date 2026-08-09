import json
from pathlib import Path

from shadow_forward_reverse_validation import build_forward_reverse_validation, _site_geometry
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_reverse_reconstruction_diagnostic import build_reverse_reconstruction_diagnostic


FIXTURES = Path(__file__).parents[1] / "fixtures" / "forward_reverse_validation"


def _centered():
    fixture = json.loads((FIXTURES / "centered_mismatch.json").read_text())
    validation = build_forward_reverse_validation(fixture)
    replay = validation["replay"]
    diagnostic = build_reverse_reconstruction_diagnostic(
        fixture, resolve_regulatory_shadow_preset(fixture["preset_id"]),
        replay["measurement_points"], _site_geometry(fixture["site_boundary"]), replay)
    return diagnostic


def _micro(maximum_height_m=6.3, guard=100000):
    fixture = {"fixture_id": "micro_no_mismatch", "site_latitude_deg": 35.0,
        "true_north_deg": 0.0, "measurement_height_m": 4.0,
        "building_height_m": 4.0, "building_footprint": [[0.2, 0.2], [0.8, 0.2],
        [0.8, 0.8], [0.2, 0.8]]}
    preset = {"true_solar_start_time": "09:00", "true_solar_end_time": "09:15"}
    site = _site_geometry([[0, 0], [2, 0], [2, 2], [0, 2]])
    replay = {"measurement_specific_excess_m": 0.0,
        "zone_common_v2_or_v3_excess_m": 0.0,
        "inverse_reconstruction_complete": True}
    return build_reverse_reconstruction_diagnostic(
        fixture, preset, [{"x_m": 3.0, "y_m": 3.0}], site, replay,
        maximum_height_m=maximum_height_m,
        maximum_diagnostic_evaluations=guard)


def test_centered_mismatch_decomposes_reconstruction_without_inventing_causes():
    result = _centered()
    assert result["forward_v2_v3_excess_m"] == 0.5
    assert result["measurement_specific_ownership_cell_excess_m"] == 4.0
    # Fixed sample-instant finite-cell/mesh reconstruction result.
    assert result["measurement_specific_sample_instant_excess_m"] == 4.0
    assert result["cell_or_grid_excess_m"] == 4.0
    assert result["mesh_evaluated_excess_m"] == 4.0
    assert result["spatial_mesh_delta_m"] == 0.0
    assert result["combined_temporal_facet_delta_m"] == 0.0
    assert result["ownership_cell_expansion_delta_m"] is None
    assert result["ray_facet_delta_m"] is None
    assert result["cause_decomposition_complete"] is False


def test_small_no_mismatch_diagnostic_is_deterministic_and_honors_arbitrary_cap():
    first = _micro()
    assert first == _micro()
    assert first["sample_instant_reconstruction_complete"] is True
    assert first["maximum_height_m"] == 6.3
    assert max(point["height_limit_m"] for point in first["height_field"]["grid_points"]
               if point["height_limit_m"] is not None) <= 6.3


def test_guard_blocks_without_automatic_coarse_fallback():
    result = _micro(guard=1)
    assert result["cause_decomposition_complete"] is False
    assert result["sample_instant_reconstruction_complete"] is False
    assert result["blockers"][0]["failure_code"] == "maximum_diagnostic_evaluations_exceeded"
