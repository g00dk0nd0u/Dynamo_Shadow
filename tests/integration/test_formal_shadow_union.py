import json

import shadow_union as union


def polygon(points, role="outer", caster=0, index=0):
    area = abs(union._signed_area(points))
    return {"generation_method": union.GENERATION_METHOD, "closed": True,
            "role": role, "points_m": [{"x": x, "y": y} for x, y in points],
            "area_m2": area, "caster_index": caster, "source_solid_index": 0,
            "split_solid_index": 0, "polygon_index": index}


def test_contract_rejects_non_formal_open_and_non_finite_polygons():
    valid = polygon([(0, 0), (2, 0), (2, 1), (0, 1)])
    assert union._valid_polygon(valid) == []
    invalid = dict(valid, generation_method="convex_hull", closed=False)
    invalid["points_m"] = [{"x": float("inf"), "y": 0}, {"x": 1, "y": 0}, {"x": 0, "y": 1}]
    reasons = union._valid_polygon(invalid)
    assert "unsupported_formal_polygon_generation_method" in reasons
    assert "formal_polygon_not_closed" in reasons
    assert "formal_polygon_non_finite_coordinate" in reasons


def test_grouping_is_deterministic_and_preserves_contained_hole():
    outer = polygon([(0, 0), (4, 0), (4, 4), (0, 4)], caster=2, index=7)
    inner = polygon([(1, 1), (1, 2), (2, 2), (2, 1)], "inner", caster=2, index=8)
    groups = union._group_slice([inner, outer])
    assert len(groups) == 1
    assert groups[0]["outer"] is outer and groups[0]["inners"] == [inner]
    assert groups[0]["key"] == (2, 0, 0, 7)


def test_capability_failure_is_explicit_json_safe_and_blocks_duration(monkeypatch):
    monkeypatch.setitem(union.REVIT_API_CAPABILITIES, "formal_shadow_union_api_available", False)
    formal = {"slices": [{"slice_index": 0, "casters": []}]}
    result = union._build_unified_shadow_slices(formal, {"elevation_m": 4}, {})
    assert result["available"] is False
    assert result["ready_for_duration_accumulation"] is False
    assert result["blockers"] == [{"failure_code": "formal_shadow_union_api_unavailable"}]
    json.dumps(result)


def test_disposal_is_identity_aware():
    class Disposable:
        def __init__(self): self.count = 0
        def Dispose(self): self.count += 1
    item = Disposable()
    union._dispose_unique([item, item])
    assert item.count == 1
