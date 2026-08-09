import json
from pathlib import Path

from shadow_forward_reverse_validation import build_forward_reverse_validation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "forward_reverse_validation"


def _run(name):
    fixture=json.loads((FIXTURES/name).read_text())
    return build_forward_reverse_validation(fixture)["replay"]


def _assert_reconstructed(result):
    assert result["reconstruction_method"] == "ownership_cell_atomic_facet_measurement_specific_v1"
    assert result["inverse_reconstruction_complete"] is True
    assert result["height_field"]["grid_points"]
    assert result["top_surface_mesh"]["triangles"]
    assert result["envelope_fit"]["validation_point_count"] > 0
    assert result["maximum_height_excess_m"] == result["measurement_specific_excess_m"]


def test_centered_mismatch_reconstructs_measurement_specific_inverse_envelope():
    first=_run("centered_mismatch.json")
    second=_run("centered_mismatch.json")
    assert first == second
    _assert_reconstructed(first)
    assert first["forward_shadow_state_count"] == sum(sum(row) for row in first["shadow_states"])
    assert first["zone_common_v2_or_v3_excess_m"] == 0.5
    # Fixed after evaluating the original 10 m prism against the reconstructed mesh.
    assert first["measurement_specific_excess_m"] == 4.0
    assert first["original_building_fits_reconstructed_envelope"] is False
    assert first["temporal_pattern_limitation_only"] is False


def test_existing_no_mismatch_fixture_reconstructs_deterministically():
    first=_run("east_west_asymmetric.json")
    _assert_reconstructed(first)
    assert first == _run("east_west_asymmetric.json")
    assert first["sample_minutes"] and first["maximum_height_m"] == 31.0
