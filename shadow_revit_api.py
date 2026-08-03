# Optional Revit API imports for Dynamo/Revit and normal Python compatibility.
try:
    import clr
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import BuiltInCategory, Options, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh, UnitUtils, Element, ElementId
    try:
        from Autodesk.Revit.DB import UnitTypeId
    except Exception:
        UnitTypeId = None
    try:
        from Autodesk.Revit.DB import DisplayUnitType
    except Exception:
        DisplayUnitType = None
except Exception:
    BuiltInCategory = Options = Solid = GeometryInstance = Face = PlanarFace = Edge = Curve = Mesh = UnitUtils = Element = ElementId = UnitTypeId = DisplayUnitType = None

# APIs used by planned native-first paths are deliberately isolated. A class
# missing from a particular Revit release must not disable the core imports.
try:
    from Autodesk.Revit.DB import CurveLoop
except Exception:
    CurveLoop = None

try:
    from Autodesk.Revit.DB import CurveElement
except Exception:
    CurveElement = None

try:
    from Autodesk.Revit.DB import ModelCurve
except Exception:
    ModelCurve = None

try:
    from Autodesk.Revit.DB import Plane, XYZ
except Exception:
    Plane = XYZ = None

try:
    from Autodesk.Revit.DB import SolidUtils
except Exception:
    SolidUtils = None

try:
    from Autodesk.Revit.DB import ExtrusionAnalyzer
except Exception:
    ExtrusionAnalyzer = None

try:
    from Autodesk.Revit.DB import BooleanOperationsUtils, BooleanOperationsType
except Exception:
    BooleanOperationsUtils = BooleanOperationsType = None

try:
    from Autodesk.Revit.DB import GeometryCreationUtilities, Line
except Exception:
    GeometryCreationUtilities = Line = None

try:
    from Autodesk.Revit.DB import ProjectLocation, SiteLocation
except Exception:
    ProjectLocation = SiteLocation = None

try:
    from Autodesk.Revit.DB import SunAndShadowSettings
except Exception:
    SunAndShadowSettings = None

# Preview-only APIs.  Keep these isolated from the formal geometry imports.
try:
    from Autodesk.Revit.DB import (DirectShape,
        FilteredElementCollector, FillPatternElement, OverrideGraphicSettings,
        Color, SubTransaction)
except Exception:
    DirectShape = FilteredElementCollector = None
    FillPatternElement = OverrideGraphicSettings = Color = SubTransaction = None

# Revit 2024 exposes the plan-specific DirectShape representation, but keep it
# optional so an older runtime cannot disable the ordinary Curve path.
try:
    from Autodesk.Revit.DB import DirectShapeTargetViewType
except Exception:
    DirectShapeTargetViewType = None


def _has_methods(value, names):
    return value is not None and all(hasattr(value, name) for name in names)


# "expected" capabilities describe import-time class/member availability only;
# they do not guarantee that a path will succeed with a particular Revit model.
REVIT_API_CAPABILITIES = {
    "revit_api_loaded": BuiltInCategory is not None,
    "curve_loop_available": CurveLoop is not None,
    "plane_xyz_available": Plane is not None and XYZ is not None,
    "face_get_edges_as_curve_loops_expected": Face is not None and hasattr(Face, "GetEdgesAsCurveLoops"),
    "solid_utils_available": SolidUtils is not None,
    "solid_utils_split_volumes_expected": SolidUtils is not None and hasattr(SolidUtils, "SplitVolumes"),
    "extrusion_analyzer_available": ExtrusionAnalyzer is not None,
    "boolean_operations_available": BooleanOperationsUtils is not None and BooleanOperationsType is not None,
    "formal_shadow_union_api_available": (
        BooleanOperationsUtils is not None and BooleanOperationsType is not None
        and GeometryCreationUtilities is not None and SolidUtils is not None
        and CurveLoop is not None and Line is not None and XYZ is not None
        and PlanarFace is not None
        and hasattr(BooleanOperationsUtils, "ExecuteBooleanOperation")
        and hasattr(GeometryCreationUtilities, "CreateExtrusionGeometry")
        and hasattr(SolidUtils, "SplitVolumes")
    ),
    "project_location_available": ProjectLocation is not None and SiteLocation is not None,
    "sun_and_shadow_settings_available": SunAndShadowSettings is not None,
    "unit_utils_available": UnitUtils is not None,
    "direct_shape_plan_representation_available": DirectShapeTargetViewType is not None,
    "unit_type_id_available": UnitTypeId is not None,
    "legacy_display_unit_type_available": DisplayUnitType is not None,
    "native_curve_loop_path_expected": (
        Face is not None
        and CurveLoop is not None
        and hasattr(Face, "GetEdgesAsCurveLoops")
        and _has_methods(CurveLoop, (
            "IsOpen", "HasPlane", "GetPlane", "IsCounterclockwise", "Flip",
            "GetExactLength", "NumberOfCurves",
        ))
    ),
    "native_shadow_analyzer_path_expected": (
        SolidUtils is not None
        and Plane is not None
        and XYZ is not None
        and ExtrusionAnalyzer is not None
        and hasattr(SolidUtils, "SplitVolumes")
        and _has_methods(ExtrusionAnalyzer, ("Create", "GetExtrusionBase", "Dispose"))
    ),
    "project_location_read_path_expected": _has_methods(
        ProjectLocation, ("GetSiteLocation", "GetProjectPosition")
    ),
    "sun_frame_read_path_expected": _has_methods(
        SunAndShadowSettings, ("GetFrameAltitude", "GetFrameAzimuth", "GetFrameTime")
    ),
    "unit_type_si_ids_expected": (
        UnitTypeId is not None
        and getattr(UnitTypeId, "Meters", None) is not None
        and getattr(UnitTypeId, "SquareMeters", None) is not None
        and getattr(UnitTypeId, "CubicMeters", None) is not None
    ),
}
