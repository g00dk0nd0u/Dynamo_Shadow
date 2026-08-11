import shadow_check_presentation as presentation
import shadow_contour_preview
import shadow_preview
import shadow_site_result_preview
from shadow_regulatory_presets import resolve_regulatory_shadow_preset
from shadow_readiness import _build_pipeline_readiness


class _Id:
    def __init__(self, value): self.IntegerValue = value


class _Color:
    def __init__(self, red, green, blue):
        self.Red, self.Green, self.Blue, self.IsValid = red, green, blue, True


class _Override:
    def SetProjectionLineColor(self, color): self.ProjectionLineColor = color
    def SetProjectionLineWeight(self, weight): self.ProjectionLineWeight = weight


class _View:
    def __init__(self, value, name, fail=False):
        self.Id, self.Name, self.fail = _Id(value), name, fail
        self.overrides, self.set_calls = {}, 0
    def SetElementOverrides(self, element_id, override):
        self.set_calls += 1
        if self.fail: raise RuntimeError("unsupported active view")
        self.overrides[element_id] = override
    def GetElementOverrides(self, element_id): return self.overrides[element_id]


def _override_test_setup(monkeypatch, active, managed):
    monkeypatch.setattr(presentation, "OverrideGraphicSettings", _Override)
    monkeypatch.setattr(presentation, "Color", _Color)
    document = type("Document", (), {"ActiveView": active})()
    targets = presentation._override_targets(document, managed)
    summaries = {"all": presentation.empty_readback_summary(),
                 "active": presentation.empty_readback_summary()}
    diagnostics = presentation._apply_overrides(targets, 99, "near_limit", summaries)
    return targets, summaries, diagnostics


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


def test_active_and_managed_views_each_receive_verified_override(monkeypatch):
    active, plan, three = (_View(1, "Working 3D"), _View(2, "Managed plan"),
                           _View(3, "Managed 3D"))
    targets, summaries, diagnostics = _override_test_setup(
        monkeypatch, active, [("managed_plan", plan), ("managed_3d", three)])
    assert [target["view_role"] for target in targets] == ["active", "managed_plan", "managed_3d"]
    assert all(item["verified"] for item in diagnostics)
    assert presentation.aggregate_status(summaries["all"])["graphical_overrides_verified"] is True


def test_active_view_is_deduplicated_from_managed_view_by_element_id(monkeypatch):
    active, plan = _View(3, "Managed active 3D"), _View(2, "Managed plan")
    targets, _, diagnostics = _override_test_setup(
        monkeypatch, active, [("managed_plan", plan), ("managed_3d", active)])
    assert [target["view_role"] for target in targets] == ["active", "managed_plan"]
    assert active.set_calls == 1 and len(diagnostics) == 2


def test_active_view_override_failure_is_nonfatal_to_managed_views(monkeypatch):
    active, plan, three = (_View(1, "Template", fail=True), _View(2, "Managed plan"),
                           _View(3, "Managed 3D"))
    _, summaries, diagnostics = _override_test_setup(
        monkeypatch, active, [("managed_plan", plan), ("managed_3d", three)])
    assert diagnostics[0]["set_succeeded"] is False
    assert all(item["verified"] for item in diagnostics[1:])
    assert summaries["active"]["write_failure_count"] == 1
    assert plan.set_calls == three.set_calls == 1


def test_preview_adapters_share_review_color_and_weight_rules():
    assert shadow_preview.HOURLY_SHADOW_COLOR == (0, 0, 0)
    assert shadow_preview.HOURLY_SHADOW_LINE_WEIGHT < shadow_site_result_preview.DISTANCE_LINE_WEIGHT
    assert shadow_site_result_preview._DISTANCE_STYLES == {
        5.0: ((220, 30, 30), 5), 10.0: ((30, 90, 220), 5)}
    assert shadow_contour_preview.HIGH_DURATION_CONTOUR_COLOR == (220, 30, 30)
    assert shadow_contour_preview.LOW_DURATION_CONTOUR_COLOR == (30, 90, 220)
    assert (shadow_site_result_preview.DISTANCE_LINE_WEIGHT <
            shadow_contour_preview.CONTOUR_LINE_WEIGHT)


