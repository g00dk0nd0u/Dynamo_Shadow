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

## 3. Settings and height reference policy

`settings = IN[3]` は optional input です。settings が未接続でも input diagnostics は fatal error にせず、`success` を維持します。

ただし、将来の等時間日影計算 readiness には settings が必要です。特に以下は、settings で明示入力してください。

- `average_ground_level_elevation_m`: 平均地盤面高さ。
- `measurement_height_m`: 平均地盤面からの測定面高さ。
- `latitude` / `longitude`: 将来の太陽方向計算に必要な緯度経度。
- `true_north_deg`: 将来の太陽方向計算に必要な真北角度。

Revit Level は作業参照であり、法規上の高さ基準ではありません。Level Elevation を平均地盤面として使わず、測定面としても使いません。

```text
measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m
```

`grid_resolution_m`、`analysis_margin_m`、`closure_tolerance_m` は計算用パラメータであり、安全な diagnostic default を持てます。一方、`average_ground_level_elevation_m` や `measurement_height_m` には法規・案件条件上の意味があるため、Dynamo_Shadow が勝手な default を与えません。

settings schema の詳細は `docs/settings_schema_v1.md` を参照してください。

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

## 5. Geometry extraction diagnostics

v1 shadow caster geometry extraction diagnostics では、ユーザーが明示的に作成・選択した Mass / Generic Model proxy から Solid / Face / Edge を読み取り専用で診断します。複数 caster は個別に読み、Revit 上で一体化した一時モデルは作成しません。

Mass / Generic Model 以外の Walls / Floors / Roofs / Equipment など既存モデル要素は、自動で shadow caster として抽出しません。

bottom face candidate は、将来の footprint extraction の候補として診断します。ただし今回の段階では footprint polygon、CurveLoop、2D 投影、offset、self-intersection 判定は作りません。top face candidate、vertical face candidate も診断候補であり、正式な幾何判定ではありません。

BoundingBox は diagnostic summary または future analysis extent estimation のみに使い、shadow geometry や shadow judgement には使いません。Revit geometry の座標単位は `revit_raw_internal_units` として扱い、正式な meters 変換は後続 PR で実装します。

詳細は `docs/geometry_extraction_v1.md` を参照してください。

## 6. Site boundary / 敷地境界

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

## 7. Level input

`level` は optional な作業参照です。法規上の高さ基準ではありません。

避けることは以下です。

- Level Elevation をそのまま平均地盤面として扱わない。
- Level に用途地域や測定面高さを埋め込まない。

## 8. What v1 should not do yet

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

## 9. Implementation roadmap

v1以降の実装順序は、以下を基本とします。

1. input diagnostics
2. shadow caster proxy validation
3. shadow caster geometry access check
4. shadow caster geometry extraction diagnostics
5. solid / face / edge summary
6. footprint candidate diagnostics
7. optional site boundary source validation
8. property line / site property diagnostics when provided
9. model lines fallback closed-loop diagnostics when provided
10. settings coercion and normalization
11. law56_2 awareness context diagnostics
12. measurement plane readiness check
13. measurement plane construction diagnostics
14. pipeline readiness diagnostics
15. footprint extraction from user-defined shadow proxy geometry
16. optional site boundary loop extraction
17. legal judgement mask preparation
18. optional 5m / 10m measurement line generation when site_boundary is available
19. true solar time diagnostics
20. sun vector calculation
21. time-slice shadow projection per caster
22. logical union of shadows per time slice
23. shadow duration accumulation without double counting
24. equal-time contour generation
25. legal judgement report

## Measurement plane input policy

The shadow measurement plane is not a Revit Level. It is the Article 56-2 horizontal plane at a designated height above average ground level:

```text
measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m
```

- Put `average_ground_level_elevation_m` in `settings`; do not use Revit Level Elevation as average ground level.
- Put `measurement_height_m` in `settings` as the ordinance / table-derived measurement height; do not let the script invent it.
- Mass / Generic Model shadow caster geometry remains raw Revit coordinates / raw internal units.
- The measurement plane is an abstract legal SI meters plane used for diagnostics, not a Revit element.
- Formal unit conversion between Revit raw geometry and legal SI meters is deferred to a later PR.
- site_boundary is not required to construct the measurement plane.
- If site_boundary is missing, future legal judgement ranges such as beyond-5m range and own-site exclusion are not constructed.

See `docs/measurement_plane_v1.md` for the detailed measurement plane diagnostics policy.

## Footprint extraction diagnostics guidance

For future footprint extraction, model shadow caster proxies as user-selected Mass or Generic Model elements with clear bottom faces. A simple, planar bottom face with readable edge loops will be easier to diagnose and to support in later PRs.

Avoid overly complex, curved, or self-intersecting proxy shapes where possible. This stage only diagnoses bottom face candidates, edge loop candidates, raw endpoint closure, and horizontal candidates. It does not create formal polygons, offsets, booleans, CurveLoops, shadow projections, 5m / 10m lines, or legal judgement outputs.

`site_boundary` is not required for footprint diagnostics. It will be needed later for own-site exclusion, beyond-5m ranges, target-area masks, and legal judgement masks. See [`footprint_extraction_v1.md`](footprint_extraction_v1.md).

## Roadmap order

1. input diagnostics
2. shadow caster proxy validation
3. shadow caster geometry access check
4. shadow caster geometry extraction diagnostics
5. solid / face / edge summary
6. footprint candidate diagnostics
7. footprint edge loop diagnostics
8. footprint extraction readiness diagnostics
9. optional site boundary source validation
10. property line / site property diagnostics when provided
11. model lines fallback closed-loop diagnostics when provided
12. settings coercion and normalization
13. law56_2 awareness context diagnostics
14. measurement plane readiness check
15. measurement plane construction diagnostics
16. pipeline readiness diagnostics
17. formal footprint polygon generation
18. optional site boundary loop extraction
19. legal judgement mask preparation
20. optional 5m / 10m measurement line generation when site_boundary is available
21. true solar time diagnostics
22. sun vector calculation
23. time-slice shadow projection per caster
24. logical union of shadows per time slice
25. shadow duration accumulation without double counting
26. equal-time contour generation
27. legal judgement report
