# Dynamo external loader for Shadow.dyn
# Finds and executes script.py from the same folder as the current .dyn file.

import clr
import os
import traceback

LOADER_NAME = "Shadow.dyn external loader"
SCRIPT_NAME = "script.py"


def get_workspace_info():
    workspace_file = None
    script_dir = None

    try:
        clr.AddReference("DynamoServices")
        from Dynamo.Applications import DynamoRevit

        ws = DynamoRevit.RevitDynamoModel.CurrentWorkspace
        workspace_file = ws.FileName

        if workspace_file and os.path.isfile(workspace_file):
            script_dir = os.path.dirname(workspace_file)
    except Exception:
        pass

    return workspace_file, script_dir


def build_failure(error, script_path, searched_paths, workspace_file, script_dir, extra=None):
    payload = {
        "success": False,
        "loader_name": LOADER_NAME,
        "script_name": SCRIPT_NAME,
        "workspace_file": workspace_file,
        "script_dir": script_dir,
        "script_path": script_path,
        "searched_paths": searched_paths,
        "error": error,
    }

    if extra:
        payload.update(extra)

    return payload


def run_script():
    searched_paths = []
    workspace_file, script_dir = get_workspace_info()
    script_path = None

    if script_dir:
        script_path = os.path.join(script_dir, SCRIPT_NAME)
        searched_paths.append(script_path)

    if not script_path or not os.path.isfile(script_path):
        return build_failure(
            "script.py not found in the same folder as the .dyn file.",
            script_path,
            searched_paths,
            workspace_file,
            script_dir,
        )

    with open(script_path, "r", encoding="utf-8-sig") as f:
        code = f.read()

    script_globals = {
        "__file__": script_path,
        "__name__": "__dynamo_external_script__",
        "IN": IN,
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
            script_path,
            searched_paths,
            workspace_file,
            script_dir,
            {
                "available_keys": sorted(
                    [str(k) for k in script_globals.keys() if not str(k).startswith("__")]
                )
            },
        )

    return script_out


try:
    OUT = run_script()
except Exception:
    OUT = build_failure(
        traceback.format_exc(),
        locals().get("script_path", None),
        locals().get("searched_paths", []),
        locals().get("workspace_file", None),
        locals().get("script_dir", None),
    )
