import shadow_reverse_preview as preview


def _source():
    return {"available": True, "complete": True, "method": preview.METHOD,
        "height_field": {"grid_points": [
            {"grid_index": 0, "x_m": 0, "y_m": 0, "height_limit_m": 2},
            {"grid_index": 1, "x_m": 1, "y_m": 0, "height_limit_m": 2},
            {"grid_index": 2, "x_m": 1, "y_m": 1, "height_limit_m": 2},
            {"grid_index": 3, "x_m": 0, "y_m": 1, "height_limit_m": 2}]},
        "top_surface_mesh": {"triangles": [
            {"vertex_grid_indices": [0, 1, 2]}, {"vertex_grid_indices": [0, 2, 3]}],
            "top_surface_boundary_loops": [{"closed": True,
                "vertex_grid_indices": [0, 1, 2, 3, 0], "signed_plan_area_m2": 1}]}}


class _Id:
    def __init__(self, value): self.Value = value


class _XYZ:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z


class _Face:
    def __init__(self, points, material): self.points = points


class _Solid: pass
class _Mesh: pass


class _Result:
    kind = "solid"
    def GetGeometricalObjects(self):
        if self.kind == "empty": return []
        if self.kind == "mixed": return [_Solid(), _Mesh()]
        return [_Solid() if self.kind == "solid" else _Mesh()]


class _Builder:
    face_sets = 0
    compatibility_check = None
    def __init__(self): self.faces = []
    def OpenConnectedFaceSet(self, closed): assert closed; type(self).face_sets += 1
    def AddFace(self, face): self.faces.append(face)
    def CloseConnectedFaceSet(self): pass
    def AreTargetAndFallbackCompatible(self, target, fallback):
        type(self).compatibility_check = (target, fallback)
        return target == "AnyGeometry" and fallback == "Mesh"
    def Build(self): pass
    def GetBuildResult(self): return _Result()


class _Shape:
    def __init__(self, document): self.document, self.Id = document, _Id(99)
    def SetShape(self, objects):
        if self.document.fail_set_shape: raise RuntimeError("fake failure")
        self.document.new_shape = self


class _DirectShape:
    @staticmethod
    def CreateElement(document, category): return _Shape(document)


class _Document:
    def __init__(self):
        self.deleted, self.new_shape, self.fail_set_shape = [], None, False
    def Delete(self, ident): self.deleted.append(ident)


class _SubTransaction:
    last = None
    def __init__(self, document): self.document, self.snapshot = document, list(document.deleted)
    def Start(self): type(self).last = "start"
    def Commit(self): type(self).last = "commit"
    def RollBack(self):
        type(self).last = "rollback"; self.document.deleted = self.snapshot; self.document.new_shape = None


class _Transactions:
    class Instance:
        @staticmethod
        def EnsureInTransaction(document): pass
        @staticmethod
        def TransactionTaskDone(): pass


def _install(monkeypatch, document):
    monkeypatch.setattr(preview, "DocumentManager", type("DM", (), {"Instance": type("I", (), {"CurrentDBDocument": document})()})())
    monkeypatch.setattr(preview, "TransactionManager", _Transactions)
    monkeypatch.setattr(preview, "DirectShape", _DirectShape)
    monkeypatch.setattr(preview, "SubTransaction", _SubTransaction)
    monkeypatch.setattr(preview, "TessellatedShapeBuilder", _Builder)
    monkeypatch.setattr(preview, "TessellatedFace", _Face)
    monkeypatch.setattr(preview, "TessellatedShapeBuilderTarget", type("Target", (), {"AnyGeometry": "AnyGeometry"}))
    monkeypatch.setattr(preview, "TessellatedShapeBuilderFallback", type("Fallback", (), {"Mesh": "Mesh"}))
    monkeypatch.setattr(preview, "XYZ", _XYZ)
    monkeypatch.setattr(preview, "Solid", _Solid); monkeypatch.setattr(preview, "Mesh", _Mesh)
    monkeypatch.setattr(preview, "ElementId", type("ElementId", (), {"InvalidElementId": -1, "__new__": lambda cls, value: value}))
    monkeypatch.setattr(preview, "BuiltInCategory", type("BIC", (), {"OST_GenericModel": 1}))
    monkeypatch.setattr(preview, "FilteredElementCollector", object)
    monkeypatch.setattr(preview, "_xyz_list", lambda values: values)
    monkeypatch.setattr(preview, "_collect_owned_preview_ids", lambda doc, application_id: {
        "succeeded": True, "element_ids": [_Id(7)] if doc is document else []})


