# D4 実装記録 — チャンネル・データ辞書連携（PF demo ブランチ）

- **日付**：2026-08-28
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、D3 コミット `9508334` 基準）
- **対象**：プロトコルのデバイスコネクタが宣言したチャンネル情報（`dataType` / `unit` / `sampleRate`）をデータ辞書として取り出し、BioDB の実験登録に付与する
- **BioDB 側変更**：**なし**（既存の `GET/POST /experiment/<id>/dictionary` を利用）

## 背景

D2 でセッションを BioDB へ推送できるようになったが、実験の辞書（チャンネル定義）は空のままで、
読戻し側はチャンネルの単位・型・サンプリングレートを知ることができなかった。
D4 では PF 側のプロトコル定義を**唯一の情報源**として、通道辞書を自動生成し推送時に付与する。

## 設計上の決定

- 辞書のキーは**チャンネル ID**（コネクタ内で一意）。コネクタの来歴（`connectorId` / `connectorVersion`）も併記し、チャンネルをデバイスまで追跡可能にする。
- **入力チャンネルのみ**を辞書に載せる。`direction: 'output'` のマーカー・トリガは時系列ストリームではないため除外する。
- V2 Graph プロトコルではグラフに配線されたデバイスノード（`node.config.deviceConnectorId`）を優先し、デバイスノードが無い場合はインストール済みコネクタ全件にフォールバックする（配線前のプレビューでも辞書が空にならないように）。
- V1（旧形式）は `protocol.deviceConnectors` をそのまま使う。セレクタは両形式を許容する。
- 辞書の推送は**ベストエフォート**。実験未登録 / 権限不足で失敗してもサンプル行の推送は成功として扱い、UI に理由を表示する（推送の主目的を壊さない）。
- 辞書は**全体置換**（`POST` は既存辞書を上書き）。部分更新は行わない。

## PF 側の変更

### 1. コア — `src/data/channelDictionary.js`（新規）

- `channelDataDictionary(protocol)` — コネクタの `channels` から `{ contractVersion, protocol, connectors, channels, inputChannels, outputChannels }` を生成。`channels[id] = { connectorId, connectorVersion, label, dataType, unit, sampleRateHz, direction }`。
- `dictionaryPayload(protocol)` — BioDB 形式（`{ channelId -> { label, unit, type, sampleRateHz, direction, connectorId, connectorVersion } }`）の入力チャンネルのみを返す。該当なしは `null`。
- `deviceConnectorsOf(protocol)` — 上記フォールバック付きのコネクタ解決。

### 2. V2 セッション書き出し — `src/data/graphExport.js`

- `channel_dictionary.json` / `channel_dictionary.csv` をバンドルに追加。
- `manifest.json` の `counts` に `channels` / `connectors` を追加。
- `graphDataDictionary()` のテーブル定義に `channels` を追加し、`data_dictionary.json` にも反映。

### 3. 汎用書き出し — `src/exporter.js`

- `bundle()` が `channel_dictionary.json` を出力し、`export_manifest.json` の `counts` と `files` 説明、`data_dictionary.csv` に通道辞書の項目を追加。

### 4. 推送クライアント — `src/bioDBClient.js`

- `pushExperimentDictionary(cfg, experimentId, dictionary)` — admin JWT を取得して `POST /experiment/<id>/dictionary`（body `{dictionary}`）。
- `pushSessionToBioDB(cfg, opts)` に `dictionary` オプションを追加。`/sensor/data/write` 成功後に辞書を付与し、戻り値に `dictionaryPushed` / `dictionaryError` を含める。

### 5. セッション推送 UI — `src/SessionManager.jsx`

- 推送時に `dictionaryPayload(protocol_snapshot)` を生成して渡し、結果メッセージに辞書の反映状態（成功 / 失敗理由）を追記する。

## 出力例

`channel_dictionary.json`:

```json
{
  "contractVersion": "1.0.0",
  "protocol": { "id": "protocol_1", "name": "D4 e2e graph", "version": 1 },
  "connectors": {
    "org.physioflow.simulated-sensor": {
      "connectorId": "org.physioflow.simulated-sensor",
      "version": "1.0.0",
      "name": "Simulated Physiology Sensor",
      "transport": "timer"
    }
  },
  "channels": {
    "signal": {
      "connectorId": "org.physioflow.simulated-sensor",
      "connectorVersion": "1.0.0",
      "label": "signal",
      "dataType": "number",
      "unit": "a.u.",
      "sampleRateHz": 100,
      "direction": "input"
    },
    "marker": { "...": "...", "dataType": "string", "unit": null, "sampleRateHz": null, "direction": "output" }
  },
  "inputChannels": ["signal"],
  "outputChannels": ["marker"]
}
```

## 検証

`node e2e-d4.mjs`（認証情報は環境変数 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID`、任意で `BIO_EXPERIMENT`）：

1. チャンネル辞書を生成（`signal` / `marker`、入力は `signal`）
2. admin JWT 取得 → 実験一覧
3. 専用実験 `PF D4 e2e` を登録（既存実験は**上書きしない**）
4. 辞書を推送（`POST /experiment/<id>/dictionary`）
5. 読戻して比較 → `signal: a.u. @ 100Hz (number)` が一致
6. グラフセッション書き出しに `channel_dictionary.json` が含まれることを確認

全ステップ PASS。

単体テスト `tests/channel-dictionary.test.js`（5 ケース）：

- V1 `deviceConnectors` からの抽出（`dataType` / `unit` / `sampleRate` / `direction`）
- V2 Graph のデバイスノード追従
- BioDB 形式ペイロード（入力のみ、該当なしは `null`）
- グラフ書き出しへの同梱と manifest counts
- 汎用 `bundle()` への同梱

`npm run build` / lint / 全単体テスト（245 件中 244 pass・1 skipped・0 fail）もパス。

## 依存

- D2（実験マッピング・セッション推送）— 前提、完了済み
- D1（BioDB 辞書 API `GET/POST /experiment/<id>/dictionary`）— 前提、完了済み
- BioDB テスト環境（`localhost:5002`、docker compose）が起動していること
- PF の BioDB 設定（Base URL / user_id / 長期 token）が設定済みであること

## 既知の制約

- 辞書は**実験単位**。参加者やセッション単位の辞書は保持しない（BioDB の辞書 API が実験単位のため）。
- `POST` は全体置換のため、手動で設定した辞書エントリは推送時に上書きされる。
- `sampleRateHz` がコネクタ定義に無いチャンネルは `null` のままとなる。

## ファイルリスト

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/data/channelDictionary.js` | 新規 |
| `src/data/graphExport.js` | 変更（`channel_dictionary.*` 出力・counts） |
| `src/exporter.js` | 変更（`bundle()` に同梱） |
| `src/bioDBClient.js` | 変更（`pushExperimentDictionary` 等） |
| `src/SessionManager.jsx` | 変更（推送時に辞書を付与） |
| `tests/channel-dictionary.test.js` | 新規（単体テスト 5 ケース） |
| `e2e-d4.mjs` | 新規（検証スクリプト、認証情報は環境変数） |
