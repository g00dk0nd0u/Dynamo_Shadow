# Dynamo Shadow

Dynamo Shadow は、Autodesk Revit / Dynamo 上で、日本の建築基準法第56条の2に関連する日影検討ワークフローを研究・検証するための公開技術プロトタイプです。

Forward Shadow（日影計算）と、低層建物向けの Reverse Shadow（初期ボリューム検討）を、1つの Dynamo Player ワークフローで扱います。計算ロジック、検証状況、制約を公開し、第三者が技術的に確認・再現できることを重視しています。

> **Technical Preview / 技術プレビュー**
>
> Dynamo Shadow は現在、研究・設計検討・技術検証を目的とした Technical Preview です。
> 確認申請用の認証済み計算ソフトではなく、法的な適否判定を行う製品でもありません。
> `permit_ready_certified=false`

## English Summary

Dynamo Shadow is an open technical preview for exploring Japanese Building Standard Law Article 56-2 shadow-study workflows inside Autodesk Revit and Dynamo. It provides experimental Forward Shadow and low-rise Reverse Shadow workflows with transparent calculation logic and reproducible diagnostics. It is intended for research, design exploration, technical review, and validation, and is not a permit-ready certified calculation product.

### Development-only compiled smoke package

A minimal, read-only Revit 2025/2026 development command can now be packaged for
later manual testing. This is not a production add-in and has not been validated
on a real Revit machine. Host-neutral CI remains Autodesk-free:

```powershell
dotnet build product/revit/RevitShadow.csproj --configuration Release
```

With `EnableRevitApi=true`, `RevitShadow.csproj` selects `net8.0-windows` for
the current Revit 2025/2026 smoke build. Reference the Autodesk DLLs installed
with the Revit version being tested:

```powershell
dotnet build product/revit/RevitShadow.csproj --configuration Release -p:EnableRevitApi=true -p:RevitApiDir="C:\path\to\Revit"
```

To create `RevitShadow.dll`, `ShadowCore.dll`, and a path-resolved
`RevitShadow.addin` without installing them, run:

```powershell
product/revit/build-smoke-package.ps1 -RevitApiDir "C:\path\to\Revit" -RevitYear 2025
```

See [`product/revit/README.md`](product/revit/README.md) for package layout and
later manual installation steps. `permit_ready_certified=false` remains
unchanged.

## このプロジェクトの目的

このリポジトリは、次のことを検証するために公開しています。

- Revit モデルから、日影検討に必要な形状・平均地盤面・True North を直接取得して計算できるか。
- 日影計算のロジックをブラックボックス化せず、第三者がコードと診断情報を確認できる形にできるか。
- Dynamo / Python を Revit 実機検証用の reference implementation として使い、将来の Revit add-in 化に耐えられる仕様を固められるか。
- Forward と Reverse を同一の入力・座標・精度 contract の上で扱えるか。

既存の商用日影計算ソフトを置き換えることや、現段階で確認申請用途を保証することを目的としていません。

## 現在できること

### Forward Shadow / 日影計算

- Revit の Mass / Generic Model を shadow caster として使用。
- Revit Area を Site Boundary として使用。
- Revit Level を Average Ground Level / 平均地盤面として使用。
- Revit Active Project Location から True North を自動取得。
- 真太陽時を基準とした太陽位置計算。
- 時刻ごとの formal shadow projection。
- 時刻ごとの Revit-native union。
- 空間グリッドと台形則による日影時間の累積。
- 等時間日影線の生成と DirectShape preview。
- 敷地境界から 5 m / 10 m の距離帯を扱う診断処理。
- 近側 / 遠側の最大日影時間と代表点の出力。
- Fast / Standard / High の精度プリセット。

### Reverse Shadow / 逆日影

- 低層建物の初期ボリューム検討用の conservative な Reverse Shadow。
- Forward と同じ Site Boundary / Average Ground Level / True North contract を使用。
- 時刻・空間を離散化した制約から height field を作成し、Revit に tessellated candidate volume を表示。
- Reverse の結果は「唯一の最大建築可能ボリューム」ではありません。
- 最終確認には必ず Forward Shadow による再検証が必要です。

