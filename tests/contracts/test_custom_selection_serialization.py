import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGULATORY_ID = "b1111111111111111111111111111111"
ACCURACY_ID = "b4444444444444444444444444444444"
REGULATORY_OUTPUT_ID = "c1111111111111111111111111111111"
ACCURACY_OUTPUT_ID = "c4444444444444444444444444444444"
PYTHON_IN4_ID = "a1111111111111111111111111111111"
PYTHON_IN7_ID = "a4444444444444444444444444444444"


def _graph():
    return json.loads((ROOT / "Shadow.dyn").read_text(encoding="utf-8"))


def _custom_selection_nodes(graph):
    return [
        node for node in graph["Nodes"]
        if node.get("ConcreteType") == "CoreNodeModels.Input.CustomSelection, CoreNodeModels"
    ]


def _selected_item(node):
    return node["SerializedItems"][node["SelectedIndex"]]


def test_custom_selection_nodes_use_dynamo_serialized_items_contract():
    graph = _graph()
    nodes = {node["Id"]: node for node in _custom_selection_nodes(graph)}
    assert set(nodes) == {REGULATORY_ID, ACCURACY_ID}
    assert len(nodes) == 2

    expected_lengths = {REGULATORY_ID: 8, ACCURACY_ID: 3}
    expected_selected_items = {REGULATORY_ID: "standard_all", ACCURACY_ID: "standard"}
    for node_id, node in nodes.items():
        assert "Items" not in node
        assert node["IsVisibleDropDownTextBlock"] is True
        assert len(node["SerializedItems"]) == expected_lengths[node_id]
        for entry in node["SerializedItems"]:
            assert set(entry) == {"Name", "Item"}
            assert "Value" not in entry
        selected = _selected_item(node)
        assert node["SelectedString"] == selected["Name"]
        assert selected["Item"] == expected_selected_items[node_id]


def test_top_level_player_values_match_selected_display_strings():
    graph = _graph()
    nodes = {node["Id"]: node for node in _custom_selection_nodes(graph)}
    inputs = {item["Id"]: item for item in graph["Inputs"]}

    for node_id in (REGULATORY_ID, ACCURACY_ID):
        selected_string = nodes[node_id]["SelectedString"]
        assert inputs[node_id]["Value"] == selected_string
        assert inputs[node_id]["SelectedIndex"] == nodes[node_id]["SelectedIndex"]


def test_custom_selection_outputs_and_python_connectors_are_preserved():
    graph = _graph()
    nodes = {node["Id"]: node for node in graph["Nodes"]}
    python_node = next(node for node in graph["Nodes"] if node["NodeType"] == "PythonScriptNode")
    assert [port["Name"] for port in python_node["Inputs"]] == ["IN[{0}]".format(i) for i in range(8)]

    for node_id, output_id in ((REGULATORY_ID, REGULATORY_OUTPUT_ID), (ACCURACY_ID, ACCURACY_OUTPUT_ID)):
        output = nodes[node_id]["Outputs"][0]
        assert output["Id"] == output_id
        assert output["Name"] == "Value"
        assert output["Description"] == "The selected Value"

    connectors = {(connector["Start"], connector["End"], connector["Id"]) for connector in graph["Connectors"]}
    assert (REGULATORY_OUTPUT_ID, PYTHON_IN4_ID, "d1111111111111111111111111111111") in connectors
    assert (ACCURACY_OUTPUT_ID, PYTHON_IN7_ID, "d4444444444444444444444444444444") in connectors


def test_settings_json_is_not_a_player_input():
    graph = _graph()
    settings_id = "f688e0f729b946d0b8ac25514f4531da"
    settings_view = next(view for view in graph["View"]["NodeViews"] if view["Id"] == settings_id)
    assert settings_view["IsSetAsInput"] is False
    assert settings_id not in {item["Id"] for item in graph["Inputs"]}