def test_all_preset_contours_use_duration_extremes_and_fixed_geometry_semantics():
    preset = resolve_regulatory_shadow_preset("standard_all")
    groups = presentation.build_shadow_check_groups(
        {"outer_loop": [{"x_m": 0, "y_m": 0}, {"x_m": 1, "y_m": 0}, {"x_m": 1, "y_m": 1}]},
        {"contours": [dict(_contour(0), distance_m=5), dict(_contour(0), distance_m=10)]},
        {"contours": [_contour(300), _contour(180)]}, {}, preset)
    styles = {group["kind"]: group["style"] for group in groups}
    assert styles["site_boundary"] == "site_boundary"
    assert styles["site_distance_5m"] == "near_limit"
    assert styles["site_distance_10m"] == "far_limit"
    assert [g["style"] for g in groups if g["kind"] == "equal_time_contour"] == ["near_contour", "far_contour"]
    assert presentation.STYLE_SEMANTICS["site_boundary"]["rgb"] == (0, 0, 0)
    assert presentation.STYLE_SEMANTICS["near_limit"]["weight"] < presentation.STYLE_SEMANTICS["near_contour"]["weight"]
    assert presentation.STYLE_SEMANTICS["far_limit"]["weight"] < presentation.STYLE_SEMANTICS["far_contour"]["weight"]
    assert presentation.STYLE_LEGEND == {
        "hourly_shadows": "black", "high_duration_contour": "red",
        "low_duration_contour": "blue", "5m_setback": "red", "10m_setback": "blue"}


def test_optional_revit_api_absence_is_nonfatal():
    result, views = presentation.build_shadow_check_presentation(
        {}, {}, {}, {}, {}, {"elevation_m": 4, "measurement_height_m": 4},
        {"equal_time_contour_preview_mode": "replace"})
    assert result["attempted"] is True and result["available"] is False
    assert views["plan"]["available"] is False


def test_compatibility_site_groups_feed_existing_readiness_contract():
    canonical = {"enabled": True, "mode": "replace", "attempted": True,
        "available": True, "complete": True, "created_element_count": 4,
        "deleted_element_count": 0, "blockers": [], "warnings": [],
        "permit_ready_certified": False, "groups": [
            {"kind": "site_distance_5m", "created": True, "element_id": 1, "curve_count": 4},
            {"kind": "site_distance_10m", "created": True, "element_id": 2, "curve_count": 4},
            {"kind": "near_maximum_marker", "created": True, "element_id": 3, "curve_count": 2},
            {"kind": "far_maximum_marker", "created": True, "element_id": 4, "curve_count": 2},
        ]}
    _, site = presentation.build_preview_compatibility_summaries(canonical, {})
    readiness = _build_pipeline_readiness({}, {}, {}, site_result_preview=site)
    assert readiness["site_distance_revit_preview_created"] is True
    assert readiness["maximum_duration_point_preview_created"] is True


def test_equal_time_compatibility_preserves_level_counts():
    canonical = {"enabled": True, "mode": "replace", "attempted": True,
        "available": True, "complete": True, "created_element_count": 2,
        "deleted_element_count": 0, "blockers": [], "warnings": [],
        "groups": [{"kind": "equal_time_contour", "level_minutes": level,
                    "created": True, "element_id": index, "curve_count": 3}
                   for index, level in enumerate((180, 300), 1)]}
    equal, _ = presentation.build_preview_compatibility_summaries(
        canonical, {"available": True, "contours": [_contour(180), _contour(300)]})
    assert equal["requested_level_count"] == equal["created_level_count"] == 2
    assert equal["created_element_count"] == 2 and equal["partial_success"] is False


def test_compatibility_summaries_preserve_graphical_override_diagnostics():
    override = {"view_role": "active", "set_succeeded": True,
                "readback_succeeded": True, "verified": True}
    canonical = {"enabled": True, "mode": "replace", "attempted": True,
        "available": True, "complete": True, "created_element_count": 2,
        "deleted_element_count": 0, "blockers": [], "warnings": [],
        "graphical_overrides_write_succeeded": True,
        "graphical_overrides_readback_succeeded": True,
        "graphical_overrides_verified": True,
        "graphical_override_readback": {"attempted_element_count": 2},
        "groups": [
            {"kind": "equal_time_contour", "level_minutes": 300, "created": True,
             "element_id": 1, "curve_count": 3, "graphical_override": override,
             "graphical_overrides": [override]},
            {"kind": "site_distance_5m", "created": True, "element_id": 2,
             "curve_count": 4, "graphical_override": override,
             "graphical_overrides": [override]}]}
    equal, site = presentation.build_preview_compatibility_summaries(
        canonical, {"available": True, "contours": [_contour(300)]})
    assert equal["graphical_overrides_verified"] is True
    assert equal["groups"][0]["graphical_override"] == override
    assert site["groups"][0]["graphical_override"] == override


