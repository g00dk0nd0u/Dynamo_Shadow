# Safe helpers and Revit-like type checks.
import sys
from shadow_revit_api import BuiltInCategory, Options, Solid, GeometryInstance, Face, PlanarFace, Edge, Curve, Mesh, Element, ElementId


def _get_global(name, default=None):
    try:
        if name in globals():
            return globals().get(name, default)
    except Exception:
        pass
    # Dynamo's loader executes script.py with a dedicated globals dictionary.
    # Imported helper functions retain this module's globals, so inspect only
    # caller global dictionaries for Dynamo-provided names such as UnwrapElement.
    try:
        frame = sys._getframe(1)
        for _index in range(8):
            if frame is None:
                break
            if name in frame.f_globals:
                return frame.f_globals.get(name, default)
            frame = frame.f_back
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

def _is_native_revit_element_like(value):
    if value is None:
        return False
    if _is_instance_of_optional(value, Element):
        return True
    value_type = type(value)
    type_module = _safe_text(getattr(value_type, "__module__", "")) or ""
    namespace = _safe_text(getattr(value_type, "Namespace", None)) or ""
    try:
        clr_type = value.GetType()
        namespace = _safe_text(getattr(clr_type, "Namespace", None)) or namespace
    except Exception:
        pass
    if type_module == "Autodesk.Revit.DB" or namespace == "Autodesk.Revit.DB":
        return True
    # Narrow fallback for non-Revit unit tests only. Wrapper-like objects are
    # deliberately excluded even when they expose Category and Id properties.
    wrapper_namespace = type_module.startswith(("Revit.Elements", "Dynamo."))
    return Element is None and not wrapper_namespace and callable(getattr(value, "get_Geometry", None)) and not (hasattr(value, "InternalElement") or hasattr(value, "InternalElementId"))

def _document_manager_document():
    try:
        import clr
        clr.AddReference("RevitServices")
        from RevitServices.Persistence import DocumentManager
        return DocumentManager.Instance.CurrentDBDocument
    except Exception:
        return None

def _try_document_get_element(element_id):
    doc = _document_manager_document()
    if doc is None or element_id is None:
        return None
    try:
        return doc.GetElement(element_id)
    except Exception:
        return None

def _error_details(exc):
    return type(exc).__name__, _safe_text(exc)

def _safe_clr_property(value, property_name):
    """Read a CLR property through reflection without exposing object reprs."""
    diagnostics = {"reflection_attempted": True, "reflection_property_found": False,
                   "reflection_succeeded": False, "error_type": None, "error": None}
    if value is None:
        diagnostics.update({"error_type": "ValueError", "error": "value is None"})
        return None, diagnostics
    try:
        get_type = getattr(value, "GetType")
        if not callable(get_type):
            raise TypeError("GetType is not callable")
        clr_type = get_type()
        get_property = getattr(clr_type, "GetProperty")
        flags = None
        try:
            from System.Reflection import BindingFlags
            flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy
        except Exception:
            pass
        try:
            property_info = get_property(property_name, flags) if flags is not None else get_property(property_name)
        except TypeError:
            property_info = get_property(property_name)
        diagnostics["reflection_property_found"] = property_info is not None
        if property_info is None:
            diagnostics.update({"error_type": "AttributeError", "error": "CLR property was not found"})
            return None, diagnostics
        try:
            result = property_info.GetValue(value, None)
        except TypeError:
            result = property_info.GetValue(value)
        diagnostics["reflection_succeeded"] = True
        return result, diagnostics
    except Exception as exc:
        diagnostics["error_type"], diagnostics["error"] = _error_details(exc)
        return None, diagnostics

def _safe_property(value, property_name, allow_reflection=True):
    diagnostics = {
        "property_name": property_name, "direct_getattr_attempted": True,
        "direct_getattr_succeeded": False, "direct_value_type": None,
        "direct_value_type_module": None, "direct_value_callable": None,
        "reflection_attempted": False, "reflection_property_found": False,
        "reflection_succeeded": False, "read_method": None,
        "error_type": None, "error": None,
    }
    try:
        result = getattr(value, property_name)
        diagnostics.update({"direct_getattr_succeeded": True,
                            "direct_value_type": _type_name(result),
                            "direct_value_type_module": _type_module(result),
                            "direct_value_callable": callable(result),
                            "read_method": "direct_getattr"})
        return result, diagnostics
    except Exception as exc:
        diagnostics["error_type"], diagnostics["error"] = _error_details(exc)
    if not allow_reflection:
        return None, diagnostics
    result, reflection = _safe_clr_property(value, property_name)
    diagnostics.update(reflection)
    if reflection.get("reflection_succeeded"):
        diagnostics.update({"read_method": "clr_reflection", "error_type": None, "error": None})
    return result, diagnostics

