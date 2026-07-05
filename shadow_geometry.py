# Read-only geometry diagnostics.
from shadow_revit_api import Options
from shadow_policies import GEOMETRY_EXTRACTION_POLICY
from shadow_utils import *
from shadow_measurement_plane import _measurement_plane_relation
from shadow_footprint import _extract_footprint_candidates_from_faces


def _safe_get_bounding_box(element):
    if element is None:
        return {"available": False, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "reason": "element is None"}
    bbox = None
    error = None
    try:
        getter = getattr(element, "get_BoundingBox", None)
        if callable(getter):
            bbox = getter(None)
        if bbox is None:
            bbox = _safe_attr(element, "BoundingBox")
    except Exception as exc:
        error = _safe_text(exc)
    if bbox is None:
        return {"available": False, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "reason": error or "BoundingBox unavailable"}
    return {"available": True, "diagnostic_only": True, "used_for_shadow_geometry": False, "used_for_shadow_judgement": False, "min_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Min")), "max_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Max")), "units": "revit_raw_internal_units"}

def _safe_get_geometry(element):
    if element is None:
        return None, "element is None"
    method = getattr(element, "get_Geometry", None)
    if not callable(method):
        return None, "get_Geometry is not available in this environment or for this element."
    try:
        if Options is not None:
            try:
                return method(Options()), None
            except Exception:
                pass
        return method(None), None
    except Exception as exc:
        return None, _safe_text(exc)

def _collect_geometry_objects(element):
    objects, warnings = [], []
    geom, error = _safe_get_geometry(element)
    if error:
        warnings.append("geometry could not be read: {0}".format(error))
    def add_many(values, depth, source):
        if depth > 3:
            warnings.append("geometry nesting exceeded diagnostic recursion depth; deeper objects were skipped.")
            return
        for value in _safe_iter(values):
            objects.append({"depth": depth, "source": source, "type": _type_name(value), "object": value, "type_lower": _type_name_lower(value)})
            if _is_geometry_instance_like(value):
                symbol = _safe_attr(value, "SymbolGeometry")
                if symbol is not None:
                    add_many(symbol, depth + 1, "geometry_instance_symbol")
                inst, inst_error = _safe_call(value, "GetInstanceGeometry")
                if inst_error:
                    warnings.append("GeometryInstance.GetInstanceGeometry unavailable: {0}".format(inst_error))
                elif inst is not None:
                    add_many(inst, depth + 1, "geometry_instance_instance")
            elif not (_is_solid_like(value) or _is_face_like(value) or _is_edge_like(value) or _is_curve_like(value) or _is_mesh_like(value)):
                nested = _safe_iter(value)
                if nested:
                    add_many(nested, depth + 1, "nested_geometry")
    if geom is not None:
        add_many(geom, 0, "element_geometry")
    return {"objects": objects, "warnings": warnings}

def _summarize_solid(solid):
    warnings = []
    volume = _safe_float_attr(solid, "Volume")
    area = _safe_float_attr(solid, "SurfaceArea")
    faces = _safe_iter(_safe_attr(solid, "Faces"))
    edges = _safe_iter(_safe_attr(solid, "Edges"))
    if volume is None or volume <= 0:
        warnings.append("solid has zero/unknown volume; retained as diagnostic only.")
    bbox = None
    try:
        bbox = _safe_attr(solid, "GetBoundingBox")
    except Exception:
        bbox = None
    return {"type": _type_name(solid), "volume_raw": volume, "surface_area_raw": area, "face_count": len(faces), "edge_count": len(edges), "has_positive_volume": bool(volume is not None and volume > 0), "bounding_box_raw": {"min_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Min")), "max_raw": _xyz_to_raw_dict(_safe_attr(bbox, "Max")), "diagnostic_only": True} if bbox is not None else None, "warnings": warnings}

def _summarize_face(face):
    warnings = []
    normal = _safe_attr(face, "FaceNormal") or _safe_attr(face, "Normal")
    normal_raw = _vector_to_raw_dict(normal)
    z = normal_raw.get("z") if normal_raw else None
    if z is None:
        orientation = "unknown"; role = "unknown"; warnings.append("face normal unavailable; orientation is diagnostic unknown.")
    elif z >= 0.9:
        orientation = "horizontal_up"; role = "top_face_candidate"
    elif z <= -0.9:
        orientation = "horizontal_down"; role = "bottom_face_candidate"
    elif abs(z) <= 0.1:
        orientation = "vertical"; role = "side_face_candidate"
    else:
        orientation = "sloped_or_unknown"; role = "unknown"
    loops = _safe_iter(_safe_attr(face, "EdgeLoops"))
    edge_count = 0
    for loop in loops:
        edge_count += len(_safe_iter(loop))
    return {"type": _type_name(face), "is_planar": _is_planar_face_like(face), "area_raw": _safe_float_attr(face, "Area"), "normal_raw": normal_raw, "origin_raw": _xyz_to_raw_dict(_safe_attr(face, "Origin")), "edge_loop_count": len(loops) if loops else None, "edge_count": edge_count if loops else None, "orientation_candidate": orientation, "height_role_candidate": role, "warnings": warnings}

