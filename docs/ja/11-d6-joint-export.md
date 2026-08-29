# D6 実装記録 — 結合エクスポート / アーカイブ

- **日付**：2026-08-29
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、D5 コミット `4238414` 基準）
- **目的**：PF セッション・パッケージ（プロトコル＋イベント＋デバイスイベント）と BioDB エクスポート封筒（時系列＋イベント＋実験メタデータ）を 1 つのアーカイブに統合する
- **BioDB 側の変更**：**なし**（`POST /sensor/data/export` を利用）

## 背景

D2/D3 で書込と読戻しは繋がったが、収集側（PF）とデータ基盤（BioDB）のエクスポートは**別々の成果物**のままだった。
PF はプロトコルと行動イベント、BioDB は生理時系列を出力するため、分析時には参加者と時間窓を手作業で突き合わせる必要があった。D6 は両者を 1 つの自己完結アーカイブに統合する。

## 設計上の決定

### 1. PF 側を優先し、BioDB 側はベストエフォート
PF セッション・パッケージは**収集現場の一次記録**であり、BioDB が到達不能（ネットワーク障害、認証情報欠落、実験未登録）でも書き出せなければならない。
したがって BioDB 側が失敗してもアーカイブは**通常どおり生成**し、`joint_manifest.json` に理由だけを記録する。ネットワーク障害で現場データの書き出しを塞がない。

### 2. PF ファイルはトップレベルに保持
統合パッケージの PF 部分は**そのままルートに置く**（`events.csv`、`channel_dictionary.json`、`export_manifest.json` …）。
BioDB 部分は `biodb/` 配下にまとめる。既存の分析スクリプトはパス変更なしで動き続ける。

### 3. 欠損サンプルは空欄のまま、0 で埋めない
BioDB は列形式 `{ time: [...], channel: [...] }` を返し、欠損は `null`。CSV 化しても空セルを保つ——0 で埋めると「データ欠損」が「0 を観測」に偽装される。生理信号では全く別の意味になる。

### 4. チャンネルは接続子の宣言を優先し、イベント・ペイロードにフォールバック
BioDB へ要求するチャンネル一覧は D4 の `channelDataDictionary(protocol).inputChannels`（接続子が宣言した権威ある一覧）を優先し、
接続子を持たないプロトコルでのみ、デバイス・イベントのペイロードから数値キーを推定する。

### 5. 時間窓は BioDB を正とする
PF と BioDB の `started_at` / `sensorStart` はいずれも manifest に記録するが、**時系列の窓は BioDB の実際の返却値を正とする**——サーバが実際に受け付けた範囲だからである。

## 実装

| ファイル | 説明 |
|---|---|
| `src/data/jointExport.js` | 統合ロジック（新規） |
| `src/bioDBClient.js` | `exportBioDBData()` を追加（3 系統を 1 呼び出しで取得） |
| `src/SessionManager.jsx` | 「Joint export (BioDB)」ボタンと状態表示 |
| `tests/joint-export.test.js` | 単体テスト 7 件 |
| `e2e-d6.mjs` | 統合検証スクリプト |

### アーカイブ構成

```
joint_manifest.json           来歴、時間窓、各系統の状態と件数、警告
joint_data_dictionary.json    追加ファイルのフィールド説明
<PF セッション・ファイル>       トップレベルにそのまま保持
biodb/sensor_data.csv         BioDB 時系列（列形式を行に平坦化）
biodb/sensor_data.json        BioDB の生レスポンス
biodb/events.json             窓内のイベント
biodb/experiment.json         実験登録メタデータ（D4 のチャンネル辞書を含む）
```

## 検証

`node e2e-d6.mjs`（認証情報は環境変数）全 PASS：

```
→ channels: signal
✓ admin JWT / experiment list      → experiment: 595a3982-...
✓ push device samples to BioDB     → 20 rows pushed
✓ attach channel dictionary
… waiting for VictoriaMetrics visibility (attempt 2/3)
✓ export BioDB envelope (sensor/events/experiment)
  → sensor: 20 points, columns signal
  → events: 0, experiment: 595a3982-...
✓ build joint export package       → 17 files; sensor CSV 20 rows, header "time,signal"
✓ PF-only archive when the BioDB leg fails
```

単体テスト 7 件：列形式の平坦化（欠損は空欄）、空ペイロードはヘッダのみ、チャンネルの由来とフォールバック、
両系統マージ時の来歴記録、BioDB 失敗時に PF をアーカイブ、空/実験なしの場合の明示的警告、結合データ辞書。

`npm run build` 成功。全テスト 264 件中 263 pass / 0 fail / 1 skipped。新規ファイルの lint は警告なし。

## 過程で判明したこと：VictoriaMetrics の書込可視化遅延

初回 e2e で 20 点を推送した直後にエクスポートすると **0 点**が返ったが、数分後に手動で診断スクリプトを走らせると 20 点読めた。
対照実験でインタフェース自体は正常（フィルタなし 40 点 / 実験フィルタあり 20 点）と確認し、真因は
**書込から検索可能になるまで約 6 秒の遅延**（e2e は 3 回目の試行で成功）だった。

対応：

- **e2e**：リトライ待機（最大 6 回、3 秒間隔）を導入し、結果整合の読みに即時 assertion を置かない。
- **プロダクト**：推送直後にエクスポートすると空になるのは実際の利用シナリオなので、manifest の警告と UI メッセージの両方で
  「推送した直後なら数秒待って再エクスポート」と明示する。「データなし」と曖昧に出さない。

> 補足確認：`export` と `read` は**別のコード経路**（export は分割取得 `victoria_metrics_export_and_format_data`、read は非分割クエリ）。
> 今回の検証で両者の結果は一致した。

## 既知の制約

- アーカイブは**単一スナップショット**で差分ではない。再エクスポートすると全データが重複して含まれる。
- 複数実験が同名チャンネルを持つ場合、BioDB の返す列名には `@<experiment_id>` 接尾辞が付き、平坦化後も列名に残る。
- `events` は BioDB イベント庫に依存する。今回の e2e では窓内にイベントがなく 0 件——サンプルのみ推送したためで、欠陥ではない。
- 自動リトライの UI は未実装（現在は手動再エクスポートを促す表示）。
- アーカイブは参加者/実験でディレクトリ階層化していない（現状はダウンロード・ファイル名で区別）。

## 依存

- D2（書込経路）/ D3（読戻し）/ D4（チャンネル辞書）— 前提、全て完了
- BioDB `/sensor/data/export` — 前提、完了

## ファイル一覧

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/data/jointExport.js` | 新規 |
| `src/bioDBClient.js` | 変更（`exportBioDBData`） |
| `src/SessionManager.jsx` | 変更（結合エクスポート導線） |
| `tests/joint-export.test.js` | 新規（7 件） |
| `e2e-d6.mjs` | 新規 |
