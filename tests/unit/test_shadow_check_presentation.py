import shadow_check_presentation as presentation
from shadow_regulatory_presets import resolve_regulatory_shadow_preset


def _contour(level):
    return {"level_minutes": level, "closed": True,
            "points_m": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}


def test_regulatory_color_semantics_for_selected_pairs():
    for preset_id, near, far in (("standard_5_3", 300, 180),
                                 ("standard_4_2_5", 240, 150)):
        preset = resolve_regulatory_shadow_preset(preset_id)
        assert presentation.classify_contour_level(near, preset) == "near_contour"
        assert presentation.STYLE_SEMANTICS["near_contour"]["rgb"] == (220, 30, 30)
        assert presentation.classify_contour_level(far, preset) == "far_contour"
        assert presentation.STYLE_SEMANTICS["far_contour"]["rgb"] == (30, 90, 220)


def test_all_preset_contours_are_neutral_and_fixed_geometry_semantics():
    preset = resolve_regulatory_shadow_preset("standard_all")
    groups = presentation.build_shadow_check_groups(
        {"outer_loop": [{"x_m": 0, "y_m": 0}, {"x_m": 1, "y_m": 0}, {"x_m": 1, "y_m": 1}]},
        {"contours": [dict(_contour(0), distance_m=5), dict(_contour(0), distance_m=10)]},
        {"contours": [_contour(300), _contour(180)]}, {}, preset)
    styles = {group["kind"]: group["style"] for group in groups}
    assert styles["site_boundary"] == "site_boundary"
    assert styles["site_distance_5m"] == "near_limit"
    assert styles["site_distance_10m"] == "far_limit"
    assert [g["style"] for g in groups if g["kind"] == "equal_time_contour"] == ["neutral_contour"] * 2
    assert presentation.STYLE_SEMANTICS["site_boundary"]["rgb"] == (0, 0, 0)


def test_optional_revit_api_absence_is_nonfatal():
    result, views = presentation.build_shadow_check_presentation(
        {}, {}, {}, {}, {}, {"elevation_m": 4, "measurement_height_m": 4},
        {"equal_time_contour_preview_mode": "replace"})
    assert result["attempted"] is True and result["available"] is False
    assert views["plan"]["available"] is False
