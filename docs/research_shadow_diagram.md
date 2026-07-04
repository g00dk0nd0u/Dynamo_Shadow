# Research: 建築基準法の等時間日影図

## 目的

Dynamo / Revit 上で建築基準法の日影規制に使う等時間日影図を作る前に、法規・自治体解説・実務解説を整理する。

## 参照した主な情報源

- 建築ピボット / 構造システム「日影図と等時間日影図」  
  https://www.pivot.co.jp/post/regulation-shadowline.html
- 上岡祐介建築設計事務所「実務で役立つ日影計算の基本と確認申請の進め方」  
  https://a-kamioka.com/column/sky-factor/sunshade-calculation/
- 江戸川区「日影規制とはどのようなことですか？」  
  https://www.city.edogawa.tokyo.jp/e021/kurashi/sumai/sumai_tebiki/tatemono/3_4.html
- 大田区「日影規制」  
  https://www.city.ota.tokyo.jp/seikatsu/sumaimachinami/kenchiku/tatemono_tyuuikisei/hikagekisei.html
- e-Gov 法令検索 / 建築基準法 第56条の2・別表第四  
  https://laws.e-gov.go.jp/

## 重要な理解

### 1. 時刻日影図と等時間日影図は別物

時刻日影図は、冬至日の各時刻における影の形状を測定面上に描く図である。
通常は標準地域で 8:00〜16:00、北海道等では 9:00〜15:00 を対象にし、30分または1時間ごとに作図する。

ただし、時刻日影図だけでは日影規制への適合判定はできない。
日影規制は「ある時刻に影が落ちるか」ではなく、「一定時間以上の日影を生じさせない」総量規制である。

### 2. 等時間日影図が適合判定の本体

等時間日影図は、測定面上で日影時間が等しい地点を結んだ等時間線を描く図である。
確認申請用では、都市計画図・条例で指定された規制時間の等時間線を作成する。

例:

- 5m〜10m の範囲: 5時間
- 10m超の範囲: 3時間

この場合、5時間線が5m測定線の内側、3時間線が10m測定線の内側に収まれば、原則として規制適合と判断する。

### 3. 法規上固定できるもの

以下はユーザー入力にせず、法規プロファイルとして固定値にする。

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

注: 30分刻みは、時刻日影線を作るための固定仕様として扱う。将来的に1時間刻み対応を入れる場合も、任意入力ではなく `calculation_profile` として切り替える。

### 4. プロジェクトごとに変わる入力

以下は都市計画図・敷地条件・プロジェクト条件で変わるため、Dynamo入力または設定プロファイルで扱う。

- 建物モデル要素
- 敷地境界
- 真北角度
- 緯度・経度
- 地域プロファイル: 標準地域 / 北海道等
- 用途地域
- 日影規制種別: 一 / 二 / 三
- 測定面高さ: 1.5m / 4m / 6.5m
- 規制時間: 5m〜10m、10m超
- 道路・水面緩和
- 高低差緩和
- 複数用途地域をまたぐ場合の扱い
- グリッド解像度

### 5. 作図・計算の基本フロー

```text
1. 敷地・用途地域・規制条件を整理する
2. 真北角度、緯度・経度、冬至日、測定面高さを設定する
3. 5m・10m測定線を敷地境界から作成する
4. 8:00〜16:00 を30分ごとに分割する
5. 各時刻の太陽高度・太陽方位を求める
6. 建物形状を測定面へ投影して、各時刻の影ポリゴンを作る
7. 測定面上の各点・グリッドセルで、影に入った時間を累積する
8. 影時間 = 影に入ったステップ数 × 0.5h とする
9. 規制時間に対応する等時間線を生成する
10. 等時間線と5m・10m測定線の位置関係で適合を判定する
```

### 6. 実装上の注意

- `time_shadow_lines` は中間成果物。
- 最終成果物は `equal_time_shadow_lines`。
- 単に30分ごとの影ポリゴンを重ねるだけでは不足。
- 必ず測定面上で累積日影時間を計算する。
- 複雑形状では「島日影」があり得る。
- 等時間線には誤差が含まれるため、v0では申請図品質を目標にしない。
- v0ではグリッド法で診断可能にし、将来的に polygon overlay / marching squares / 日影チャート検算に進める。

## v0で実装する範囲

v0は、いきなり申請図を作らず、次を安定化する。

- Dynamo入力の読み取り
- 建物要素のBBox取得
- 敷地境界BBox取得
- 法規固定値の出力
- 8:00〜16:00、30分刻みの時刻リスト生成
- 仮太陽ベクトルの生成
- 仮影ポリゴンの生成
- グリッド点ごとの影回数カウント
- `Shadow_log.txt` 出力

## OUTの想定

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

## 当面の非スコープ

- 確認申請に提出できる最終図面品質
- 厳密な太陽位置計算の完全実装
- 道路・水面緩和の完全自動判定
- 高低差緩和の完全自動判定
- 複数用途地域の厳密自動判定
- 日影チャートによる誤差ゼロ検算
