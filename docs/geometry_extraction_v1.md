# Geometry Extraction v1 Diagnostics

## 目的

このドキュメントは、将来の等時間日影計算に向けた v1 shadow caster geometry extraction diagnostics の範囲を定義します。今回の段階では Revit geometry を読み取り専用で診断し、日影計算本体は実装しません。

## 対象

対象は、ユーザーが明示的に選択した Mass / Generic Model の shadow caster proxy elements です。Walls、Floors、Roofs、Equipment、その他既存モデル要素から日影用外形を自動抽出しません。

複数 caster は個別に読み、Revit 上で一体化した一時モデルを作成しません。

## 診断する geometry

Mass / Generic Model proxy から安全に読み取れる範囲で、以下を診断します。

- Solid 件数、体積、表面積、Face / Edge 数
- Face 件数、面積、PlanarFace 候補、法線、原点、EdgeLoop / Edge 数
- Edge / Curve 件数、長さ、端点、水平候補
- Mesh 件数

Revit API が利用できない通常 Python 環境や、geometry が読めない要素でも fatal error にせず、warning と readiness blocker として扱います。

## Face candidate の考え方

Face normal が安全に読める場合だけ、診断候補として分類します。

- Z 成分が `+0.9` 以上: `top_face_candidate`
- Z 成分が `-0.9` 以下: `bottom_face_candidate`
- `abs(Z)` が `0.1` 以下: `side_face_candidate` / vertical face candidate
- それ以外: sloped or unknown

これは正式な幾何判定ではなく、次 PR 以降で footprint extraction に進むための候補診断です。

## Footprint candidate

bottom face candidate がある場合、将来の footprint extraction 候補として数えます。ただし今回 PR では以下を行いません。

- footprint polygon generation
- CurveLoop 生成
- 2D 投影
- offset
- self-intersection 判定
- footprint 精度保証

## BoundingBox の扱い

BoundingBox は diagnostic summary または future analysis extent estimation のみに使用できます。BoundingBox を shadow geometry、shadow polygon generation、shadow judgement に使用しません。

## Measurement plane relation

`settings_normalized.measurement_plane.available` が True の場合だけ、caster の BoundingBox diagnostic または face origin raw Z と `measurement_plane_elevation_m` の関係を raw diagnostic として診断します。

Revit geometry 座標は `revit_raw_internal_units` として扱い、meters への正式単位変換はこの PR では未実装です。そのため relation は厳密な交差判定ではなく、将来実装前の概略診断です。

## 非スコープ

今回 PR では以下を実装しません。

- 日影計算
- 太陽位置計算 / sun vector calculation
- shadow polygon generation
- time-slice shadow projection
- logical union 実処理
- shadow duration accumulation
- measurement grid accumulation
- 5m / 10m measurement line generation
- equal-time contour generation
- Revit element creation

## Measurement plane relation diagnostics

- Geometry Z values reported by v1 diagnostics are Revit `raw_internal_units`.
- The measurement plane elevation is reported in meters as an Article 56-2 legal SI diagnostic plane.
- Formal Revit unit conversion is not implemented in this PR.
- Any raw Z relation to `measurement_plane_elevation_m` is a placeholder diagnostic only.
- Raw relation diagnostics are not formal intersections, not legal judgement, and not shadow geometry decisions.
- Even when measurement plane construction succeeds, this PR does not perform footprint polygon generation, true solar time, sun vector calculation, shadow projection, duration accumulation, or equal-time contour generation.
