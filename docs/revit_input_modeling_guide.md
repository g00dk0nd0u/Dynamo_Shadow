# Revit Input Modeling Guide for Dynamo_Shadow

## 1. Purpose

このドキュメントは、Dynamo_Shadow で等時間日影図の検討を進めるために、Revit側でどのような要素、ファミリ、入力を用意するべきかを整理するものです。

このリポジトリは検討・開発段階であり、建築確認申請にそのまま使える完成ツールではありません。

このドキュメントは、最終的な唯一のRevit運用ルールではなく、v1初期検証を安定して進めるための推奨入力モデル方針です。

## 2. Current Dynamo input contract

現在の Dynamo 入力契約は、`dynamo_loader.py` が `IN[]` を名前付き入力へ対応付ける前提で、次のように扱います。

- `building_elements = IN[0]`
- `site_boundary = IN[1]`
- `level = IN[2] if exists else None`
- `settings = IN[3] if exists else None`

各入力の役割は以下です。

- `building_elements`: 影を落とす建物要素。
- `site_boundary`: 敷地境界。
- `level`: optional な作業参照。ビュー整理、モデル整理、デバッグ補助に使う可能性はあります。
- `settings`: 平均地盤面、測定面高さ、緯度経度、真北角度、グリッド解像度などを持つ条件入力。

重要: `level` は法規上の高さ基準ではありません。

## 3. Height reference policy

日影計算の高さ基準は、Revit Level ではなく平均地盤面とします。

測定面高さは、次の関係で扱います。

```text
measurement_plane_elevation = average_ground_level + measurement_height_m
```

方針は以下です。

- 日影計算の高さ基準は Revit Level ではなく平均地盤面とする。
- 測定面高さは `average_ground_level + measurement_height_m` として扱う。
- Revit Level は作業参照、ビュー整理、入力補助として使う可能性はある。
- ただし Revit Level を法規上の高さ基準そのものにはしない。
- 平均地盤面の算定結果は、v1ではユーザーが `settings` として入力する。
- 傾斜地などの平均地盤面自動算定は将来タスクで扱い、v1では実装しない。

初期 `settings` 案は以下です。

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

各キーの意味は以下です。

- `profile`: 標準時刻帯や法規条件をまとめるプロファイル名。
- `average_ground_level_elevation_m`: Revit内部座標またはプロジェクト基準に対する平均地盤面高さ。
- `measurement_height_m`: 平均地盤面からの測定面高さ。
- `latitude`: 緯度。
- `longitude`: 経度。
- `true_north_deg`: Revitプロジェクト北と真北の差分。
- `grid_resolution_m`: 測定グリッド解像度。

## 4. Shadow caster / 影を落とす建物要素

v1初期検証では、専用の簡易プロキシ要素を使うことを第一候補とします。カテゴリは Generic Models を第一候補にします。

ただし、Generic Models が唯一のベストプラクティスまたは唯一の正解という意味ではありません。v1初期検証で安定した入力を作るための第一候補であり、将来は Mass、実モデルカテゴリ収集、Property Lines、CAD境界などへ拡張できる設計にします。

推奨する作り方は以下です。

- 単純な箱形状、押出形状、または簡易マスとして作る。
- ファミリ名、タイプ名、共有パラメータで日影計算対象だと分かるようにする。
- 実建物モデルそのものをいきなり全カテゴリ対象にしない。

推奨ファミリ案は以下です。

### SHD_Caster_Box.rfa

- Category: Generic Models
- Purpose: Rectangular shadow caster proxy
- Parameters:
  - `Width`
  - `Depth`
  - `Height`
  - `Base Offset`
  - `ShadowRole = Caster`

### SHD_Caster_SimpleMass.rfa

- Category: Generic Models
- Purpose: Simplified irregular building mass or tower volume
- Parameters:
  - `Height`
  - `Base Offset`
  - `ShadowRole = Caster`

理由は以下です。

- Walls、Floors、Roofs を全自動収集すると、庇、手すり、内装、設備、不要な小物を拾いやすい。
- Mass は概念検討には有効だが、案件ごとの運用差が出やすい。
- Generic Models の単純なプロキシは、選択、表示制御、フィルタ、BoundingBox抽出がしやすい。
- v1ではまずBoundingBox抽出で検証するため、簡易形状の方が安全。

