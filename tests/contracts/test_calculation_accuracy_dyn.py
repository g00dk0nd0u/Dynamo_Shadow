import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _graph():
    return json.loads((ROOT / "Shadow.dyn").read_text(encoding="utf-8"))


def test_python_node_has_eight_connected_inputs():
    graph = _graph()
    python_node = next(node for node in graph["Nodes"] if node["NodeType"] == "PythonScriptNode")
    assert [port["Name"] for port in python_node["Inputs"]] == ["IN[{0}]".format(i) for i in range(8)]
    ends = {connector["End"] for connector in graph["Connectors"]}
    assert all(port["Id"] in ends for port in python_node["Inputs"])


def test_accuracy_custom_selection_is_player_input_defaulting_to_standard():
    graph = _graph()
    views = {view["Id"]: view for view in graph["View"]["NodeViews"]}
    node = next(node for node in graph["Nodes"] if views[node["Id"]]["Name"] == "Calculation Accuracy / 計算精度")
    assert node["ConcreteType"].startswith("CoreNodeModels.Input.CustomSelection")
    assert views[node["Id"]]["IsSetAsInput"] is True
    assert node["SelectedIndex"] == 1
    assert [item["Value"] for item in node["Items"]] == ["rough", "standard", "high"]


def test_player_input_display_order_and_settings_remains_hidden():
    graph = _graph()
    players = sorted((v for v in graph["View"]["NodeViews"] if v["IsSetAsInput"]), key=lambda v: v["Y"])
    assert [v["Name"] for v in players] == [
        "Levels", "Select Model Element", "Regulatory Shadow Preset / 日影規制時間",
        "Calculation Accuracy / 計算精度", "Site Latitude / 緯度（deg）", "Site Longitude / 経度（deg）",
    ]
    settings = next(v for v in graph["View"]["NodeViews"] if v["Id"] == "f688e0f729b946d0b8ac25514f4531da")
    assert settings["IsSetAsInput"] is False


def test_top_level_inputs_register_accuracy_once_with_default_and_order():
    graph = _graph()
    inputs = graph["Inputs"]
    accuracy_inputs = [item for item in inputs if item["Id"] == "b4444444444444444444444444444444"]
    assert len(accuracy_inputs) == 1
    accuracy = accuracy_inputs[0]
    assert accuracy["Name"] == "Calculation Accuracy / 計算精度"
    assert accuracy["Type"] == "selection"
    assert accuracy["Type2"] == "dropdownSelection"
    assert accuracy["Value"] == "standard"
    assert accuracy["SelectedIndex"] == 1
    assert [item["Name"] for item in inputs] == [
        "Levels",
        "Select Model Element",
        "Regulatory Shadow Preset / 日影規制時間",
        "Calculation Accuracy / 計算精度",
        "Site Latitude / 緯度（deg）",
        "Site Longitude / 経度（deg）",
    ]


def test_all_player_nodeviews_are_registered_as_top_level_inputs():
    graph = _graph()
    top_level_input_ids = {item["Id"] for item in graph["Inputs"]}
    player_input_ids = {
        view["Id"] for view in graph["View"]["NodeViews"] if view.get("IsSetAsInput") is True
    }
    assert player_input_ids <= top_level_input_ids
