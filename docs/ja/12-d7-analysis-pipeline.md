# D7 実装記録 — 分析パイプライン

- **日付**：2026-08-29
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、D6 コミット `5a554cb` 基準）
- **目的**：前処理（リサンプル/フィルタ/アーティファクト除去）・特徴（HRV/EDA/スペクトル）・統計/ML を実装し、BioDB の読戻しを消費してセッション・パッケージに成果を格納する
- **BioDB 側の変更**：**なし**（`/sensor/data/features` と `/sensor/analysis/*` を利用）

## 背景

D3 で読戻し、D6 で結合書き出しができたが、書き出されるのは**生の時系列**のままだった。
心拍変動や周波数帯パワーを得るには研究者が自前でスクリプトを書く必要があった。
D7 は「前処理 → 特徴 → 統計/ML」を PF 内蔵パイプラインとして実装し、分析結果を書き出しに同梱する。

## 設計上の決定

### 1. ローカル実装とサーバ側エンドポイントを併存させる
BioDB は `/sensor/data/features`（サーバ側特徴）と `/sensor/analysis/*`（kmeans/regression の学習・推論）を既に備える。
それでも PF 側に**完全なローカル実装**を置く理由：

- BioDB へ未推送のローカル・セッションも解析したい
- アルゴリズムをオフラインで検証・単体テストしたい
- 分析結果をネットワーク到達性に縛られたくない

両者は e2e で突き合わせ（サンプルレート一致）、置換ではなく相互参照とする。

### 2. 依存追加ゼロ
FFT（radix-2 Cooley-Tukey）、リッジ回帰（Gauss-Jordan）、k-means、t 分布の p 値はすべて自前実装。
理由：PF はフロントエンドであり数値ライブラリの追加はバンドルを大きく増やす。また構成信号で正しさを直接検証できる。

### 3. 欠損は補間するが外挿しない
書き出し CSV では欠損を空欄にする（D6 の取り決め）が、**分析前には補間が必須**——FFT も HRV も穴を扱えない。
折衷：内部の空隙は線形補間し、**先頭と末尾は最近傍の観測値**（生理信号を外挿しない）。結果に `missing` と `interpolatedFraction` を記録する。

### 4. アーティファクト除去は移動中央値残差ではなく一次差分で
初版は「信号 − 移動中央値」のロバスト z スコアだったが、テストが深刻な問題を露呈した。100 点中 **39 点**の正常点を誤剔除した。
原因は移動中央値がどんな湾曲信号にも系統的な遅れ残差を残すため、それをノイズ尺度にすると通常の変動までアーティファクト化される。
**一次差分 + MAD** に変更：スパイクは差分で急峻な跳躍になり、平滑な信号はそうならない。修正後は同一データで 3 点のみ（スパイク位置とその近傍）を剔除し、正常点は元値を保持した。

### 5. サンプルレート不明時は推測せず縮退する
タイムラインからレートを決定できない場合は時間領域統計のみを出し、**スペクトルと HRV は出さない**。理由は `warnings` に明記する。
既定値を埋めない——推測を誤ると周波数領域の結果全体が暗黙のうちに歪む。

## 実装

| ファイル | 説明 |
|---|---|
| `src/analysis/signal/preprocess.js` | 欠損補間、リサンプル、移動平均/中央値、トレンド除去、アーティファクト除去 |
| `src/analysis/signal/spectrum.js` | radix-2 FFT、ピリオドグラム PSD、帯域パワー（絶対＋相対）、主周波数 |
| `src/analysis/signal/features.js` | 時間領域統計、ピーク検出、RR 間隔、HRV 時間/周波数領域、EDA の tonic/phasic 分解と SCR |
| `src/analysis/signal/stats.js` | 記述統計、Pearson、Welch の t 検定、Cohen's d、リッジ回帰、k-means |
| `src/analysis/signal/pipeline.js` | 統括：チャンネル識別 → 分析 → JSON/CSV 生成 |
| `src/bioDBClient.js` | `fetchBioDBFeatures` / `trainBioDBModel` / `predictBioDB` / `listBioDBAnalyses` |
| `src/data/jointExport.js` | 結合書き出しに `analysis/` を同梱し、パイプラインの警告を manifest に引き上げる |

### チャンネル識別

チャンネル ID と単位で特徴族を振り分け、未識別は汎用時間領域統計（常に安全）に落とす：

| 族 | トリガ | 特徴 |
|---|---|---|
| `cardiac` | `ecg`/`ekg`/`ppg`/`bvp`/`blood_volume` | HRV 時間領域（SDNN/RMSSD/pNN50/平均心拍）＋周波数領域（VLF/LF/HF/LF-HF） |
| `eda` | `eda`/`gsr`/`electrodermal`、または単位 `uS` | tonic 水準、phasic 変動、SCR 回数と振幅 |
| `eeg` | `eeg`/`tp9`/`af7`/`af8`/`tp10`/`aux`、または単位 `uV` | 帯域パワー（EEG 5 帯域を含む） |
| `generic` | その他 | 平均/標準偏差/最小最大/RMS/分位/主周波数 |

