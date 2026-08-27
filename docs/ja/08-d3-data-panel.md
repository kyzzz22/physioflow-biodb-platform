# D3 実装記録 — データ管理パネル（PF demo ブランチ）

- **日付**：2026-08-28
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、コミット `9508334`）
- **対象**：PF 側に BioDB のデータ管理パネル（participant 選択 / 読戻しテーブル / SVG 曲線 / イベント CRUD）を実装
- **BioDB 側変更**：**なし**（D1 で整備済みの読戻し・イベント・participant API を利用）

## 設計上の決定

- 読戻しは列式 JSON（`{time:[...], [channel]:[...]}`）をそのままテーブル + SVG 折れ線グラフで表示する（依存ゼロ）。
- read JWT は**リクエストの時間窓で発行**する（`/auth/jwt/sensors/readjwt` の窓が JWT の有効窓になるため、別窓で発行すると "Request time out of range" になる）。
- participant 一覧は read JWT では取得不可（participant_id が存在しないと発行できない）ため、admin JWT（`WebUI` claim）で `GET /auth/participant`（→ auth `/participant`）を呼ぶ。
- イベント JWT は `/auth/jwt/events`、イベント CRUD は `/event/events`（nginx で event サービスへ転送）。イベント作成 body の `user_id` は **participant_id**（JWT claim の `user_id` が participant_id のため一致必須）。

## PF 側の変更（physioflow-app、demo ブランチ）

### 1. クライアント拡張 — `src/bioDBClient.js`

- `getBioDBAdminJwt(cfg)` — admin JWT（WebUI claim）
- `readBioDBData(cfg, {participantId, startTime, endTime, rows, chunkSeconds})` — リクエスト窓で read JWT → `/sensor/data/read` → base64 を UTF-8 デコードして列式 JSON を返す
- `getBioDBEventJwt(cfg, {participantId, startTime, endTime})` — `/auth/jwt/events`
- `listBioDBEvents(cfg, ...)` — `/event/events?role=experimenter&start_time&end_time`
- `createBioDBEvent(cfg, {participantId, startTime, endTime, event, description, experimentId})` — `POST /event/events`（body の `user_id` = participant_id、`end_time` 必須で start より後）
- `deleteBioDBEvent(cfg, {participantId, eventId, startTime, endTime})` — `DELETE /event/events/<id>`（JWT 窓がイベント窓を覆う必要あり）

### 2. データ管理パネル — `src/DataPanel.jsx`（新規）

- participant ドロップダウン（admin JWT で一覧取得、`id` フィールド対応）
- 時間範囲：1h / 6h / 24h ショートカット + datetime-local
- チャンネル入力（カンマ区切り、既定 `eda,hr`）→ 「Read data」
- 結果：行数 / チャンネル統計、列式テーブル（最大表示行数変更可）、SVG 折れ線グラフ（チャンネル選択）
- イベント一覧 + 新規作成（現在の窓の中央時刻に 1 分間のイベントを作成）+ 行ごと削除

### 3. エントリ — `src/Dashboard.jsx`

ヘッダーの「Data」ボタンでパネルを開閉。`BioDBSettings` の settings を共有し、未設定時は案内を表示。

### 4. i18n / CSS

`src/i18n.jsx` に zh/ja 辞書、`src/questionnaire.css` に D3 ブロック（`.d3-panel`、`.d3-table`、`.d3-chart`、`.d3-event-create`、`.d3-del` 等）を追加。

## 検証

`node e2e-d3.mjs`（認証情報は環境変数 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID`）：

1. participant 一覧（1 名）
2. 列式読戻し（`rows=eda,hr` → 40 行、チャンネル eda/hr）
3. イベント一覧（空）
4. イベント作成（`e2e-d3-verify`）→ 一覧に反映
5. イベント削除 → 一覧から消滅

全ステップ PASS。`npm run build` / lint もパス。

## 依存

- D1（BioDB 読戻し / イベント CRUD / participant API）— 前提、完了済み
- BioDB テスト環境（`localhost:5002`）が起動していること
- PF の BioDB 設定（Base URL / user_id / 長期 token）が設定済みであること

## ファイルリスト

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/bioDBClient.js` | 変更（D3 関数追加） |
| `src/DataPanel.jsx` | 新規 |
| `src/Dashboard.jsx` | 変更 |
| `src/i18n.jsx` / `src/questionnaire.css` | 変更 |
| `e2e-d3.mjs` | 新規（検証スクリプト、認証情報は環境変数） |
