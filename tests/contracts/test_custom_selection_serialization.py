import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGULATORY_ID = "b1111111111111111111111111111111"
ACCURACY_ID = "b4444444444444444444444444444444"
ANALYSIS_MODE_ID = "b5555555555555555555555555555555"
REGULATORY_OUTPUT_ID = "c1111111111111111111111111111111"
ACCURACY_OUTPUT_ID = "c4444444444444444444444444444444"
PYTHON_IN4_ID = "a1111111111111111111111111111111"
PYTHON_IN7_ID = "a4444444444444444444444444444444"


def _graph():
    return json.loads((ROOT / "runtime" / "Shadow.dyn").read_text(encoding="utf-8"))


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
    assert set(nodes) == {REGULATORY_ID, ACCURACY_ID, ANALYSIS_MODE_ID}
    assert len(nodes) == 3

    expected_lengths = {REGULATORY_ID: 8, ACCURACY_ID: 2, ANALYSIS_MODE_ID: 2}
    expected_selected_items = {REGULATORY_ID: "standard_all", ACCURACY_ID: "standard",
                               ANALYSIS_MODE_ID: "forward_shadow"}
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

    for node_id in (REGULATORY_ID, ACCURACY_ID, ANALYSIS_MODE_ID):
        selected_string = nodes[node_id]["SelectedString"]
        assert inputs[node_id]["Value"] == selected_string
        assert inputs[node_id]["SelectedIndex"] == nodes[node_id]["SelectedIndex"]


def test_player_menu_display_names_and_defaults_are_bilingual_and_stable():
    graph = _graph()
    nodes = {node["Id"]: node for node in _custom_selection_nodes(graph)}

    regulatory = nodes[REGULATORY_ID]
    assert regulatory["SelectedIndex"] == 0
    assert regulatory["SelectedString"] == "Standard / 標準｜All / 全候補"
    assert [entry["Item"] for entry in regulatory["SerializedItems"]] == [
        "standard_all",
        "standard_3_2",
        "standard_4_2_5",
        "standard_5_3",
        "hokkaido_all",
        "hokkaido_2_1_5",
        "hokkaido_3_2",
        "hokkaido_4_2_5",
    ]
    assert [entry["Name"] for entry in regulatory["SerializedItems"]] == [
        "Standard / 標準｜All / 全候補",
        "Standard / 標準｜3h / 2h",
        "Standard / 標準｜4h / 2.5h",
        "Standard / 標準｜5h / 3h",
        "Hokkaido / 北海道｜All / 全候補",
        "Hokkaido / 北海道｜2h / 1.5h",
        "Hokkaido / 北海道｜3h / 2h",
        "Hokkaido / 北海道｜4h / 2.5h",
    ]

    accuracy = nodes[ACCURACY_ID]
    assert accuracy["SelectedIndex"] == 1
    assert accuracy["SelectedString"] == "Standard / 標準"
    assert accuracy["SerializedItems"] == [
        {"Name": "Fast / 高速", "Item": "rough"},
        {"Name": "Standard / 標準", "Item": "standard"},
    ]


def test_top_level_inputs_and_nodeviews_use_matching_player_names():
    graph = _graph()
    nodeviews = {view["Id"]: view for view in graph["View"]["NodeViews"]}
    for player_input in graph["Inputs"]:
        assert player_input["Name"] == nodeviews[player_input["Id"]]["Name"]


def test_custom_selection_outputs_and_python_connectors_are_preserved():
    graph = _graph()
    nodes = {node["Id"]: node for node in graph["Nodes"]}
    python_node = next(node for node in graph["Nodes"] if node["NodeType"] == "PythonScriptNode")
    assert [port["Name"] for port in python_node["Inputs"]] == ["IN[{0}]".format(i) for i in range(9)]

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
