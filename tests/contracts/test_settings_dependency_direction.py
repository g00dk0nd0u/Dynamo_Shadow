import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_meter_based_settings_do_not_import_revit_adapter_or_api():
    tree = ast.parse((ROOT / "runtime" / "shadow_settings.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "shadow_level_adapter" not in imports
    assert "shadow_revit_api" not in imports
    assert "shadow_units" not in imports
