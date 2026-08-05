import importlib

from shadow_site_geometry import build_site_boundary_geometry
from shadow_site_masks import build_measurement_masks
from shadow_duration import build_shadow_duration


def extraction_rect():
    pts=[(0,0,0),(20,0,0),(20,20,0),(0,20,0)]
    segs=[]
    for i,a in enumerate(pts):
        b=pts[(i+1)%len(pts)]
        segs.append({"curve_type":"Line","segment_index":i,"start":{"x_m":a[0],"y_m":a[1],"z_m":a[2]},"end":{"x_m":b[0],"y_m":b[1],"z_m":b[2]}})
    return {"complete":True,"loops":[{"segment_count":4,"segments":segs}],"maximum_z_difference_m":0.0,"blockers":[],"warnings":[]}


def test_adapter_import_without_revit():
    assert importlib.import_module("shadow_site_area_adapter")


def test_rectangle_normalized_ccw_start_area():
    g=build_site_boundary_geometry(extraction_rect())
    assert g["complete"] is True
    assert g["outer_loop"][0] == {"x_m":0.0,"y_m":0.0}
    assert g["vertex_count"] == 4
    assert g["orientation"] == "counter_clockwise"
    assert g["area_m2"] == 400.0


def test_clockwise_reversed_to_ccw():
    e=extraction_rect(); e["loops"][0]["segments"]=list(reversed([{"curve_type":"Line","segment_index":i,"start":s["end"],"end":s["start"]} for i,s in enumerate(e["loops"][0]["segments"])]))
    assert build_site_boundary_geometry(e)["orientation"] == "counter_clockwise"


def test_unsupported_curve_propagated():
    e=extraction_rect(); e["loops"][0]["segments"][1]["curve_type"]="Arc"
    r=build_site_boundary_geometry(e)
    assert r["complete"] is False
    assert r["blockers"][0]["failure_code"] == "unsupported_site_boundary_curve_type"


def test_disconnected_and_nonplanar_blockers():
    e=extraction_rect(); e["loops"][0]["segments"][1]["start"]["x_m"] += 1
    assert build_site_boundary_geometry(e)["blockers"][0]["failure_code"] == "site_boundary_disconnected_segments"
    e=extraction_rect(); e["maximum_z_difference_m"] = 0.01
    assert build_site_boundary_geometry(e)["blockers"][0]["failure_code"] == "site_boundary_area_nonplanar"


def test_masks_distance_thresholds_and_tie_break():
    g=build_site_boundary_geometry(extraction_rect())
    dur={"complete":True,"duration_grid":[
        {"x_m":10,"y_m":10,"shadow_duration_minutes":1},
        {"x_m":0,"y_m":10,"shadow_duration_minutes":2},
        {"x_m":-4.99,"y_m":10,"shadow_duration_minutes":3},
        {"x_m":-5.0,"y_m":10,"shadow_duration_minutes":4},
        {"x_m":-5.01,"y_m":10,"shadow_duration_minutes":5},
        {"x_m":-10.0,"y_m":10,"shadow_duration_minutes":6},
        {"x_m":-10.01,"y_m":10,"shadow_duration_minutes":7},
        {"x_m":30.01,"y_m":10,"shadow_duration_minutes":7},
    ]}
    m=build_measurement_masks(dur,g)
    assert m["complete"] is True
    assert m["zone_counts"]["inside_site"] == 1
    assert m["zone_counts"]["on_site_boundary"] == 1
    assert m["zone_counts"]["outside_0_to_5m"] == 2
    assert m["zone_counts"]["near_5_to_10m"] == 2
    assert m["zone_counts"]["far_over_10m"] == 2
    assert m["near"]["maximum_shadow_duration_minutes"] == 6
    assert m["far"]["point"]["x_m"] == -10.01
    assert "points" not in m


def test_duration_includes_site_bounds_metadata():
    slices={"complete":True,"slices":[{"complete":True,"true_solar_time":"08:00","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]},{"complete":True,"true_solar_time":"08:30","polygons":[{"role":"outer","points_m":[{"x":100,"y":100},{"x":101,"y":100},{"x":100,"y":101}]}]}]}
    settings={"normalized":{"grid_resolution_m":10,"analysis_margin_m":0,"max_duration_grid_points":10000}}
    d=build_shadow_duration(slices, settings, site_boundary_geometry=build_site_boundary_geometry(extraction_rect()))
    assert d["site_boundary_bounds_included"] is True
    assert "site_boundary_area_expanded_10m" in d["bounds_sources"]
    assert d["bounds_m"]["min_x"] <= -10
