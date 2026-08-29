# D8 実装記録 — 可視化

- **日付**：2026-08-29
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、D7 コミット `b1e2267` 基準）
- **目的**：履歴マルチチャンネル曲線・リアルタイム表示・感情マップを実装し、D3 の読戻しと D7 の分析結果を可視化する
- **BioDB 側の変更**：**なし**

## 背景

D3 で読戻し、D7 で特徴算出ができたが、読戻しパネルは単一チャンネルの簡易図だけで、D7 の結果は JSON を見るしかなかった。
D8 は提示層を埋める：マルチチャンネル重ね描き、リアルタイム窓、感情マップ、そして D7 特徴の図示。

## 設計上の決定

### 1. 幾何計算と描画の分離
座標変換、間引き、目盛り、パス生成はすべて `chartGeometry.js` の**純関数**に置き、コンポーネントは返り値を描くだけにする。
利点は D7 と同じ——**グラフの数学を DOM なしで単体テストできる**。今回「パスに NaN が含まれない」「マーカーが描画領域内に収まる」を検証できたのはこの前提による。

### 2. Canvas ではなく SVG
既存の `analysis/charts.js` は Canvas 2D（棒グラフ/散布図）。D8 の新規部分は SVG にした：

- パスは文字列であり、アサーションやスナップショットが可能
- ブラウザのネイティブ拡縮で高解像度でも劣化しない
- イベントマーカーやホバー円に直接 DOM イベントを張れる

Canvas の既存グラフはそのまま（正常に動いており、書き直す利点がない）。

### 3. 間引きは min/max 方式（単純間引や平均ではなく）
256 Hz で 5 分の EEG は 76,800 点になり、約 600 ピクセルに押し込む——全部描けば遅く、かつ誤解を招く。
ピクセルごとにバケット化し、**各バケットの min と max を保持**することで視覚的エンベロープ（ピークが平均で消えない）を保つ。目が実際に読んでいるのはこれである。

### 4. 欠損はゼロで描かず線を切る
`seriesPath` は null に当たるとサブパスを切り（新しい `M` コマンド）、ゼロまで落ちる線をつなげない。
D6 で「欠損は空欄、0 埋めしない」と決めており、可視化もそれに従う必要がある——ゼロで描けばデータ欠損が「0 を観測」に偽装される。

### 5. リアルタイムは rAF で間引き、データ源は呼び出し側が注入
256 Hz で「サンプルごとに再描画」はメインスレッドを飢えさせるため、`requestAnimationFrame` でフレームごとに取得する。
D9（ストリーミング推送）は未完で、デバイス runtime からこのパネルへは流れてこない。そのため `sampleSource` は**呼び出し側注入**にした。
データ源がなくても渡された `samples` は描画できる（録画セッションの再生に使える）。

## 実装

| ファイル | 説明 |
|---|---|
| `src/analysis/chartGeometry.js` | 純幾何：min/max 間引き、座標変換と逆変換、nice 目盛り、パス/エリアパス、イベントマーカーのスナップ、感情座標 |
| `src/analysis/MultiChannelChart.jsx` | 履歴マルチチャンネル曲線：重ね描き、イベントマーカー、ホバー読み取り、ドラッグ拡大 |
| `src/analysis/LiveChart.jsx` | リアルタイム窓：スライドバッファ、rAF 取得、一時停止/再開 |
| `src/analysis/FeaturePanel.jsx` | D7 結果の可視化：指標ブロック、帯域スタックバー、HRV、EDA |
| `src/analysis/AffectMap.jsx` | 感情マップ：価値-覚醒サーカムプレックス、象限の色分けと件数、軌跡線 |
| `src/DataPanel.jsx` | 4 ビュー（単一/全チャンネル/特徴/感情マップ）を接続 |
| `src/questionnaire.css` | D8 のスタイル（ダークモード対応） |

### ビュー切替

D3 のデータパネルに 4 ビューを追加し、既定は「全チャンネル」：

| ビュー | データ源 |
|---|---|
| Single series | 単一チャンネル（D3 既存の簡易図） |
| All channels | BioDB 読戻し ＋ イベント一覧を重ね描き |
| Features | D7 パイプラインによる現在窓の分析結果 |
| Affect map | イベント中の価値/覚醒（研究が記録していれば） |

## 検証

`node e2e-d8.mjs`（認証情報は環境変数）全 PASS。モックではなく**実際の読戻しデータ**（推送 → 読戻し、VictoriaMetrics の可視化待機を含む）で検証した：