## Quick Start / 最短の使い方

### 確認済みソフトウェア環境

- Autodesk Revit 2024.3
- Dynamo 3.3
- CPython3
- Windows（Revit がサポートする環境）

現時点では installer や production Revit add-in はありません。開発用 smoke-test command のみ package 化できます。

### 実行方法

1. リポジトリを取得します。
2. `runtime/` フォルダをローカルへコピーします。
3. Revit モデルを開きます。
4. Dynamo Player から `runtime/Shadow.dyn` を開きます。
5. 必要な Player input を設定します。
6. Revit の Project Location / True North が正しく設定されていることを確認します。
7. `Run` を実行します。

`runtime/` はそのまま配布可能な runtime bundle です。`Shadow.dyn`、loader、script、`shadow_*.py` を同じフォルダに保ってください。

## Dynamo Player Inputs

| Input | 入力内容 | 用途 / 注意 |
|---|---|---|
| `Site Boundary Area / 敷地境界エリア` | 配置済み Revit Area を1つ選択 | 現在の正式な敷地境界入力。Area Boundary line そのものではありません。 |
| `Building Model / 建物モデル` | Mass / Generic Model | Forward の shadow caster。Reverse では現在使用しません。 |
| `Shadow Limits / 日影規制時間` | 候補 preset | 適用する規制区分は自治体条例等で利用者が確認する必要があります。 |
| `Average Ground Level / 平均地盤面` | Revit Level | Level Elevation を共通 AGL source として使用します。 |
| `Calculation Accuracy / 計算精度` | Fast / Standard / High | 空間分解能と時間刻みを変更します。 |
| `Analysis Mode / 解析モード` | Forward / Reverse | Forward Shadow または Reverse Shadow を選択します。 |
| `Site Latitude / 緯度` | 緯度（度） | Player 入力。 |
| `Site Longitude / 経度` | 経度（度） | Player 入力。真太陽時モードでは longitude が直接結果を変えない場合があります。 |

True North の手入力はありません。Revit の Active Project Location を source of truth として自動取得します。

## Revit 側で準備するもの

### Average Ground Level / 平均地盤面

Forward / Reverse ともに、選択した Revit Level の Elevation を平均地盤面として使用します。Revit internal units から meter へ変換した値が Shadow Core に渡されます。

測定面は Level 自体ではなく、

`measurement plane = average ground level + measurement height`

です。

### Project North / True North

Project North は作図上の基準方向、True North は実際の地理上の北です。Dynamo Shadow は日影方向の計算に True North を使用します。

Revit Runtime では、Active Project Location の `ProjectPosition.Angle` を読み取り、Forward / Reverse 共通の model XY orientation として使用します。Project Location を作成・変更する処理は行いません。

Revit 2024.3 実機では True North の符号 contract を確認しており、Survey Point の True North 表示と shadow direction が一致することを検証対象としています。

## Forward Shadow の計算ロジック

Forward は概ね次の pipeline で処理します。

```text
Revit geometry
→ geometry / footprint extraction
→ solar position
→ Revit True North を反映した model-XY shadow direction
→ time-slice formal shadow projection
→ per-slice union
→ bounded grid sampling
→ trapezoidal shadow-duration accumulation
→ equal-time contour generation
→ Revit DirectShape preview
```

主な contract は次の通りです。

- 太陽方位は True North から時計回りで扱います。
- 基本の法規検討モードでは真太陽時を使用します。
- Shadow Core に渡る計算データは meter / degree / minute を基本単位とします。
- Revit API / internal units の責務は Revit Adapter 側に閉じ込めます。
- 日影時間は時間方向・空間方向ともに離散化を含む数値近似です。
- 精度を自動的に落として計算を成功扱いにする silent fallback は行いません。

## Reverse Shadow の考え方

Reverse Shadow は、Site Boundary と規制条件から低層建物の初期 massing を検討するための補助機能です。

```text
Site Boundary
→ measurement / candidate grids
→ time-discretized solar constraints
→ conservative height envelope
→ tessellated candidate volume
→ final Forward validation
```

