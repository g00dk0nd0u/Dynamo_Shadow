import ast
import importlib

import pytest
from pathlib import Path


MODULE = importlib.import_module("shadow_revit_api")
SOURCE_PATH = Path(__file__).resolve().parents[1] / "shadow_revit_api.py"

CORE_NAMES = (
    "BuiltInCategory", "Options", "Solid", "GeometryInstance", "Face",
    "PlanarFace", "Edge", "Curve", "GeometryObject", "Mesh", "UnitUtils", "Element",
    "ElementId", "UnitTypeId", "DisplayUnitType",
)

OPTIONAL_NAMES = (
    "CurveLoop", "Plane", "XYZ", "SolidUtils", "ExtrusionAnalyzer",
    "BooleanOperationsUtils", "BooleanOperationsType", "ProjectLocation",
    "SiteLocation", "SunAndShadowSettings",
    "GeometryCreationUtilities", "Line", "DirectShapeTargetViewType", "ViewShapeBuilder",
)

CAPABILITY_KEYS = {
    "revit_api_loaded",
    "curve_loop_available",
    "plane_xyz_available",
    "face_get_edges_as_curve_loops_expected",
    "solid_utils_available",
    "solid_utils_split_volumes_expected",
    "extrusion_analyzer_available",
    "boolean_operations_available",
    "boolean_cut_with_half_space_available",
    "project_location_available",
    "sun_and_shadow_settings_available",
    "unit_utils_available",
    "unit_type_id_available",
    "legacy_display_unit_type_available",
    "native_curve_loop_path_expected",
    "native_shadow_analyzer_path_expected",
    "project_location_read_path_expected",
    "sun_frame_read_path_expected",
    "unit_type_si_ids_expected",
    "formal_shadow_union_api_available",
    "direct_shape_target_view_type_available",
    "view_shape_builder_available",
    "direct_shape_plan_representation_available",
}


def test_public_revit_api_names_exist():
    for name in CORE_NAMES + OPTIONAL_NAMES:
        assert hasattr(MODULE, name), name


def test_optional_imports_are_safe_without_revit():
    if MODULE.BuiltInCategory is None:
        assert all(getattr(MODULE, name) is None for name in OPTIONAL_NAMES)
        assert not MODULE.REVIT_API_CAPABILITIES["revit_api_loaded"]


def test_capability_dictionary_contains_booleans_only():
    capabilities = MODULE.REVIT_API_CAPABILITIES
    assert set(capabilities) == CAPABILITY_KEYS
    assert all(type(value) is bool for value in capabilities.values())


def test_planned_optional_apis_are_not_in_the_core_import_statement():
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    revit_imports = [
        {alias.name for alias in node.names}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "Autodesk.Revit.DB"
    ]

    optional = set(OPTIONAL_NAMES)
    assert revit_imports
    assert not any(optional <= imported_names for imported_names in revit_imports)
    assert max(len(optional & imported_names) for imported_names in revit_imports) <= 2


def test_revit_2024_capabilities_do_not_require_future_closure_methods():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "ComputeIsGeometricallyClosed" not in source
    assert "ComputeIsTopologicallyClosed" not in source


def _execute_preview_optional_imports(available):
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        names = {alias.name for child in node.body if isinstance(child, ast.ImportFrom)
                 for alias in child.names}
        if names & {"DirectShapeTargetViewType", "ViewShapeBuilder"}:
            selected.append(node)
    namespace = {}
    real_import = __import__
    class FakeDb:
        pass
    for name in available:
        setattr(FakeDb, name, type(name, (), {"Plan": object()}) if name == "DirectShapeTargetViewType" else type(name, (), {}))
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "Autodesk.Revit.DB":
            for item in fromlist:
                if not hasattr(FakeDb, item):
                    raise ImportError(item)
            return FakeDb
        return real_import(name, globals, locals, fromlist, level)
    namespace["__builtins__"] = dict(vars(__import__("builtins")), __import__=fake_import)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE_PATH), "exec"), namespace)
    target = namespace["DirectShapeTargetViewType"]
    builder = namespace["ViewShapeBuilder"]
    combined = target is not None and hasattr(target, "Plan") and builder is not None
    return target, builder, combined


@pytest.mark.parametrize("available,target,builder,combined", [
    ({"DirectShapeTargetViewType"}, True, False, False),
    ({"ViewShapeBuilder"}, False, True, False),
    ({"DirectShapeTargetViewType", "ViewShapeBuilder"}, True, True, True),
])
def test_preview_optional_imports_are_independent(available, target, builder, combined):
    actual_target, actual_builder, actual_combined = _execute_preview_optional_imports(available)
    assert (actual_target is not None) is target
    assert (actual_builder is not None) is builder
    assert actual_combined is combined
