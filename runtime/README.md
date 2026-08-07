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
- `Reverse Shadow / 逆日影`: Site Boundary、特定のShadow Limitsペア、Accuracy、settings/緯度等から逆日影候補ボリュームを表示する。BuildingとLevelは使用しない。`All / 全候補`では生成できない。

Fast / Standardはモード別の解像度を使う。順日影は0.5 m / 30分と0.5 m / 15分、逆日影は4 m height grid / 30分と2 m height grid / 15分。逆日影結果は必ず最終的な順日影で検証する。

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
- 実行時に `debug_logs` フォルダが生成される場合がある
