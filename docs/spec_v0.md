# spec_v0: 等時間日影図検討の初期仕様

## 目的

Dynamo / Revit 上で概略設計段階の日影検討を進める前に、v0/v1 で扱う入力・出力・非スコープを明確にする。

このリポジトリは計算ロジックの完成版ではなく、建築確認申請レベルの正式判定は ADS 等の専用ツールで行う前提である。

## 入力候補

将来の実装では、次の入力を Dynamo 入力または設定プロファイルとして扱う想定とする。

- `building_elements`: 単一要素ではなく複数選択を前提とする shadow caster proxy elements。ユーザーが明示的に作成・選択した Mass / Generic Model を対象とする。
- `site_boundary`: optional な敷地境界。未入力でも等時間日影図の出力フローは継続可能で、敷地境界依存ステップだけを skip する。
- `level`: optional な参照入力。法規上の高さ基準ではなく、平均地盤面でもない。
- `settings.average_ground_level_elevation_m`: 法規上の高さ基準として扱う平均地盤面高さ。
- `settings.measurement_height_m`: 平均地盤面からの測定面高さ。
- 真北角度、緯度・経度、地域プロファイル、用途地域、日影規制種別、規制時間、グリッド解像度。

測定面は `average_ground_level_elevation_m + measurement_height_m` として扱う。Revit Level の Elevation を、そのまま平均地盤面や測定面高さとして扱わない。

## Shadow caster proxy 方針

建物本体、屋上塔屋、機械室、EV機械室、庇、キャノピー、設備基礎などは、必要に応じて別々の shadow caster として扱う。

- Mass は概略設計段階のボリュームスタディとして自然な入力である。
- Generic Model は実務上の作りやすさ、ファミリ管理、選択性の面で同等に許容する。
- カテゴリ判定は Revit API の `BuiltInCategory` を優先し、初期 accepted カテゴリは `BuiltInCategory.OST_Mass` と `BuiltInCategory.OST_GenericModel` とする。
- 表示名（Mass / Generic Models / マス / 一般モデルなど）は fallback としてのみ扱う。
- `ShadowRole` は補助診断であり、unsupported category を accepted にする代替条件ではない。
- `OST_MassForm`、`OST_MassFloor`、`OST_Massing`、その他 `OST_Mass...` 系は Mass 関連カテゴリとして診断し、初期 accepted カテゴリとして黙って受け入れない。
- どちらも、ユーザーが日影検討用外径として明示作成・選択したプロキシ要素のみを対象にする。
- 既存 Revit モデルの Walls / Floors / Roofs / 設備 / 小物などから外径を自動推定しない。
- BoundingBox を日影外形、影ポリゴン生成、日影判定に使わない。
- Revit上に一体化済みの一時モデルを作らない。

将来の計算では、各 caster ごとに影を投影し、同一時刻内の影は logical union として扱う。重なった影は二重加算しない。


## Site boundary 方針

`site_boundary` は optional input とする。site_boundary が無い場合でも fatal error にせず、等時間日影図の出力フローは継続可能とする。skip するのは Property Line / Site Boundary based offset、5m / 10m measurement line generation、boundary-based regulation reference check などの boundary-dependent steps だけであり、shadow caster geometry reading、time-slice shadow projection、logical union、shadow duration accumulation、equal-time shadow output は継続対象である。

site_boundary がある場合の第一候補は Revit Property Line / Site Property とし、Revit API `BuiltInCategory` による判定を優先する。primary accepted category は `BuiltInCategory.OST_SiteProperty` と `BuiltInCategory.OST_SitePropertyLineSegment` とする。`BuiltInCategory.OST_SitePointBoundary` は関連診断扱いであり、単独では閉じた境界線として扱わない。

Model Lines の閉じたループは fallback として許容するが、第一候補ではない。Detail Lines はビュー依存のため非推奨または rejected/warning とする。CAD import lines や Toposolid / SiteSurface / Topography 外周は、敷地境界として自動採用しない。Revit上に敷地境界用の一時モデルは作成しない。

v1 出力候補には `site_boundary` diagnostics、`site_boundary_policy`、`settings_normalized`、`settings_policy`、`pipeline_readiness` を追加する。今回PRでは入力診断と簡易 loop_diagnostics までとし、5m / 10m 測定線生成、日影計算、太陽位置計算、影ポリゴン生成、等時間線生成は非スコープとする。

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

## 出力候補

v1 入力診断で確認したい出力は以下とする。

```text
success
message
legal_constants
inputs
shadow_casters
shadow_caster_policy
site_boundary
site_boundary_policy
settings_normalized
settings_policy
pipeline_readiness
planned_pipeline
warnings
error
```

## planned_pipeline

BoundingBox summary 抽出を日影計算ロードマップの主工程にしない。将来の主工程は以下とする。

1. input diagnostics
2. shadow caster proxy validation
3. shadow caster geometry access check
4. optional site boundary source validation
5. property line / site property diagnostics when provided
6. model lines fallback closed-loop diagnostics when provided
7. settings coercion and normalization
8. measurement plane readiness check
9. pipeline readiness diagnostics
10. footprint extraction from user-defined shadow proxy geometry
11. optional site boundary loop extraction
12. optional 5m / 10m measurement line generation when site_boundary is available
13. sun vector calculation
14. time-slice shadow projection per caster
15. logical union of shadows per time slice
16. shadow duration accumulation without double counting
17. equal-time contour generation

## 非スコープ

今回の初期整備では、以下を実装しない。

- 実建物全カテゴリの自動収集
- Walls / Floors / Roofs の一括自動対象化または外径自動推定
- BoundingBox を使った日影外形、影ポリゴン、日影判定
- Revit上での一体化済み一時モデル作成
- 平均地盤面の自動算定
- Property Line / Site Property の完全な loop extraction と offset
- CADリンク境界自動認識または CAD lines の site_boundary 自動採用
- 5m / 10m 測定線生成
- 日影計算ロジック
- 厳密な太陽位置計算
- 影ポリゴン生成
- 等時間線生成アルゴリズム
- 建築確認申請に提出できる図面品質の出力

## 関連資料

- 調査メモ: `docs/research_shadow_diagram.md`
- Revit入力モデル方針: `docs/revit_input_modeling_guide.md`
- Settings schema: `docs/settings_schema_v1.md`
