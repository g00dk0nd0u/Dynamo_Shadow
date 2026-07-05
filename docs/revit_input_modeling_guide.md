# Revit Input Modeling Guide for Dynamo_Shadow

## 1. Purpose

このドキュメントは、Dynamo_Shadow で概略設計段階の等時間日影図検討を進めるために、Revit側で用意する入力要素の方針を整理するものです。

このリポジトリは検討・開発段階であり、建築確認申請レベルの正式判定は ADS 等の専用ツールで行う前提です。

## 2. Current Dynamo input contract

`dynamo_loader.py` が `IN[]` を名前付き入力へ対応付ける前提で、Dynamo 入力契約は以下です。

- `building_elements = IN[0]`: 複数選択された shadow caster proxy elements。
- `site_boundary = IN[1]`: optional な敷地境界。未選択でも等時間日影出力フローは継続し、敷地境界依存ステップだけを skip する。
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

`site_boundary = IN[1]` は optional input です。敷地境界に基づく 5m / 10m 測定線生成や境界ベースの法規判定には必要ですが、等時間日影図そのものの出力フローを開始するための必須入力ではありません。

site_boundary が未選択または空の場合でも、Dynamo_Shadow は fatal error にせず、等時間日影出力に向けた単一 pipeline を継続できる設計とします。この場合に skip するのは、敷地境界依存ステップだけです。

skip される boundary-dependent steps は以下です。

- Property Line / Site Boundary based offset
- 5m / 10m 測定線生成
- 境界ベースの法規参照・判定

skip しない non-boundary-dependent steps は以下です。

- shadow caster geometry reading
- time-slice shadow projection
- logical union
- shadow duration accumulation
- equal-time shadow output

site_boundary がある場合の第一候補は Revit Property Line / Site Property です。Revit API 判定では `BuiltInCategory.OST_SiteProperty` と `BuiltInCategory.OST_SitePropertyLineSegment` を primary accepted category とします。`BuiltInCategory.OST_SitePointBoundary` は関連要素として診断しますが、点だけでは閉じた境界線として扱わず、単独では loop extraction に進めません。

Model Lines の閉じたループは fallback として許容します。Dynamo graph の site_boundary 入力は複数選択対応とし、Property Line 全体、Property Line segments、または fallback の Model Lines 複数本を選択できるようにします。ただし Model Lines は第一候補ではありません。

Detail Lines はビュー依存のため site_boundary 入力として非推奨です。CAD import lines は自動で site_boundary として採用しません。Toposolid / SiteSurface / Topography の外周も敷地境界そのものとして自動採用しません。必要な場合は、ユーザーが Revit Property Line / Site Property、または fallback の閉じた Model Lines loop として明示的に用意してください。

この段階では入力診断のみを行います。境界オフセット、5m / 10m 測定線生成、日影計算、太陽位置計算、影ポリゴン生成、等時間線生成は将来工程です。

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
4. optional site boundary source validation
5. property line / site property diagnostics when provided
6. model lines fallback closed-loop diagnostics when provided
7. settings normalization
8. footprint extraction from user-defined shadow proxy geometry
9. optional site boundary loop extraction
10. optional 5m / 10m measurement line generation when site_boundary is available
11. time-slice shadow projection per caster
12. logical union of shadows per time slice
13. shadow duration accumulation without double counting
14. equal-time contour generation
