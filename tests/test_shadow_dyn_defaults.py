import json
from pathlib import Path


def test_player_string_value_and_input_value_are_identical_valid_json():
    graph = json.loads((Path(__file__).parents[1] / "Shadow.dyn").read_text(encoding="utf-8"))
    node_id = "f688e0f729b946d0b8ac25514f4531da"
    value = next(item["Value"] for item in graph["Inputs"] if item["Id"] == node_id)
    input_value = next(item["InputValue"] for item in graph["Nodes"] if item["Id"] == node_id)
    assert value == input_value
    settings = json.loads(value)
    assert settings["preview_mode"] == "replace"
    assert settings["solar_parameter_mode"] == "regulatory_winter_solstice_v1"
