# Measurement plane v1 diagnostics

## 目的

v1 measurement plane diagnostics は、建築基準法56条の2の日影時間評価で参照する「平均地盤面から指定高さの水平面」を、Revit 要素ではなく Python dict の内部診断データとして安全に構築するための仕様です。

この段階では日影計算本体は実装しません。

## 建築基準法56条の2 awareness

このリポジトリでは、法56条の2に関係する次の要素を awareness / policy / future requirements として扱います。

- 冬至日
- 真太陽時
- 標準の午前8時から午後4時までの時間帯
- 道の区域内に関する午前9時から午後3時までの時間帯
- 平均地盤面から指定高さの水平面
- 敷地境界線から水平距離5mを超える範囲
- 対象区域外、自己敷地内、高層住居誘導地区、都市再生特別地区などの除外
- 条例・別表に依存する測定面高さと許容日影時間
- 同一敷地内の複数建築物を一の建築物とみなす考え方
- 道路、川、海、著しい高低差などの緩和は政令側の扱い

正式な許認可レベルの判定は ADS などの専用ツールで行う前提です。

## Measurement plane definition

measurement plane は、平均地盤面から指定高さの水平面です。

```text
measurement_plane_elevation_m = average_ground_level_elevation_m + measurement_height_m
```

- `average_ground_level_elevation_m` は settings から明示入力します。
- `measurement_height_m` は建築基準法56条の2および条例・別表由来の値として settings から明示入力します。
- `measurement_height_m` はこのツールが推測・発明しません。

## Revit Level ではない

- Revit Level Elevation は平均地盤面ではありません。
- Revit Level Elevation は測定面ではありません。
- Level が入力されても、measurement plane の代替値として使いません。

## Internal diagnostic data only

measurement plane は Revit 要素ではありません。

- DirectShape、ModelCurve、FilledRegion、デバッグ面、デバッグ線は作成しません。
- Revit ドキュメントへの書き込みは行いません。
- `coordinate_system` は `legal_si_meters` です。
- 原点は診断用の抽象 SI 座標であり、Revit 点ではありません。

## Geometry relation caution

Mass / Generic Model から読む geometry は Revit の `raw_internal_units` です。一方、measurement plane は法規上の SI meters の抽象平面です。

この PR では正式な Revit unit conversion を実装しません。そのため raw Z と `measurement_plane_elevation_m` の関係診断は placeholder diagnostic only です。

- formal intersection ではありません。
- formal legal judgement ではありません。
- shadow geometry 判定ではありません。
- 日影投影には使いません。

## Future masks and judgement

次は将来の mask / judgement として分離します。

- 敷地境界線から5mを超える範囲
- 敷地内除外
- 対象区域外除外
- 高層住居誘導地区除外
- 都市再生特別地区除外
- 道路・川・海・高低差などの緩和
- 区域またぎ判定
- 条例による許容日影時間

site_boundary が無くても measurement plane は構築できます。ただし site_boundary は将来の beyond-5m range、own-site exclusion、boundary-dependent legal judgement masks に必要です。

## Not implemented in this PR

この PR では以下を実装しません。

- 真太陽時計算
- 太陽位置計算 / sun vector calculation
- 影投影
- shadow polygon generation
- footprint polygon generation
- 測定グリッド累積
- 5m / 10m 測定線生成
- 等時間線生成
- 法規 OK / NG 判定
- Revit 要素作成
