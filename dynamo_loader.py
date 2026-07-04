# Dynamo external loader for Shadow.dyn
# Finds and executes script.py from the same folder as the current .dyn file.

import clr
import os
import traceback

LOADER_NAME = "Shadow.dyn external loader"
SCRIPT_NAME = "script.py"


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
    searched_paths = []
    workspace_file, workspace_dir, loader_path = resolve_workspace()
    script_path = None

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
            )

        with open(script_path, "r", encoding="utf-8-sig") as f:
            code = f.read()

        script_globals = {
            "__file__": script_path,
            "__name__": "__dynamo_external_script__",
            "IN": IN,
            "INPUTS": INPUTS,
            "OUT": None,
        }

        try:
            script_globals["UnwrapElement"] = UnwrapElement
        except Exception:
            pass

        exec(compile(code, script_path, "exec"), script_globals)

        script_out = script_globals.get("OUT", None)

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
            )

        return script_out
    except Exception:
        return build_failure(
            traceback.format_exc(),
            workspace_file=workspace_file,
            workspace_dir=workspace_dir,
            loader_path=loader_path,
            script_path=script_path,
            searched_paths=searched_paths,
        )


OUT = run_script()
