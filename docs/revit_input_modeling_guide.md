# Revit Input Modeling Guide for Dynamo_Shadow

## 1. Purpose

このドキュメントは、Dynamo_Shadow で概略設計段階の等時間日影図検討を進めるために、Revit側で用意する入力要素の方針を整理するものです。

このリポジトリは検討・開発段階であり、建築確認申請レベルの正式判定は ADS 等の専用ツールで行う前提です。

## 2. Current Dynamo input contract

`dynamo_loader.py` が `IN[]` を名前付き入力へ対応付ける前提で、Dynamo 入力契約は以下です。

- `building_elements = IN[0]`: 複数選択された shadow caster proxy elements。
- `site_boundary = IN[1]`: 敷地境界。
- `level = IN[2] if exists else None`: optional な作業参照。
- `settings = IN[3] if exists else None`: 平均地盤面、測定面高さ、緯度経度、真北角度、グリッド解像度など。

重要: `level` は法規上の高さ基準ではありません。Level Elevation を平均地盤面として扱わず、平均地盤面は `settings.average_ground_level_elevation_m` で扱います。

## 3. Height reference policy

日影計算の高さ基準は、Revit Level ではなく平均地盤面とします。

```text
measurement_plane_elevation = average_ground_level_elevation_m + measurement_height_m
```

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

v1では平均地盤面の自動算定は行わず、ユーザーが settings として入力します。

## 4. Shadow caster / 影を落とすプロキシ要素

`building_elements` は単一要素ではなく、複数選択を前提にします。対象は、ユーザーが日影検討用に明示的に作成・選択した Mass または Generic Model のプロキシ要素です。

Mass は概略設計段階のボリュームスタディとして自然です。Generic Model は実務上の作りやすさ、ファミリ管理、選択性の面で Mass と同等に許容します。Generic Model だけを唯一の第一候補とはしません。

建物本体、屋上塔屋、機械室、EV機械室、庇、キャノピー、設備基礎などは、必要に応じて別々の shadow caster proxy として作成・選択します。Dynamo_Shadow は各 caster を個別要素として読み、個別に診断する方針です。

推奨方針は以下です。

- Mass または Generic Model で、日影検討用の外径プロキシを明示的に作る。
- カテゴリ判定は Revit API の `BuiltInCategory` を優先し、初期 accepted カテゴリは `BuiltInCategory.OST_Mass` と `BuiltInCategory.OST_GenericModel` とする。
- 表示名（Mass / Generic Models / マス / 一般モデルなど）は fallback としてのみ扱う。
- ファミリ名、タイプ名、共有パラメータ `ShadowRole` などで日影計算対象だと分かるようにする。ただし `ShadowRole` は補助診断であり、unsupported category を accepted にしない。
- `OST_MassForm`、`OST_MassFloor`、`OST_Massing`、その他 `OST_Mass...` 系は Mass 関連カテゴリとして診断し、初期 accepted カテゴリとして黙って受け入れない。
- 既存 Revit モデルの Walls / Floors / Roofs / 設備 / 小物などから外径を自動推定しない。
- BoundingBox を日影外形、影ポリゴン生成、日影判定に使わない。
- Revit上に一体化済みの一時モデルを作らない。

将来の計算では、各 caster ごとに影を出し、同一時刻内の影は logical union として扱います。重なった影は二重加算しません。今回の段階では logical union の計算自体は実装しません。

## 5. Site boundary / 敷地境界

v1初期検証では、Model Lines の閉じたループを使うことを第一候補とします。Dynamoではその Model Lines を `site_boundary` として選択します。

将来対応候補は以下です。

- Property Lines
- CADリンク境界
- Floor境界
- Area Boundary
- Filled Region由来の境界

## 6. Level input

`level` は optional な作業参照です。法規上の高さ基準ではありません。

避けることは以下です。

- Level Elevation をそのまま平均地盤面として扱わない。
- Level に用途地域や測定面高さを埋め込まない。

## 7. What v1 should not do yet

v1では、以下をまだ行いません。

- 実建物全カテゴリの自動収集
- Walls / Floors / Roofs からの日影用外径の自動推定
- BoundingBox ベースの日影外形抽出、影ポリゴン生成、日影判定
- Revit上での一体化済み一時モデル作成
- 複雑なSolidブーリアン
- 平均地盤面の自動算定
- Property Line完全対応
- CADリンク境界自動認識
- 5m / 10m測定線生成
- 太陽位置計算
- 影ポリゴン生成
- 等時間線生成
- 建築確認申請品質の図面出力

## 8. Implementation roadmap

v1以降の実装順序は、以下を基本とします。

1. input diagnostics
2. shadow caster proxy validation
3. shadow caster geometry access check
4. site boundary curve diagnostics
5. settings normalization
6. footprint extraction from user-defined proxy geometry
7. time-slice shadow projection per caster
8. logical union of shadows per time slice
9. shadow duration accumulation without double counting
10. equal-time contour generation
