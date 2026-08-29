# 開発が必要な部分（開発リストとロードマップ）

依存関係に沿って整理した開発項目。各項目に、関連モジュール・依存・受け入れ条件を記載する。

## 開発項目一覧

| # | 開発項目 | モジュール | 依存 | 優先度 |
|---|---|---|---|---|
| D1 | **BioDB `experiment` タグ次元** | `p_victoria_metrics.py` の `tag_columns` に `experiment` 追加；書き込み側（BioDbClient）が experiment_id を渡す | BioDB 側 | P0 |
| D2 | **実験/協力者マッピング**：PF `protocol.biodb.experimentId` + settings マッピング UI；`pushSession` に experiment を注入 | PF `src/biodb/` + ComposerV2 設定 | D1 | P0 |
| D3 | **PF BioDB データ管理パネル**：participant 選択、データ閲覧、イベント CRUD、簡易曲線 | PF 新 `BioDbPanel` + BioDbClient の event/read メソッド | D2 | P1 |
| D4 | **データ辞書連携**：チャネルリスト（dataType/unit/sampleRate）→ データ辞書、プッシュ/エクスポートに同梱 | PF `src/data/` + BioDB メタデータ | D2 | P1 |
| D5 | **実脳波デバイス adapter**（例：Muse）：transport bluetooth/serial、device connector に接続 | PF `src/devices/` | — | P1 |
| D6 | **結合エクスポート/アーカイブ**：PF セッション（プロトコル+イベント+device_events）+ BioDB データ → 1 つのデータパケット | PF `src/data/` | D3 | P2 |
| D7 | **分析パイプライン**：前処理（リサンプリング/フィルタ）、特徴（HRV/EDA/スペクトル）、統計/ML；BioDB 読み戻しを消費 | PF `src/biodb/analysis/` | D3 | P2 |
| D8 | **可視化**：履歴複数カラム曲線、リアルタイムモード、感情マップ | PF チャートコンポーネント | D3/D7/D9 | P2 |
| D9 | **ストリーミングプッシュ**：実行中のバッファ flush + 窓単位 JWT | PF `src/runtime/deviceRuntime.js` + `pushSession` | D1/D2 | P3 |
| D10 | **プラットフォームレベル権限/監査/統一認証ビュー** | PF App + BioDB 認証連携 | D3 | P3 |

## 現在の進捗（2026-08-28）

