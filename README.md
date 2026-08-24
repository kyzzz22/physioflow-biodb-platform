# PhysioFlow × BioDB 研究データプラットフォーム

実験の**ライフサイクル全体**をカバーする研究データプラットフォーム：設計 → 収集 → 保存 → 管理 → 分析 → 可視化。

**📖 オンラインドキュメント（GitHub Pages）**：https://kyzzz22.github.io/physioflow-biodb-platform/

- **PhysioFlow（PF）**：実験ワークフロー（ビジュアルなプロトコル設計、実行、参加者インタラクション、再現可能なデータパケットのエクスポート）。
- **BioDB**：生体データウェアハウス（センサ時系列 VictoriaMetrics、イベント MongoDB、ユーザー/権限 PostgreSQL、JWT 認証）。
- **統合**：PF が収集した生体データを BioDB へプッシュし、「実験ID + 協力者ID」の二段識別で保存。プラットフォームで一元的に管理・分析・可視化。

## ドキュメント索引

| 文書 | 内容 |
|---|---|
| `docs/ja/01-situation.md` | **現状の棚卸しと参考にできる点**：PF / BioDB の既存能力（業務機能・技術アーキテクチャ・データモデル）、直接再利用できる部分 |
| `docs/ja/02-gap.md` | **統合システムに不足している部分**：業務・技術・データの 3 次元でギャップを列挙 |
| `docs/ja/03-development.md` | **開発が必要な部分**：優先度 + 依存関係による開発リストとロードマップ |
| `docs/ja/04-d1-experiment-tag.md` | **D1/D2 実装計画**：BioDB の `experiment` 次元 + PF マッピング |
| `docs/ja/05-business-analysis.md` | **プラットフォーム業務分析（v2）**：背景 / 役割 / ユースケース / 業務ルール / 識別体系 / プロトタイプ計画 / 受け入れ |

参考資料（`docs/sourced/`）：

| 文書 | 内容 |
|---|---|
| `docs/sourced/MEETING_EXPERIMENT_ID.md` | 会議メモ：実験ID + 協力者ID 二段識別 |
| `docs/sourced/PF_EXPERIMENT_DESIGN_ANALYSIS.md` | PF 実験設計能力分析（原文：中国語） |
| `docs/sourced/PF_COMPOSER_V2_GAP_ANALYSIS.md` | PF エディタ差異分析（原文：中国語） |
| `docs/sourced/PF_BIODB_INTEGRATION.md` | PF×BioDB 連携方案（Phase 1-3、原文：中国語） |
| `docs/sourced/PLATFORM_BUSINESS_ANALYSIS.md` | プラットフォーム全体業務分析（第一版、原文：中国語） |

中文版ドキュメント：`docs/zh/`

## 核心的な結論

1. **実験ID + 協力者ID の二段構造** = PF の `protocolId` + participant が、BioDB の `experiment` + `participant` タグに写像される。
2. **PF プロトコル = ドメインモデル**、BioDB = データウェアハウス。両者の役割は相補的。
3. 次の段階：BioDB に `experiment` タグ次元を追加 → PF で BioDB データ管理パネル → 分析 / 可視化。
