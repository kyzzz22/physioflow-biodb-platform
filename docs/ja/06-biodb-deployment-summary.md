# BioDB テスト環境デプロイメントまとめ（概要）

> 本文書は BioDB（生体データウェアハウス）テスト環境のデプロイ構成・手順・自動 E2E 実行記録を要約する。手動受入の完了記録ではない。
> 詳しい技術情報（設定・トラブルシューティング・自動 E2E の詳細記録）は[中文詳細版](../zh/06-biodb-deployment-summary.md)を参照。

---

## 1. 概要

| 項目 | 内容 |
|---|---|
| システム | BioDB：生体データウェアハウス（センサ時系列 + イベント + ユーザー/権限） |
| デプロイ方式 | Docker Compose 単機編成（`compose.yaml`） |
| 外部入口 | NGINX、`http://localhost:5002/` |
| WebUI | `/WebUI/`（SvelteKit SSG 静的ビルド、NGINX 配信） |
| API ルート | `/auth`（認証）、`/sensor`（センサ）、`/event`（イベント） |
| データ保存 | VictoriaMetrics（時系列）、MongoDB（イベント/長期 Token）、PostgreSQL（ユーザー/権限） |

**構成方針**：外部には NGINX ポートのみ公開し、API と DB は Compose 内部ネットワークでサービス名解決する。

## 2. 認証とデータ書き込みフロー（クライアント視点）

1. `user_id` + **長期 token**（WebUI で作成、scope=all）で権限付き JWT を取得：
   - 書き込み：`POST /auth/jwt/sensors/writejwt`
   - 読み出し：`POST /auth/jwt/sensors/readjwt`
   - JWT は短期有効（約 10 分）。`experiment_id` を渡すと `experiment` claim が付与される。
2. JWT を `Authorization: Bearer <jwt>` ヘッダに付けて業務 API を呼ぶ：
   - 書き込み：`POST /sensor/data/write`
   - 読み出し：`POST /sensor/data/read`
   - 結合エクスポート：`POST /sensor/data/export`（sensor データ + イベント + 実験メタデータ）
   - 特徴統計：`POST /sensor/data/features`、ML 解析：`POST /sensor/analysis/...`

> **重要**：`Authorization` ヘッダの `Bearer ` プレフィックス必須（欠落すると 400 "JWT Secret Key Error"）。

## 3. デプロイ手順（実機）

```bash
cd biodb-main
# .env を .env.example から作成し、APP_SECRET_KEY / APP_JWT_SECRET_KEY を secrets.token_urlsafe(32) で生成
docker compose up --build -d            # 初回ビルド 5-15 分（npm ci + pip install）
docker compose --profile tools run --rm admin --email <メール>   # 初期管理者作成
# 検証
#   WebUI   : http://localhost:5002/WebUI/
#   Swagger : http://localhost:5002/auth/apidocs など
```

## 4. 運用上の注意

- キー管理：`.env` の `APP_SECRET_KEY` / `APP_JWT_SECRET_KEY` は既定値を本番で使用禁止。
- Google OAuth：`GOOGLE_CLIENT_ID` 必須（無いと nginx ビルド失敗）。WebUI は GIS popup モードで ID token を `POST /auth/google/callback` に渡す。
- ポート：外部公開は 5002 のみ。変更時は `compose.yaml` の `ports` も同時に調整。
- データ保持：VictoriaMetrics `retentionPeriod=100y`（研究データ長期保存向け）。ディスク容量計画に注意。
- アップグレード：イメージタグ変更後 `docker compose up -d --build`、データディレクトリを先にバックアップ。

## 5. 機能実装と自動 E2E 記録（2026-08-26）

### 5.1 実装済み機能（D1 完了）

| 機能 | 状態 | 説明 |
|---|---|---|
| `experiment` タグ付き書き込み | ✅ | sensor JWT の `experiment` claim → VictoriaMetrics にタグ付与 |
| 読み戻し（experiment フィルタ） | ✅ | `/sensor/data/read`、48h 大時間窓動的シャーディング対応 |
| イベント + 実験関連付け | ✅ | イベント `experiment_id`（JWT claim 優先、R2 偽造不可） |
| 実験登録表（データ辞書付き） | ✅ | MongoDB `event_database.experiments` |
| 結合エクスポート | ✅ | sensor + イベント + 実験メタデータの 3 部構成 |
| 特徴統計 / ML 解析 | ✅ | 時間/周波数領域特徴、KMeans/回帰/予測/結果管理 |
| util 可視化ページ | ✅ | `/util/`（履歴/リアルタイム/イベントチャート/感情マップ） |
| WebUI（管理画面） | ✅ | ユーザー情報、長期 token CRUD、実験協力者 CRUD |