Reverse は初期検討用です。道路・水面・高低差等の緩和、自治体固有の条件、法的な最大ボリューム判定は含みません。

## 計算精度

### Forward

| Preset | 空間分解能 | 時間刻み | 想定用途 |
|---|---:|---:|---|
| Fast | 1.0 m | 30分 | 初期検討・素早い反復 |
| Standard | 0.5 m | 15分 | 通常の設計検討（default） |
| High | 0.25 m | 5分 | より高い分解能での技術確認 |

High は計算負荷が大きくなります。また High を使用しても `permit_ready_certified=false` は変わりません。

### Reverse

| Preset | Site distance | Measurement spacing | Height grid XY | 時間刻み | Vertical step |
|---|---:|---:|---:|---:|---:|
| Fast | 1 m | 4 m | 4 m | 30分 | 0.5 m |
| Standard | 1 m | 1 m | 1 m | 15分 | 0.5 m |
| High | 1 m | 1 m | 1 m | 15分 | 0.5 m |

現在の Reverse High は Reverse Standard と同じ数値分解能です。

## 計算負荷 / Performance

実行時間とメモリ使用量は、主に次の条件で変わります。

- 敷地の大きさ
- Calculation Accuracy
- 時刻 sample 数
- caster solid の数と形状複雑度
- duration grid の大きさ
- Reverse の candidate / measurement grid 数

Forward / Standard では、開発中の単一実機での参考測定として、0.5 m / 15分、33 time samples、約15万 logical grid points のケースで約23秒の実行を確認しています。これは **ハードウェア条件やモデル条件を正規化した正式 benchmark ではなく、性能保証でもありません**。モデル形状、敷地範囲、PC、Revit session の状態によって変動します。

計算結果の数値精度は PC 性能によって変更しない方針です。PC 差は execution time、memory capacity、chunking 等にのみ影響させ、精度 preset を silent に変更しません。

## 推奨環境について

### 確認済み

- Revit 2024.3
- Dynamo 3.3
- CPython3

### Hardware

正式な minimum / recommended hardware requirement は、まだ十分な複数PC benchmark がないため確定していません。

現段階では、Revit 2024.3 を安定して実行できる CPU / RAM 環境での評価を想定しています。大きな duration grid や Reverse 計算ではメモリ使用量が増えるため、余裕のある環境ほど扱いやすくなります。具体的な RAM 容量や CPU class の推奨値は、複数環境での benchmark が揃うまで設定しません。

GPU acceleration は現在使用していません。

## 検証と信頼性

このプロジェクトでは、結果を「正しいと宣言する」より、どの部分をどう検証したかを追跡できることを重視しています。

現在の主な検証方法:

- Pure-Python unit / regression / contract / integration tests
- GitHub CI
- Revit 2024.3 実機検証
- formal projection の direction / extent runtime validation
- True North の実機 sign / orientation validation
- no-silent-accuracy-fallback contract
- privacy-safe debug diagnostics
- Forward / Reverse 共通の座標・AGL contract tests

独立ソフトウェアや固定 Golden fixture との比較は、今後も継続して強化する対象です。

## Known Limitations / 現在の主な制約

- 確認申請用の認証済み計算ソフトではありません。
- Formal legal pass / fail judgement は未実装です。
- 自治体条例の自動選択は行いません。
- 適用する日影規制区分は利用者が確認する必要があります。
- 道路、水面、高低差その他の法規緩和は未実装です。
- Site Boundary は現在、単一 outer loop・hole なし・straight segment を基本対象としています。
- Forward の shadow caster は現在 Mass / Generic Model を中心に扱います。
- Existing Wall / Floor / Roof / equipment / CAD import / topography edge を自動 caster 化しません。
- Reverse Shadow は unique / maximum legally buildable volume を求めるものではありません。
- Reverse の結果には最終 Forward validation が必要です。
- High accuracy はモデルによって計算負荷が大きくなります。
- Product UI / installer / production C# add-in は未提供です。
- Verification report output は未実装です。

## Preview 表示

Preview は可視化用であり、法的な合否判定ではありません。

