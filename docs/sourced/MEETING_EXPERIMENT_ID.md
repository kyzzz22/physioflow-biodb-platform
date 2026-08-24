# 会議メモ — 実験データ管理と実験ID導入

Date: 2026-08-23
Related: `docs/refactor/PF_BIODB_INTEGRATION.md`

## 背景（議題）

実験データ管理において、異なる実験協力者・異なる実験間のデータを区別するための**実験IDの導入**が必要であると合意。ただし、最適な DB 設計の議論は収束せず、**既存システム（PhysioFlow）で複数の実験パターンを実際に作成し、そこから要件を抽象化・整理する**方針に決定。

## 決定事項

- **実験IDの導入方針**：時系列 DB 上に複数のデータ塊が並ぶだけでは「どの実験か」を区別できないため、実験単位で ID を付与してラベリングする。
- **二段階の識別構造**：「実験ID（例：野村二宮実験 = ID1）」＋「実験協力者ID（例：ID1の被験者12345）」の二層管理。
- **進め方の方針**：いきなり要件定義・DB設計ではなく、既存実験システム（PhysioFlow）でプロトタイプを作成し、5パターン程度から要件を整理・抽象化する。
- **ドメインロジック優先**：DBスキーマより先に「アプリで何がしたいか」「どんなドメインオブジェクト・ロジックがあるか」を決める。DB設計はその後。

## 未解決の問題・ブロッカー → 解決策

| 問題 | 解決策（既存システム能力） | 対応成果 |
|---|---|---|
| データ塊の区別：同一ユーザーの複数データ塊が「別の実験」であることを区別する手段がない | BioDB の時系列書き込みに **`experiment` tag 次元**を追加（VictoriaMetrics は任意タグ対応）。現状 `participant`+`experimenter` の二層に第三層 `experiment` を足す | BioDB `p_victoria_metrics.py` の `tag_columns` に `experiment` を追加するだけで対応可能 |
| 実験IDの粒度・命名規則：名前付けで十分か、条件情報（刺激種類・数・タイムスタンプ等）をどこまで DB に持たせるか | **条件・刺激情報は PhysioFlow の protocol に保持**（構造化・バージョン化・凍結・再現可能）。DB には時系列＋イベントのみ。protocol スナップショットを experiment メタデータとして BioDB に保存するのは任意 | PF の protocol JSON が実験条件の唯一の事実源 |
| 脳波・ブレインウェーブデータとの紐付け：既存システムに脳波関連が未統合、実験IDとの紐付け方法が未解決 | PhysioFlow の **device connector フレームワーク**（serial/bluetooth/network）が脳波取得の入口。Phase 1（シミュレーション）で経路を検証後、実脳波デバイス adapter を接続し、時系列に `experiment` tag を付けて BioDB へ | device connector SDK ＋ Phase 1 収集パイプライン（`src/runtime/deviceRuntime.js`） |

## オープンクエスチョン → 決定案

| 質問 | 決定案 |
|---|---|
| 実験条件の一覧（刺激セット等）は DB か Excel か外部ファイルか | **PhysioFlow の protocol を使用**（構造化・再現可能・バージョン管理可能）。Excel は導入しない |
| 実験ID＋実験協力者IDの組み合わせで一意に特定できる設計で十分か | 十分。PF の `protocolId`（実験）＋ session `participant_id`（協力者）の二層が対応し、BioDB では `experiment`＋`participant` tag に写像する |
| タイムスタンプはどこまで DB に保存するか（時分秒単位の要否） | 維持：BioDB は**ナノ秒**、PF イベントは ISO＋epoch ms＋monotonic。時分秒では不足するレベルを既に超えている |

## 主な成果（システム側で実現済み・会議要件を支えるもの）

1. **PF プロトコル = ドメインモデル**：`protocolId`（実験）＋ participant（協力者）の二層構造が既に成立 → ①実験ID、②二段識別構造をそのまま実現
2. **BioDB の多層 tag が拡張可能**：VictoriaMetrics 書き込みが任意 tag 対応 → `experiment` を追加するのは `tag_columns` の一行変更
3. **PF の 3 つのタスクテンプレート**：Emotion / Stroop / Go/No-Go テンプレートから、会議の「5 パターン程度のプロトタイプ」を即座に作成可能
4. **device connector 収集パイプライン**：Phase 1 でシミュレーション経路を検証済み。脳波デバイスは実 adapter の追加で対応
5. **統合計画書**：`PF_BIODB_INTEGRATION.md` が Phase 1（実装済み）/ 2（PF 側データ閲覧・管理）/ 3（研究・データ管理、分析、可視化）を規定

## 決定事項（次回に向けて）

| 項目 | 決定 |
|---|---|
| **実験ID次元** | BioDB 時系列書き込みに `experiment` tag を追加。値は PF `protocolId` または意味名（例：`exp_nomura_ninomiya`）。二段 = `experiment`＋`participant` |
| **条件管理** | PF プロトコルを使用（Excel・条件DBは導入しない）。protocol スナップショットを BioDB に保存するのは任意 |
| **脳波統合パス** | Phase 1 シミュレーション経路 → 実脳波デバイス adapter 接続 → 時系列に `experiment` tag を付けて BioDB へ |
| **プロトタイプ先行** | PF の 3 テンプレート＋空プロトコルで 5 パターン作成し、要件を抽象化（9/1 までに実施可能） |
| **タイムスタンプ** | BioDB ナノ秒＋PF イベント三時計を維持 |

## アクションアイテム

- 全員：既存の実験システム（PhysioFlow）で実験設定を作成し、複数パターンを試す。
- 古久・なべしま・くおわみ：システム上でプロトタイプ実験を作成する担当として実施。
- 次回ミーティング：プロトタイプ作成後に要件整理。日程は 9月1日 前後を目安に調整・共有。

## 結論

会議で求める「実験ID＋実験協力者ID」の二段構造は、**PF の `protocolId`＋participant** にそのまま対応する。BioDB に `experiment` tag 次元を補えば、残りの問題はほぼすべて PF プロトコルをドメインモデルとして解決できる。