v1での扱いは以下です。

- `building_elements` として選択された Generic Model proxy から BoundingBox を読む。
- Solid抽出や複雑形状対応は次段階とする。
- 自動カテゴリ収集はまだ行わない。

## 5. Site boundary / 敷地境界

v1初期検証では、Model Lines の閉じたループを使うことを第一候補とします。専用 Line Style を作り、例として `SHD_SITE_BOUNDARY` を使います。Dynamoではその Model Lines を `site_boundary` として選択します。

ただし、Model Lines が最終的な唯一の方式または唯一の正解という意味ではありません。v1初期検証で扱いやすい第一候補であり、将来は Property Lines、CADリンク境界、Floor境界、Area Boundary などへ拡張できる設計にします。

理由は以下です。

- Detail Lines はビュー依存なので初期入力としては避ける。
- Property Lines は正攻法だが、案件ごとに作成方法が揺れやすい。
- Model Lines は3D座標を持ち、Dynamo / Revit APIからCurveとして扱いやすい。
- 初期検証では、閉じたループを作りやすくデバッグしやすい。

v1での扱いは以下です。

- 選択されたModel LinesからCurveを読む。
- XY平面上のPolylineに変換する。
- 閉じたループかどうかを診断する。
- 5m / 10m測定線の生成はまだ行わない。

将来対応候補は以下です。

- Property Lines
- CADリンク境界
- Floor境界
- Area Boundary
- Filled Region由来の境界

## 6. Level input

`level` は optional な入力です。法規上の高さ基準ではありません。

方針は以下です。

- `level` は optional とする。
- 法規上の高さ基準ではない。
- 作業参照、モデル整理、デバッグ補助として扱う。
- 測定面高さは Level ではなく `settings` の `average_ground_level_elevation_m` と `measurement_height_m` から決める。

避けることは以下です。

- Level Elevation をそのまま平均地盤面として扱わない。
- Level に用途地域や測定面高さを埋め込まない。

## 7. Settings input

`settings` は、法規プロファイル、敷地条件、計算解像度をまとめる入力とします。

初期キーは以下です。

- `profile`
- `average_ground_level_elevation_m`
- `measurement_height_m`
- `latitude`
- `longitude`
- `true_north_deg`
- `grid_resolution_m`

方針は以下です。

- 法規上固定できる値は任意入力にしない。
- 地域、用途地域、敷地ごとに変わる値は `settings` または将来の `profile` で管理する。
- 初期キーはv1のたたき台であり、将来変更・拡張できる設計にする。
- 将来は `shadow_config.json` も検討するが、v1ではDynamo入力の `settings` を優先する。

## 8. Recommended initial Revit setup

初期検証用のRevitモデル作成手順は以下です。

1. Generic Model の簡易建物プロキシを配置する。
2. ファミリ名またはタイプ名を `SHD_Caster_...` とする。
3. Model Linesで敷地境界を閉じたループとして作成する。
4. Line Styleを `SHD_SITE_BOUNDARY` とする。
5. Dynamoで `building_elements` に建物プロキシを選択する。
6. Dynamoで `site_boundary` に敷地境界Model Linesを選択する。
7. `settings` に平均地盤面、測定面高さ、緯度経度、真北角度、グリッド解像度を渡す。
8. Levelは必要な場合だけ参照入力として渡す。

## 9. What v1 should not do yet

v1では、以下をまだ行いません。

- 実建物全カテゴリの自動収集
- Walls / Floors / Roofs の一括自動対象化
- 複雑なSolidブーリアン
- 平均地盤面の自動算定
- Property Line完全対応
- CADリンク境界自動認識
- 5m / 10m測定線生成
- 太陽位置計算
- 等時間線生成
- 建築確認申請品質の図面出力

## 10. Implementation roadmap

v1以降の実装順序は、以下を基本とします。

1. Revit入力モデル方針docs化
2. `building_elements` から bbox summary 抽出
3. `site_boundary` から2D閉ループ抽出
4. `settings` 正規化
5. 冬至日・標準時刻リスト生成
6. 簡易太陽方向計算
7. bboxベースの簡易影ポリゴン生成
8. 測定グリッド上で影時間を累積
9. 等時間線生成