def _safe_method_call(value, method_name, *args):
    return _safe_call(value, method_name, *args)

def _safe_zero_arg_method_call(value, method_name):
    return _safe_method_call(value, method_name)

def _read_id_object(id_object, prefix="element_id"):
    diagnostics = {prefix + "_available": False, prefix: None,
                   prefix + "_object_type": _type_name(id_object),
                   prefix + "_object_module": _type_module(id_object),
                   prefix + "_value_read_method": None,
                   prefix + "_error_type": None, prefix + "_error": None}
    if id_object is None:
        return None, diagnostics
    for property_name in ("Value", "IntegerValue"):
        raw, prop_diag = _safe_property(id_object, property_name)
        if prop_diag.get("read_method") and raw is not None:
            try:
                result = int(raw)
                diagnostics.update({prefix + "_available": True, prefix: result,
                                    prefix + "_value_read_method": property_name})
                return result, diagnostics
            except Exception as exc:
                diagnostics[prefix + "_error_type"], diagnostics[prefix + "_error"] = _error_details(exc)
    try:
        result = int(id_object)
        diagnostics.update({prefix + "_available": True, prefix: result,
                            prefix + "_value_read_method": "int_conversion"})
        return result, diagnostics
    except Exception as exc:
        diagnostics[prefix + "_error_type"], diagnostics[prefix + "_error"] = _error_details(exc)
        return None, diagnostics

def _read_element_id(element):
    id_object, prop_diag = _safe_property(element, "Id")
    result, diagnostics = _read_id_object(id_object)
    diagnostics["element_id_property_read_method"] = prop_diag.get("read_method")
    diagnostics["property_diagnostics"] = prop_diag
    if result is None and prop_diag.get("error_type"):
        diagnostics["element_id_error_type"] = prop_diag.get("error_type")
        diagnostics["element_id_error"] = prop_diag.get("error")
    return result, diagnostics

def _read_element_category(element):
    diagnostics = {"category_available": False, "category_source": None,
                   "category_object_type": None, "category_object_module": None,
                   "category_property_read_method": None, "category_fallback_attempts": [],
                   "category_error_type": None, "category_error": None,
                   "property_diagnostics": {}}
    category, prop_diag = _safe_property(element, "Category")
    diagnostics["property_diagnostics"]["Category"] = prop_diag
    source = "element.Category"
    if category is None:
        symbol, symbol_diag = _safe_property(element, "Symbol")
        diagnostics["property_diagnostics"]["Symbol"] = symbol_diag
        diagnostics["category_fallback_attempts"].append("element.Symbol.Category")
        if symbol is not None:
            category, prop_diag = _safe_property(symbol, "Category")
            diagnostics["property_diagnostics"]["Symbol.Category"] = prop_diag
            source = "element.Symbol.Category"
    if category is None:
        diagnostics["category_fallback_attempts"].append("element.GetTypeId -> CurrentDBDocument.GetElement -> Category")
        type_id, method_error = _safe_zero_arg_method_call(element, "GetTypeId")
        type_element = _try_document_get_element(type_id) if type_id is not None else None
        if type_element is not None:
            category, prop_diag = _safe_property(type_element, "Category")
            diagnostics["property_diagnostics"]["TypeElement.Category"] = prop_diag
            source = "type element Category"
        elif method_error:
            diagnostics.update({"category_error_type": "MethodAccessError", "category_error": method_error})
    if category is not None:
        diagnostics.update({"category_available": True, "category_source": source,
                            "category_object_type": _type_name(category),
                            "category_object_module": _type_module(category),
                            "category_property_read_method": prop_diag.get("read_method")})
    elif diagnostics["category_error_type"] is None:
        diagnostics.update({"category_error_type": prop_diag.get("error_type"),
                            "category_error": prop_diag.get("error")})
    return category, diagnostics

def _probe_native_candidate(candidate, strategy):
    native = _is_native_revit_element_like(candidate)
    valid, valid_diag = _safe_property(candidate, "IsValidObject")
    valid_status = "false" if valid is False else ("true" if valid is True else "unknown")
    element_id, id_diag = _read_element_id(candidate)
    category, category_diag = _read_element_category(candidate)
    usable = native and valid_status != "false" and (element_id is not None or category is not None)
    return {"strategy": strategy, "candidate_type": _type_name(candidate),
            "candidate_type_module": _type_module(candidate),
            "is_native_revit_element": native, "is_valid_object": valid,
            "is_valid_object_status": valid_status,
            "is_valid_object_read_method": valid_diag.get("read_method"),
            "element_id_readable": element_id is not None,
            "category_readable": category is not None, "candidate_usable": usable,
            "element_id_diagnostics": id_diag, "category_diagnostics": category_diag,
            "property_access_diagnostics": {"Id": id_diag.get("property_diagnostics"),
                                             "Category": category_diag.get("property_diagnostics", {}).get("Category"),
                                             "IsValidObject": valid_diag,
                                             "Symbol": category_diag.get("property_diagnostics", {}).get("Symbol")}}

