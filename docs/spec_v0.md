# spec_v0: 等時間日影図検討の初期仕様

## 目的

Dynamo / Revit 上で日影検討を進める前に、v0 で扱う入力・出力・非スコープを明確にする。

v0 は計算ロジックの完成版ではなく、Codex Cloud で安全に開発を始めるための仕様整理である。

## v0 のゴール

- 既存リポジトリ構成を壊さず、調査メモと仕様メモを分離する。
- 法規・自治体条件・プロジェクト条件の区別を明確にする。
- 将来の Dynamo / Revit 実装で必要になる入出力のたたき台を残す。
- 生成ファイルを Git 管理から外し、開発時の差分を読みやすくする。

## 入力候補

将来の実装では、次の入力を Dynamo 入力または設定プロファイルとして扱う想定とする。

- 建物モデル要素（v1初期検証では Generic Models の専用プロキシを第一候補とし、将来は Mass や実モデルカテゴリ収集へ拡張できる余地を残す）
- 敷地境界（v1初期検証では Model Lines の閉じたループを第一候補とし、将来は Property Lines、CAD境界、Floor境界、Area Boundary へ拡張できる余地を残す）
- Level（optional な参照入力。法規上の高さ基準ではない）
- average_ground_level（法規上の高さ基準）
- measurement_height_m（平均地盤面からの測定面高さ）
- 真北角度
- 緯度・経度
- 地域プロファイル
- 用途地域
- 日影規制種別
- 規制時間
- グリッド解像度

測定面は `average_ground_level + measurement_height_m` として扱う。平均地盤面の高さは、初期 settings では `average_ground_level_elevation_m` として入力する。Revit Level の Elevation を、そのまま平均地盤面や測定面高さとして扱わない。

## 固定値候補

法令や標準的な作図条件として固定しやすい値は、任意入力ではなくプロファイル化する。

```python
LEGAL_CONSTANTS = {
    "date_basis": "winter_solstice",
    "standard_start_time": "08:00",
    "standard_end_time": "16:00",
    "hokkaido_start_time": "09:00",
    "hokkaido_end_time": "15:00",
    "time_step_minutes": 30,
    "measurement_line_near_m": 5.0,
    "measurement_line_far_m": 10.0,
}
```

## 初期 settings 候補

Dynamo 入力または設定プロファイルで扱う初期 settings の候補は以下とする。

```python
settings = {
    "profile": "standard_8_16",
    "average_ground_level_elevation_m": 0.0,
    "measurement_height_m": 4.0,
    "latitude": 35.68,
    "longitude": 139.76,
    "true_north_deg": 0.0,
    "grid_resolution_m": 1.0,
}
```

`average_ground_level_elevation_m` は Revit 内部座標またはプロジェクト基準に対する平均地盤面高さを表す。v1では平均地盤面の自動算定は行わず、ユーザーが settings として入力する。

## 出力候補

v0 で最終的に確認したい出力は以下とする。

```text
success
message
legal_constants
input_summary
calculated_time_steps
building_bbox_count
site_boundary_summary
shadow_polygon_count_by_time
grid_resolution_mm
warnings
errors
log_path
```

## 非スコープ

今回の初期整備では、以下を実装しない。

- 実建物全カテゴリの自動収集
- Walls / Floors / Roofs の一括自動対象化
- 平均地盤面の自動算定
- Property Line 完全対応
- CADリンク境界自動認識
- 5m / 10m 測定線生成
- 日影計算ロジック
- 厳密な太陽位置計算
- 等時間線生成アルゴリズム
- 建築確認申請に提出できる図面品質の出力
- `script.py` の本格実装
- `Shadow.dyn` / `Shadow - Copy.json` の変更

## 関連資料

- 調査メモ: `docs/research_shadow_diagram.md`
- Revit入力モデル方針: `docs/revit_input_modeling_guide.md`