### BioDB 側：D1 ✅ 完了、エンドツーエンド受入済み
D1（`experiment` タグ次元）は BioDB テスト環境で実装・デプロイ・6 項目の機能受入を完了（詳細は [`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)）：

| 機能 | 状態 | 説明 |
|---|---|---|
| `experiment` タグ付き書き込み | ✅ | `p_victoria_metrics.py` がタグ対応；sensor JWT が `experiment` claim を持つと書き込み時にタグ付与 |
| 読み戻し（experiment フィルタ含む） | ✅ | `/sensor/data/read`；48h 大時間窓の動的シャーディング読戻し 6000 点/0.47s（時刻形式 Bug と aiohttp 8KB 行上限 Bug を修正済み） |
| イベント + 実験関連付け | ✅ | イベントが `experiment_id` で登録表と関連 |
| 実験登録表 | ✅ | MongoDB `event_database.experiments`（データ辞書 `dictionary` 含む） |
| 結合エクスポート | ✅ | `/sensor/data/export` が sensor データ + イベント + 実験メタデータの 3 部を返却 |
| 特徴統計 / ML 解析 | ✅ | `/sensor/data/features`（時間領域+周波数領域）、KMeans/回帰/予測/結果一覧・削除 |
| util 可視化ページ | ✅ | `/util/` 履歴/リアルタイム/イベントチャート/感情マップ（JWT Bearer プレフィックス Bug 修正済み） |

受入で修正した 5 問題：① シャーディング時刻のタイムゾーン無し+小数秒により VictoriaMetrics export が全 400；② KMeans `label_distribution` の整数キーを BSON が拒否；③ テストスクリプトのタイムスタンプ秒切り捨てで VM が重複排除；④ util ページの `Authorization` に `Bearer ` プレフィックス欠落；⑤ 48h 大時間窓の読戻しが `data=null`（aiohttp の行単位イテレーションで 1 行上限約 8KB、86.4s chunk の 8640 点単行 JSON 約 95KB が拒否 → `response.read()` で一括読取後に改行分割して解析）。

### BioDB Console（`/db/`）✅ 新 WebUI（D3 の参考実装）
日常運用向けの軽量独立コンソール（`biodb-main/bio_console/`、nginx `/db/` で配信）：

| 機能 | 説明 |
|---|---|
| 発見（Discover） | 長期 token から sensor read JWT を取得し participant・実験を自動発見（大窓読戻しの `@experiment` サフィックスを解析） |
| 閲覧 | participant/時間窓/実験で読戻し、曲線描画（ネイティブ Canvas、外部チャート依存なし） |
| イベント | event JWT による一覧/作成/削除（自分が作成したイベントのみ削除可、バックエンドの `created_by` セマンティクスと一致） |
| 実験登録 | 実験レジストリ/データ辞書の一覧・作成・削除（書込みは管理者のみ：長期 token scope=all かつ role=admin） |
| 分析 | `/sensor/data/features` と `/sensor/data/quality` を呼び出し |
| エクスポート | `/sensor/data/export`（sensor データ + イベント + 実験メタデータの 3 部）を呼び出し |
| 設定 | 長期 token 設定（user_id / token / participant_id） |

開発中に緩和した認可：
- `GET /auth/participant` と実験レジストリ読端点（`GET /experiments`、`GET /experiment/<id>`、`GET /experiment/<id>/dictionary`）を WebUI JWT 限定から `sensor_read`/`sensor_write`/`event` ロール JWT（または WebService）にも許可。
- 新設 `POST /auth/jwt/admin`：長期 token（scope=all）+ role=admin で 10 分間の WebUI admin JWT を発行（Google OAuth 非依存）。Console の実験レジストリ書込み（作成/削除）用。

### WebUI 統合：`/WebUI/console` 日本語版 ✅（2026-08-27）
`bio_console`（旧 `/db/` 中国語 UI）を既存の SvelteKit WebUI（`/WebUI/`）に統合し、単一エントリとして全面日本語化（ダークテーマ）。実装は `bio_svelte/`（新規 10 ファイル）：
- `src/lib/console-state.svelte.js`（共有状態 + API モジュール、bio_console の `common.js`/`app.js` に相当）、`src/lib/console-draw.js`（Canvas 曲線描画、イベントマーカー重ね描き対応）。
- `src/routes/console/`：`+page.svelte`（ビュー制御）+ 7 タブ：Overview（データ棚卸し、カードクリックで閲覧連動）、DataBrowse（曲線 + サマリ表）、Events（イベント CRUD）、Experiments（実験登録 CRUD + データ辞書）、Analysis（特徴統計/品質）、Export（3 部構成 JSON ダウンロード）、Settings（接続設定 + 接続テスト）。
- nginx 修正：`location /WebUI/` の `try_files` に `$uri.html` を追加（`adapter-static` はフラットな `xxx.html` を出力するため、`/WebUI/console` が index.html にフォールバックする問題を修正）。
- 検証：`GET /WebUI/console` → 200 かつ 7 タブすべてがプリレンダリング；エンドツーエンド readjwt → participant → experiments → sensor/data/read → event/events すべて 200。
- 旧 `/db/` 中国語 UI は引き続きアクセス可能。完全削除は別途対応（Dockerfile `COPY bio_console/` + nginx `location /db/`）。

### PF 側：D2 ✅ 実験/協力者マッピング（demo ブランチ、2026-08-28）
PF リポジトリ（`kyzzz22/physioflow-app`、`demo` ブランチ）に D2 を実装・端到端検証済み。BioDB 側は変更ゼロ（D1 で整備済みの `experiment` tag 経路を利用）：

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| プロトコル設定 | `protocol.biodb.experimentId`（`src/core/protocolGraph.js` 生成、`src/domain.js` 既定値、`src/core/protocolSelectors.js` の `experimentIdOf`/`experimentLabelOf`/`withBioDBConfig`） | V2 は camelCase `experimentId`、V1 は snake_case `experiment_id` を両対応 |
| グローバル設定 | `src/BioDBSettings.jsx`（Base URL / user_id / 長期 token / 接続テスト、Dashboard から開く、`loadSettings`/`saveSettings` で永続化） | 接続先を 1 箇所で管理 |
| プロトコル→実験マッピング | `src/ProtocolBioDBConfig.jsx`（ComposerV2 Header の BioDB ボタン） | BioDB の実験リストを読み込み、実験をプロトコルに紐付け |
| プッシュクライアント | `src/bioDBClient.js`（`getAdminJwt` / `fetchExperiments` / `pushSessionToBioDB` / `rowsFromDeviceEvents`） | admin JWT → writejwt（`experiment_id` 指定）→ `/data/write` へ session データを push |
| セッション推送 UI | `src/SessionManager.jsx` の "Push to BioDB" ボタン | 未設定時は Alert 案内、成功時は行数 / channels / experiment を表示 |
| i18n / CSS | `src/i18n.jsx`、`src/questionnaire.css`（BioDB D2 ブロック） | zh / ja 辞書・スタイル追加 |

- **検証**：`node e2e-d2.mjs`（admin JWT → 実験登録 → `pushSessionToBioDB` で 20 行 push → `experiment` フィルタ付き読戻し）をすべて PASS。読戻しで `experiment` タグ付きデータが一致。
- **コミット**：`2faa06e`（D2 本体）+ `5fecf8c`（package-lock 同期 + 認証情報を環境変数化した e2e スクリプト）。

### PF 側：D3 ✅ データ管理パネル（demo ブランチ、2026-08-28）
Dashboard の「Data」ボタンから開くデータ管理パネルを実装。BioDB 側は変更ゼロ（D1 で整備済みの読戻し/イベント/participant API を利用）：

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| 読み取りクライアント | `src/bioDBClient.js`：`getBioDBAdminJwt` / `readBioDBData` / `getBioDBEventJwt` / `listBioDBEvents` / `createBioDBEvent` / `deleteBioDBEvent` | read JWT はリクエスト窓で発行（窓越えを回避）；participant 一覧は admin JWT（WebUI claim）で取得；イベントは `/event/events`（CRUD） |
| データ管理パネル | `src/DataPanel.jsx`（新規） | participant 選択 / 時間範囲（1h・6h・24h ショートカット + datetime-local）/ チャンネル指定で読戻し |
| 表示 | 列式データのテーブル + 依存ゼロの SVG 折れ線グラフ（チャンネル選択可） | 読戻しは `{time:[...], [channel]:[...]}` の列式 JSON |
| イベント管理 | イベント一覧 + 新規作成（現在の窓の中央時刻）/ 行ごと削除 | body の `user_id` は participant_id（JWT claim 準拠）、削除はイベント窓で JWT 発行 |
| エントリ | `src/Dashboard.jsx` ヘッダー「Data」ボタン + パネルマウント | `BioDBSettings` の settings を共有 |
| i18n / CSS | `src/i18n.jsx`、`src/questionnaire.css`（D3 ブロック） | zh / ja 辞書・スタイル追加 |

- **検証**：`node e2e-d3.mjs`（participant 一覧 → 40 行の列式読戻し（eda/hr）→ イベント作成 → 一覧反映 → 削除 → 消滅確認）をすべて PASS。
- **コミット**：`9508334`（D3 本体）。

### PF 側：D4 ✅ チャンネル・データ辞書連携（demo ブランチ、2026-08-28）
プロトコルのデバイスコネクタが宣言したチャンネル情報（`dataType` / `unit` / `sampleRate`）からチャンネル辞書を生成し、書き出しに同梱＋推送時に実験へ付与する。BioDB 側は変更なし（`GET/POST /experiment/<id>/dictionary` を利用）。詳細は [`09-d4-channel-dictionary.md`](09-d4-channel-dictionary.md)。

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| チャンネル辞書の抽出 | `src/data/channelDictionary.js` | 入力チャンネルのみ。V2 Graph のデバイスノードを優先し、インストール済みコネクタへフォールバック。V1 も対応 |
| V2 書き出し同梱 | `src/data/graphExport.js` | `channel_dictionary.json`/`.csv` + manifest の `channels`/`connectors` 件数 |
| 汎用書き出し同梱 | `src/exporter.js` | `bundle()` に同梱 + データ辞書エントリ |
| 推送時の付与 | `src/bioDBClient.js` | `pushExperimentDictionary()` と `pushSessionToBioDB` の `dictionary` オプション（ベストエフォート） |
| 推送 UI | `src/SessionManager.jsx` | 辞書を自動生成して付与し、結果に反映状態を表示 |

検証：`node e2e-d4.mjs`（辞書生成 → 専用実験 `PF D4 e2e` 登録 → 推送 → 読戻し `signal: a.u. @ 100Hz` → 書き出し同梱確認）全 PASS。単体テスト 5 件。**コミット**：`2a8b68c`。

### PF 側：D5 ⚠️ Muse 脳波デバイス adapter（demo ブランチ、2026-08-28、コード完成・実機未検証）
InteraXon Muse を device connector として接続。BioDB 側は変更なし。詳細は [`10-d5-eeg-adapter.md`](10-d5-eeg-adapter.md)。

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| プロトコル解析 | `src/devices/museProtocol.js` | Classic ファームウェア：12-bit アンパック → µV、テレメトリ/IMU/PPG、制御コマンドフレーム |
| トランスポート | `src/devices/transports/webBluetooth.js` | Web Bluetooth 実装＋環境判定。transport は注入可能（Tauri ネイティブプラグイン用の口を確保） |
| コネクタとアダプタ | `src/devices/museConnector.js` | 4 電極 @256Hz `uV` + marker。通知ストリームを有界キュー化し、パケット番号からタイムスタンプを再構成 |
| 実行時接続 | `src/GraphRuntimeRunnerPage.jsx` | `transport` でアダプタを選択（従来は `simulated` のみ） |

**制約**：Tauri デスクトップ（WebView2）は Web Bluetooth を公開しないため、ブラウザ形態かネイティブ transport の注入が必要。Muse S Athena（Gen 3）は非対応（検出したら推測デコードせず失敗）。検証：単体テスト 12 件 PASS（D5→D4 の辞書連携を含む）、`npm run build` 成功。ただし実機未接続で、「実デバイスの格納」受け入れは未完了。

### PF 側：D6 ✅ 結合エクスポート/アーカイブ（demo ブランチ、2026-08-29）
PF セッション・パッケージと BioDB エクスポート封筒（時系列＋イベント＋実験メタデータ）を 1 つのアーカイブに統合。BioDB 側は変更なし（`POST /sensor/data/export` を利用）。詳細は [`11-d6-joint-export.md`](11-d6-joint-export.md)。

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| 統合ロジック | `src/data/jointExport.js` | PF ファイルはトップレベル保持、`biodb/` にプラットフォーム側。欠損は空欄（0 埋めしない）。来歴と時間窓は manifest に記録 |
| 封筒の取得 | `src/bioDBClient.js` | `exportBioDBData()` が sensor / events / experiment を一括取得 |
| 書き出し導線 | `src/SessionManager.jsx` | 「Joint export (BioDB)」ボタン。BioDB 失敗時も PF をアーカイブし理由を表示 |

**要点**：BioDB 側はベストエフォート——失敗してもアーカイブは生成される。検証：`node e2e-d6.mjs` 全 PASS（20 点の時系列＋17 ファイル＋縮退アーカイブ）。単体テスト 7 件。過程で **VictoriaMetrics は書込後およそ 6 秒でないと検索できない**ことを確認し、e2e にリトライを追加、UI と manifest に明示的な案内を入れた。

### PF 側：D7 ✅ 分析パイプライン（demo ブランチ、2026-08-29）
前処理 → 特徴（HRV/EDA/スペクトル）→ 統計/ML を実装し、BioDB の読戻しを消費して分析結果を書き出しに同梱する。BioDB 側は変更なし。詳細は [`12-d7-analysis-pipeline.md`](12-d7-analysis-pipeline.md)。

| 実装 | ファイル（PF demo ブランチ） | 説明 |
|---|---|---|
| 前処理 | `src/analysis/signal/preprocess.js` | 欠損補間、リサンプル、移動平均/中央値、トレンド除去、アーティファクト除去 |
| スペクトル | `src/analysis/signal/spectrum.js` | radix-2 FFT、PSD、帯域パワー、主周波数 |
| 特徴 | `src/analysis/signal/features.js` | 時間領域統計、HRV 時間/周波数領域、EDA の tonic/phasic と SCR |
| 統計/ML | `src/analysis/signal/stats.js` | Pearson、Welch の t、Cohen's d、リッジ回帰、k-means |
| 統括 | `src/analysis/signal/pipeline.js` | チャンネル識別 → 分析 → JSON/CSV |
| サーバ連携 | `src/bioDBClient.js` | `fetchBioDBFeatures` / `trainBioDBModel` / `predictBioDB` / `listBioDBAnalyses` |
| 書き出し統合 | `src/data/jointExport.js` | 結合書き出しに `analysis/` を同梱 |

**要点**：依存追加ゼロ（FFT/回帰/クラスタリングは全て自前実装）。サンプルレート不明時は推測せず縮退。アーティファクト除去は一次差分 + MAD に変更（初版の移動中央値残差では正常点 100 中 39 を誤剔除）。検証：`node e2e-d7.mjs` 全 PASS——60 bpm / SCR 3 回 / 2 Hz を構成し、60.0 bpm / SCR=3 / 1.99 Hz を測定。ローカルのリッジ回帰は r²=1.000000。ローカルとサーバのサンプルレートが一致。単体テスト 19 件＋結合書き出し 2 件。

### PF 側：D8〜D10 は未開発（PF 独立リポジトリ）
BioDB 側の依存は全て整っており、PF 側は既存エンドポイントに直接接続できる：

| # | 状態 | 接続前提（BioDB 側は実装済み） |
|---|---|---|
| D8 可視化 | 未開発 | util ページを参考実装として利用可 ✅ |
| D9 ストリーミングプッシュ | 未開発 | write JWT の窓単位認可 ✅ |
| D10 権限/監査 | 未開発 | `/auth` 体系 ✅ |

### 次のステップ計画
1. **短期（PF リポジトリ）**：D5 実機調整（Muse 実機が必要、コードは完成）→ D8 可視化。BioDB 側依存は全て整備済みで、既存エンドポイントに直接接続可能。
2. **中期（PF リポジトリ）**：D8 可視化（D7 の分析結果を直接消費できる）→ D9 ストリーミングプッシュ。
3. **長期**：D9 ストリーミングプッシュ → D10 プラットフォームレベル権限/監査。
4. **BioDB 側運用**：テスト残骸は整理済み（`exp_quality`、10:00 無タグ窓、単点 `exp_emotion`/`exp_cognition` 等を削除し、`exp_emotion_verify` と `evt_verify_001` は連携確認用に保持）；実データ接続後に結合エクスポートのメタデータと 48h 大窓性能を再検証。

## ロードマップ（段階 → 開発項目）

```
Phase 2（P0-P1）   D1 experiment tag ✅ → D2 実験/協力者マッピング ✅ → D3 データ管理パネル ✅ → D4 データ辞書 ✅
Phase 3（P1-P2）   D5 脳波デバイス ⚠️（コード完成・実機未検証）→ D7 分析パイプライン ✅ → D8 可視化 → D6 結合エクスポート ✅
Phase 4（P3）      D9 ストリーミングプッシュ → D10 プラットフォーム権限/監査
```

## 主要開発項目の詳細

### D1 — BioDB `experiment` タグ（最小コストで二段識別を解放）
- `p_victoria_metrics.py` を変更：`dataframe_to_line_protocol(data_df, "biodb", tag_columns=["participant","experimenter","experiment"])`。
- 書き込み側 `BioDbClient.writeChunk`：columns に `experiment` 値を注入（`protocol.biodb.experimentId` またはマッピング由来）。
- 読み戻し：`/sensor/data/read` の selector に `experiment="..."` を追加。
- 受け入れ：同一 participant の 2 つの異なる実験データがそれぞれ読み戻せる。

### D2 — 実験/協力者マッピング（識別を利用可能にする）
- PF `protocol.biodb`：`experimentId`（セマンティック名またはプロトコルID）+ 任意の `experimentLabel` を追加。
- `settings.biodb.participantMapping` の UI 化（BioDbConfigPanel アップグレード）。
- `pushSessionToBioDb`：`experiment` を注入 + participant を解決（既存）。
- 受け入れ：セッション完了で BioDB にプッシュされ、データに experiment+participant が付き、読み戻し一致。

### D3 — PF BioDB データ管理パネル（プラットフォーム「管理」の実装）
- `BioDbClient` に追加：`listParticipants`、`readSensor`（ページング読み戻し）、イベント CRUD（`/event/events`）。
- `BioDbPanel.jsx`：participant ドロップダウン、時間帯閲覧、簡易曲線（Analytics チャートを再利用）、イベントリスト管理。
- 入口：`App.jsx` の `view==='biodb'` + Dashboard の "BioDB"。
- 受け入れ：D2 でプッシュしたデータがパネルで見え、イベントを管理できる。

### D7 — 分析パイプライン（プラットフォーム「分析」の実装）
- `src/biodb/analysis/`：`resample`、`filter`、`hrv`、`eda`、`spectral`、`artifactReject`、`ml`。
- `readSensor` の読み戻しを消費（書き込み側に依存しない）。
- 出力 `.jsonl/.csv` をセッションパケットに含める；任意で BioDB イベントに書き戻し。
- 受け入れ：シミュレーション信号から HRV/スペクトル特徴を算出、統計/ML が合成データでトレーニング/予測可能。

## マイルストーンと受け入れ

| マイルストーン | 内容 | 受け入れ |
|---|---|---|
| M1（Phase 2） | experiment tag + マッピング + データ管理パネル | 2 実験のデータがそれぞれ読み戻せ、パネルで閲覧管理できる |
| M2（Phase 3） | 脳波接続 + 分析 + 可視化 | 実デバイスが保存され、特徴が算出でき、曲線/感情マップが描画できる |
| M3（Phase 4） | ストリーミング + 権限監査 | リアルタイム曲線、プラットフォームレベル権限ビュー |

## やらないこと（明確に除外）

- プラットフォームレベルのマルチテナント/クラウドホスティング（研究室ローカルデプロイを維持）。
- 任意 JS 注入のランタイム（サンドボックスを維持）。
- 自動統計結論生成（慎重さが必要、誤導を避ける）。
