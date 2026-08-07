"""Revit DirectShape preview adapter for the low-rise reverse-shadow mesh."""
import math

from shadow_preview import _collect_owned_preview_ids, _element_id, _safe_message
from shadow_units import _meters_to_internal_length
from shadow_revit_api import (
    BuiltInCategory, DirectShape, ElementId, FilteredElementCollector, Mesh,
    Solid, SubTransaction, TessellatedFace, TessellatedShapeBuilder,
    TessellatedShapeBuilderFallback, TessellatedShapeBuilderTarget, XYZ,
    REVIT_API_CAPABILITIES)

try:
    from RevitServices.Persistence import DocumentManager
except Exception:
    DocumentManager = None
try:
    from RevitServices.Transactions import TransactionManager
except Exception:
    TransactionManager = None

APPLICATION_ID = "Dynamo_Shadow.ReverseShadowPreview"
APPLICATION_DATA_ID = ("method=low_rise_midday_continuous_sunlight_envelope_v1;"
                       "output_kind=reverse_shadow_volume")
ELEMENT_NAME = "Dynamo_Shadow_ReverseShadowVolume"
METHOD = "low_rise_midday_continuous_sunlight_envelope_v1"
_AREA_TOLERANCE = 1.0e-10
_HEIGHT_TOLERANCE = 1.0e-9


def normalize_reverse_shadow_preview_settings(settings):
    source = (settings or {}).get("normalized") if isinstance(settings, dict) else None
    source = source if isinstance(source, dict) else (settings if isinstance(settings, dict) else {})
    mode = source.get("reverse_shadow_preview_mode", "off")
    warnings = []
    if mode not in ("off", "replace", "clear"):
        warnings.append("settings.reverse_shadow_preview_mode must be off, replace, or clear; preview disabled.")
        mode = "off"
    return {"mode": mode, "warnings": warnings}


def _empty(config, core, plane):
    return {
        "enabled": config["mode"] != "off", "mode": config["mode"],
        "attempted": False, "available": False, "complete": False,
        "partial_success": False,
        "source_available": bool((core or {}).get("available")),
        "source_complete": bool((core or {}).get("complete")),
        "source_method": (core or {}).get("method"),
        "geometry_kind": "TessellatedShapeBuilder", "geometry_type": "unavailable",
        "target": "Solid", "fallback": "Mesh", "connected_component_count": 0,
        "source_top_triangle_count": 0, "top_face_count": 0,
        "side_face_count": 0, "bottom_face_count": 0,
        "total_tessellated_face_count": 0,
        "top_face_orientation_normalized_count": 0,
        "created_element_count": 0, "created_element_ids": [],
        "deleted_element_count": 0, "application_id": APPLICATION_ID,
        "element_name": ELEMENT_NAME,
        "average_ground_level_elevation_m": (plane or {}).get("average_ground_level_elevation_m"),
        "minimum_top_elevation_m": None, "maximum_top_elevation_m": None,
        "api_capabilities": {
            "tessellated_shape_builder_available": REVIT_API_CAPABILITIES.get("tessellated_shape_builder_available", False),
            "tessellated_face_available": REVIT_API_CAPABILITIES.get("tessellated_face_available", False),
            "tessellated_solid_preview_expected": REVIT_API_CAPABILITIES.get("tessellated_solid_preview_expected", False),
        },
        "blockers": [], "warnings": list(config["warnings"]),
        "legal_judgement_generated": False,
        "ordinance_selection_certified": False, "permit_ready_certified": False,
    }


def _block(result, code, message=None):
    item = {"failure_code": code}
    if message: item["message"] = message
    result["blockers"].append(item)
    result["available"] = result["complete"] = False
    return result


def _source_parts(core):
    if not isinstance(core, dict) or core.get("available") is not True or core.get("complete") is not True:
        raise ValueError("reverse_shadow_preview_source_incomplete")
    if core.get("method") != METHOD:
        raise ValueError("reverse_shadow_preview_method_unsupported")
    mesh = core.get("top_surface_mesh")
    field = core.get("height_field")
    if not isinstance(mesh, dict) or not isinstance(field, dict):
        raise ValueError("reverse_shadow_preview_mesh_invalid")
    triangles = mesh.get("triangles")
    loops = mesh.get("top_surface_boundary_loops")
    points = field.get("grid_points")
    if not isinstance(triangles, list) or not triangles or not isinstance(loops, list) or not loops or not isinstance(points, list):
        raise ValueError("reverse_shadow_preview_mesh_invalid")
    return mesh, triangles, loops, points


