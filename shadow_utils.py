# Safe helpers and Revit-like type checks.
import sys
from shadow_revit_api import BuiltInCategory, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh


def _get_global(name, default=None):
    try:
        if name in globals():
            return globals().get(name, default)
    except Exception:
        pass
    try:
        main_mod = sys.modules.get("__main__")
        if main_mod is not None and hasattr(main_mod, name):
            return getattr(main_mod, name)
    except Exception:
        pass
    try:
        import builtins
        if hasattr(builtins, name):
            return getattr(builtins, name)
    except Exception:
        pass
    return default

def _fallback_in(index, default=None):
    values = _get_global("IN", None)
    try:
        if values is not None and len(values) > index:
            return values[index]
    except Exception:
        pass
    return default

def _try_unwrap(value):
    unwrap = _get_global("UnwrapElement", None)
    if unwrap is None:
        return value
    try:
        return unwrap(value)
    except Exception:
        return value

def _is_string(value):
    try:
        return isinstance(value, basestring)
    except NameError:
        return isinstance(value, str)

def _is_sequence(value):
    if value is None or _is_string(value):
        return False
    if isinstance(value, dict):
        return False
    try:
        iter(value)
        return True
    except Exception:
        return False

def _to_list(value):
    if value is None:
        return []
    if _is_sequence(value):
        try:
            return list(value)
        except Exception:
            return [value]
    return [value]

def _safe_text(value):
    if value is None:
        return None
    try:
        text = str(value)
    except Exception:
        try:
            text = repr(value)
        except Exception:
            text = "<unrepresentable>"
    if len(text) > 160:
        return text[:157] + "..."
    return text

def _safe_attr(value, attr):
    try:
        attr_value = getattr(value, attr)
    except Exception:
        return None
    try:
        if callable(attr_value):
            return attr_value()
    except Exception:
        return None
    return attr_value

def _safe_call(value, method_name, *args):
    try:
        method = getattr(value, method_name)
    except Exception:
        return None, "{0} is not available".format(method_name)
    if not callable(method):
        return None, "{0} is not callable".format(method_name)
    try:
        return method(*args), None
    except Exception as exc:
        return None, _safe_text(exc)

def _revit_id_to_int(value):
    if value is None:
        return None
    for attr in ("IntegerValue", "Value"):
        raw = _safe_attr(value, attr)
        if raw is not None:
            try:
                return int(raw)
            except Exception:
                pass
    try:
        return int(value)
    except Exception:
        return None

def _built_in_category_value(value):
    raw = _safe_attr(value, "value__")
    if raw is not None:
        try:
            return int(raw)
        except Exception:
            pass
    try:
        return int(value)
    except Exception:
        return None

def _element_id(value):
    element_id = _safe_attr(value, "Id")
    if element_id is None:
        return None
    integer_id = _revit_id_to_int(element_id)
    if integer_id is not None:
        return integer_id
    return _safe_text(element_id)

def _category(value):
    return _safe_attr(value, "Category")

def _category_id_from_category(category):
    if category is None:
        return None
    category_id = _safe_attr(category, "Id")
    integer_id = _revit_id_to_int(category_id)
    if integer_id is not None:
        return integer_id
    return _safe_text(category_id) if category_id is not None else None

def _category_name(value):
    category = _category(value)
    name = _safe_attr(category, "Name") if category is not None else None
    return _safe_text(name) if name else None

def _element_name(value):
    name = _safe_attr(value, "Name")
    return _safe_text(name) if name else None

def _family_name(value):
    for candidate in (value, _safe_attr(value, "Symbol")):
        family_name = _safe_attr(candidate, "FamilyName")
        if family_name:
            return _safe_text(family_name)
        family = _safe_attr(candidate, "Family")
        family_name = _safe_attr(family, "Name") if family is not None else None
        if family_name:
            return _safe_text(family_name)
    return None

def _type_label(value):
    symbol = _safe_attr(value, "Symbol")
    symbol_name = _safe_attr(symbol, "Name") if symbol is not None else None
    if symbol_name:
        return _safe_text(symbol_name)
    type_id = _safe_attr(value, "GetTypeId")
    if type_id is not None:
        return _safe_text(type_id)
    return None

def _type_name(value):
    try:
        return type(value).__name__
    except Exception:
        return "unknown"

def _lookup_parameter_text(value, parameter_name):
    parameter, error = _safe_call(value, "LookupParameter", parameter_name)
    if error or parameter is None:
        return None
    for method_name in ("AsString", "AsValueString"):
        text, method_error = _safe_call(parameter, method_name)
        if not method_error and text:
            return _safe_text(text)
    return _safe_text(parameter)

def _built_in_category_name_for_id(category_id):
    if BuiltInCategory is None or category_id is None:
        return None
    try:
        category_id_int = int(category_id)
    except Exception:
        return None
    for name in dir(BuiltInCategory):
        if not name.startswith("OST_"):
            continue
        try:
            candidate = getattr(BuiltInCategory, name)
        except Exception:
            continue
        if _built_in_category_value(candidate) == category_id_int:
            return name
    return None

def _type_name_lower(value):
    return (_type_name(value) or "unknown").lower()

def _is_instance_of_optional(value, cls):
    try:
        return cls is not None and isinstance(value, cls)
    except Exception:
        return False

def _is_geometry_instance_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, GeometryInstance) or "geometryinstance" in t or hasattr(value, "GetInstanceGeometry") or hasattr(value, "SymbolGeometry")

def _is_solid_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Solid) or "solid" in t or (hasattr(value, "Faces") and hasattr(value, "Volume"))

def _is_face_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Face) or "face" in t or hasattr(value, "Area")

def _is_planar_face_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, PlanarFace) or "planarface" in t or hasattr(value, "FaceNormal")

def _is_edge_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Edge) or "edge" in t or hasattr(value, "AsCurve")

def _is_curve_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Curve) or "curve" in t or "line" in t or "arc" in t or hasattr(value, "GetEndPoint")

def _is_mesh_like(value):
    t = _type_name_lower(value)
    return _is_instance_of_optional(value, Mesh) or "mesh" in t

def _safe_iter(value):
    if value is None or _is_string(value):
        return []
    try:
        return list(value)
    except Exception:
        return []

def _safe_float_attr(value, attr):
    raw = _safe_attr(value, attr)
    try:
        return float(raw)
    except Exception:
        return None

def _xyz_to_raw_dict(point):
    if point is None:
        return None
    result = {}
    for attr in ("X", "Y", "Z"):
        result[attr.lower()] = _safe_float_attr(point, attr)
    if all(result.get(k) is None for k in ("x", "y", "z")):
        return None
    result["units"] = "revit_raw_internal_units"
    return result

def _vector_to_raw_dict(vector):
    return _xyz_to_raw_dict(vector)

__all__ = [name for name in globals() if name.startswith("_") and callable(globals()[name])]
