import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_python_node_in_zero_through_eight_mapping_is_unchanged():
    loader = (ROOT / "runtime" / "dynamo_loader.py").read_text(encoding="utf-8")
    expected = [
        '"building_elements": get_in(0)', '"site_boundary": get_in(1)',
        '"level": get_in(2)', '"settings": get_in(3)',
        '"regulatory_shadow_preset": get_in(4)', '"site_latitude_deg": get_in(5)',
        '"site_longitude_deg": get_in(6)', '"calculation_accuracy_preset": get_in(7)',
        '"analysis_mode": get_in(8)',
    ]
    assert all(item in loader for item in expected)
    assert "get_in(9)" not in loader


def test_dynamo_player_display_order_remains_eight_inputs():
    graph = json.loads((ROOT / "runtime" / "Shadow.dyn").read_text(encoding="utf-8"))
    player_inputs = [node for node in graph["View"]["NodeViews"]
                     if node.get("IsSetAsInput")]
    names = [node["Name"] for node in sorted(player_inputs, key=lambda node: node["Y"])]
    assert names == [
        "Site Boundary Area / 敷地境界エリア", "Building Model / 建物モデル",
        "Shadow Limits / 日影規制時間（5–10m / 10m超）", "Average Ground Level / 平均地盤面",
        "Calculation Accuracy / 計算精度", "Analysis Mode / 解析モード",
        "Site Latitude / 緯度（deg）", "Site Longitude / 経度（deg）",
    ]