def build_reverse_shadow_mesh_components(reverse_shadow_core):
    """Return triangle-index components based on shared, undirected top edges."""
    _, triangles, _, _ = _source_parts(reverse_shadow_core)
    vertices = []
    edge_to_triangles = {}
    for index, triangle in enumerate(triangles):
        ids = triangle.get("vertex_grid_indices") if isinstance(triangle, dict) else None
        if not isinstance(ids, (list, tuple)) or len(ids) != 3 or len(set(ids)) != 3:
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        ids = tuple(ids); vertices.append(ids)
        for a, b in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            edge_to_triangles.setdefault(tuple(sorted((a, b))), []).append(index)
    adjacency = [set() for _ in vertices]
    for linked in edge_to_triangles.values():
        for index in linked:
            adjacency[index].update(other for other in linked if other != index)
    remaining = set(range(len(vertices))); components = []
    while remaining:
        todo = [min(remaining)]; remaining.remove(todo[0]); component = []
        while todo:
            current = todo.pop(); component.append(current)
            neighbours = adjacency[current] & remaining
            remaining.difference_update(neighbours); todo.extend(sorted(neighbours, reverse=True))
        components.append(sorted(component))
    return components


def plan_reverse_shadow_preview_faces(reverse_shadow_core, measurement_plane):
    """Validate meter data and plan closed triangular shells without Revit."""
    _, triangles, loops, points = _source_parts(reverse_shadow_core)
    try:
        ground = float((measurement_plane or {})["average_ground_level_elevation_m"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("reverse_shadow_preview_mesh_invalid")
    if not math.isfinite(ground): raise ValueError("reverse_shadow_preview_mesh_invalid")
    required_grid_indices = set()
    for triangle in triangles:
        ids = triangle.get("vertex_grid_indices") if isinstance(triangle, dict) else None
        if not isinstance(ids, (list, tuple)) or len(ids) != 3:
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        required_grid_indices.update(ids)
    for loop in loops:
        ids = loop.get("vertex_grid_indices") if isinstance(loop, dict) else None
        if not isinstance(ids, (list, tuple)) or len(ids) < 4:
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        required_grid_indices.update(ids)

    by_index = {}
    for point in points:
        try:
            index = point["grid_index"]
        except (KeyError, TypeError):
            continue
        if index not in required_grid_indices:
            continue
        if index in by_index:
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        try:
            x = float(point["x_m"]); y = float(point["y_m"])
            height = float(point["height_limit_m"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        if not all(math.isfinite(v) for v in (x, y, height)) or height < -_HEIGHT_TOLERANCE:
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        by_index[index] = {"x_m": x, "y_m": y, "bottom_z_m": ground, "top_z_m": ground + height,
                           "height_limit_m": height}
    if set(by_index) != required_grid_indices:
        raise ValueError("reverse_shadow_preview_mesh_invalid")
    components = build_reverse_shadow_mesh_components(reverse_shadow_core)
    planned = []; normalized = 0; skipped = 0
    for triangle_indices in components:
        component_vertices = set()
        for ti in triangle_indices: component_vertices.update(triangles[ti]["vertex_grid_indices"])
        if any(index not in by_index for index in component_vertices):
            raise ValueError("reverse_shadow_preview_mesh_invalid")
        if any(by_index[index]["height_limit_m"] <= _HEIGHT_TOLERANCE for index in component_vertices):
            skipped += 1; continue
        component_loops = []
        for loop in loops:
            ids = loop.get("vertex_grid_indices") if isinstance(loop, dict) else None
            if not isinstance(ids, (list, tuple)) or len(ids) < 4 or ids[0] != ids[-1] or len(set(ids[:-1])) < 3:
                raise ValueError("reverse_shadow_preview_mesh_invalid")
            if set(ids[:-1]).issubset(component_vertices): component_loops.append(list(ids))
        if not component_loops: raise ValueError("reverse_shadow_preview_mesh_invalid")
        top = []; bottom = []
        for ti in triangle_indices:
            ids = list(triangles[ti]["vertex_grid_indices"])
            a, b, c = (by_index[i] for i in ids)
            cross = (b["x_m"] - a["x_m"]) * (c["y_m"] - a["y_m"]) - (b["y_m"] - a["y_m"]) * (c["x_m"] - a["x_m"])
            if abs(cross) <= _AREA_TOLERANCE: raise ValueError("reverse_shadow_preview_mesh_invalid")
            if cross < 0: ids[1], ids[2] = ids[2], ids[1]; normalized += 1
            top.append(tuple((index, "top") for index in ids))
            bottom.append(((ids[0], "bottom"), (ids[2], "bottom"), (ids[1], "bottom")))
        side = []
        for ids in component_loops:
            area = sum(by_index[a]["x_m"] * by_index[b]["y_m"] - by_index[b]["x_m"] * by_index[a]["y_m"] for a, b in zip(ids, ids[1:])) / 2.0
            if abs(area) <= _AREA_TOLERANCE: raise ValueError("reverse_shadow_preview_mesh_invalid")
            for a, b in zip(ids, ids[1:]):
                pa, pb = by_index[a], by_index[b]
                if math.hypot(pb["x_m"] - pa["x_m"], pb["y_m"] - pa["y_m"]) <= _AREA_TOLERANCE:
                    raise ValueError("reverse_shadow_preview_mesh_invalid")
                side.extend([((a, "top"), (a, "bottom"), (b, "bottom")),
                             ((a, "top"), (b, "bottom"), (b, "top"))])
        planned.append({"triangle_indices": triangle_indices, "top_faces": top,
                        "side_faces": side, "bottom_faces": bottom})
    if not planned: raise ValueError("reverse_shadow_preview_no_valid_volume")
    heights = [point["top_z_m"] for component in planned for face in component["top_faces"] for index, _ in face for point in (by_index[index],)]
    return {"vertices": by_index, "components": planned, "skipped_component_count": skipped,
            "source_top_triangle_count": len(triangles),
            "top_face_count": sum(len(c["top_faces"]) for c in planned),
            "side_face_count": sum(len(c["side_faces"]) for c in planned),
            "bottom_face_count": sum(len(c["bottom_faces"]) for c in planned),
            "top_face_orientation_normalized_count": normalized,
            "minimum_top_elevation_m": min(heights), "maximum_top_elevation_m": max(heights),
            "average_ground_level_elevation_m": ground}


def _xyz(vertex, level):
    x, _ = _meters_to_internal_length(vertex["x_m"])
    y, _ = _meters_to_internal_length(vertex["y_m"])
    z, _ = _meters_to_internal_length(vertex["top_z_m"] if level == "top" else vertex["bottom_z_m"])
    return XYZ(x, y, z)


def _xyz_list(values):
    system = __import__("System")
    result = system.Collections.Generic.List[XYZ]()
    for value in values: result.Add(value)
    return result


def _material_id():
    try: return ElementId.InvalidElementId
    except BaseException: return ElementId(-1)


def _build_geometry(plan):
    builder = TessellatedShapeBuilder(); cache = {}
    def native(key):
        if key not in cache: cache[key] = _xyz(plan["vertices"][key[0]], key[1])
        return cache[key]
    for component in plan["components"]:
        builder.OpenConnectedFaceSet(True)
        for kind in ("top_faces", "side_faces", "bottom_faces"):
            for face in component[kind]:
                builder.AddFace(TessellatedFace(_xyz_list([native(key) for key in face]), _material_id()))
        builder.CloseConnectedFaceSet()
    builder.Target = TessellatedShapeBuilderTarget.Solid
    builder.Fallback = TessellatedShapeBuilderFallback.Mesh
    builder.Build(); objects = builder.GetBuildResult().GetGeometricalObjects()
    values = list(objects)
    if not values:
        raise ValueError("reverse_shadow_preview_geometry_build_failed")
    if Solid is not None and any(isinstance(item, Solid) for item in values): geometry_type = "tessellated_solid"
    elif Mesh is not None and values and all(isinstance(item, Mesh) for item in values): geometry_type = "tessellated_mesh"
    else: geometry_type = "tessellated_geometry"
    return objects, geometry_type


def build_reverse_shadow_preview(reverse_shadow_core, measurement_plane, settings):
    config = normalize_reverse_shadow_preview_settings(settings)
    result = _empty(config, reverse_shadow_core, measurement_plane)
    if config["mode"] == "off": return result
    result["attempted"] = True
    plan = None
    if config["mode"] == "replace":
        try: plan = plan_reverse_shadow_preview_faces(reverse_shadow_core, measurement_plane)
        except ValueError as exc: return _block(result, str(exc))
        for key in ("source_top_triangle_count", "top_face_count", "side_face_count", "bottom_face_count",
                    "top_face_orientation_normalized_count", "minimum_top_elevation_m",
                    "maximum_top_elevation_m", "average_ground_level_elevation_m"):
            result[key] = plan[key]
        result["connected_component_count"] = len(plan["components"])
        result["total_tessellated_face_count"] = result["top_face_count"] + result["side_face_count"] + result["bottom_face_count"]
        if plan["skipped_component_count"]:
            result["warnings"].append("Zero-height reverse-shadow mesh component was omitted from preview.")
    required = (DocumentManager, TransactionManager, DirectShape, ElementId, BuiltInCategory,
                FilteredElementCollector, SubTransaction)
    if config["mode"] == "replace": required += (TessellatedShapeBuilder, TessellatedFace,
        TessellatedShapeBuilderTarget, TessellatedShapeBuilderFallback, XYZ)
    if any(item is None for item in required):
        return _block(result, "reverse_shadow_preview_api_unavailable")
    try:
        document = DocumentManager.Instance.CurrentDBDocument
        cleanup = _collect_owned_preview_ids(document, APPLICATION_ID)
    except BaseException as exc:
        return _block(result, "reverse_shadow_preview_document_access_failed", _safe_message(exc))
    if not cleanup.get("succeeded"):
        return _block(result, "reverse_shadow_preview_cleanup_collection_failed", cleanup.get("failure_message"))
    started = False; sub = None
    try:
        TransactionManager.Instance.EnsureInTransaction(document); started = True
        sub = SubTransaction(document); sub.Start()
        for ident in cleanup["element_ids"]:
            document.Delete(ident); result["deleted_element_count"] += 1
        if config["mode"] == "replace":
            try: objects, geometry_type = _build_geometry(plan)
            except BaseException as exc: raise RuntimeError("reverse_shadow_preview_geometry_build_failed: %s" % _safe_message(exc))
            shape = DirectShape.CreateElement(document, ElementId(BuiltInCategory.OST_GenericModel))
            shape.ApplicationId = APPLICATION_ID; shape.ApplicationDataId = APPLICATION_DATA_ID; shape.Name = ELEMENT_NAME
            try: shape.SetShape(objects)
            except BaseException as exc: raise RuntimeError("reverse_shadow_preview_set_shape_failed: %s" % _safe_message(exc))
            result["created_element_ids"].append(_element_id(shape)); result["geometry_type"] = geometry_type
            if geometry_type == "tessellated_mesh":
                result["warnings"].append("Reverse-shadow preview used TessellatedShapeBuilder Mesh fallback.")
        sub.Commit(); sub = None
    except BaseException as exc:
        if sub is not None:
            try: sub.RollBack()
            except BaseException: pass
        result["deleted_element_count"] = 0; result["created_element_ids"] = []
        message = _safe_message(exc)
        code = next((candidate for candidate in ("reverse_shadow_preview_geometry_build_failed",
            "reverse_shadow_preview_set_shape_failed") if candidate in message), "reverse_shadow_preview_write_failed")
        _block(result, code, message)
    finally:
        if started:
            try: TransactionManager.Instance.TransactionTaskDone()
            except BaseException as exc: _block(result, "reverse_shadow_preview_transaction_close_failed", _safe_message(exc))
    result["created_element_count"] = len(result["created_element_ids"])
    result["available"] = not result["blockers"]
    result["complete"] = result["available"] and (config["mode"] == "clear" or result["created_element_count"] == 1)
    result["partial_success"] = result["available"] and not result["complete"]
    return result


_build_reverse_shadow_preview = build_reverse_shadow_preview
