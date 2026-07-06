# Optional Revit API imports for Dynamo/Revit and normal Python compatibility.
try:
    import clr
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import BuiltInCategory, Options, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh, UnitUtils
    try:
        from Autodesk.Revit.DB import UnitTypeId
    except Exception:
        UnitTypeId = None
    try:
        from Autodesk.Revit.DB import DisplayUnitType
    except Exception:
        DisplayUnitType = None
except Exception:
    BuiltInCategory = Options = Solid = GeometryInstance = Face = PlanarFace = Edge = Curve = Mesh = UnitUtils = UnitTypeId = DisplayUnitType = None
