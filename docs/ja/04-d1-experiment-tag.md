# D1/D2 実装計画 — BioDB `experiment` 次元 + PF マッピング

会議の核心要件：**実験ID + 協力者ID の二段構造**。本計画では以下を実装する：
- **D1**：BioDB 時系列に `experiment` タグ次元を追加（3 タグ：experiment + participant + experimenter）。
- **D2**：PF 側の実験/協力者マッピング + プッシュ時の `experiment` 注入。

## 設計上の決定

`experiment` は **JWT claim から取得**する（リクエストボディからの直接注入ではなく、participant/experimenter と同様）：
- より安全（書き込み者が experiment を偽造できず、長期トークン + writejwt 発行側が制御）。
- 読み戻し時に JWT scope でフィルタされ、実験ごとに自然に隔離される。

## BioDB 側の変更（biodb-main）

### 1. JWT 発行 — `bio_api_server/main.py`
`POST /auth/jwt/sensors/writejwt`（readjwt と対称）：
- リクエストボディに任意の `experiment_id` を追加（`pvalid` の `SensorJwtRequestBody` を拡張）。
- 指定された場合、JWT `additional_claims` に `"experiment": request_data.experiment_id` を追加。

```python
additional_claim = {
    "participant_id": request_data.participant_id,
    "experiment": request_data.experiment_id,   # 新規、null 可
    "start_time": request_data.start_time.isoformat(),
    "end_time": request_data.end_time.isoformat(),
    "jwt_role": "sensor_write",
}
```

### 2. 書き込み — `bio_api_server/victoria_sensor_server.py`
write 時に JWT から `experiment` を取得（あれば注入）：
```python
experiment = claims.get("experiment")
if experiment:
    data_df["experiment"] = experiment
# line protocol に渡す tag_columns に "experiment" を追加
```

### 3. タグ — `bio_api_server/p_victoria_metrics.py`
`dataframe_to_line_protocol(data_df, "biodb", tag_columns=["participant","experimenter"])` の呼び出しに `"experiment"` を追加（条件付き：その列が存在する場合のみタグ化）。

### 4. 読み戻し — `victoria_sensor_server.py` / `p_victoria_metrics.py`
- `read` リクエストボディに任意の `experiment` フィルタを追加；JWT に `experiment` がある場合、selector に `experiment="..."` を追加。
- `victoria_metrics_export_and_format_data` の `__name__` selector に `experiment=...` 条件を追加。

## PF 側の変更（physioflow-app）

### 1. プロトコル設定 — `protocol.biodb`
```js
{ enabled: true, experimentId: 'exp_nomura_ninomiya', participantId: '<21桁>', experimentLabel?: '野村二宮実験' }
```
`validateProtocolGraph`：`experimentId` は任意（空の場合は `protocolId` でフォールバック）。

### 2. BioDbClient — `src/biodb/bioDbClient.js`
- `issueJwt(role, { participantId, startTime, endTime, experimentId })`：body に `experiment_id` を追加（任意）。
- JWT キャッシュキーに `experimentId` を追加。
- `writeChunk({ participantId, experimentId, columns })`：透過。

### 3. pushSession — `src/biodb/pushSession.js`
- `resolveBioDbExperiment(protocol, settings)`：`protocol.biodb.experimentId` → `protocolId` フォールバック → settings デフォルト。
- 各 chunk の `writeChunk` 呼び出し時に `experimentId` を渡す。

### 4. 設定パネル — `BioDbConfigPanel.jsx`
`experimentId` 入力欄を追加（デフォルト空 = プロトコルID を使用）。

## 検証

1. BioDB スタック起動、`POST /auth/jwt/sensors/writejwt` に `experiment_id` を指定 → JWT デコードで `experiment` を含む。
2. PF でシミュレーションコネクタ実験を実行（`protocol.biodb.experimentId` を設定）→ プッシュ → 保存。
3. VictoriaMetrics クエリ：シリーズに `experiment=<id>` タグが付く。
4. 同一 participant の 2 つの異なる experiment をプッシュ → `experiment` でそれぞれ読み戻せ、データが混ざらない。

## 依存

- BioDB：`pvalid` リクエストボディ schema、`main.py` writejwt、`victoria_sensor_server.py`、`p_victoria_metrics.py`。
- PF：`protocol.biodb` schema + `bioDbClient`/`pushSession`/`BioDbConfigPanel`。
- サードパーティ依存なし；変更はすべて増分。

## ファイルリスト

| プロジェクト | ファイル | 変更 |
|---|---|---|
| BioDB | `bio_api_server/pvalid.py` | リクエストボディに `experiment_id` 追加 |
| BioDB | `bio_api_server/main.py` | writejwt/readjwt/events JWT に `experiment` claim 追加 |
| BioDB | `bio_api_server/victoria_sensor_server.py` | 書き込みで experiment タグ注入；読み戻しでフィルタ |
| BioDB | `bio_api_server/p_victoria_metrics.py` | tag_columns に experiment 追加 |
| PF | `src/biodb/bioDbClient.js` | issueJwt/writeChunk で experiment を渡す |
| PF | `src/biodb/pushSession.js` | resolveBioDbExperiment + 注入 |
| PF | `src/biodb/BioDbConfigPanel.jsx` | experimentId 入力欄 |
| PF | `src/core/validateProtocolGraph.js` | experimentId の検証（任意） |
