# 日影図 Dynamoツール

## 動作環境

- Revit 2024.3
- Dynamo 3.3
- CPython3

## 実行方法

1. このフォルダ一式をPC上の任意の場所へコピーする
2. フォルダ内の `Shadow.dyn` をDynamo Playerから開く
3. 必要な入力を選択して実行する

## 解析モード

- `Forward Shadow / 順日影`: Buildingを選択し、従来の順日影計算を実行する。
- `Reverse Shadow / 逆日影`: Site Boundary、特定のShadow Limitsペア、Accuracy、平均地盤面Level、settings/緯度等から逆日影候補ボリュームを表示する。Buildingは使用しない。`All / 全候補`では生成できない。

順日影の精度は Fast = 1.0 m / 30分、Standard = 0.5 m / 15分、High = 0.25 m / 5分。逆日影はFastで4 m height grid / 4 m measurement / 30分、Standardで1 m height grid / 1 m measurement / 15分を使い、最終高さは0.5 m単位に安全側へ切り下げる。逆日影のHighは現在Standard相当であり、逆日影結果は必ず最終的な順日影で検証する。

Forward / Reverseともに、`Average Ground Level / 平均地盤面`で選択したRevit LevelのElevationをinternal unitsからmeterへ変換してAGLとして使う。Level自体は測定面ではなく、測定面はAGL + 規制presetのmeasurement heightである。Level未選択時のみsettingsのAGLを互換fallbackとして使い、選択済みLevelのElevationが読めない場合はsilent fallbackしない。

Forward / Reverseともに、日影方向はActive Project Locationに設定されたRevit標準のTrue Northを自動使用する。Project Northは作図方向、True Northは実際の地理上の北である。Playerに真北角度入力はないため、実行前にRevit側でTrue Northを正しく設定する。取得不能時は0°へsilent fallbackせずdiagnosticsへwarning/blockerを出す。緯度・経度は従来どおりPlayer入力を使用する。

## フォルダ名

このフォルダは「日影図」「日影検討ツール」などへ改名してよい。

ただし、次を同じフォルダ内に保つこと。

- `Shadow.dyn`
- `dynamo_loader.py`
- `script.py`
- すべての `shadow_*.py`

個々のPythonファイルを別フォルダへ移動しない。

## 注意

- 現在は社内試用／検証用
- 法的適合を保証しない
- 自治体条例を自動確定しない
- `permit_ready_certified=false`
- 出力は有資格者・担当者が確認する
- debug logを有効にすると、この配布フォルダ内の `debug_logs/latest_debug.json` に出力される（current working directoryには依存しない）
