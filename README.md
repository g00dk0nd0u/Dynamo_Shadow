# Dynamo Shadow

Dynamo / Revit 上で、建築基準法の日影規制に関する等時間日影図の検討を進めるための実験リポジトリです。

## 現在の位置づけ

このリポジトリは初期整備段階です。現時点では、申請図として利用できる日影計算ロジックは実装していません。

- 調査メモ: `docs/research_shadow_diagram.md`
- v0 仕様メモ: `docs/spec_v0.md`
- 既存 Dynamo / Revit 関連ファイル: `Shadow.dyn`, `Shadow - Copy.json`, `Shadow.html`, `script.py`

## 開発方針

- Codex Cloud で安全に作業できるよう、生成物やバックアップを Git 管理から除外します。
- 変更は小さく保ち、Dynamo / Revit の既存ファイルを不用意に変更しません。
- 日影計算ロジックは、仕様と検証方針を固めてから段階的に実装します。

## 生成ファイルの扱い

以下のようなファイルは Git 管理対象外です。

- `logs/`, `output/`, `backup/`, `backups/`
- `*.log`, `*_log.txt`
- Python キャッシュや仮想環境
- OS / エディタ由来の一時ファイル

## 注意

このリポジトリの内容は検討・開発用です。建築確認申請や法適合判定に使う場合は、法令・自治体条例・審査機関の要件を必ず確認してください。
