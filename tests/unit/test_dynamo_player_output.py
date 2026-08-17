import os
import sys
import types


def _load_loader_helpers():
    loader_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "runtime", "dynamo_loader.py")
    namespace = {"__file__": loader_path, "__name__": "__loader_test__", "IN": []}
    fake_clr = types.ModuleType("clr")
    fake_clr.AddReference = lambda _name: None
    previous = sys.modules.get("clr")
    sys.modules["clr"] = fake_clr
    try:
        with open(loader_path, "r", encoding="utf-8") as stream:
            code = stream.read().rsplit("\n_INTERNAL_RESULT = run_script()", 1)[0]
        exec(compile(code, loader_path, "exec"), namespace)
    finally:
        if previous is None:
            sys.modules.pop("clr", None)
        else:
            sys.modules["clr"] = previous
    return namespace["build_compact_player_output"]


def test_compact_player_output_excludes_detailed_payload():
    compact = _load_loader_helpers()({
        "success": True,
        "shadow_calculation_completed": True,
        "permit_ready_certified": True,
        "warnings": ["first", "second"],
        "formal_shadow_polygons": {"slices": [[{"points": list(range(1000))}]]},
        "shadow_duration": {"grid": list(range(1000))},
        "performance_diagnostics": {"stages": {"total": {"elapsed_ms": 123.5}}},
    })

    assert compact == {
        "success": True,
        "message": "Dynamo_Shadow completed",
        "complete": True,
        "permit_ready_certified": False,
        "blocker_count": 0,
        "warning_count": 2,
        "total_ms": 123.5,
    }


def test_compact_player_output_reports_failure_without_leaking_error_details():
    compact = _load_loader_helpers()({
        "success": False,
        "error": "private detailed traceback",
        "warnings": [],
    })

    assert compact["success"] is False
    assert compact["complete"] is False
    assert compact["blocker_count"] == 1
    assert compact["total_ms"] is None
    assert "private" not in str(compact)
