# 現状の棚卸しと参考にできる点（既存能力リスト）

2 つのプロジェクトの現状を「直接再利用できるもの」と「改造が必要なもの」に分けて棚卸し。業務機能・技術アーキテクチャ・データモデルの 3 次元で整理する。

## 1. PhysioFlow（PF）— 実験ワークフロー

### 業務機能（参考にできる / 直接再利用）

| 能力 | 説明 | 再利用方法 |
|---|---|---|
| ビジュアルプロトコル設計 | ノード図（13+ ノードタイプ）、ドラッグ＆ドロップ配線、グループ化、サブフロー、undo/redo、キャンバス操作（pan/zoom/複数選択/検索/自動レイアウト/フロースナップショット/ミニマップ） | 直接再利用（フロントエンド設計側） |
| PPT 式インターフェースエディタ | 参加者画面の WYSIWYG 編集（要素ライブラリのドラッグ、プロパティパネル、全画面ノード編集） | 直接再利用 |
| アンケートデザイナ | 9 問題タイプ / 11 プリセット / 条件スキップ / 決定的ランダム / 問題ごとの制限時間 / スコア出力 / CSV | 直接再利用 |
| 認知タスク実行 | Stroop / Go/No-Go 本試行（RT / 正答率 / 見逃し / 誤反応） | 直接再利用 |
| タスクテンプレート | Emotion（SAM）/ Stroop / Go-No-Go | 直接再利用（プロトタイプ先行） |
| 決定的ランタイム | クロック/ID の注入、一時停止/再開/リトライ/スキップ、スナップショット復元、イベントリプレイ | 直接再利用（実行側） |
| エクスポート | graph データパケット（events/responses/device_events JSONL+CSV）、BIDS v1.8.0、データ辞書 | 直接再利用（分析入力） |

### 技術アーキテクチャ（参考にできる）

| 能力 | 説明 |
|---|---|
| 単一事実源（Protocol Graph） | プロトコル schema + 不変コマンド + フリーズハッシュ、再現可能 |
| コンポーネントレジストリ | 宣言的コンポーネント（editorFields/ports/runtime.kind）、拡張可能 |
| Hosted サービス層 | デプロイ/launch token/bootstrap/HTTP API（アーキテクチャ参考として BioDB にも適用可能） |
| 純関数コア | 大部分のロジックが純関数 + 厳格なテストゲート（208+ テスト） |
| ブラウザネイティブ | 圧縮/Base64/ストリームはすべてブラウザの能力 |

### データモデル（参考にできる）

| モデル | 説明 |
|---|---|
| プロトコル schema | protocolId（= 実験ID）、ノード/エッジ/グループ/変数/アンケート/デバイスコネクタ |
| ランタイムイベント envelope | protocolId/sequence/三時計/ノード/コンポーネント |
| デバイスイベント envelope | connector/device/時刻/サンプル（Phase 1 で収集済み） |
| データ契約 v2 | events/responses/device_events JSONL+CSV + データ辞書 |

### 改造が必要（統合に向けて）

| 項目 | 説明 |
|---|---|
| 実験ID の明示化 | `protocolId` は実験IDだが、BioDB の `experiment` タグ / セマンティック名へのマッピングが必要 |
| BioDB クライアント | Phase 1 で `src/biodb/` 実装済み（プッシュ、JWT、コンテナ） |

## 2. BioDB — 生体データウェアハウス

### 業務機能（参考にできる）

| 能力 | 説明 | 再利用方法 |
|---|---|---|
| センサーデータの取り込み | `/sensor/data/write`（コンテナ：format/compression/data）、VictoriaMetrics 時系列 | 直接再利用（保存側） |
| データ読み出し | `/sensor/data/read`（rows/時間窓）、列主導で読み戻し | 直接再利用（分析取数） |
| イベント管理 | `/event/events` CRUD（協力者/実験者の二視点） | 直接再利用（管理側） |
| ユーザー/権限 | PostgreSQL + 長期トークン → JWT（scope/時間窓） | 直接再利用（認証） |
| WebUI/可視化クライアント | ユーザー/協力者/長期トークン管理 UI；util リアルタイム/履歴曲線、感情マップ | 一部移植可（Phase 3） |

### 技術アーキテクチャ（参考にできる）

| 能力 | 説明 |
|---|---|
| 3 DB の階層分離 | 時系列（VictoriaMetrics）/ 半構造化（MongoDB）/ 構造化（PostgreSQL） |
| nginx リバースプロキシ + 複数 API サービス | `/auth` `/sensor` `/event` 独立サービス、docker compose ワンクリックデプロイ |
| JWT 認証モデル | 長期トークン → 短命の用途別 JWT（sensor_read/write/event、時間窓 claim） |
| CORS 全開放 | ブラウザから直接クロスドメイン可（Phase 1 検証済み、プロキシ不要） |

### データモデル（参考にできる）

| モデル | 説明 |
|---|---|
| 時系列シリーズ | `biodb_<column>`、タグ `participant` + `experimenter`、ナノ秒タイムスタンプ |
| イベント | Mongo `user_id`（=協力者）/ `created_by`（=実験者）/ 時刻 / details |
| 識別 | ユーザー/協力者 21 桁 ID（nanoid） |

### 改造が必要（統合に向けて）

| 項目 | 説明 |
|---|---|
| **experiment タグ次元** | 時系列に「実験」次元が無い（会議の核心問題）——`p_victoria_metrics.py` の `tag_columns` に `experiment` を追加 |
| 条件/実験メタデータ | 実験条件（刺激セット等）の構造化保存が無い（PF プロトコルで担う方針） |
| 分析/ML/可視化 | BioDB に分析パイプライン無し、完全な可視化無し（Phase 3 で PF 側または新モジュール） |

## 3. 統合済み部分（Phase 1、参考にできる）

| 能力 | 説明 |
|---|---|
| `src/biodb/` | PF→BioDB プッシュ（コンテナ編デコード、BioDbClient、JWT キャッシュ/リフレッシュ、pushSession） |
| `src/runtime/deviceRuntime.js` | デバイスサンプラー（drift-corrected、sampleRateHz 準拠） |
| ランタイムデバイス収集 | `device_events` 収集 + ローカルエクスポート（jsonl/csv）+ 完了画面の BioDB エクスポートボタン |
| `protocol.biodb` | プロトコル内の実験設定（enabled/participantId） |
