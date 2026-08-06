#!/usr/bin/env python3
"""Validate the self-contained Dynamo/Revit runtime distribution directory."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REQUIRED_FILES = ("Shadow.dyn", "dynamo_loader.py", "script.py", "README.md")
FORBIDDEN_DIRECTORY_NAMES = {"tests", "tools", ".github", ".git", "__pycache__"}
FORBIDDEN_FILE_SUFFIXES = {".pyc", ".log"}


def _shadow_imports(source: str, filename: str) -> set[str]:
    tree = ast.parse(source, filename=filename)
    imports: set[str] = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            root_name = name.split(".", 1)[0]
            if root_name.startswith("shadow_"):
                imports.add(root_name)
    return imports


def _embedded_python(graph: object) -> list[str]:
    if not isinstance(graph, dict):
        return []
    return [
        node["Code"]
        for node in graph.get("Nodes", [])
        if isinstance(node, dict) and isinstance(node.get("Code"), str)
    ]


def validate_runtime_bundle(bundle: Path) -> list[str]:
    """Return human-readable errors for a runtime bundle, or an empty list."""
    bundle = Path(bundle)
    errors: list[str] = []
    if not bundle.is_dir():
        return [f"runtime bundle directory missing: {bundle}"]

    for filename in REQUIRED_FILES:
        if not (bundle / filename).is_file():
            errors.append(f"missing required file: {filename}")

    modules = sorted(bundle.glob("shadow_*.py"))
    if not modules:
        errors.append("missing runtime modules: shadow_*.py")

    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle)
        if any(part in FORBIDDEN_DIRECTORY_NAMES for part in relative.parts):
            errors.append(f"forbidden runtime placement: {relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_FILE_SUFFIXES:
            errors.append(f"forbidden runtime artifact: {relative}")
        if path.is_file() and "debug" in path.name.lower() and "fixture" in path.name.lower():
            errors.append(f"debug log fixture is not distributable: {relative}")

    python_files = sorted(bundle.glob("*.py"))
    local_names = {path.stem for path in modules}
    imported_names: set[str] = set()
    for path in python_files:
        try:
            source = path.read_text(encoding="utf-8-sig")
            compile(source, str(path), "exec")
            if path.name == "script.py" or path.name.startswith("shadow_"):
                imported_names.update(_shadow_imports(source, str(path)))
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"Python syntax/read failure: {path.name}: {exc}")
    for name in sorted(imported_names - local_names):
        errors.append(f"unresolved local import: {name} (expected {name}.py)")

    graph_path = bundle / "Shadow.dyn"
    if graph_path.is_file():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
            embedded = _embedded_python(graph)
            matching = [code for code in embedded if 'LOADER_NAME = "dynamo_loader.py"' in code]
            if not matching:
                errors.append('Shadow.dyn embedded Python lacks LOADER_NAME = "dynamo_loader.py"')
            elif not any("os.path.join(workspace_dir, LOADER_NAME)" in code for code in matching):
                errors.append("Shadow.dyn does not resolve its loader from the workspace directory")
            if any('"runtime"' in code or "'runtime'" in code for code in embedded):
                errors.append('Shadow.dyn embedded Python requires the fixed folder name "runtime"')
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"Shadow.dyn JSON parse failure: {exc}")

    loader_path = bundle / "dynamo_loader.py"
    if loader_path.is_file():
        try:
            loader = loader_path.read_text(encoding="utf-8-sig")
            if 'SCRIPT_NAME = "script.py"' not in loader:
                errors.append('dynamo_loader.py lacks SCRIPT_NAME = "script.py"')
            if "os.path.join(workspace_dir, SCRIPT_NAME)" not in loader:
                errors.append("dynamo_loader.py does not resolve script.py from the workspace directory")
            if "os.pardir" in loader or "Path(__file__).parent.parent" in loader:
                errors.append("dynamo_loader.py requires a parent/repository directory")
            if '"runtime"' in loader or "'runtime'" in loader:
                errors.append('dynamo_loader.py requires the fixed folder name "runtime"')
        except (OSError, UnicodeError) as exc:
            errors.append(f"dynamo_loader.py read failure: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runtime",
        help="bundle directory (default: repository runtime directory)",
    )
    args = parser.parse_args()
    errors = validate_runtime_bundle(args.bundle)
    if errors:
        for error in errors:
            print(f"runtime bundle check failed: {error}")
        return 1
    print("runtime bundle check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
