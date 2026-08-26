# BioDB テスト環境デプロイメントまとめ（概要）

> 本文書は BioDB（生体データウェアハウス）テスト環境のデプロイ構成・手順・受入結果を要約する。
> 詳しい技術情報（設定・トラブルシューティング・全受入記録）は[中文詳細版](../zh/06-biodb-deployment-summary.md)を参照。

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

## 5. 機能実装と受入記録（2026-08-26）

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

### 5.2 受入結果（6 項目エンドツーエンド）

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

---

## 6. 今後の予定

BioDB 側の D1 は完了。次は PF（`physioflow-app` リポジトリ）側で D2（実験/協力者マッピング）→ D4（データ辞書）→ D3（データ管理パネル）を進める。詳細は[開発ロードマップ](03-development.md)を参照。

テスト環境のデータ・設定はリポジトリ内 `biodb-main/`（データディレクトリ含む）に保持。バックアップは `docker compose down` 後のデータディレクトリコピーまたは WSL2 ボリューム移行で対応。
