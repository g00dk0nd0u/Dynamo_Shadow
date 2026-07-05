# Optional Revit API imports for Dynamo/Revit and normal Python compatibility.
try:
    import clr
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import BuiltInCategory, Options, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh
except Exception:
    BuiltInCategory = Options = Solid = GeometryInstance = Face = PlanarFace = Edge = Curve = Mesh = None
