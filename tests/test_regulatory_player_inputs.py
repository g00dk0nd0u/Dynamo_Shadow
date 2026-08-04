import json
from pathlib import Path

import pytest

from shadow_policies import INPUT_KEYS, SETTINGS_DIAGNOSTIC_DEFAULTS
from shadow_regulatory_presets import PRESETS, overlay_player_settings, resolve_regulatory_shadow_preset
from shadow_settings import _normalize_settings

ROOT = Path(__file__).parents[1]


def graph():
    return json.loads((ROOT / "Shadow.dyn").read_text(encoding="utf-8"))


def test_all_presets_resolve_in_sorted_order():
    for preset_id in PRESETS:
        resolved = resolve_regulatory_shadow_preset(preset_id)
        assert resolved["valid"] is True
        assert resolved["equal_time_contour_levels_minutes"] == sorted(resolved["equal_time_contour_levels_minutes"])
        assert resolved["legal_judgement_generated"] is False
        assert resolved["ordinance_selection_certified"] is False


@pytest.mark.parametrize("preset_id,levels,start,end", [
    ("standard_all", [120, 150, 180, 240, 300], "08:00", "16:00"),
    ("hokkaido_all", [90, 120, 150, 180, 240], "09:00", "15:00"),
    ("standard_4_2_5", [150, 240], "08:00", "16:00"),
    ("hokkaido_2_1_5", [90, 120], "09:00", "15:00"),
])
def test_expected_preset_contract(preset_id, levels, start, end):
    value = resolve_regulatory_shadow_preset(preset_id)
    assert value["equal_time_contour_levels_minutes"] == [float(v) for v in levels]
    assert (value["true_solar_start_time"], value["true_solar_end_time"]) == (start, end)


def test_invalid_preset_returns_machine_readable_blocker():
    value = resolve_regulatory_shadow_preset("not-a-preset")
    assert value["valid"] is False
    assert value["blockers"][0]["failure_code"] == "invalid_regulatory_shadow_preset"


@pytest.mark.parametrize("key,value", [("site_latitude_deg", -90.01), ("site_latitude_deg", 90.01),
                                        ("site_longitude_deg", -180.01), ("site_longitude_deg", 180.01)])
def test_player_coordinate_ranges_are_validated(key, value):
    kwargs = {key: value}
    overlaid, _, _, _, _ = overlay_player_settings({"latitude": 35, "longitude": 139}, **kwargs)
    normalized = _normalize_settings(overlaid)
    assert key in normalized["invalid_keys"]
    assert normalized["normalized"][key] is None


def test_player_inputs_override_json_without_mutating_it():
    original = {"profile": "hokkaido_9_15", "latitude": 1, "longitude": 2,
                "equal_time_contour_levels_minutes": [360, 480]}
    overlaid, preset, _, _, _ = overlay_player_settings(original, "standard_4_2_5", 35.6812, 139.7671)
    assert original["profile"] == "hokkaido_9_15"
    assert overlaid["profile"] == "standard_8_16"
    assert overlaid["equal_time_contour_levels_minutes"] == [150.0, 240.0]
    assert overlaid["site_latitude_deg"] == 35.6812
    assert overlaid["site_longitude_deg"] == 139.7671
    assert "latitude" not in overlaid and "longitude" not in overlaid
    assert preset["preset_id"] == "standard_4_2_5"


def test_legacy_four_port_contract_remains_prefix_compatible():
    assert INPUT_KEYS[:4] == ["building_elements", "site_boundary", "level", "settings"]
    assert len(INPUT_KEYS) == 7


def test_player_graph_inputs_and_connectors():
    data = graph()
    views = {v["Id"]: v for v in data["View"]["NodeViews"]}
    nodes = {n["Id"]: n for n in data["Nodes"]}
    settings_id = "f688e0f729b946d0b8ac25514f4531da"
    assert views[settings_id]["IsSetAsInput"] is False
    assert settings_id not in {item["Id"] for item in data["Inputs"]}
    custom = next(n for n in nodes.values() if "CustomSelection" in n["ConcreteType"])
    numbers = [n for n in nodes.values() if n["NodeType"] == "NumberInputNode"]
    assert views[custom["Id"]]["IsSetAsInput"] is True
    assert custom["Items"][custom["SelectedIndex"]]["Value"] == "standard_all"
    assert len(numbers) == 2 and all(views[n["Id"]]["IsSetAsInput"] for n in numbers)
    python_node = next(n for n in nodes.values() if n["NodeType"] == "PythonScriptNode")
    assert len(python_node["Inputs"]) == 7
    output_ids = {p["Id"] for n in nodes.values() for p in n.get("Outputs", [])}
    input_ids = {p["Id"] for n in nodes.values() for p in n.get("Inputs", [])}
    assert all(c["Start"] in output_ids and c["End"] in input_ids for c in data["Connectors"])
    assert "3daad2f0de954b2a971f92fd9f671601" in nodes
    assert "af2519f73dff436c8aba2f16c3788bf3" in nodes


def test_graph_internal_settings_and_safe_python_defaults():
    data = graph()
    node = next(n for n in data["Nodes"] if n["Id"] == "f688e0f729b946d0b8ac25514f4531da")
    settings = json.loads(node["InputValue"])
    assert settings["preview_mode"] == settings["equal_time_contour_preview_mode"] == "replace"
    assert not ({"latitude", "longitude", "site_latitude_deg", "site_longitude_deg",
                 "equal_time_contour_levels_minutes"} & settings.keys())
    assert SETTINGS_DIAGNOSTIC_DEFAULTS["preview_mode"] == "off"
    assert SETTINGS_DIAGNOSTIC_DEFAULTS["equal_time_contour_preview_mode"] == "off"


def test_explicit_six_to_eight_hour_contours_remain_supported():
    normalized = _normalize_settings({"equal_time_contour_levels_minutes": [360, 480]})
    assert normalized["normalized"]["equal_time_contour_levels_minutes"] == [360.0, 480.0]