`runtime/Shadow.dyn` の現在の initial setting は `preview_mode="replace"` です。

```json
{"preview_mode": "off"}
```

```json
{"preview_mode": "replace"}
```

```json
{"preview_mode": "clear"}
```

`replace` は既存の Dynamo Shadow preview DirectShape を削除して新しい preview を作ります。`clear` は owned preview を削除し、新規作成しません。色は表示上の識別用であり、legal pass / fail を意味しません。

## Architecture

開発上は次の3層を分離しています。

- **Revit Adapter**: Revit element / Area / Level / Project Location を読み、Revit geometry、unit conversion、formal projection、Boolean、preview/write behavior を担当。
- **Shadow Core**: meter-based / JSON-safe data で solar calculation、duration accumulation、contours、distance masks、Reverse logic 等を担当。`Autodesk.Revit.DB` を直接 import しません。
- **Dynamo Host**: `Shadow.dyn`、loader、`IN[]` / `INPUTS` mapping、`script.py` orchestration、`OUT` を担当。

Dynamo / Python 実装は、将来 add-in 化する場合にも仕様・実機挙動を比較できる reference implementation として維持する方針です。

## Project Structure

- `runtime/` — 実行可能な Dynamo/Revit runtime bundle と開発 source of truth
- `runtime/Shadow.dyn` — Dynamo Player graph
- `runtime/dynamo_loader.py` — same-folder loader と input mapping
- `runtime/script.py` — top-level orchestration
- `runtime/shadow_*.py` — Revit Adapter / Shadow Core / supporting modules
- `tests/` — unit / integration / contract tests と fixtures
- `tools/` — repository checks
- `docs/` — user guide、specification、runtime QA、development notes

## Debug Logs

Debug logging は default では無効です。有効時は、コピーした `runtime/` 内の `debug_logs/latest_debug.json` に runtime diagnostics を書きます。

Debug log には local path、username、email、client/project name、raw Revit object representation、大規模 geometry payload 等を残さない方針です。True North、精度、計算時間、grid size、projection validation 等の privacy-safe な情報を技術検証に使用します。

## Units

Revit Adapter 内では必要に応じて Revit internal units を扱いますが、Shadow Core 側では meter / degree / minute を基本とします。meter-based field には `_m`、`_m2`、`_m3` suffix を付け、raw field を無言で置き換えません。

## 技術レビュー歓迎

技術的な指摘、再現可能な不具合、精度比較、Revit API 上の挙動確認を歓迎します。

特にレビュー対象として重要な領域:

- Revit Project Location / True North
- Average Ground Level / measurement plane
- Revit geometry extraction
- solar coordinate convention
- formal shadow projection
- duration accumulation
- equal-time contour generation
- Reverse Shadow approximation
- performance / memory behavior

再現条件を伴う Issue / Pull Request は、実装改善の重要な材料になります。

## Documentation

- Architecture / add-in migration: `docs/development/addin_migration_direction.md`
- Research notes: `docs/development/research_shadow_diagram.md`
- v0 specification: `docs/development/spec_v0.md`
- Revit input modeling guide: `docs/user/revit_input_modeling_guide.md`
- Site boundary Area setup: `docs/user/site_boundary_area_setup.md`
- Settings schema: `docs/specifications/settings_schema_v1.md`
- Measurement plane: `docs/specifications/measurement_plane_v1.md`
- Geometry extraction: `docs/development/geometry_extraction_v1.md`
- Footprint extraction: `docs/specifications/footprint_extraction_v1.md`
- Debug logging: `docs/runtime/debug_logging_v1.md`
- Unit conversion: `docs/specifications/unit_conversion_v1.md`
- Contributor / agent rules: `AGENTS.md`

## Professional Use / Scope Warning

Dynamo Shadow は、設計検討や独立した技術確認を補助することはできますが、専門家による判断、適用条例の確認、確認申請審査機関との協議を置き換えるものではありません。

正式な法規判定、確認申請、行政・審査機関への提出には、適用法令・条例・審査要件を別途確認してください。

`permit_ready_certified=false`
