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

## オンラインエントリ（単一 origin）

BioDB の nginx（デフォルト `:5002`）が全 UI を単一 origin で配信する。研究室 LAN のどの端末からも `http://<ホストIP>:5002/` でアクセス可能（Windows ファイアウォールで 5002 の受信許可が必要）。

| パス | 内容 |
|---|---|
| `/` | **統合ランディングページ**（日/中切替）— PF Dashboard / BioDB Console の 2 大カード + サブリンク |
| `/pf/` | PhysioFlow Dashboard（PF のビルド成果を同梱、ブラウザローカル保存） |
| `/WebUI/console` | BioDB コンソール（SvelteKit、日本語・ダークテーマ）— 棚卸し / 閲覧 / イベント / 実験 / 分析 / エクスポート / 接続設定 |
| `/db/` | BioDB コンソール（中国語版、静的版） |
| `/util/` | 可視化クライアント（履歴 / リアルタイム / イベントチャート / 感情マップ） |
| `/shared/theme.css` | 共通デザイントークン（暗色 + 緑テーマ） |

全 UI は**共通の暗色 + グリーン**のデザインシステム（`biodb-main/webui-theme/theme.css`）で統一されている。

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
| `docs/ja/09-d4-channel-dictionary.md` | **D4 実装記録（PF demo ブランチ）**：チャネルデータ辞書（抽出 / 同梱 / 実験への付与） |
| `docs/ja/10-d5-eeg-adapter.md` | **D5 実装記録（PF demo ブランチ）**：Muse 脳波デバイス adapter（コード完成・実機未検証） |
| `docs/ja/11-d6-joint-export.md` | **D6 実装記録（PF demo ブランチ）**：結合エクスポート/アーカイブ |
| `docs/ja/12-d7-analysis-pipeline.md` | **D7 実装記録（PF demo ブランチ）**：分析パイプライン（前処理 / HRV・EDA・スペクトル / 統計・ML） |
| `docs/ja/13-d8-visualization.md` | **D8 実装記録（PF demo ブランチ）**：可視化（マルチチャンネル曲線 / リアルタイム / 感情マップ） |
| `docs/ja/14-webui-console.md` | **WebUI 統合デプロイとコンソール拡充**：統一エントリ / 共通テーマ / コンソール機能（ダッシュボード・ズーム・分析チャート等） |

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

### ✅ 完了

| 項目 | 状態 |
|---|---|
| **D1** `experiment` タグ次元（書込/読戻し/イベント関連/実験登録表/結合エクスポート/特徴・ML 解析） | ✅ 端到端受入済み（[`docs/ja/06-biodb-deployment-summary.md`](docs/ja/06-biodb-deployment-summary.md)） |
| util 可視化ページ（`/util/`） | ✅ |
| bio_console 中国語 WebUI（`/db/`） | ✅ |
| WebUI 統合 `/WebUI/console`（日本語版） | ✅ 2026-08-27 |
| **D2** 実験/協力者マッピング（PF demo ブランチ）— `protocol.biodb` + 設定 UI + セッションプッシュ | ✅ 2026-08-28（[`docs/ja/07-d2-experiment-mapping.md`](docs/ja/07-d2-experiment-mapping.md)） |
| **D3** データ管理パネル（PF demo ブランチ）— participant 選択 / 読戻し / イベント CRUD | ✅ 2026-08-28（[`docs/ja/08-d3-data-panel.md`](docs/ja/08-d3-data-panel.md)） |
| **D4** データ辞書連携（PF demo ブランチ）— チャネルリスト → データ辞書、プッシュ/エクスポートに同梱 | ✅ 2026-08-28（[`docs/ja/09-d4-channel-dictionary.md`](docs/ja/09-d4-channel-dictionary.md)） |
| **D6** 結合エクスポート/アーカイブ（PF demo ブランチ）— PF セッション＋ BioDB データ → 単一パケット | ✅ 2026-08-29（[`docs/ja/11-d6-joint-export.md`](docs/ja/11-d6-joint-export.md)） |
| **D7** 分析パイプライン（PF demo ブランチ）— 前処理 / HRV・EDA・スペクトル / 統計・ML（依存追加ゼロ） | ✅ 2026-08-29（[`docs/ja/12-d7-analysis-pipeline.md`](docs/ja/12-d7-analysis-pipeline.md)） |
| **D8** 可視化（PF demo ブランチ）— マルチチャンネル曲線 / リアルタイム / 感情マップ | ✅ 2026-08-29（[`docs/ja/13-d8-visualization.md`](docs/ja/13-d8-visualization.md)） |
| **WebUI 統一エントリ** — ランディング（日/中）/ `/pf/` 同梱 / `/shared` テーマ配信 | ✅ 2026-08-30（[`docs/ja/14-webui-console.md`](docs/ja/14-webui-console.md)） |
| **共通デザインシステム** — 全 UI を暗色 + グリーンで統一（token 集約） | ✅ 2026-08-30 |
| **コンソール拡充** — 棚卸しダッシュボード / 閲覧ズーム・CSV / 分析チャート / イベント一括削除 / 辞書編集 | ✅ 2026-08-30 |

### 🚧 保留中

| 開発項目 | 優先度 | 状態 |
|---|---|---|
| D5 脳波デバイス adapter（Muse） | P1 | コード完成・**実機未検証**（Muse 実機での受入が開いたまま） |
| D9 ストリーミングプッシュ | P3 | 未開発 |
| D10 権限/監査 | P3 | 未開発 |

### ロードマップ

```
Phase 2（P0-P1）  D1 ✅ → D2 ✅ → D3 ✅ → D4 ✅ データ辞書
Phase 3（P1-P2）  D5 脳波デバイス（実機検証待ち）→ D7 ✅ → D8 ✅ → D6 ✅
Phase 4（P3）     D9 ストリーミングプッシュ → D10 権限/監査
```

詳細： [`docs/ja/03-development.md`](docs/ja/03-development.md)

## 核心的な結論

1. **実験ID + 協力者ID の二段構造** = PF の `protocolId` + participant が、BioDB の `experiment` + `participant` タグに写像される。これがプラットフォーム全体の識別基盤。
2. **PF プロトコル = ドメインモデル**、BioDB = データウェアハウス。両者の役割は相補的で、PF が設計・収集・体験を、BioDB が保存・管理・分析・可視化を担う。
3. **全 WebUI は単一 nginx 入口で統合**：`/`（日/中ランディング）→ PF `/pf/`・BioDB `/WebUI/console`。全 UI が共通の暗色 + グリーンデザインシステム（`webui-theme/theme.css`、`/shared/` 配信）に統一されている。
4. **開発ステータス**：D1〜D4・D6〜D8（PF 側）と WebUI 統合・コンソール拡充は完了・検証済み。**唯一の未達は D5 実機検証**（Muse コードは完成、実機が必要）。
5. **次の段階**：D5 実機検証 → D9 ストリーミングプッシュ → D10 権限/監査。WebUI は LAN 多端末向けに HTTPS 化（Google ログインが LAN IP でも可能になる）。