def _try_unwrap_with_diagnostics(value):
    diagnostics = {"wrapper_type": _type_name(value), "wrapper_type_module": _type_module(value), "candidate_type": None, "candidate_type_module": None, "native_type": None, "native_type_module": None, "unwrap_strategy": "none", "unwrapped": False, "unwrap_attempts": [], "unwrap_failure_reasons": [], "candidate_probes": [], "native_candidate_usable": False, "document_reacquire_attempted": False, "document_reacquire_attempts": [], "document_reacquire_succeeded": False, "document_reacquire_strategy": None, "document_reacquired_type": None, "document_reacquired_type_module": None, "document_reacquire_error_type": None, "document_reacquire_error": None}
    first_native = [None]
    def adopt(candidate, strategy):
        diagnostics["unwrap_attempts"].append(strategy)
        diagnostics["candidate_type"] = _type_name(candidate)
        diagnostics["candidate_type_module"] = _type_module(candidate)
        if candidate is None:
            diagnostics["unwrap_failure_reasons"].append("{0}: candidate is None".format(strategy))
            return None
        probe = _probe_native_candidate(candidate, strategy)
        diagnostics["candidate_probes"].append(probe)
        if not probe["is_native_revit_element"]:
            diagnostics["unwrap_failure_reasons"].append("{0}: candidate is not a native Autodesk.Revit.DB.Element".format(strategy))
            return None
        if first_native[0] is None:
            first_native[0] = candidate
        if not probe["candidate_usable"]:
            diagnostics["unwrap_failure_reasons"].append("{0}: native candidate properties are unusable or IsValidObject is false".format(strategy))
            return None
        diagnostics["unwrap_strategy"] = strategy
        diagnostics["unwrapped"] = candidate is not value
        diagnostics["native_type"] = _type_name(candidate)
        diagnostics["native_type_module"] = _type_module(candidate)
        diagnostics["native_candidate_usable"] = True
        return candidate

    native = adopt(value, "original_native_element")
    if native is not None:
        return native, diagnostics

    unwrap = _get_global("UnwrapElement", None)
    unwrap_candidate = None
    if unwrap is not None:
        try:
            unwrap_candidate = unwrap(value)
            native = adopt(unwrap_candidate, "UnwrapElement")
            if native is not None: return native, diagnostics
        except Exception as exc:
            diagnostics["unwrap_attempts"].append("UnwrapElement")
            diagnostics["unwrap_failure_reasons"].append("UnwrapElement failed: {0}".format(_safe_text(exc)))
    else:
        diagnostics["unwrap_failure_reasons"].append("UnwrapElement is unavailable")

    native = adopt(_safe_attr(value, "InternalElement"), "InternalElement")
    if native is not None: return native, diagnostics
    native = adopt(_safe_attr(unwrap_candidate, "InternalElement"), "UnwrapElement.InternalElement")
    if native is not None: return native, diagnostics

    seen_ids = set()
    for owner, source in ((value, "wrapper.InternalElementId"), (value, "wrapper.Id"), (unwrap_candidate, "unwrapped.InternalElementId"), (unwrap_candidate, "unwrapped.Id")):
        property_name = source.rsplit(".", 1)[-1]
        id_object, id_prop_diag = _safe_property(owner, property_name)
        id_value, _id_diag = _read_id_object(id_object, "id")
        dedupe_key = id_value if id_value is not None else (property_name, _type_name(id_object))
        if id_object is None or dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        diagnostics["document_reacquire_attempted"] = True
        get_id = id_object
        if isinstance(id_object, (int, float)) and ElementId is not None:
            try: get_id = ElementId(int(id_object))
            except Exception: pass
        candidate = _try_document_get_element(get_id)
        attempt = {"source": source, "id_object_type": _type_name(id_object), "id_value": id_value,
                   "id_property_read_method": id_prop_diag.get("read_method"), "get_element_attempted": True,
                   "get_element_succeeded": candidate is not None, "result_type": _type_name(candidate),
                   "result_type_module": _type_module(candidate)}
        diagnostics["document_reacquire_attempts"].append(attempt)
        strategy = ("InternalElementId.CurrentDBDocument.GetElement" if source == "wrapper.InternalElementId" else source + ".CurrentDBDocument.GetElement")
        native = adopt(candidate, strategy)
        if native is not None:
            diagnostics.update({"document_reacquire_succeeded": True, "document_reacquire_strategy": source,
                                "document_reacquired_type": _type_name(native),
                                "document_reacquired_type_module": _type_module(native)})
            return native, diagnostics
    if first_native[0] is not None:
        diagnostics["first_native_candidate_type"] = _type_name(first_native[0])
        diagnostics["first_native_candidate_type_module"] = _type_module(first_native[0])
    return None, diagnostics