def _summarize_edge_or_curve(value):
    warnings = []
    curve = value
    if _is_edge_like(value):
        curve, err = _safe_call(value, "AsCurve")
        if err:
            warnings.append("Edge.AsCurve unavailable: {0}".format(err))
            curve = None
    p0 = p1 = None
    if curve is not None:
        p0, e0 = _safe_call(curve, "GetEndPoint", 0)
        p1, e1 = _safe_call(curve, "GetEndPoint", 1)
        if e0 or e1:
            warnings.append("curve endpoints unavailable; edge remains diagnostic only.")
    z0 = (_xyz_to_raw_dict(p0) or {}).get("z")
    z1 = (_xyz_to_raw_dict(p1) or {}).get("z")
    length = _safe_float_attr(curve, "Length") if curve is not None else None
    return {"type": _type_name(value), "curve_type": _type_name(curve) if curve is not None else None, "length_raw": length, "endpoint0_raw": _xyz_to_raw_dict(p0), "endpoint1_raw": _xyz_to_raw_dict(p1), "is_horizontal_candidate": (z0 is not None and z1 is not None and abs(z0 - z1) < 1e-9), "z_min_raw": min([z for z in (z0, z1) if z is not None]) if z0 is not None or z1 is not None else None, "z_max_raw": max([z for z in (z0, z1) if z is not None]) if z0 is not None or z1 is not None else None, "warnings": warnings}

