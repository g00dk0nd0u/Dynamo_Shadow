"""Debug-log paths stay inside the copied runtime bundle."""

import json
from pathlib import Path

import shadow_debug


def _enabled_default_settings():
    return {"normalized": {"debug_log_enabled": True}}


def test_default_debug_path_is_runtime_relative_from_repository_cwd(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "copied_runtime"
    runtime_dir.mkdir()
    monkeypatch.setattr(shadow_debug, "__file__", str(runtime_dir / "shadow_debug.py"))
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    path = shadow_debug._safe_debug_log_path(_enabled_default_settings())

    assert Path(path["absolute_path"]) == runtime_dir / "debug_logs" / "latest_debug.json"
    assert path["relative_path"] == "debug_logs/latest_debug.json"


def test_default_debug_write_is_runtime_relative_from_unrelated_cwd(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "copied_runtime"
    unrelated_dir = tmp_path / "unrelated_working_directory"
    runtime_dir.mkdir()
    unrelated_dir.mkdir()
    monkeypatch.setattr(shadow_debug, "__file__", str(runtime_dir / "shadow_debug.py"))
    monkeypatch.chdir(unrelated_dir)

    status = shadow_debug._write_debug_log_if_enabled(
        {"success": True}, _enabled_default_settings()
    )

    output = runtime_dir / "debug_logs" / "latest_debug.json"
    assert status["written"] is True
    assert status["path"] == "debug_logs/latest_debug.json"
    assert output.is_file()
    assert json.loads(output.read_text())["success"] is True
    assert not (unrelated_dir / "debug_logs").exists()