### 5.2 自動 E2E 実行記録（6 項目）

| # | 機能 | 結果 |
|---|---|---|
| 1 | 48h 動的シャーディング読戻し | ✅ 3300 点 / 378ms |
| 2 | 結合エクスポート（実験メタデータ含む） | ✅ sensor 6000×2 + イベント + 実験データ辞書 |
| 3 | 特徴統計（時域 + 周波数域） | ✅ 主周波数 0.1Hz が模擬信号と一致 |
| 4 | ML 解析（KMeans/回帰/予測/一覧/削除） | ✅ 全て合格（BSON 整数キー Bug 修正後） |
| 5 | util 可視化ページ | ✅ 全リソース 200 |
| 6 | ドキュメント更新 | ✅ 本文書含む |

### 5.3 修正した Bug（5 件）

1. シャーディング時刻が「タイムゾーン無し + 小数秒」で VictoriaMetrics export が全 400 → `_to_vm_iso()` で UTC 付き ISO に統一。
2. KMeans の `label_distribution` 整数キーを BSON が拒否 → キー文字列化。
3. テストスクリプトのタイムスタンプ秒切り捨てで VM が重複排除 → 6 桁マイクロ秒に固定。
4. util ページの `Authorization` に `Bearer ` プレフィックス欠落（"JWT Secret Key Error"）→ `common.js`/`history.html` 4 箇所修正。
5. **48h 大時間窓読戻しが空（`data=null`）**：`fetch_vm_export_chunk` の `async for line_bytes in response.content` は aiohttp の約 8KB 行上限があり、86.4s チャンク（8640 点、単行 JSON ~95KB）で `Chunk too big` → `response.read()` で一括読取し `split(b"\n")` に変更。復験：48h 窓 read/export とも 6000 点、約 0.47s。

### 5.4 テストデータ整理（2026-08-26）

- VictoriaMetrics：`exp_quality`（QTest* 4 series）、無ラベル 10:00 窓（2 series）、単点 `exp_emotion`/`exp_cognition`（2 series）を削除（`/api/v1/admin/tsdb/delete_series`）。
- MongoDB：`exp_emotion` 実験登録 1 件 + イベント 3 件を削除（`tools/cleanup_mongo_testdata.js` で再実行可）。
- 残存：`exp_emotion_verify`（eda/ppg 各 6000 点）+ イベント `evt_verify_001`（デモ/受入データとして保持）。

### 5.5 時系列データの時刻について

- データは **UTC** で保存・クエリされる（書き込み時の naive 文字列は UTC 扱い）。
- util ページはフォームのローカル時刻を `toISOString()` で UTC に変換して照会する。
- 例：東九区（UTC+9）で UTC 11:00 のデータを見るにはフォームに `20:00` を入力する。

### 5.6 BioDB Console 新 WebUI + participant 認可緩和（2026-08-26）

**BioDB Console（`/db/`）**
- 軽量独立コンソール `biodb-main/bio_console/`（index.html + style.css + app.js + `bio_util/common.js` を共用）、nginx `location /db/` で配信（`try_files ... /db/index.html`、Dockerfile に `COPY bio_console/ /usr/share/nginx/html/db/` 追加）。
- 機能：発見（participant/実験の自動発見）、閲覧（大窓読戻し曲線）、イベント CRUD、分析（features/quality）、エクスポート（export 3 部）、設定（長期 token）。
- 自動発見の仕組み：`experiment` フィルタなしの大窓読戻しでは返却キーに `@<experiment>` サフィックスが付く（例 `biodb_eda@exp_emotion_verify`）ため、これを解析して実験次元を識別。
- エンドツーエンド検証済み：`/db/` と静的リソース 200；readJWT で participant 一覧取得（code 200）；広時間窓 event JWT + イベント一覧/作成（end_time 未入力時は自動で +1 秒）/削除が全て 200。

**認可緩和**
- `GET /auth/participant` は元々 WebUI JWT（`get_jwt()["WebUI"]`）のみ許可。Console には Google OAuth ログインの流れがないため、`sensor_read`/`sensor_write`/`event` ロール JWT（または WebService）にも許可するよう緩和（発見機能用）。participant 一覧は低感度メタデータでありリスクは限定的。