def _try_unwrap(value):
    unwrapped, _diagnostics = _try_unwrap_with_diagnostics(value)
    return unwrapped

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
    result, _diagnostics = _safe_property(value, attr)
    return result

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
    result, _diagnostics = _read_id_object(value, "id")
    return result

def _id_read_method(value):
    if value is None:
        return None
    for attr in ("Value", "IntegerValue"):
        if _safe_attr(value, attr) is not None:
            return attr
    try:
        int(value)
        return "int_conversion"
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
    element_id, _diagnostics = _read_element_id(value)
    return element_id

def _category(value):
    category, _diagnostics = _read_element_category(value)
    return category

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
    type_id, _error = _safe_zero_arg_method_call(value, "GetTypeId")
    if type_id is not None:
        return _safe_text(type_id)
    return None

def _type_name(value):
    try:
        return type(value).__name__
    except Exception:
        return "unknown"

def _type_module(value):
    try:
        return _safe_text(getattr(type(value), "__module__", "")) or None
    except Exception:
        return None

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


def _safe_get_geometry(element):
    result = {
        "attempted": False,
        "geometry": None,
        "geometry_access_method": None,
        "geometry_fallback_used": False,
        "geometry_readable": False,
        "error_type": None,
        "error": None,
    }
    if element is None:
        result["error"] = "element is None"
        return result
    method = getattr(element, "get_Geometry", None)
    if not callable(method):
        result["error"] = "get_Geometry is not available in this environment or for this element."
        return result
    result["attempted"] = True
    option_error = None
    if Options is not None:
        try:
            opts = Options()
            try:
                opts.ComputeReferences = False
                opts.IncludeNonVisibleObjects = True
            except Exception:
                pass
            geometry = method(opts)
            result.update({"geometry": geometry, "geometry_access_method": "Options", "geometry_readable": geometry is not None})
            if geometry is not None:
                return result
        except Exception as exc:
            option_error = exc
    try:
        geometry = method(None)
        result.update({"geometry": geometry, "geometry_access_method": "None_fallback", "geometry_fallback_used": True, "geometry_readable": geometry is not None})
        if geometry is None and option_error is not None:
            result["error_type"] = type(option_error).__name__
            result["error"] = _safe_text(option_error)
        return result
    except Exception as exc:
        result["geometry_access_method"] = "Options_then_None_fallback" if Options is not None else "None"
        result["geometry_fallback_used"] = Options is not None
        result["error_type"] = type(exc).__name__
        result["error"] = _safe_text(exc)
        return result

def _collect_geometry_objects(element, max_depth=4):
    access = _safe_get_geometry(element)
    objects, warnings = [], []
    if access.get("error"):
        err = access.get("error")
        if access.get("error_type"):
            err = "{0}: {1}".format(access.get("error_type"), err)
        warnings.append("geometry could not be read: {0}".format(err))
    def add_many(values, depth, source):
        if depth > max_depth:
            warnings.append("geometry nesting exceeded diagnostic recursion depth; deeper objects were skipped.")
            return
        for val in _safe_iter(values):
            objects.append({"depth": depth, "source": source, "type": _type_name(val), "object": val, "type_lower": _type_name_lower(val)})
            if _is_geometry_instance_like(val):
                inst, inst_error = _safe_call(val, "GetInstanceGeometry")
                if inst_error:
                    warnings.append("GeometryInstance.GetInstanceGeometry unavailable: {0}".format(inst_error))
                elif inst is not None:
                    add_many(inst, depth + 1, "geometry_instance_instance")
                if inst_error or inst is None or not _safe_iter(inst):
                    symbol, symbol_error = _safe_call(val, "GetSymbolGeometry")
                    if symbol_error:
                        warnings.append("GeometryInstance.GetSymbolGeometry fallback unavailable: {0}".format(symbol_error))
                    elif symbol is not None:
                        add_many(symbol, depth + 1, "geometry_instance_symbol")
            elif not (_is_solid_like(val) or _is_face_like(val) or _is_edge_like(val) or _is_curve_like(val) or _is_mesh_like(val)):
                nested = _safe_iter(val)
                if nested:
                    add_many(nested, depth + 1, "nested_geometry")
    if access.get("geometry") is not None:
        add_many(access.get("geometry"), 0, "element_geometry")
    access["geometry"] = None
    return {"objects": objects, "warnings": warnings, "access": access}

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
