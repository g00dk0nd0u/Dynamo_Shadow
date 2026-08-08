"""Causal replay of Forward-equivalent shadow states (research diagnostic only)."""
import math

from shadow_forward_equivalent_validator import build_prismatic_shadow_states

METHOD = "forward_equivalent_shadow_state_replay_v1"


def build_shadow_state_replay(fixture, resolved_preset, measurement_points,
                              maximum_height_m=31.0, temporal_step_minutes=15):
    result = {"method": METHOD, "fixture_id": fixture.get("fixture_id"),
              "maximum_height_m": maximum_height_m, "forward_shadow_state_count": 0,
              "inverse_reconstruction_complete": False,
              "original_building_fits_reconstructed_envelope": None,
              "maximum_height_excess_m": None, "temporal_pattern_limitation_only": None,
              "blockers": [], "warnings": []}
    try:
        cap = float(maximum_height_m)
        if not math.isfinite(cap) or cap <= 0:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        result["blockers"].append({"failure_code": "invalid_maximum_height_m"})
        return result
    points = [(float(p[0]), float(p[1])) if not isinstance(p, dict) else
              (float(p["x_m"]), float(p["y_m"])) for p in measurement_points]
    data = build_prismatic_shadow_states(fixture, resolved_preset, points, temporal_step_minutes)
    states = data["shadow_states"]
    result["maximum_height_m"] = cap
    result["sample_minutes"] = data["sample_minutes"]
    result["measurement_point_count"] = len(points)
    result["shadow_states"] = states
    result["forward_shadow_state_count"] = sum(sum(bool(value) for value in row) for row in states)

    # Find the exact (to reported tolerance) height cap for this same finite prism:
    # candidate shadow is permitted only where the original q,k state was shadow.
    def satisfies_replay(height):
        candidate = build_prismatic_shadow_states(
            fixture, resolved_preset, points, temporal_step_minutes,
            building_height_m=height)["shadow_states"]
        return all(not candidate[q][k] or states[q][k]
                   for q in range(len(points)) for k in range(len(data["sample_minutes"])))

    low, high = 0.0, cap
    if satisfies_replay(high):
        reconstructed_height = high
    else:
        for _ in range(32):
            midpoint = (low + high) / 2.0
            if satisfies_replay(midpoint): low = midpoint
            else: high = midpoint
        reconstructed_height = low
    result["reconstructed_same_prism_height_limit_m"] = reconstructed_height
    result["reconstruction_height_tolerance_m"] = cap / (2.0 ** 32)
    original_height = float(fixture["building_height_m"])
    excess = max(0.0, original_height - reconstructed_height)
    result["maximum_height_excess_m"] = excess
    result["original_building_fits_reconstructed_envelope"] = excess <= 1e-9
    result["blockers"].append({"failure_code": "replay_spatial_semantics_not_identical",
        "detail": "Forward replays a finite prismatic footprint; production Reverse reconstructs a sampled point-height cone envelope."})
    result["warnings"].append("Causal q-by-k states are exact for the pure-Python Forward-equivalent prism, but spatial reconstruction is intentionally not claimed complete.")
    return result
