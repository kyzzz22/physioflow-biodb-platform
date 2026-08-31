# 14. WebUI 統合デプロイとコンソール拡充

- **日付**：2026-08-30
- **リポジトリ**：`physioflow-biodb-platform`（biodb-main / nginx）
- **対象**：単一 nginx 入口への統一（PF Dashboard 同梱）、全 UI の共通デザインシステム化、コンソール機能の拡充
- **BioDB バックエンド変更**：**なし**（既存エンドポイントのみ利用。辞書編集は既存の `POST /experiment/<id>/dictionary` を新たに呼び出し）

## 1. 統一エントリ（単一 origin）

研究室 LAN にデプロイした BioDB の nginx（`:5002`）が全 UI を単一 origin で配信する。外部に公開されるポートは nginx のみ。

| パス | 内容 |
|---|---|
| `/` | 統合ランディングページ（日/中切替、`localStorage` で記憶、既定は日本語） |
| `/pf/` | PhysioFlow Dashboard（PF の `dist/` を相対パスビルドのまま同梱） |
| `/WebUI/console` | BioDB コンソール（SvelteKit） |
| `/db/`、`/util/` | 既存の静的 UI（テーマは共通化） |
| `/shared/theme.css` | 共通デザイントークン配信 |

### 実装メモ

- PF は `vite.config.js` の `base: './'`（相対パス）により、サブパス `/pf/` でそのまま動作。`nginx/nginx.conf` の `location /pf/` は SPA フォールバック付き静的配信。
- PF の BioDB Base URL はランタイム設定（`http://<ホスト>:5002` または同 origin 相対パス）。各ブラウザの localStorage に保存されるため、端末ごとに 1 回設定が必要。
- ビルド手順：`node nginx/build-pf.cjs`（PF リポジトリで `npm run build` → `biodb-main/pf-build/` にコピー）→ `docker compose build --no-cache nginx` → `docker compose up -d nginx`。
- PF の Service Worker（`/sw.js` 絶対パス登録）はサブパス下では inert（404 を `.catch` が握る）。オフライン/PWA 化は意図的に保留。

## 2. 共通デザインシステム（暗色 + グリーン）

全 UI（`/WebUI/console`・`/db/`・`/util/`・`/`）を 1 つのトークンセットで統一。

- **トークン契約**：`biodb-main/webui-theme/theme.css`（唯一のソース）。`:root` 変数で surfaces / text / accent / status / radius / shadow / font / chart 8 色パレット / イベント色を定義。
- **配信**：nginx `location /shared/` で `theme.css` を配信。`/db/`・`/util/` は `<link rel="stylesheet" href="/shared/theme.css">` で参照。SvelteKit は dev モードで nginx が無いため、`+layout.svelte` の `:root` に同一トークンを内聯（コメントで同期を明記）。
- **修復した不整合**：
  - ページ背景が白のままだった（body に背景未設定）→ 暗色を全面に塗り
  - 緑 accent と青 `rgba(76,154,255,…)` の混在（表ヘッダ等）→ 緑 tint に統一
  - 未定義の「幽霊トークン」（`--muted-color` 等）→ 正式定義
  - Bootstrap 系の明色アラート（ユーザ管理ページ）→ 暗色 tint ベースの単一ステータス体系に
  - チャートパレットが 3 箇所で分裂（`console-draw.js` / `common.js`×2）→ 同一 8 色 + イベント色に統一（暗色 canvas に可読な Tailwind-400 系）
- **コンポーネント共通化**：`bio_svelte/src/lib/global.css`（button/.btn、.card、.grid/.field、table、.chip、.link 等）を新設。コンソール 7 tab の裸ボタン/入力/表が即座に統一スタイルになる。

## 3. コンソール拡充

`/WebUI/console` の 4 tab を拡充（すべて純フロントエンド、新規 API なし）。

| Tab | 追加機能 |
|---|---|
| 棚卸し（Overview） | 統計カード 4 枚（実験登録数 / 参加者数 / 総データ点数 / 期間）、最近の活動（最新 5 件）、マウント時自動実行 |
| データ閲覧（DataBrowse） | 摘要に mean / std / 欠損数 / 欠損率 を追加、**CSV ダウンロード**、**canvas ドラッグで範囲選択 → ズーム再読込**（`console-draw.js` に `window` 切抜き対応）、チャンネル表示トグル |
| 分析（Analysis） | 周波数バンドエネルギー比のスタックバー、支配周波数バッジ、時域指標（mean/std/rms）の相対バー、品質チェックを完全性プログレスバーで表示 |
| イベント（Events） | 種別フィルタ（start/end/marker/note）、**一括削除**（チェックボックス + 全選択） |
| 実験登録（Experiments） | 検索フィルタ、**データ辞書の編集・保存**（`POST /experiment/<id>/dictionary`、admin JWT 必要） |

## 4. 検証状況

- ✅ SvelteKit / PF のプロダクションビルド、nginx のルーティング定義、`/db/`・`/util/` の theme link を確認済み。
- ⏳ 最新の統合環境における全パスの HTTP 確認は未実施。
- ⏳ ランディングの日/中切替と記憶、コンソールの統計カード/ズーム/CSV/チャート/一括削除/辞書保存はブラウザ手動確認が必要。
- ⏳ API プロキシと `/pf/` SPA フォールバックを含む統合回帰は、BioDB 全サービス起動後に実施する。

## 5. 運用ノート

- **ファイアウォール**（Windows）：`New-NetFirewallRule -DisplayName "PhysioFlow BioDB 5002" -Direction Inbound -Protocol TCP -LocalPort 5002 -Action Allow -Profile Public,Private`（管理者権限）。
- nginx の設定/静的ファイル変更は常に `docker compose build --no-cache nginx && docker compose up -d nginx`（COPY キャッシュの無効化が確実な手順）。
- ランディングの言語選択は `localStorage["biodb_landing_lang"]`（既定 `ja`）。
