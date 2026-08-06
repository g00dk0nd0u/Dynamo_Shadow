"""Distribution-layout contracts for the self-contained runtime bundle."""

import json
import shutil
from pathlib import Path

from tools.check_runtime_bundle import validate_runtime_bundle


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = REPOSITORY_ROOT / "runtime"


def _assert_same_folder_contract(bundle: Path) -> None:
    graph = json.loads((bundle / "Shadow.dyn").read_text(encoding="utf-8-sig"))
    embedded = "\n".join(
        node.get("Code", "") for node in graph.get("Nodes", []) if isinstance(node, dict)
    )
    loader = (bundle / "dynamo_loader.py").read_text(encoding="utf-8-sig")
    assert 'LOADER_NAME = "dynamo_loader.py"' in embedded
    assert "os.path.join(workspace_dir, LOADER_NAME)" in embedded
    assert 'SCRIPT_NAME = "script.py"' in loader
    assert "os.path.join(workspace_dir, SCRIPT_NAME)" in loader
    assert not any(token in embedded for token in ('"runtime"', "'runtime'"))
    assert not any(token in loader for token in ('"runtime"', "'runtime'"))


def test_repository_runtime_bundle_is_valid_and_root_has_no_runtime_duplicates():
    assert validate_runtime_bundle(RUNTIME_ROOT) == []
    assert not (REPOSITORY_ROOT / "Shadow.dyn").exists()
    assert not (REPOSITORY_ROOT / "dynamo_loader.py").exists()
    assert not (REPOSITORY_ROOT / "script.py").exists()
    assert list(REPOSITORY_ROOT.glob("shadow_*.py")) == []


def test_runtime_bundle_remains_valid_after_japanese_space_rename(tmp_path):
    renamed_bundle = tmp_path / "日影図 社内試用版"
    shutil.copytree(RUNTIME_ROOT, renamed_bundle)

    assert validate_runtime_bundle(renamed_bundle) == []
    _assert_same_folder_contract(renamed_bundle)
    json.loads((renamed_bundle / "Shadow.dyn").read_text(encoding="utf-8-sig"))
    for path in renamed_bundle.glob("*.py"):
        compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