def test_cleanup_sets_include_only_exact_current_and_legacy_application_ids(monkeypatch):
    calls = []
    def collect(document, application_id):
        calls.append(application_id)
        return {"succeeded": True, "element_ids": [application_id]}
    monkeypatch.setattr(presentation, "_collect_owned_preview_ids", collect)
    current, legacy = presentation._collect_cleanup_sets(object())
    assert calls == [presentation.APPLICATION_ID] + list(presentation.LEGACY_APPLICATION_IDS)
    assert current["element_ids"] == [presentation.APPLICATION_ID]
    assert [item["element_ids"][0] for item in legacy] == list(presentation.LEGACY_APPLICATION_IDS)
    assert "Other" not in calls


def test_replace_and_clear_delete_current_and_legacy_owned_elements(monkeypatch):
    class Sub:
        def __init__(self, document): pass
        def Start(self): pass
        def Commit(self): pass
        def RollBack(self): pass
    class Transactions:
        def EnsureInTransaction(self, document): pass
        def TransactionTaskDone(self): pass
    class Document:
        Application = type("Application", (), {"ShortCurveTolerance": 0.0})()
        def __init__(self): self.deleted = []
        def Delete(self, ident): self.deleted.append(ident)
    for mode in ("replace", "clear"):
        document = Document()
        monkeypatch.setattr(presentation, "DocumentManager", type("DM", (), {
            "Instance": type("Instance", (), {"CurrentDBDocument": document})()})())
        monkeypatch.setattr(presentation, "TransactionManager", type("TM", (), {
            "Instance": Transactions()})())
        for name in ("DirectShape", "FilteredElementCollector", "XYZ", "Line", "ViewPlan",
                     "View3D", "ViewFamilyType", "ViewFamily", "View", "Level",
                     "PlanViewPlane", "BoundingBoxXYZ"):
            monkeypatch.setattr(presentation, name, object())
        monkeypatch.setattr(presentation, "SubTransaction", Sub)
        monkeypatch.setattr(presentation, "_collect_cleanup_sets", lambda doc: (
            {"succeeded": True, "element_ids": [1]},
            [{"succeeded": True, "element_ids": [2]}, {"succeeded": True, "element_ids": [3]}]))
        monkeypatch.setattr(presentation, "_prepare_views", lambda *args: {
            "plan": {"view_id": None}, "three_d": {"view_id": None}})
        monkeypatch.setattr(presentation, "_collect", lambda *args: [])
        result, _ = presentation.build_shadow_check_presentation(
            {}, {}, {}, {}, {}, {"elevation_m": 4, "measurement_height_m": 4},
            {"equal_time_contour_preview_mode": mode})
        assert result["complete"] is True
        assert result["current_deleted_element_count"] == 1
        assert result["legacy_deleted_element_count"] == 2
        assert document.deleted == [1, 2, 3]


def test_ownership_mark_failure_removes_view_and_is_not_success(monkeypatch):
    class Document:
        def __init__(self): self.deleted = []
        def Delete(self, ident): self.deleted.append(ident)
    document = Document(); view = type("View", (), {"Id": 42})()
    diagnostic = presentation._view_result("FloorPlan", 4.0, 4.0)
    monkeypatch.setattr(presentation, "_mark_view", lambda value: False)
    assert presentation._accept_new_managed_view(document, view, diagnostic,
        "ownership_failed", "Plan view") is None
    assert diagnostic["created"] is False and diagnostic["blockers"] == [{"failure_code": "ownership_failed"}]
    assert document.deleted == [42]


def test_managed_view_is_reused_without_name_growth(monkeypatch):
    managed = type("View", (), {"Name": "Dynamo_Shadow_ShadowCheck_4.0m"})()
    user = type("View", (), {"Name": "Unrelated"})()
    monkeypatch.setattr(presentation, "_collect", lambda document, cls: [managed, user])
    monkeypatch.setattr(presentation, "_owned_view", lambda view: view is managed)
    name, reused = presentation._unique_managed_name(object(), managed.Name)
    assert name == managed.Name and reused is managed
