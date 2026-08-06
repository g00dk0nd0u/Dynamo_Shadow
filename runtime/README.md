# 日影図 Dynamoツール

## 動作環境

- Revit 2024.3
- Dynamo 3.3
- CPython3

## 実行方法

1. このフォルダ一式をPC上の任意の場所へコピーする
2. フォルダ内の `Shadow.dyn` をDynamo Playerから開く
3. 必要な入力を選択して実行する

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