def _diagnose_shadow_caster_geometry(building_elements, shadow_casters, settings_normalized, measurement_plane=None):
    items_in = _to_list(building_elements)
    diag = {"policy": GEOMETRY_EXTRACTION_POLICY, "provided": bool(items_in), "count": len(items_in), "accepted_caster_count": (shadow_casters or {}).get("accepted_count", 0), "geometry_readable_caster_count": 0, "solid_count": 0, "positive_solid_count": 0, "face_count": 0, "edge_count": 0, "mesh_count": 0, "bottom_face_candidate_count": 0, "top_face_candidate_count": 0, "vertical_face_candidate_count": 0, "footprint_candidate_count": 0, "footprint_loop_candidate_count": 0, "closed_footprint_loop_candidate_count": 0, "best_candidate_count": 0, "casters_with_footprint_candidate_count": 0, "casters_with_closed_footprint_loop_candidate_count": 0, "measurement_plane_relation_available": False, "measurement_plane_elevation_m": ((measurement_plane or {}).get("elevation_m")), "units": {"geometry": "revit_raw_internal_units", "official_unit_conversion": "not_implemented_in_this_pr"}, "items": [], "readiness": {}, "warnings": [], "info": ["Geometry extraction diagnostics are read-only and create no Revit elements.", "Footprint candidates are diagnostic only; no footprint polygon, shadow polygon, projection, grid accumulation, or equal-time contour is generated."]}
    caster_items = (shadow_casters or {}).get("items") or []
    for index, item in enumerate(items_in):
        unwrapped = _try_unwrap(item)
        caster_info = caster_items[index] if index < len(caster_items) else {}
        accepted = caster_info.get("accepted") is True
        item_warnings = []
        collected = _collect_geometry_objects(unwrapped) if accepted else {"objects": [], "warnings": ["shadow caster category is not accepted; geometry diagnostics skipped for this item."]}
        item_warnings.extend(collected.get("warnings", []))
        objs = collected.get("objects") or []
        solids=[]; faces=[]; face_objects=[]; edges=[]; mesh_count=0
        for obj in objs:
            val = obj.get("object")
            if _is_solid_like(val):
                ss = _summarize_solid(val); solids.append(ss)
                for f in _safe_iter(_safe_attr(val, "Faces")):
                    faces.append(_summarize_face(f)); face_objects.append(f)
                for e in _safe_iter(_safe_attr(val, "Edges")):
                    edges.append(_summarize_edge_or_curve(e))
            elif _is_face_like(val):
                faces.append(_summarize_face(val)); face_objects.append(val)
            elif _is_edge_like(val) or _is_curve_like(val):
                edges.append(_summarize_edge_or_curve(val))
            elif _is_mesh_like(val):
                mesh_count += 1
        bottom=sum(1 for f in faces if f.get("height_role_candidate")=="bottom_face_candidate")
        top=sum(1 for f in faces if f.get("height_role_candidate")=="top_face_candidate")
        vertical=sum(1 for f in faces if f.get("height_role_candidate")=="side_face_candidate")
        pos=sum(1 for solid in solids if solid.get("has_positive_volume"))
        if accepted and bottom == 0:
            item_warnings.append("No bottom face candidate was found; future footprint extraction may be blocked for this caster.")
        bbox = _safe_get_bounding_box(unwrapped)
        relation = _measurement_plane_relation(bbox, faces[:20], measurement_plane)
        footprint = _extract_footprint_candidates_from_faces(faces, face_objects, measurement_plane) if accepted else {"available": False, "bottom_face_candidate_count": 0, "loop_candidate_count": 0, "closed_loop_candidate_count": 0, "horizontal_loop_candidate_count": 0, "best_candidate": None, "candidates": [], "readiness": {"ready_for_future_footprint_polygon_generation": False, "blockers": ["shadow caster category is not accepted; footprint diagnostics skipped."]}, "warnings": [], "info": []}
        if footprint.get("warnings"):
            item_warnings.extend(footprint.get("warnings") or [])
        if relation.get("available"):
            diag["measurement_plane_relation_available"] = True
        entry={"index": index, "element_id": _element_id(unwrapped), "name": _element_name(unwrapped), "category_name": _category_name(unwrapped), "accepted_shadow_caster": accepted, "geometry_attempted": accepted, "geometry_available": len(objs)>0, "geometry_object_count": len(objs), "solid_count": len(solids), "positive_solid_count": pos, "face_count": len(faces), "edge_count": len(edges), "mesh_count": mesh_count, "bottom_face_candidate_count": bottom, "top_face_candidate_count": top, "vertical_face_candidate_count": vertical, "footprint_candidate_count": len(footprint.get("candidates") or []), "footprint_loop_candidate_count": footprint.get("loop_candidate_count", 0), "closed_footprint_loop_candidate_count": footprint.get("closed_loop_candidate_count", 0), "best_footprint_candidate": footprint.get("best_candidate"), "footprint_extraction": footprint, "footprint_extraction_warnings": footprint.get("warnings", []), "bounding_box_diagnostic": bbox, "measurement_plane_relation": relation, "solids": solids[:20], "faces_summary": faces[:20], "edges_summary_sample": edges[:20], "warnings": item_warnings}
        diag["items"].append(entry); diag["warnings"].extend(item_warnings)
        if len(objs)>0: diag["geometry_readable_caster_count"] += 1
        diag["solid_count"] += len(solids); diag["positive_solid_count"] += pos; diag["face_count"] += len(faces); diag["edge_count"] += len(edges); diag["mesh_count"] += mesh_count; diag["bottom_face_candidate_count"] += bottom; diag["top_face_candidate_count"] += top; diag["vertical_face_candidate_count"] += vertical; diag["footprint_candidate_count"] += len(footprint.get("candidates") or []); diag["footprint_loop_candidate_count"] += footprint.get("loop_candidate_count", 0); diag["closed_footprint_loop_candidate_count"] += footprint.get("closed_loop_candidate_count", 0); diag["best_candidate_count"] += 1 if footprint.get("best_candidate") else 0; diag["casters_with_footprint_candidate_count"] += 1 if footprint.get("loop_candidate_count", 0) > 0 else 0; diag["casters_with_closed_footprint_loop_candidate_count"] += 1 if footprint.get("closed_loop_candidate_count", 0) > 0 else 0
    fp_ready = diag["accepted_caster_count"] > 0 and diag["closed_footprint_loop_candidate_count"] > 0
    settings_ready = (((settings_normalized or {}).get("readiness") or {}).get("ready_for_equal_time_shadow_calculation") is True)
    fp_blockers=[]; proj_blockers=[]
    if diag["accepted_caster_count"] <= 0: fp_blockers.append("No accepted shadow caster proxy elements are available.")
    if diag["bottom_face_candidate_count"] <= 0: fp_blockers.append("No bottom face candidate was found.")
    if diag["footprint_loop_candidate_count"] <= 0: fp_blockers.append("No edge loop candidate was found from bottom face candidates.")
    if diag["closed_footprint_loop_candidate_count"] <= 0: fp_blockers.append("No closed footprint loop candidate was verified.")
    if not fp_ready: proj_blockers.extend(fp_blockers)
    if not settings_ready: proj_blockers.append("Settings are not ready for future equal-time shadow calculation.")
    mp_ready = ((measurement_plane or {}).get("readiness") or {}).get("measurement_plane_constructed") is True
    if not mp_ready:
        proj_blockers.append("Measurement plane is not constructed; future shadow projection context is blocked.")
    diag["readiness"]={"geometry_diagnostics_ready": True, "ready_for_future_footprint_extraction": fp_ready, "ready_for_future_footprint_polygon_generation": fp_ready, "ready_for_future_shadow_projection": fp_ready and settings_ready and mp_ready, "blockers_for_future_footprint_extraction": fp_blockers, "blockers_for_future_shadow_projection": proj_blockers}
    return diag
