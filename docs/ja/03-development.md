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

## 現在の進捗（2026-08-26）

### BioDB 側：D1 ✅ 完了、エンドツーエンド受入済み
D1（`experiment` タグ次元）は BioDB テスト環境で実装・デプロイ・6 項目の機能受入を完了（詳細は [`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)）：

| 機能 | 状態 | 説明 |
|---|---|---|
| `experiment` タグ付き書き込み | ✅ | `p_victoria_metrics.py` がタグ対応；sensor JWT が `experiment` claim を持つと書き込み時にタグ付与 |
| 読み戻し（experiment フィルタ含む） | ✅ | `/sensor/data/read`；48h 大時間窓の動的シャーディング読戻し 3300 点/378ms（時刻形式 Bug 修正済み） |
| イベント + 実験関連付け | ✅ | イベントが `experiment_id` で登録表と関連 |
| 実験登録表 | ✅ | MongoDB `event_database.experiments`（データ辞書 `dictionary` 含む） |
| 結合エクスポート | ✅ | `/sensor/data/export` が sensor データ + イベント + 実験メタデータの 3 部を返却 |
| 特徴統計 / ML 解析 | ✅ | `/sensor/data/features`（時間領域+周波数領域）、KMeans/回帰/予測/結果一覧・削除 |
| util 可視化ページ | ✅ | `/util/` 履歴/リアルタイム/イベントチャート/感情マップ（JWT Bearer プレフィックス Bug 修正済み） |

受入で修正した 4 問題：① シャーディング時刻のタイムゾーン無し+小数秒により VictoriaMetrics export が全 400；② KMeans `label_distribution` の整数キーを BSON が拒否；③ テストスクリプトのタイムスタンプ秒切り捨てで VM が重複排除；④ util ページの `Authorization` に `Bearer ` プレフィックス欠落。

### PF 側：D2〜D10 は未開発（PF 独立リポジトリ）
BioDB 側の依存は全て整っており、PF 側は既存エンドポイントに直接接続できる：

| # | 状態 | 接続前提（BioDB 側は実装済み） |
|---|---|---|
| D2 実験/協力者マッピング | 未開発 | `experiment` タグ書込/読戻し、sensor JWT claim ✅ |
| D3 データ管理パネル | 未開発 | `/sensor/data/read`、イベント CRUD、participant API ✅ |
| D4 データ辞書連携 | 未開発 | 登録表の `dictionary` フィールド ✅ |
| D5 脳波デバイス adapter | 未開発 | 書込経路（experiment/participant タグ付き）✅ |
| D6 結合エクスポート/アーカイブ | 未開発 | `/sensor/data/export` の 3 部構成 ✅ |
| D7 分析パイプライン | 未開発 | `/sensor/data/features` + ML エンドポイントをバックエンドに可 ✅ |
| D8 可視化 | 未開発 | util ページを参考実装として利用可 |
| D9 ストリーミングプッシュ | 未開発 | write JWT の窓単位認可 ✅ |
| D10 権限/監査 | 未開発 | `/auth` 体系 ✅ |

### 次のステップ計画
1. **短期（PF リポジトリ）**：D2 実験/協力者マッピング UI → D4 データ辞書 → D3 データ管理パネル。BioDB 側依存は全て整備済みで、既存エンドポイントに直接接続可能。
2. **中期（PF リポジトリ）**：D5 脳波デバイス → D7 分析パイプライン（BioDB 読戻しと既存の特徴/ML エンドポイントを活用）→ D8 可視化。
3. **長期**：D9 ストリーミングプッシュ → D10 プラットフォームレベル権限/監査。
4. **BioDB 側運用**：テスト残骸（`exp_quality` 等）の整理；実データ接続後に結合エクスポートのメタデータと 48h 大窓性能を再検証。

## ロードマップ（段階 → 開発項目）

```
Phase 2（P0-P1）   D1 experiment tag → D2 実験/協力者マッピング → D3 データ管理パネル → D4 データ辞書
Phase 3（P1-P2）   D5 脳波デバイス → D7 分析パイプライン → D8 可視化 → D6 結合エクスポート
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