### アーカイブ構成

```
analysis/analysis.json    完全な結果（warnings を含む）
analysis/analysis.csv     チャンネルごと 1 行に平坦化した特徴
```

## 検証

`node e2e-d7.mjs`（認証情報は環境変数）全 PASS。**構成した既知信号**を推送 → 読戻し → 分析し、真値を復元できるかで検証した：

```
→ 300 samples/channel at 10 Hz (ecg, eda, eeg)
✓ run local analysis pipeline
   → sample rate 10 Hz, channels: ecg, eda, eeg
      ecg (cardiac): HR=60.0 bpm, RMSSD=0.0
      eda (eda):     tonic=2.16, SCR=3
      eeg (eeg):     peak=1.99 Hz
✓ server-side /data/features
   → server: 300 points @ 10 Hz
   → sample rates agree (local 10 vs server 10)
✓ train kmeans on BioDB      → model kmeans_42_..., inertia 64.69
✓ predict with the trained model
✓ train regression on BioDB
✓ list stored analyses       → 8 analysis record(s)
✓ local ridge regression recovers a known slope   → r2 1.000000
✓ local kmeans separates two planted clusters     → 2 clusters
✓ joint export carries the analysis               → 19 files, 3 channels
```

数値の照合：60 bpm の心拍を構成 → 60.0 bpm を測定。3 回の皮膚コンダクタンス反応を構成 → 3 回を検出。2 Hz の正弦波を構成 → 1.99 Hz を測定（FFT 分解能 0.039 Hz）。
リッジ回帰は既知の傾き `1.5 + 3a - 2b` を復元し、r² = 1.000000。

単体テスト `tests/analysis-pipeline.test.js` **19 件** と `tests/joint-export.test.js` 追加 2 件：

- 欠損補間（内部は補間／端は保持）、リサンプルの長さ比、移動中央値のスパイク耐性、トレンド除去
- **アーティファクト除去がスパイクのみを捉え正常点を変更しないこと**（上記修正の回帰テスト）
- FFT が純音の周波数を復元し、2 の冪でない長さを拒否すること
- ピーク検出と RR 間隔が模擬心拍を復元すること。規則／不規則リズムの RMSSD・SDNN 分離
- EDA の tonic と SCR 計数。チャンネル振り分けが各特徴族に当たること
- Pearson / Welch の t / Cohen's d。リッジ回帰の係数復元。k-means の決定性と分簇
- パイプラインが BioDB の列形式を読み、サンプルレートを推定し、欠損を報告し、レート不明時に縮退し、チャンネル指定に従うこと
- 結合書き出しが分析を同梱して警告を引き上げること／同梱しない場合に不在を記録すること

`npm run build` 成功。全テスト 285 件中 284 pass / 0 fail / 1 skipped。新規ファイルの lint は警告なし。

## 過程で発見・修正した e2e 自身の物理的誤り

初回 e2e で EEG を 10 Hz のアルファ波として構成したが、推送のサンプルレートは 10 Hz——**5 Hz のナイキスト限界を超えており必然的にエイリアスする**。
測定値は `peak=0.94 Hz`（エイリアス生成物）だったのに、許容誤差を ±5 Hz と書いていたため見逃した。

修正：2 Hz（レートで表現可能）に変更し、許容誤差を**FFT 分解能 2 個分**（0.078 Hz）に絞った。修正後は 1.99 Hz を測定。

教訓：緩い許容誤差は誤った実装を検証通過させ、検証しないのと同じである。

## 既知の制約

- サーバ側回帰の r² は低い（0.008）。e2e で**もともと線形関係のない** `ecg/eeg/eda` をデモに使っているためで、欠陥ではない。
- HRV の周波数領域は 4 Hz 補間グリッド（HRV 解析の慣例）。短い窓（RR 間隔 4 個未満）では周波数領域を出さない。
- ピーク検出の閾値は信号振幅に対する固定比。極端な振幅漂移のある信号では `sensitivity` の調整が必要な場合がある。
- チャンネル注釈の UI は未実装——現状はチャンネル ID/単位の取り決めで識別する。
- 分析は窓全体の一括計算で、スライディング窓/分割は未対応。

## 依存

- D3（読戻し）/ D4（チャンネル辞書）/ D6（結合書き出し）— 前提、全て完了
- BioDB `/sensor/data/features` と `/sensor/analysis/*` — 前提、完了

## ファイル一覧

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/analysis/signal/preprocess.js` | 新規 |
| `src/analysis/signal/spectrum.js` | 新規 |
| `src/analysis/signal/features.js` | 新規 |
| `src/analysis/signal/stats.js` | 新規 |
| `src/analysis/signal/pipeline.js` | 新規 |
| `src/bioDBClient.js` | 変更（分析エンドポイント 4 件） |
| `src/data/jointExport.js` | 変更（分析を同梱） |
| `tests/analysis-pipeline.test.js` | 新規（19 件） |
| `tests/joint-export.test.js` | 変更（+2 件） |
| `e2e-d7.mjs` | 新規 |
