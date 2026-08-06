import math
from shadow_reverse_low_rise import build_midday_sunlight_interval, evaluate_adjacent_ray_facet


def test_midday_interval_example():
    value = build_midday_sunlight_interval(480, 960, 180)
    assert value["required_sunlight_minutes"] == 300
    assert (value["sunlight_start_minutes"], value["sunlight_end_minutes"]) == (570, 870)


def test_analytic_facet_45_degrees():
    h = math.sqrt(.5)
    ray0 = {"x": 0, "y": h, "z": h}
    ray1 = {"x": .01, "y": math.sqrt(.5-.0001), "z": h}
    value = evaluate_adjacent_ray_facet((0,0), (0,10), ray0, ray1)
    assert math.isclose(4 + value["delta_z_m"], 14, abs_tol=1e-9)
    assert value["conservative_endpoint_altitude_clamp_applied"]
