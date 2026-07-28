import json
import os
import sys
import types
from pathlib import Path

import pytest

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
    shadow_utils._probe_native_candidate(object(), "test_strategy")
    assert stages.index("NATIVE_TYPE_CHECK_BEFORE") < stages.index("CLR_GETTYPE_BEFORE")


def test_clr_reflection_before_after_order(monkeypatch):
    events = []
    monkeypatch.setattr(shadow_utils, "RUNTIME_CHECKPOINT", lambda stage, detail=None: events.append((stage, detail)))

    class Property:
        def GetValue(self, value, optional=None):
            return "category"

    class ClrType:
        def GetProperty(self, name, flags=None):
            return Property()

    class Value:
        def GetType(self):
            return ClrType()

    result, diagnostics = shadow_utils._safe_clr_property(Value(), "Category")
    assert result == "category"
    assert diagnostics["reflection_succeeded"] is True
    assert [stage for stage, _ in events] == [
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
        def GetProperty(self, name, flags=None):
            return Property()

    class Value:
        def GetType(self):
            return ClrType()

    with pytest.raises(BaseException):
        shadow_utils._safe_clr_property(Value(), "Category")
    assert ("CLR_GETVALUE_BEFORE", "Category") in events
    assert events[-1] == ("CLR_GETVALUE_BEFORE", "Category")
