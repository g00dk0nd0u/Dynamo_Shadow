import json

import pytest

from shadow_debug import (
    _build_debug_log_payload,
    _formal_footprint_debug_summary,
    _polygon_convexity_summary,
)


L_SHAPE = [
    {"x": 0.0, "y": 0.0},
    {"x": 4.0, "y": 0.0},
    {"x": 4.0, "y": 2.0},
    {"x": 2.0, "y": 2.0},
    {"x": 2.0, "y": 4.0},
    {"x": 0.0, "y": 4.0},
]


def _formal_extraction(points=L_SHAPE):
    return {
        "formal_footprints": {
            "available": True,
            "complete": True,
            "partial_success": False,
            "ready_for_shadow_projection_input": True,
            "tolerance_m_used": 0.001,
            "caster_count": 1,
            "successful_caster_count": 1,
            "failed_caster_count": 0,
            "polygon_count": 1,
            "outer_loop_count": 1,
            "inner_loop_count": 0,
            "unknown_role_count": 0,
            "invalid_loop_count": 0,
            "boolean_union_performed": False,
            "items": [{
                "polygon_index": 0,
                "source_caster_index": 0,
                "source_candidate_index": 0,
                "source_face_index": 1,
                "source_loop_index": 0,
                "point_count": len(points),
                "area_m2": 12.0,
                "area_m2_signed": 12.0,
                "orientation": "ccw",
                "role": "outer",
                "containment_depth": 0,
                "classification_group_key": [0, 1],
                "closed": True,
                "units": "meter",
                "points_m": points,
                "endpoints_m": [{"x": 99.0, "y": 99.0}],
            }],
            "invalid_loops": [],
            "blockers": [],
            "warnings": [],
        }
    }


def test_l_shape_debug_summary_preserves_concavity_without_coordinates():
    summary = _formal_footprint_debug_summary(_formal_extraction())
    item = summary["items"][0]
    assert summary["polygon_count"] == 1
    assert summary["outer_loop_count"] == 1
    assert summary["inner_loop_count"] == 0
    assert summary["invalid_loop_count"] == 0
    assert summary["complete"] is True
    assert summary["ready_for_shadow_projection_input"] is True
    assert item["point_count"] == 6
    assert item["area_m2"] == 12.0
    assert item["role"] == "outer"
    assert item["is_convex"] is False
    assert item["concave_vertex_count"] >= 1
    assert "points_m" not in item and "endpoints_m" not in item


def test_rectangle_is_convex():
    rectangle = [
        {"x": 0.0, "y": 0.0}, {"x": 2.0, "y": 0.0},
        {"x": 2.0, "y": 1.0}, {"x": 0.0, "y": 1.0},
    ]
    assert _polygon_convexity_summary(rectangle) == {
        "is_convex": True,
        "concave_vertex_count": 0,
    }


def test_l_shape_convexity_is_winding_independent():
    forward = _polygon_convexity_summary(L_SHAPE)
    reverse = _polygon_convexity_summary(list(reversed(L_SHAPE)))
    assert forward == reverse
    assert forward["is_convex"] is False
    assert forward["concave_vertex_count"] >= 1


def test_debug_payload_adds_summary_without_geometry_or_private_fields():
    payload = _build_debug_log_payload({
        "success": True,
        "footprint_extraction": _formal_extraction(),
    })
    assert "footprint_extraction_summary" in payload
    assert payload["formal_footprint_summary"]["polygon_count"] == 1
    text = json.dumps(payload["formal_footprint_summary"])
    for forbidden in ("points_m", "endpoints_m", "absolute_path", "Autodesk.Revit.DB"):
        assert forbidden not in text


@pytest.mark.parametrize("footprint_extraction", [None, {}, {"formal_footprints": None}])
def test_missing_formal_footprints_has_safe_empty_summary(footprint_extraction):
    summary = _formal_footprint_debug_summary(footprint_extraction)
    assert summary["available"] is False
    assert summary["polygon_count"] == 0
    assert summary["items"] == []
    assert summary["invalid_loops"] == []


def test_invalid_loop_summary_is_allowlisted_and_keeps_reasons():
    extraction = {
        "formal_footprints": {
            "invalid_loop_count": 1,
            "invalid_loops": [{
                "caster_index": 2,
                "candidate_index": 3,
                "source_face_index": 4,
                "source_loop_index": 5,
                "reasons": ["segment graph is open"],
                "points_m": L_SHAPE,
                "geometry": "Autodesk.Revit.DB.Face",
                "absolute_path": "/home/alice/model.rvt",
            }],
        }
    }
    summary = _formal_footprint_debug_summary(extraction)
    assert summary["invalid_loops"] == [{
        "caster_index": 2,
        "candidate_index": 3,
        "source_face_index": 4,
        "source_loop_index": 5,
        "reasons": ["segment graph is open"],
    }]
    text = json.dumps(summary)
    assert "points_m" not in text
    assert "Autodesk.Revit.DB" not in text
    assert "/home/alice" not in text
