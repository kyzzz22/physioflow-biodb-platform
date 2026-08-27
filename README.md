# PhysioFlow × BioDB 研究データプラットフォーム

実験の**ライフサイクル全体**をカバーする研究データプラットフォーム：設計 → 収集 → 保存 → 管理 → 分析 → 可視化。

**📖 オンラインドキュメント（GitHub Pages）**：https://kyzzz22.github.io/physioflow-biodb-platform/

- **PhysioFlow（PF）**：実験ワークフロー（ビジュアルなプロトコル設計、実行、参加者インタラクション、再現可能なデータパケットのエクスポート）。
- **BioDB**：生体データウェアハウス（センサ時系列 VictoriaMetrics、イベント MongoDB、ユーザー/権限 PostgreSQL、JWT 認証）。
- **統合**：PF が収集した生体データを BioDB へプッシュし、「実験ID + 協力者ID」の二段識別で保存。プラットフォームで一元的に管理・分析・可視化。

## プロジェクトリンク

| プロジェクト | リンク | 説明 |
|---|---|---|
| **PhysioFlow（PF）** | https://github.com/kyzzz22/physioflow-app | 実験ワークフロー（フロントエンド） |

> BioDB（生体データウェアハウス）はプライベートリポジトリのためリンクなし。

## ドキュメント索引

| 文書 | 内容 |
|---|---|
| `docs/ja/01-situation.md` | **現状の棚卸しと参考にできる点**：PF / BioDB の既存能力（業務機能・技術アーキテクチャ・データモデル）、直接再利用できる部分 |
| `docs/ja/02-gap.md` | **統合システムに不足している部分**：業務・技術・データの 3 次元でギャップを列挙 |
| `docs/ja/03-development.md` | **開発が必要な部分**：優先度 + 依存関係による開発リストとロードマップ |
| `docs/ja/04-d1-experiment-tag.md` | **D1/D2 実装計画**：BioDB の `experiment` 次元 + PF マッピング |
| `docs/ja/05-business-analysis.md` | **プラットフォーム業務分析（v2）**：背景 / 役割 / ユースケース / 業務ルール / 識別体系 / プロトタイプ計画 / 受け入れ |
| `docs/ja/06-biodb-deployment-summary.md` | **BioDB テスト環境デプロイメントまとめ**：アーキテクチャ / デプロイ手順 / 認証フロー / 機能実装と受入記録（D1 完了） |
| `docs/ja/07-d2-experiment-mapping.md` | **D2 実装記録（PF demo ブランチ）**：`protocol.biodb` 設定 / 設定 UI / セッションプッシュ / e2e 検証（D2 完了） |
| `docs/ja/08-d3-data-panel.md` | **D3 実装記録（PF demo ブランチ）**：データ管理パネル（participant 選択 / 読戻し / イベント CRUD）/ e2e 検証（D3 完了） |

参考資料（`docs/sourced/`）：

| 文書 | 内容 |
|---|---|
| `docs/sourced/MEETING_EXPERIMENT_ID.md` | 会議メモ：実験ID + 協力者ID 二段識別 |
| `docs/sourced/PF_EXPERIMENT_DESIGN_ANALYSIS.md` | PF 実験設計能力分析（原文：中国語） |
| `docs/sourced/PF_COMPOSER_V2_GAP_ANALYSIS.md` | PF エディタ差異分析（原文：中国語） |
| `docs/sourced/PF_BIODB_INTEGRATION.md` | PF×BioDB 連携方案（Phase 1-3、原文：中国語） |
| `docs/sourced/PLATFORM_BUSINESS_ANALYSIS.md` | プラットフォーム全体業務分析（第一版、原文：中国語） |

中文版ドキュメント：`docs/zh/`

## 進捗と計画（一覧）

### ✅ 完了（BioDB 側 + PF 側 D1〜D3）

| 項目 | 状態 |
|---|---|
| **D1** `experiment` タグ次元（書込/読戻し/イベント関連/実験登録表/結合エクスポート/特徴・ML 解析） | ✅ 端到端受入済み（[`docs/ja/06-biodb-deployment-summary.md`](docs/ja/06-biodb-deployment-summary.md)） |
| util 可視化ページ（`/util/`） | ✅ |
| bio_console 中国語 WebUI（`/db/`） | ✅ |
| WebUI 統合 `/WebUI/console`（日本語版・ダークテーマ） | ✅ 2026-08-27 |
| **D2** 実験/協力者マッピング（PF demo ブランチ）— `protocol.biodb` + 設定 UI + セッションプッシュ | ✅ 2026-08-28（[`docs/ja/07-d2-experiment-mapping.md`](docs/ja/07-d2-experiment-mapping.md)） |
| **D3** データ管理パネル（PF demo ブランチ）— participant 選択 / 読戻し / イベント CRUD | ✅ 2026-08-28（[`docs/ja/08-d3-data-panel.md`](docs/ja/08-d3-data-panel.md)） |

### 🚧 未開発（PF 側 D4〜D10）

| 開発項目 | 優先度 | 状態 |
|---|---|---|
| D4 データ辞書連携 | P1 | 未開発（次に着手） |
| D5 脳波デバイス adapter | P1 | 未開発 |
| D6 結合エクスポート/アーカイブ | P2 | 未開発 |
| D7 分析パイプライン | P2 | 未開発 |
| D8 可視化 | P2 | 未開発 |
| D9 ストリーミングプッシュ | P3 | 未開発 |
| D10 権限/監査 | P3 | 未開発 |

### ロードマップ

```
Phase 2（P0-P1）  D1 ✅ → D2 ✅ → D3 ✅ → D4 データ辞書
Phase 3（P1-P2）  D5 脳波デバイス → D7 分析パイプライン → D8 可視化 → D6 結合エクスポート
Phase 4（P3）     D9 ストリーミングプッシュ → D10 権限/監査
```

詳細： [`docs/ja/03-development.md`](docs/ja/03-development.md)

## 核心的な結論

1. **実験ID + 協力者ID の二段構造** = PF の `protocolId` + participant が、BioDB の `experiment` + `participant` タグに写像される。
2. **PF プロトコル = ドメインモデル**、BioDB = データウェアハウス。両者の役割は相補的。
3. 次の段階：PF で D4 データ辞書連携 → D5 脳波デバイス adapter → 分析 / 可視化（D6〜D10）。
