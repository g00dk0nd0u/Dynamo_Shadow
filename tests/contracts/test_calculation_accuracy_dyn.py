import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _graph():
    return json.loads((ROOT / "runtime" / "Shadow.dyn").read_text(encoding="utf-8"))


def test_python_node_has_nine_connected_inputs():
    graph = _graph()
    python_node = next(node for node in graph["Nodes"] if node["NodeType"] == "PythonScriptNode")
    assert [port["Name"] for port in python_node["Inputs"]] == ["IN[{0}]".format(i) for i in range(9)]
    ends = {connector["End"] for connector in graph["Connectors"]}
    assert all(port["Id"] in ends for port in python_node["Inputs"])


def test_accuracy_custom_selection_is_player_input_defaulting_to_standard():
    graph = _graph()
    views = {view["Id"]: view for view in graph["View"]["NodeViews"]}
    node = next(node for node in graph["Nodes"] if views[node["Id"]]["Name"] == "Calculation Accuracy / 計算精度")
    assert node["ConcreteType"].startswith("CoreNodeModels.Input.CustomSelection")
    assert views[node["Id"]]["IsSetAsInput"] is True
    assert node["SelectedIndex"] == 1
    assert {item["Item"] for item in node["SerializedItems"]} == {"rough", "standard", "high"}
    assert node["SelectedString"] == node["SerializedItems"][node["SelectedIndex"]]["Name"]
    assert {item["Name"] for item in node["SerializedItems"]} == {
        "Fast / 高速", "Standard / 標準", "High / 高精度"}
    assert "1.0m / 30min" in node["Description"]
    assert "0.5m / 15min" in node["Description"]
    assert "0.25m / 5min" in node["Description"]


def test_player_input_display_order_and_settings_remains_hidden():
    graph = _graph()
    players = sorted((v for v in graph["View"]["NodeViews"] if v["IsSetAsInput"]), key=lambda v: v["Y"])
    assert [v["Name"] for v in players] == [
        "Analysis Mode / 解析モード", "Levels", "Select Model Element", "Site Boundary Area / 敷地境界エリア",
        "Shadow Limits / 日影規制時間（5–10m / 10m超）", "Calculation Accuracy / 計算精度", "Site Latitude / 緯度（deg）", "Site Longitude / 経度（deg）",
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
    assert accuracy["Value"] == "Standard / 標準"
    assert accuracy["SelectedIndex"] == 1
    assert [item["Name"] for item in inputs] == [
        "Analysis Mode / 解析モード",
        "Levels",
        "Select Model Element",
        "Site Boundary Area / 敷地境界エリア",
        "Shadow Limits / 日影規制時間（5–10m / 10m超）",
        "Calculation Accuracy / 計算精度",
        "Site Latitude / 緯度（deg）",
        "Site Longitude / 経度（deg）",
    ]


def test_analysis_mode_is_append_only_in8_and_player_dropdown():
    graph = _graph()
    views = {view["Id"]: view for view in graph["View"]["NodeViews"]}
    node = next(node for node in graph["Nodes"]
                if views[node["Id"]]["Name"] == "Analysis Mode / 解析モード")
    assert [item["Item"] for item in node["SerializedItems"]] == ["forward_shadow", "reverse_shadow"]
    assert node["SelectedIndex"] == 0
    python_node = next(item for item in graph["Nodes"] if item["NodeType"] == "PythonScriptNode")
    connector = next(item for item in graph["Connectors"] if item["Start"] == node["Outputs"][0]["Id"])
    assert connector["End"] == python_node["Inputs"][8]["Id"]
    assert len(graph["Inputs"]) == 8


def test_all_player_nodeviews_are_registered_as_top_level_inputs():
    graph = _graph()
    top_level_input_ids = {item["Id"] for item in graph["Inputs"]}
    player_input_ids = {
        view["Id"] for view in graph["View"]["NodeViews"] if view.get("IsSetAsInput") is True
    }
    assert player_input_ids <= top_level_input_ids
