#!/usr/bin/env python3
"""Run release gates and assemble compiled product distributions.

This is intentionally strict: until real DLL-backed Dynamo and Revit product
inputs exist, the command fails rather than packaging reference Python sources or
placeholder artifacts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = REPOSITORY_ROOT / "product"
DIST_ROOT = REPOSITORY_ROOT / "dist"


class ReleaseError(RuntimeError):
    """A release gate or packaging validation failed."""


def run_stage(name: str, arguments: list[str]) -> None:
    """Run one deterministic repository-root command without a shell."""
    print(f"\n==> {name}", flush=True)
    print("    " + " ".join(arguments), flush=True)
    try:
        subprocess.run(arguments, cwd=REPOSITORY_ROOT, check=True)
    except FileNotFoundError as exc:
        raise ReleaseError(f"Required executable is unavailable: {arguments[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise ReleaseError(f"{name} failed with exit code {exc.returncode}") from exc


def run_python_validation() -> None:
    run_stage("Python tests", [sys.executable, "-m", "pytest", "-q"])
    run_stage(
        "Runtime bundle check",
        [sys.executable, "tools/check_runtime_bundle.py"],
    )
    run_stage(
        "Python compile check",
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "runtime",
            "tests",
            "tools",
            "-x",
            r"(^|[\\/])(\.git|\.pytest_cache|debug_logs)([\\/]|$)",
        ],
    )
    with (REPOSITORY_ROOT / "runtime" / "Shadow.dyn").open(
        "r", encoding="utf-8"
    ) as graph_file:
        json.load(graph_file)
    run_stage(
        "Debug-log privacy check",
        [sys.executable, "tools/check_debug_log_privacy.py"],
    )
    run_stage("Git whitespace check", ["git", "diff", "--check"])


def run_compiled_validation() -> None:
    run_stage(
        "ShadowCore tests",
        [
            "dotnet",
            "test",
            "product/tests/ShadowCore.Tests.csproj",
            "--configuration",
            "Release",
        ],
    )
    run_stage(
        "ShadowCore Release build",
        [
            "dotnet",
            "build",
            "product/core/ShadowCore.csproj",
            "--configuration",
            "Release",
            "--no-restore",
        ],
    )
    run_stage(
        "RevitShadow Release build",
        [
            "dotnet",
            "build",
            "product/revit/RevitShadow.csproj",
            "--configuration",
            "Release",
        ],
    )


def reset_distribution() -> None:
    if DIST_ROOT.exists():
        shutil.rmtree(DIST_ROOT)
    DIST_ROOT.mkdir()


def require_files(paths: list[Path], product_name: str) -> None:
    missing = [path.relative_to(REPOSITORY_ROOT) for path in paths if not path.is_file()]
    if missing:
        details = ", ".join(str(path) for path in missing)
        raise ReleaseError(
            f"{product_name} is not ready for product packaging; missing: {details}"
        )


def assemble_distributions() -> None:
    core_dll = PRODUCT_ROOT / "core" / "bin" / "Release" / "netstandard2.0" / "ShadowCore.dll"
    dynamo_graph = PRODUCT_ROOT / "dynamo" / "DynamoShadow.dyn"
    dynamo_manifest = PRODUCT_ROOT / "dynamo" / "pkg.json"
    revit_dll = PRODUCT_ROOT / "revit" / "bin" / "Release" / "net48" / "RevitShadow.dll"
    revit_manifest = PRODUCT_ROOT / "revit" / "RevitShadow.addin"

    require_files(
        [core_dll, dynamo_graph, dynamo_manifest], "DynamoShadow"
    )
    require_files(
        [core_dll, revit_dll, revit_manifest], "RevitShadow"
    )

    dynamo_dist = DIST_ROOT / "DynamoShadow"
    revit_dist = DIST_ROOT / "RevitShadow"
    (dynamo_dist / "bin").mkdir(parents=True)
    (dynamo_dist / "extra").mkdir()
    revit_dist.mkdir()

    shutil.copy2(core_dll, dynamo_dist / "bin" / "ShadowCore.dll")
    shutil.copy2(dynamo_graph, dynamo_dist / "extra" / "DynamoShadow.dyn")
    shutil.copy2(dynamo_manifest, dynamo_dist / "pkg.json")
    shutil.copy2(core_dll, revit_dist / "ShadowCore.dll")
    shutil.copy2(revit_dll, revit_dist / "RevitShadow.dll")
    shutil.copy2(revit_manifest, revit_dist / "RevitShadow.addin")


def validate_distribution() -> None:
    required = {
        "DynamoShadow/bin/ShadowCore.dll",
        "DynamoShadow/extra/DynamoShadow.dyn",
        "DynamoShadow/pkg.json",
        "RevitShadow/ShadowCore.dll",
        "RevitShadow/RevitShadow.dll",
        "RevitShadow/RevitShadow.addin",
    }
    actual = {
        str(path.relative_to(DIST_ROOT)).replace("\\", "/")
        for path in DIST_ROOT.rglob("*")
        if path.is_file()
    }
    if actual != required:
        raise ReleaseError(
            f"Distribution file set mismatch; missing={sorted(required - actual)}, "
            f"unexpected={sorted(actual - required)}"
        )

    forbidden_suffixes = {".py", ".cs", ".csproj", ".sln", ".pdb", ".map"}
    forbidden_names = {"RevitAPI.dll", "RevitAPIUI.dll"}
    forbidden_parts = {
        "tests", "tools", ".git", ".github", "debug_logs", "obj"
    }
    for path in DIST_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(DIST_ROOT)
        if (
            path.suffix.lower() in forbidden_suffixes
            or path.name in forbidden_names
            or forbidden_parts.intersection(relative.parts)
        ):
            raise ReleaseError(f"Forbidden public distribution file: {relative}")


def main() -> int:
    try:
        run_python_validation()
        run_compiled_validation()
        reset_distribution()
        assemble_distributions()
        validate_distribution()
    except (ReleaseError, json.JSONDecodeError) as exc:
        print(f"\nRELEASE FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"\nRelease distributions assembled at {DIST_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
