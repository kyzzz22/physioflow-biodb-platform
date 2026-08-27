# D2 実装記録 — 実験/協力者マッピング（PF demo ブランチ）

- **日付**：2026-08-28
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、コミット `2faa06e` + `5fecf8c`）
- **対象**：PF 側で「プロトコル → BioDB 実験」のマッピングを設定し、セッションを BioDB へプッシュする
- **BioDB 側変更**：**なし**（D1 で整備済みの `experiment` tag 書込/読戻し経路を利用）

## 設計上の決定

- マッピングはプロトコル単位で保持する：`protocol.biodb.experimentId`（+ 表示用 `experimentLabel`）。
- V2 プロトコルグラフは camelCase（`experimentId`）、V1 は snake_case（`experiment_id`）で永続化されるため、セレクタは両方を許容する。
- 接続設定（Base URL / user_id / 長期 token）は PF のグローバル設定（localStorage）に保持し、プロトコル設定から分離する（機密情報をプロトコル JSON に入れない）。
- プッシュ時に admin JWT → sensor write JWT（`experiment_id` claim 付き）→ `/data/write` の順で発行・書込する。

## PF 側の変更（physioflow-app、demo ブランチ）

### 1. プロトコル設定 — `protocol.biodb`

`src/core/protocolGraph.js`：`createProtocolGraph` の metadata に以下を追加（デフォルト空）。

```js
biodb: { experimentId: options.experimentId || '', experimentLabel: options.experimentLabel || '' },
```

`src/domain.js`：`protocol()` 既定値に `biodb:{experiment_id:'',experiment_label:''}`（V1 形式）を追加。

### 2. セレクタ — `src/core/protocolSelectors.js`

- `bioDBConfigOf(protocol)` — protocol の biodb 設定を取得（V2 優先、V1 フォールバック）
- `experimentIdOf(protocol)` — `experimentId` / `experiment_id` 両対応で実験 ID を返す
- `experimentLabelOf(protocol)` — 実験ラベルを返す
- `withBioDBConfig(protocol, cfg)` — 設定をマージした新プロトコルを返す

### 3. プッシュクライアント — `src/bioDBClient.js`（新規）

- `getAdminJwt({baseUrl, userId, token})` → `POST /auth/jwt/admin`
- `fetchExperiments(...)` → 実験リスト取得（マッピング UI 用）
- `pushSessionToBioDB(settings, {participantId, experimentId, startedAt, endedAt, deviceEvents})`
  - sensor write JWT を `POST /jwt/sensors/writejwt`（body に `experiment_id`）で取得
  - イベントを `rowsFromDeviceEvents` で行に変換 → `POST /data/write`（base64）
- `rowsFromDeviceEvents(deviceEvents, ...)` — camelCase（`eventType/timestampIso/payload`）と snake_case（`event_type/timestamp_iso/metadata`）の両方を受け付ける

### 4. グローバル設定 — `src/BioDBSettings.jsx`（新規）

Dashboard ヘッダーの「BioDB」ボタンから開く接続設定ダイアログ。Base URL / user_id / 長期 token を入力し「接続テスト」で疎通確認。`loadSettings`/`saveSettings` で localStorage に永続化。

### 5. プロトコル→実験マッピング — `src/ProtocolBioDBConfig.jsx`（新規）

ComposerV2 ヘッダーの「BioDB」ボタンから開く。BioDB の実験リストを取得して選択肢を表示し、選択した実験を `protocol.biodb` に保存。

### 6. セッション推送 UI — `src/SessionManager.jsx`

`SessionDetail` に「Push to BioDB」ボタンを追加。未設定時は Alert で案内、成功時は行数 / channels / experiment を表示。

### 7. i18n / CSS

`src/i18n.jsx` に zh/ja 辞書を追加、`src/questionnaire.css` に BioDB（D2）ブロック（`.bio-btn`、`.field-label` 等）を追加。

## 検証

`node e2e-d2.mjs`（認証情報は環境変数 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID` で注入）：

1. admin JWT 取得（`POST /auth/jwt/admin`）
2. 実験登録（`POST /experiment`）
3. `pushSessionToBioDB` で 20 行をプッシュ
4. `experiment` フィルタ付きで読戻し → タグ付きデータが一致

全ステップ PASS。`npm run build` / lint / `rowsFromDeviceEvents` 単体テストもパス。

## 依存

- D1（BioDB `experiment` tag 次元）— 前提、完了済み
- BioDB テスト環境（`localhost:5002`）が起動していること

## ファイルリスト

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/core/protocolGraph.js` | 変更 |
| `src/domain.js` | 変更 |
| `src/core/protocolSelectors.js` | 変更 |
| `src/bioDBClient.js` | 新規 |
| `src/BioDBSettings.jsx` | 新規 |
| `src/ProtocolBioDBConfig.jsx` | 新規 |
| `src/ComposerV2.jsx` / `src/composer/Header.jsx` | 変更 |
| `src/Dashboard.jsx` | 変更 |
| `src/SessionManager.jsx` | 変更 |
| `src/i18n.jsx` / `src/questionnaire.css` | 変更 |
| `e2e-d2.mjs` | 新規（検証スクリプト、認証情報は環境変数） |
