# Dynamo external loader for Shadow.dyn
# Finds and executes script.py from the same folder as the current .dyn file.

import clr
import importlib
import os
import sys
import traceback

LOADER_NAME = "Shadow.dyn external loader"
SCRIPT_NAME = "script.py"
LOADER_BUILD_ID = "2026-07-28-loader-module-isolation-v1"
_RUNTIME_CHECKPOINT = globals().get("RUNTIME_CHECKPOINT")


def _checkpoint(stage, detail=None):
    callback = _RUNTIME_CHECKPOINT
    if callback is None:
        return
    try:
        callback(stage, detail)
    except BaseException:
        pass


def _normalized_path(value):
    if not value:
        return None
    return os.path.normcase(os.path.normpath(os.path.abspath(value)))


def _force_workspace_first(workspace_dir):
    """Put one normalized workspace entry first, regardless of prior spelling."""
    normalized_workspace = _normalized_path(workspace_dir)
    retained = []
    for entry in sys.path:
        try:
            normalized_entry = _normalized_path(entry)
        except Exception:
            normalized_entry = None
        if normalized_entry != normalized_workspace:
            retained.append(entry)
    sys.path[:] = [normalized_workspace] + retained
    return normalized_workspace


def _prepare_runtime_imports(workspace_dir):
    """Discard only cache entries backed by shadow_*.py files in this workspace."""
    normalized_workspace = _normalized_path(workspace_dir)
    local_module_names = []
    for filename in os.listdir(normalized_workspace):
        if filename.startswith("shadow_") and filename.endswith(".py"):
            local_module_names.append(filename[:-3])
    local_module_names.sort()

    removed_cached_modules = []
    for module_name in local_module_names:
        if sys.modules.pop(module_name, None) is not None:
            removed_cached_modules.append(module_name)
    importlib.invalidate_caches()
    _force_workspace_first(normalized_workspace)
    return {
        "loader_build_id": LOADER_BUILD_ID,
        "workspace_resolved": bool(normalized_workspace),
        "workspace_inserted_at_sys_path_zero": bool(
            sys.path and _normalized_path(sys.path[0]) == normalized_workspace
        ),
        "import_caches_invalidated": True,
        "local_module_names": local_module_names,
        "removed_cached_modules": removed_cached_modules,
        "cached_module_count_removed": len(removed_cached_modules),
    }


def get_workspace_info():
    workspace_file = None
    workspace_dir = None

    try:
        clr.AddReference("DynamoServices")
        from Dynamo.Applications import DynamoRevit

        ws = DynamoRevit.RevitDynamoModel.CurrentWorkspace
        workspace_file = ws.FileName

        if workspace_file and os.path.isfile(workspace_file):
            workspace_dir = os.path.dirname(workspace_file)
    except Exception:
        pass

    return workspace_file, workspace_dir


def get_in(index, default=None):
    try:
        if IN is not None and len(IN) > index:
            return IN[index]
    except Exception:
        pass
    return default


def summarize_input(value):
    if value is None:
        return {"is_none": True, "type": None}
    return {"is_none": False, "type": type(value).__name__}


INPUTS = {
    "building_elements": get_in(0),
    "site_boundary": get_in(1),
    "level": get_in(2),
    "settings": get_in(3),
    "regulatory_shadow_preset": get_in(4),
    "site_latitude_deg": get_in(5),
    "site_longitude_deg": get_in(6),
    "calculation_accuracy_preset": get_in(7),
}

input_summary = {
    key: summarize_input(value)
    for key, value in INPUTS.items()
}


def build_failure(
    error,
    workspace_file=None,
    workspace_dir=None,
    loader_path=None,
    script_path=None,
    searched_paths=None,
    extra=None,
    runtime_import_bootstrap=None,
):
    payload = {
        "success": False,
        "loader_name": LOADER_NAME,
        "workspace_file": workspace_file,
        "workspace_dir": workspace_dir,
        "loader_path": loader_path,
        "script_name": SCRIPT_NAME,
        "script_path": script_path,
        "searched_paths": searched_paths or [],
        "input_summary": input_summary,
        "error": error,
        "runtime_code_diagnostics": runtime_import_bootstrap,
    }

    if extra:
        payload.update(extra)

    return payload