```
→ 200 samples/channel at 10 Hz (eeg, eda, ecg)
✓ read session back
✓ geometry: every channel produces a finite SVG path
✓ geometry: decimation bounds the point count
✓ geometry: event markers land inside the plot
✓ render: MultiChannelChart emits an SVG with one path per channel
✓ D7 pipeline over the read-back window
✓ render: FeaturePanel shows the analysed channels
✓ render: AffectMap plots valence/arousal points
✓ render: empty inputs degrade to a message, not a crash
✓ data panel exposes the D8 views
```

コンポーネントは Vite の SSR ローダーで静的マークアップに描画した（Node は `.jsx` を直接読めない）。SVG 要素数、イベントラベルの存在、さらに**描画結果に NaN/Infinity が含まれないこと**をアサートしている。

単体テスト `tests/visualization.test.js` **19 件**：

- 間引きがピークのエンベロープを保持し、出力インデックスが単調、小系列はそのまま通過
- 極値が null を無視。**平坦系列にゼロ高ではなく対称バンド**を与える
- 座標変換が末端を右端に一致させ、逆変換が往復一致
- nice 目盛りが丸い刻み幅を選び、退化範囲で縮退
- **データの空洞でパスが切れる**（`M` コマンドが 2 回現れることをアサート）かつ NaN を含まない
- イベントマーカーが最寄りサンプルにスナップし、窓外イベントを捨てる
- 感情座標の SAM 1..9 → -1..1 変換。象限名がサーカムプレックスの慣例に従う
- **D7 結果が FeaturePanel の読む全フィールドを保持**（リネーム回帰を防止）

`npm run build` 成功。全テスト 304 件中 303 pass / 0 fail / 1 skipped。新規ファイルの lint は警告なし。

## 過程で発見・修正した 2 つの実際の欠陥

**1. タイムゾーンのバグ（軸ラベルが閲覧者の場所で変わる）**

`formatAxisTime` が `getHours()` などの**ローカルタイム**メソッドを使っていた。BioDB は UTC で保持するため、同じ記録が北京では `19:20:30`、ロンドンでは `11:20:30` と表示される——拠点をまたぐチームでスクリーンショットと書き出しが突き合わせられない。
`getUTCHours()` などの UTC メソッドに変更し、理由をコメントに明記した。テスト名は `locale-independent` である。

**2. 正規化の意味がコメントと不一致（小さな単位のチャンネルが潰される）**

`normalizeSeries` のコメントは「各チャンネルが自身のスケールを保つ」とあったが、実装は**大域 extent** を使っていた。軽微ではない：EDA は 2 µS 規模、EEG は数十 µV であり、大域正規化は単位の小さいチャンネルを一直線に潰す。
**チャンネルごとの独立正規化**に修正し、EDA と EEG がそれぞれ全高を使うことをアサートする回帰テストを追加した。

どちらもテストが炙り出した——先にアサーションを書き、実装がコメントに見合うか確かめる、という手順の価値である。

## 既知の制約

- **リアルタイム表示は実デバイスストリームに未接続**：データ源は呼び出し側注入であり、D9 完了後に device runtime へ直結できる。
- 感情マップはイベント中の valence/arousal に依存。研究が収集していなければ空になる（空状態の表示があり、欠陥ではない）。
- マルチチャンネル重ね描きでは各チャンネルが独立スケールになるため、振幅は**チャンネル間で比較できない**（凡例に単位を出すが、明示的な警告バーは未実装）。
- ドラッグ拡大は一回きりのブラシ選択で、パンと複数段ズーム（Reset のみ）は非対応。
- 大規模データ（10 万点超）の性能ベンチマークは未実施。間引き予算による保護のみ。

## 依存

- D3（読戻しとイベント）/ D7（分析結果）— 前提、全て完了
- D9（ストリーミング推送）— リアルタイムの完全形に必要。現状は録画データの再生が可能

## ファイル一覧

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/analysis/chartGeometry.js` | 新規 |
| `src/analysis/MultiChannelChart.jsx` | 新規 |
| `src/analysis/LiveChart.jsx` | 新規 |
| `src/analysis/FeaturePanel.jsx` | 新規 |
| `src/analysis/AffectMap.jsx` | 新規 |
| `src/DataPanel.jsx` | 変更（4 ビュー接続） |
| `src/questionnaire.css` | 変更（D8 スタイル） |
| `tests/visualization.test.js` | 新規（19 件） |
| `e2e-d8.mjs` | 新規 |