### 5.7 実験レジストリ管理（bio_console）+ admin JWT チャネル（2026-08-26）

**背景**：実験レジストリ CRUD 端点は元々全て WebUI admin JWT（Google OAuth）が必要で、bio_console からはアクセス不可。テスト環境では MongoDB 直接投入で実験を作成していた。

**変更**
- 新設 `POST /auth/jwt/admin`：長期 token（`check_token` + scope に `all`）+ ユーザー role `admin`（`psql.get_user_from_id`）を検証し、10 分間の WebUI admin JWT（`additional_claims={"WebUI": True, "userRole": "admin"}`）を発行。Google OAuth 非依存。
- 新設 `_require_read()`（WebUI / WebService / sensor_read / sensor_write / event を許可する緩い読取認可）を `GET /experiments`・`GET /experiment/<id>`・`GET /experiment/<id>/dictionary` に適用。書込み端点（POST/update/delete/dictionary）は引き続き admin のみ。
- nginx に `location /experiments` と `location /experiment`（末尾スラッシュなしのプレフィックス、`proxy_pass http://auth:8000`）を追加し実験レジストリ API をプロキシ。
- bio_console に「実験登録」ビューを追加：一覧（緩い読取 JWT）、作成/削除（admin JWT）、データ辞書表示。

**検証**：一覧 200（count=1）→ 作成 200（UUID experiment_id 自動生成）→ 辞書 200（eda.unit=uS）→ 詳細 200 → 削除 200 → 一覧が count=1 に復帰。

**注意**：`docker compose up --build nginx` では nginx.conf 変更時に COPY キャッシュが無効化されないことがある（変更未反映）。`build --no-cache nginx` で強制再ビルドすること。

### 5.8 WebUI 統合：bio_console を /WebUI/console へ移行（日本語版）（2026-08-27）

**要件**：`bio_console`（旧 `/db/` 中国語 UI）を既存の SvelteKit WebUI（`/WebUI/`）に統合し、単一エントリとして全面日本語化（ダークテーマ）。

**実装**（`bio_svelte/`、新規 10 ファイル、純増分）：
- `src/lib/console-state.svelte.js`：共有状態（Svelte 5 runes）+ API モジュール（bio_console の `common.js`/`app.js` に相当：JWT 取得、participant/experiment/event CRUD、読戻し/特徴/品質/エクスポート）。
- `src/lib/console-draw.js`：Canvas 曲線描画（イベントマーカー重ね描き対応）、ダークテーマ適応。
- `src/routes/console/`：`+page.svelte`（ビュー制御）+ 7 タブ：
  - `Overview.svelte`（データ棚卸し：participant/実験の自動発見、カードクリックでデータ閲覧へ連動）
  - `DataBrowse.svelte`（データ閲覧：canvas 曲線 + サマリ表）
  - `Events.svelte`（イベント管理 CRUD）
  - `Experiments.svelte`（実験登録 CRUD + データ辞書）
  - `Analysis.svelte`（特徴統計 / 品質チェック）
  - `Export.svelte`（エクスポート：export 3 部構成 JSON ダウンロード）
  - `Settings.svelte`（接続設定：user_id / 長期 token / participant_id + 接続テスト）

**nginx 修正**（`nginx/nginx.conf`）：
- `adapter-static` はフラットな `xxx.html` を出力するため、拡張子なしの `/WebUI/console` が index.html へフォールバックしてしまう問題を修正。`location /WebUI/` の `try_files` に `$uri.html` を追加：`try_files $uri $uri/ $uri.html /WebUI/index.html;`。

**検証**（NGINX `http://localhost:5002` 経由）：
- `GET /WebUI/console` → 200、7 タブすべての内容がプリレンダリングされていることを確認 ✅。
- エンドツーエンド：readjwt（sensors/read）→ participant=200 → experiments=200 → sensor/data/read=200 → event/events（event-jwt）=200 ✅。
- 旧 `/db/` 中国語 UI は引き続きアクセス可能。将来削除する場合は Dockerfile の `COPY bio_console/` と nginx `location /db/` を併せて削除する。

**注意**：bio_svelte ソース変更後は nginx イメージを再ビルドする（静的ファイルはビルド時に COPY）：`docker compose build --no-cache nginx && docker compose up -d nginx`。

---

### 5.9 PF 側 D2：実験/協力者マッピング（2026-08-28）