def resolve_workspace():
    workspace_file = globals().get("WORKSPACE_FILE", None)
    workspace_dir = globals().get("WORKSPACE_DIR", None)
    loader_path = globals().get("LOADER_PATH", globals().get("__file__", None))

    if workspace_dir:
        return workspace_file, workspace_dir, loader_path

    fallback_file, fallback_dir = get_workspace_info()
    if not workspace_file:
        workspace_file = fallback_file
    if not workspace_dir:
        workspace_dir = fallback_dir

    return workspace_file, workspace_dir, loader_path


def run_script():
    _checkpoint("LOADER_ENTER")
    searched_paths = []
    workspace_file, workspace_dir, loader_path = resolve_workspace()
    script_path = None
    runtime_import_bootstrap = {
        "loader_build_id": LOADER_BUILD_ID,
        "workspace_resolved": False,
        "workspace_inserted_at_sys_path_zero": False,
        "import_caches_invalidated": False,
        "local_module_names": [],
        "removed_cached_modules": [],
        "cached_module_count_removed": 0,
    }

    try:
        if workspace_dir:
            script_path = os.path.join(workspace_dir, SCRIPT_NAME)
            searched_paths.append(script_path)

        if not script_path or not os.path.isfile(script_path):
            return build_failure(
                "script.py not found in the same folder as the .dyn file.",
                workspace_file=workspace_file,
                workspace_dir=workspace_dir,
                loader_path=loader_path,
                script_path=script_path,
                searched_paths=searched_paths,
                runtime_import_bootstrap=runtime_import_bootstrap,
            )

        _checkpoint("IMPORT_PREPARATION_BEFORE")
        runtime_import_bootstrap = _prepare_runtime_imports(workspace_dir)
        _checkpoint("IMPORT_PREPARATION_AFTER", "ok")

        _checkpoint("SCRIPT_FILE_READ_BEFORE")
        with open(script_path, "r", encoding="utf-8-sig") as f:
            code = f.read()
        _checkpoint("SCRIPT_FILE_READ_AFTER", "ok")

        _checkpoint("SCRIPT_COMPILE_BEFORE")
        compiled_code = compile(code, script_path, "exec")
        _checkpoint("SCRIPT_COMPILE_AFTER", "ok")

        script_globals = {
            "__file__": script_path,
            "__name__": "__dynamo_external_script__",
            "IN": IN,
            "INPUTS": INPUTS,
            "OUT": None,
            "RUNTIME_IMPORT_BOOTSTRAP": runtime_import_bootstrap,
            "RUNTIME_CHECKPOINT": _RUNTIME_CHECKPOINT,
        }
        _checkpoint("SCRIPT_GLOBALS_READY", "dict")

        try:
            script_globals["UnwrapElement"] = UnwrapElement
        except Exception:
            pass

        _checkpoint("SCRIPT_EXEC_BEFORE")
        exec(compiled_code, script_globals)
        _checkpoint("SCRIPT_EXEC_AFTER", "ok")

        _checkpoint("SCRIPT_OUT_READ_BEFORE")
        script_out = script_globals.get("OUT", None)
        _checkpoint("SCRIPT_OUT_READ_AFTER", "none" if script_out is None else "ok")

        if script_out is None:
            return build_failure(
                "script.py executed, but OUT is None. Check that script.py contains final OUT assignment.",
                workspace_file=workspace_file,
                workspace_dir=workspace_dir,
                loader_path=loader_path,
                script_path=script_path,
                searched_paths=searched_paths,
                extra={
                    "available_keys": sorted(
                        [str(k) for k in script_globals.keys() if not str(k).startswith("__")]
                    )
                },
                runtime_import_bootstrap=runtime_import_bootstrap,
            )

        _checkpoint("LOADER_RETURN_READY", "ok")
        return script_out
    except BaseException as exc:
        _checkpoint("LOADER_EXCEPTION", type(exc).__name__)
        return build_failure(
            "{0}: loader execution failed".format(type(exc).__name__),
            workspace_file=workspace_file,
            workspace_dir=workspace_dir,
            loader_path=loader_path,
            script_path=script_path,
            searched_paths=searched_paths,
            runtime_import_bootstrap=runtime_import_bootstrap,
        )


OUT = run_script()
