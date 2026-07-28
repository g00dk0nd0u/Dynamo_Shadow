import json
import os
import sys
import types
from pathlib import Path

import pytest

import shadow_policies
import shadow_utils

ROOT = Path(__file__).resolve().parents[1]


def node_code():
    data = json.loads((ROOT / "Shadow.dyn").read_text(encoding="utf-8"))
    nodes = [node for node in data["Nodes"] if "Code" in node]
    assert len(nodes) == 1
    return nodes[0]["Code"]


def install_dynamo_stubs(monkeypatch, workspace_file):
    clr = types.ModuleType("clr")
    clr.AddReference = lambda _name: None
    applications = types.ModuleType("Dynamo.Applications")
    applications.DynamoRevit = types.SimpleNamespace(
        RevitDynamoModel=types.SimpleNamespace(
            CurrentWorkspace=types.SimpleNamespace(FileName=str(workspace_file))
        )
    )
    dynamo = types.ModuleType("Dynamo")
    dynamo.Applications = applications
    monkeypatch.setitem(sys.modules, "clr", clr)
    monkeypatch.setitem(sys.modules, "Dynamo", dynamo)
    monkeypatch.setitem(sys.modules, "Dynamo.Applications", applications)


def run_node(monkeypatch, tmp_path, loader_source, fsync=None):
    workspace = tmp_path / "Shadow.dyn"
    workspace.write_text("{}", encoding="utf-8")
    (tmp_path / "dynamo_loader.py").write_text(loader_source, encoding="utf-8")
    install_dynamo_stubs(monkeypatch, workspace)
    if fsync is not None:
        monkeypatch.setattr(os, "fsync", fsync)
    namespace = {"IN": [None, None, None, None]}
    exec(compile(node_code(), "Shadow.dyn", "exec"), namespace)
    return namespace["OUT"], tmp_path / "debug_logs" / "runtime_checkpoint.txt"


