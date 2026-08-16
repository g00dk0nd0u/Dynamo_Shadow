"""Focused parity coverage for the compiled solar / True North contract."""
import json
from pathlib import Path

import pytest
from shadow_sun import _sun_position_for_true_solar_minutes


FIXTURE = Path(__file__).parents[1] / "fixtures" / "parity" / "forward_solar_true_north_v0.json"
SOLAR_FIELDS = (
    "solar_altitude_deg",
    "solar_azimuth_deg",
    "shadow_azimuth_true_north_deg",
    "shadow_azimuth_model_deg",
    "shadow_length_factor",
)


def test_forward_solar_true_north_fixture_is_python_reference_output():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    inputs = fixture["input"]

    for case in fixture["cases"]:
        for expected in case["samples"]:
            actual = _sun_position_for_true_solar_minutes(
                expected["true_solar_minutes"],
                inputs["latitude_deg"],
                inputs["solar_declination_deg"],
                case["true_north_deg"],
            )
            for field in SOLAR_FIELDS:
                assert actual[field] == pytest.approx(expected[field], abs=1e-6)
            for axis in ("x", "y"):
                assert actual["shadow_direction_model"][axis] == pytest.approx(
                    expected["shadow_direction_model"][axis], abs=1e-12
                )


def test_true_north_rotates_only_model_space_orientation_with_canonical_sign():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_angle = {case["true_north_deg"]: case["samples"] for case in fixture["cases"]}

    for index, baseline in enumerate(by_angle[0.0]):
        for true_north_deg in (30.0, -30.0):
            rotated = by_angle[true_north_deg][index]
            assert rotated["shadow_azimuth_model_deg"] == pytest.approx(
                (baseline["shadow_azimuth_model_deg"] + true_north_deg) % 360.0,
                abs=1e-6,
            )
            for invariant in (
                "solar_altitude_deg",
                "solar_azimuth_deg",
                "shadow_azimuth_true_north_deg",
                "shadow_length_factor",
            ):
                assert rotated[invariant] == baseline[invariant]