**概要**：PF（`physioflow-app`、`demo` ブランチ）側で「プロトコル → BioDB 実験」マッピングを実装。BioDB 側は変更ゼロ（D1 の `experiment` tag 経路を利用）。

**実装**（詳細は [`07-d2-experiment-mapping.md`](07-d2-experiment-mapping.md)）：
- `protocol.biodb.experimentId`：プロトコル単位の実験マッピング（V2 camelCase / V1 snake_case 両対応）。
- `BioDBSettings.jsx`：グローバル接続設定（Base URL / user_id / 長期 token / 接続テスト、localStorage 永続化）。
- `ProtocolBioDBConfig.jsx`：実験リストからプロトコルへ実験を紐付け（ComposerV2 ヘッダー「BioDB」ボタン）。
- `bioDBClient.js`：`getAdminJwt` → sensor write JWT（`experiment_id` claim）→ `/data/write` のプッシュクライアント。
- `SessionManager.jsx`：「Push to BioDB」ボタンでセッション（device events）を実験に紐付けて推送。

**検証**：`node e2e-d2.mjs`（admin JWT → 実験登録 → 20 行 push → `experiment` フィルタ読戻し）全 PASS。

### 5.10 PF 側 D3：データ管理パネル（2026-08-28）

**概要**：PF（`physioflow-app`、`demo` ブランチ）側でデータ管理パネルを実装。BioDB 側は変更ゼロ（D1 の読戻し / イベント CRUD / participant API を利用）。

**実装**（詳細は [`08-d3-data-panel.md`](08-d3-data-panel.md)）：
- `readBioDBData`：リクエスト窓で read JWT を発行し `/sensor/data/read` から列式 JSON を読戻し。
- `DataPanel.jsx`：participant 選択（admin JWT + `/auth/participant`）/ 時間範囲 / チャンネル指定 → テーブル + SVG 折れ線グラフ。
- イベント CRUD：`/auth/jwt/events` + `/event/events`（一覧 / 作成 / 削除）。
- エントリ：Dashboard ヘッダーの「Data」ボタン。

**検証**：`node e2e-d3.mjs`（participant 一覧 → 40 行読戻し（eda/hr）→ イベント作成/削除）全 PASS。

### 5.11 PF 側 D4：チャンネル・データ辞書連携（2026-08-28）

**概要**：PF（`physioflow-app`、`demo` ブランチ）側で、プロトコルのデバイスコネクタが宣言したチャンネル情報（`dataType` / `unit` / `sampleRate`）からチャンネル辞書を生成し、書き出しに同梱＋推送時に実験へ付与する。BioDB 側は変更ゼロ（`GET/POST /experiment/<id>/dictionary` を利用）。

**実装**（詳細は [`09-d4-channel-dictionary.md`](09-d4-channel-dictionary.md)）：
- `data/channelDictionary.js`：コネクタの `channels` から辞書を生成（入力チャンネルのみ）。V2 Graph のデバイスノードを優先し、V1 `deviceConnectors` にも対応。
- `graphExport.js` / `exporter.js`：書き出しに `channel_dictionary.json`（+CSV）を同梱し、manifest に `channels` / `connectors` を追加。
- `bioDBClient.js`：`pushExperimentDictionary()` と `pushSessionToBioDB` の `dictionary` オプション（`/data/write` 成功後にベストエフォートで辞書を付与）。
- `SessionManager.jsx`：推送時に辞書を自動生成して付与し、結果メッセージに反映状態を表示。

**検証**：`node e2e-d4.mjs`（辞書生成 → 専用実験 `PF D4 e2e` 登録 → 推送 → 読戻し `signal: a.u. @ 100Hz` → 書き出し同梱確認）全 PASS。単体テスト 5 件、全テスト 245 件中 244 pass / 0 fail。

## 6. 今後の予定

本節は 2026-08-26 時点の記録である。その後、PF 側では D4・D6〜D8 のプロトタイプ実装まで進んだ。現在の未完了項目は D5 の実機検証、D9 ストリーミングプッシュ、D10 権限／監査、および主要フローの手動・実データ総合確認。最新状況は[開発ロードマップ](03-development.md)を参照。

テスト環境のデータ・設定はリポジトリ内 `biodb-main/`（データディレクトリ含む）に保持。バックアップは `docker compose down` 後のデータディレクトリコピーまたは WSL2 ボリューム移行で対応。
