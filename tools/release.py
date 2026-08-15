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
REVIT_HOST_FRAMEWORKS = ("net8.0-windows", "net10.0-windows")


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
        "DynamoShadow Release build",
        [
            "dotnet",
            "build",
            "product/dynamo/DynamoShadow.csproj",
            "--configuration",
            "Release",
        ],
    )
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

    missing_outputs = [
        PRODUCT_ROOT / "revit" / "bin" / "Release" / framework / "RevitShadow.dll"
        for framework in REVIT_HOST_FRAMEWORKS
        if not (
            PRODUCT_ROOT / "revit" / "bin" / "Release" / framework / "RevitShadow.dll"
        ).is_file()
    ]
    if missing_outputs:
        missing = ", ".join(str(path.relative_to(REPOSITORY_ROOT)) for path in missing_outputs)
        raise ReleaseError(f"RevitShadow multi-target build output is missing: {missing}")


def reset_distribution() -> None:
    if DIST_ROOT.exists():
        shutil.rmtree(DIST_ROOT)
    DIST_ROOT.mkdir()


def assemble_distributions() -> None:
    """Stop until real, version-validated product hosts are implemented."""
    raise ReleaseError(
        "Compiled product packaging is not ready: final DynamoShadow.dyn, "
        "pkg.json, Revit API references, version-specific "
        "Revit validation, and RevitShadow.addin are not implemented"
    )


def validate_distribution() -> None:
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