def primitive_only(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(primitive_only(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and primitive_only(item) for key, item in value.items())
    return False


def test_shadow_dyn_is_json_and_embedded_node_compiles():
    json.loads((ROOT / "Shadow.dyn").read_text(encoding="utf-8"))
    compile(node_code(), "Shadow.dyn", "exec")


@pytest.mark.parametrize("base", ["Exception", "BaseException"])
def test_fake_loader_failure_returns_primitive_only_out(monkeypatch, tmp_path, base):
    out, checkpoint_file = run_node(monkeypatch, tmp_path, "raise %s('loader failed')\n" % base)
    assert out["error_code"] == "python_node_bootstrap_failure"
    assert out["error_type"] == base
    assert primitive_only(out)
    assert "NODE_EXCEPTION | %s" % base in checkpoint_file.read_text(encoding="utf-8")


def test_checkpoint_failure_does_not_mask_original_operation(monkeypatch, tmp_path):
    def fail_fsync(_fileno):
        raise OSError("checkpoint unavailable")
    out, _path = run_node(monkeypatch, tmp_path, "raise BaseException('original')\n", fail_fsync)
    assert out["error_type"] == "BaseException"
    assert out["error"] == "original"


def test_checkpoint_is_overwritten_and_handles_are_closed(monkeypatch, tmp_path):
    out, path = run_node(monkeypatch, tmp_path, "OUT = {'success': True}\n")
    assert out["success"] is True
    path.write_text("STALE\n", encoding="utf-8")
    out, path = run_node(monkeypatch, tmp_path, "OUT = {'success': True}\n")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "NODE_ENTER"
    assert "STALE" not in lines
    assert lines[-1] == "NODE_RETURN_READY"
    renamed = path.with_suffix(".moved")
    path.rename(renamed)
    assert renamed.exists()


def test_checkpoint_lines_never_contain_absolute_paths(monkeypatch, tmp_path):
    _out, path = run_node(monkeypatch, tmp_path, "OUT = {'success': True}\n")
    for line in path.read_text(encoding="utf-8").splitlines():
        assert str(tmp_path) not in line
        assert not line.startswith("/")
        assert ":\\" not in line


def test_non_native_probe_type_check_precedes_reflection(monkeypatch):
    stages = []
    monkeypatch.setattr(shadow_utils, "RUNTIME_CHECKPOINT", lambda stage, detail=None: stages.append(stage))
    result = shadow_utils._probe_native_candidate(object(), "test_strategy")
    assert result["is_valid_object_status"] == "not_checked_non_native"
    assert stages.index("NATIVE_TYPE_CHECK_BEFORE") < stages.index("CLR_GETTYPE_BEFORE")
    assert stages[-1] == "CANDIDATE_PROBE_AFTER"
    assert "PROPERTY_ISVALID_DIRECT_BEFORE" not in stages
    assert "CLR_GETPROPERTY_BEFORE" not in stages
    assert "CLR_GETVALUE_BEFORE" not in stages


def test_clr_reflection_before_after_order(monkeypatch):
    events = []
    monkeypatch.setattr(shadow_utils, "CLR_REFLECTION_ENABLED", True)
    monkeypatch.setattr(shadow_utils, "RUNTIME_CHECKPOINT", lambda stage, detail=None: events.append((stage, detail)))

    class Property:
        def GetValue(self, value, optional=None):
            return "category"

    class ClrType:
        Namespace = "Autodesk.Revit.DB"
        def GetProperty(self, name):
            return Property()

    class Value:
        def GetType(self):
            return ClrType()

    result, diagnostics = shadow_utils._safe_property(Value(), "Category")
    assert result == "category"
    assert diagnostics["reflection_succeeded"] is True
    assert [stage for stage, _ in events] == [
        "PROPERTY_CATEGORY_DIRECT_BEFORE", "PROPERTY_CATEGORY_DIRECT_AFTER",
        "CLR_GETTYPE_BEFORE", "CLR_GETTYPE_AFTER", "CLR_GETPROPERTY_BEFORE",
        "CLR_GETPROPERTY_AFTER", "CLR_GETVALUE_BEFORE", "CLR_GETVALUE_AFTER",
    ]


def test_getvalue_failure_leaves_location_identifiable(monkeypatch):
    events = []
    monkeypatch.setattr(shadow_utils, "RUNTIME_CHECKPOINT", lambda stage, detail=None: events.append((stage, detail)))

    class Property:
        def GetValue(self, value, optional=None):
            raise BaseException("simulated uncatchable CLR failure")

    class ClrType:
        Namespace = "Autodesk.Revit.DB"
        def GetProperty(self, name):
            return Property()

    class Value:
        def GetType(self):
            return ClrType()

    result, diagnostics = shadow_utils._safe_clr_property(Value(), "Category")
    assert result is None
    assert diagnostics["error_type"] == "BaseException"
    assert ("CLR_GETVALUE_BEFORE", "Category") in events
    assert events[-1] == ("CLR_GETVALUE_AFTER", "failed")


def test_non_native_wrapper_probe_never_reads_properties(monkeypatch):
    events = []
    monkeypatch.setattr(shadow_utils, "RUNTIME_CHECKPOINT", lambda stage, detail=None: events.append((stage, detail)))

    class Wrapper:
        __module__ = "Revit.Elements"
        def GetType(self):
            return types.SimpleNamespace(Namespace="Revit.Elements")
        def __getattribute__(self, name):
            if name in ("IsValidObject", "Id", "Category", "Symbol", "InternalElement", "InternalElementId"):
                raise AssertionError("non-native property accessed: " + name)
            return object.__getattribute__(self, name)

    result = shadow_utils._probe_native_candidate(Wrapper(), "original_native_element")
    assert result["is_native_revit_element"] is False
    assert result["candidate_usable"] is False
    assert ("NATIVE_TYPE_CHECK_AFTER", "none") in events
    assert events[-1] == ("CANDIDATE_PROBE_AFTER", "non_native_skipped")
    assert not any(stage.startswith("PROPERTY_") for stage, _ in events)
    assert not any(stage in ("CLR_GETPROPERTY_BEFORE", "CLR_GETVALUE_BEFORE") for stage, _ in events)


def test_unwrap_advances_from_wrapper_to_usable_native(monkeypatch):
    class Wrapper:
        __module__ = "Revit.Elements"
        def GetType(self): return types.SimpleNamespace(Namespace="Revit.Elements")

    class Native:
        __module__ = "Autodesk.Revit.DB"
        IsValidObject = True
        Id = 42
        Category = object()

    monkeypatch.setattr(shadow_utils, "_get_global", lambda name, default=None: (lambda value: Native()) if name == "UnwrapElement" else default)
    result, diagnostics = shadow_utils._try_unwrap_with_diagnostics(Wrapper())
    assert isinstance(result, Native)
    assert diagnostics["unwrap_strategy"] == "UnwrapElement"
    assert diagnostics["native_candidate_usable"] is True


def test_reflection_guards_namespace_whitelist_and_single_argument(monkeypatch):
    monkeypatch.setattr(shadow_utils, "CLR_REFLECTION_ENABLED", True)
    calls = []
    class Property:
        def GetValue(self, value, optional=None): return 7
    class ClrType:
        Namespace = "Autodesk.Revit.DB"
        def GetProperty(self, *args):
            calls.append(args)
            assert len(args) == 1
            return Property()
    class RevitDbMock:
        def __getattribute__(self, name):
            if name == "Id": raise RuntimeError("direct blocked")
            return object.__getattribute__(self, name)
        def GetType(self): return ClrType()

    value, diagnostics = shadow_utils._safe_property(RevitDbMock(), "Id")
    assert value == 7 and diagnostics["reflection_succeeded"] is True
    assert calls == [("Id",)]
    for non_native in (object(), "text"):
        value, diagnostics = shadow_utils._safe_property(non_native, "Id")
        assert value is None
        assert diagnostics["reflection_attempted"] is False
        assert diagnostics["reflection_skipped_reason"] == "non_revit_db_object"
    value, diagnostics = shadow_utils._safe_property(RevitDbMock(), "Symbol")
    assert value is None
    assert diagnostics["reflection_skipped_reason"] == "property_not_whitelisted"


def test_clr_reflection_is_disabled_by_default():
    assert shadow_policies.CLR_REFLECTION_ENABLED is False


def test_disabled_policy_never_calls_getproperty():
    calls = []
    class ClrType:
        Namespace = "Autodesk.Revit.DB"
        def GetProperty(self, *args):
            calls.append(args)
            raise AssertionError("GetProperty must not be called")
    class RevitDbMock:
        def __getattribute__(self, name):
            if name == "Category": raise RuntimeError("direct blocked")
            return object.__getattribute__(self, name)
        def GetType(self): return ClrType()

    value, diagnostics = shadow_utils._safe_property(RevitDbMock(), "Category")
    assert value is None
    assert diagnostics["reflection_attempted"] is False
    assert diagnostics["reflection_skipped_reason"] == "disabled_by_policy"
    assert diagnostics["reflection_enabled_by_policy"] is False
    assert calls == []


def test_reflection_skip_reasons_and_direct_success(monkeypatch):
    class Blocked:
        def __getattribute__(self, name):
            if name in ("Category", "Symbol"): raise RuntimeError("direct blocked")
            return object.__getattribute__(self, name)

    value, diagnostics = shadow_utils._safe_property(Blocked(), "Category", allow_reflection=False)
    assert value is None
    assert diagnostics["reflection_attempted"] is False
    assert diagnostics["reflection_skipped_reason"] == "disabled_by_caller"

    value, diagnostics = shadow_utils._safe_property(Blocked(), "Symbol")
    assert value is None
    assert diagnostics["reflection_attempted"] is False
    assert diagnostics["reflection_skipped_reason"] == "property_not_whitelisted"

    monkeypatch.setattr(shadow_utils, "CLR_REFLECTION_ENABLED", True)
    value, diagnostics = shadow_utils._safe_property(object(), "Category")
    assert value is None
    assert diagnostics["reflection_attempted"] is False
    assert diagnostics["reflection_skipped_reason"] == "non_revit_db_object"

    monkeypatch.setattr(shadow_utils, "CLR_REFLECTION_ENABLED", False)
    value, diagnostics = shadow_utils._safe_property(type("Direct", (), {"Id": 17})(), "Id")
    assert value == 17
    assert diagnostics["read_method"] == "direct_getattr"
    assert diagnostics["reflection_attempted"] is False
    assert diagnostics["reflection_skipped_reason"] is None
    assert diagnostics["reflection_enabled_by_policy"] is False
