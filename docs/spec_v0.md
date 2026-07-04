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

- 建物モデル要素
- 敷地境界
- 真北角度
- 緯度・経度
- 地域プロファイル
- 用途地域
- 日影規制種別
- 測定面高さ
- 規制時間
- グリッド解像度

## 固定値候補

法令や標準的な作図条件として固定しやすい値は、任意入力ではなくプロファイル化する。

```python
LEGAL_CONSTANTS = {
    "date_basis": "winter_solstice",
    "standard_start_time": "08:00",
    "standard_end_time": "16:00",
    "hokkaido_start_time": "09:00",
    "hokkaido_end_time": "15:00",
    "interval_minutes": 30,
    "measurement_line_near_m": 5.0,
    "measurement_line_far_m": 10.0,
}
```

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

- 日影計算ロジック
- 厳密な太陽位置計算
- 等時間線生成アルゴリズム
- 建築確認申請に提出できる図面品質の出力
- `script.py` の本格実装
- `Shadow.dyn` / `Shadow - Copy.json` の変更

## 関連資料

- 調査メモ: `docs/research_shadow_diagram.md`