def test_replace_uses_one_direct_shape_and_solid_result(monkeypatch):
    document = _Document(); _install(monkeypatch, document); _Result.kind = "solid"; _Builder.face_sets = 0; _Builder.compatibility_check = None
    result = preview.build_reverse_shadow_preview(_source(), {"average_ground_level_elevation_m": 0},
                                                  {"reverse_shadow_preview_mode": "replace"})
    assert result["complete"] and result["geometry_type"] == "tessellated_solid"
    assert result["created_element_count"] == 1 and result["deleted_element_count"] == 1
    assert _SubTransaction.last == "commit" and _Builder.face_sets == 1
    assert result["target"] == "AnyGeometry" and result["fallback"] == "Mesh"
    assert _Builder.compatibility_check == ("AnyGeometry", "Mesh")


def test_mesh_fallback_is_complete_with_warning(monkeypatch):
    document = _Document(); _install(monkeypatch, document); _Result.kind = "mesh"
    result = preview.build_reverse_shadow_preview(_source(), {"average_ground_level_elevation_m": 0},
                                                  {"reverse_shadow_preview_mode": "replace"})
    assert result["complete"] and result["geometry_type"] == "tessellated_mesh"
    assert any("Mesh fallback" in warning for warning in result["warnings"])


def test_mixed_build_result_is_tessellated_geometry_with_warning(monkeypatch):
    document = _Document(); _install(monkeypatch, document); _Result.kind = "mixed"
    result = preview.build_reverse_shadow_preview(
        _source(), {"average_ground_level_elevation_m": 0},
        {"reverse_shadow_preview_mode": "replace"})
    assert result["complete"] and result["geometry_type"] == "tessellated_geometry"
    assert any("mixed or non-Solid" in warning for warning in result["warnings"])


def test_clear_deletes_without_creating(monkeypatch):
    document = _Document(); _install(monkeypatch, document)
    result = preview.build_reverse_shadow_preview(None, None, {"reverse_shadow_preview_mode": "clear"})
    assert result["complete"] and result["deleted_element_count"] == 1
    assert result["created_element_count"] == 0 and document.new_shape is None


def test_replace_failure_rolls_back_old_delete_and_new_shape(monkeypatch):
    document = _Document(); document.fail_set_shape = True; _install(monkeypatch, document)
    result = preview.build_reverse_shadow_preview(_source(), {"average_ground_level_elevation_m": 0},
                                                  {"reverse_shadow_preview_mode": "replace"})
    assert not result["complete"] and result["deleted_element_count"] == 0
    assert result["created_element_count"] == 0 and document.deleted == [] and document.new_shape is None
    assert _SubTransaction.last == "rollback"


def test_empty_tessellated_build_result_is_rejected_before_set_shape(monkeypatch):
    document = _Document(); _install(monkeypatch, document); _Result.kind = "empty"
    result = preview.build_reverse_shadow_preview(
        _source(), {"average_ground_level_elevation_m": 0},
        {"reverse_shadow_preview_mode": "replace"})
    assert not result["complete"] and document.new_shape is None
    assert result["blockers"][0]["failure_code"] == "reverse_shadow_preview_geometry_build_failed"
    assert _SubTransaction.last == "rollback"
