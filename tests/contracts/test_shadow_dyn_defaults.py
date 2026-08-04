import json
from pathlib import Path


def test_internal_settings_value_is_valid_json_with_preview_enabled():
    graph = json.loads((Path(__file__).parents[2] / "Shadow.dyn").read_text(encoding="utf-8"))
    node_id = "f688e0f729b946d0b8ac25514f4531da"
    node = next(item for item in graph["Nodes"] if item["Id"] == node_id)
    settings = json.loads(node["InputValue"])
    assert settings["preview_mode"] == "replace"
    assert settings["equal_time_contour_preview_mode"] == "replace"
    assert settings["solar_parameter_mode"] == "regulatory_winter_solstice_v1"
    assert node_id not in {item["Id"] for item in graph["Inputs"]}
