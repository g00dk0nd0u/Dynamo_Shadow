# settings_schema_v1

## Purpose

`settings` は、将来の等時間日影計算へ進む前提条件を安全に診断するための optional input です。平均地盤面、測定面高さ、緯度経度、真北角度、グリッド解像度、解析余白などを管理します。

この v1 schema は入力を辞書化・型変換・単位方針確認・不足診断するためのものであり、今回PRでは日影計算、太陽位置計算、影ポリゴン生成、測定グリッド累積、5m/10m測定線生成、等時間線生成は実装しません。

## Optional input and readiness

`settings` は input diagnostics では optional です。未入力でも fatal error にはせず、`success` は維持します。

ただし、将来の equal-time shadow calculation readiness には、以下のキーが明示入力されている必要があります。

- `average_ground_level_elevation_m`
- `measurement_height_m`
- `latitude`
- `longitude`
- `true_north_deg`

これらは法規上または案件条件として重要な値であり、Dynamo_Shadow が勝手に推定したり default を与えたりしません。

## Units

settings の単位は原則 SI 単位です。

- length: meter
- angle: degree
- latitude / longitude: decimal_degree

Revit internal unit 変換は、この v1 schema では扱いません。

## Height reference policy

Revit Level Elevation は平均地盤面として使いません。Revit Level Elevation は測定面としても使いません。

平均地盤面は `settings.average_ground_level_elevation_m` として明示入力します。測定面高さは `settings.measurement_height_m` として明示入力します。

測定面標高は以下の式で診断出力します。

`measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m`

## Diagnostic defaults

以下の計算用パラメータだけは、安全な diagnostic default を持ちます。

- `profile = standard_8_16`
- `grid_resolution_m = 1.0`
- `analysis_margin_m = 20.0`
- `closure_tolerance_m = 0.01`

## Keys without defaults

以下には default を与えません。

- `average_ground_level_elevation_m`
- `measurement_height_m`
- `latitude`
- `longitude`
- `true_north_deg`

## Accepted input formats

settings は以下の入力形式を受ける方針です。

- Python dict
- JSON string
- list / tuple of key-value pairs
- .NET Dictionary 風オブジェクト
- `Keys` / `Values` を持つ Dynamo dictionary 風オブジェクト

JSON parse や dict 化に失敗しても fatal error にはせず、空 settings として扱い warning を返します。

## Example

  settings example:
    profile: standard_8_16
    average_ground_level_elevation_m: 0.0
    measurement_height_m: 4.0
    latitude: 35.6812
    longitude: 139.7671
    true_north_deg: 0.0
    grid_resolution_m: 1.0
    analysis_margin_m: 20.0

## Measurement plane and Article 56-2 awareness

- `measurement_height_m` is treated as the Article 56-2 / ordinance table measurement-plane height and must be explicitly supplied through settings; the script does not invent a legal default.
- When both `average_ground_level_elevation_m` and `measurement_height_m` are valid, measurement plane construction diagnostics can build `measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m`.
- Revit Level Elevation is not used as average ground level and is not used as the measurement plane.
- `settings.profile` may be used for time-window awareness. `standard_8_16` is diagnostic awareness for the 08:00-16:00 profile, and `hokkaido_9_15` / `hokkaido` is diagnostic awareness for the 09:00-15:00 profile.
- These profile values do not implement true solar time calculation, JST clock-time conversion, sun vectors, shadow projection, or legal judgement.
- Future legal judgement will require inputs such as `ordinance_profile`, target-area status, applicable building threshold, allowed shadow duration profile, site boundary, own-site boundary, exclusion masks, relaxation profiles, true-solar-time profile, and same-site building grouping.

## Development debug log settings

The following development-only settings are accepted for sanitized review logs:

- `debug_log_enabled`: boolean, default `false`. Safe string / numeric values such as `"true"`, `"false"`, `1`, and `0` are accepted.
- `debug_log_dir`: optional relative directory, default `debug_logs`. Absolute paths and paths containing `..` are rejected with a warning and fall back to `debug_logs`.
- `debug_log_filename`: optional fixed JSON filename, default `latest_debug.json`. Filenames containing `/`, `\\`, `..`, or growth/private prefixes such as `run_`, `raw_`, or `private_` are rejected with a warning and fall back to `latest_debug.json`.

Debug logging is disabled by default, uses fixed filename overwrite behavior, and write failures are non-fatal diagnostics warnings only.
