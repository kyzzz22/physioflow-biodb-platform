# D5 実装記録 — 実脳波デバイス adapter（Muse EEG）

- **日付**：2026-08-28
- **リポジトリ**：`kyzzz22/physioflow-app`（ブランチ `demo`、D4 コミット `2a8b68c` 基準）
- **目的**：実デバイス（InteraXon Muse）を device connector として接続し、EEG チャンネルを既存のセッション/書き出し/推送パイプラインに流す
- **BioDB 側の変更**：**なし**

> ⚠️ **重要：実機での検証は未実施。** デコードは公開されている OSS 実装を根拠に実装し、構成したバイト列で単体検証したが、開発環境に Muse 実機がないため「実デバイスのデータが BioDB に格納されるまで」の受け入れ（M2）は**未完了**。実機入手後に本稿末尾の手順で再検証すること。

## 設計上の決定

### 1. トランスポートとアダプタの分離
アダプタは**純粋なプロトコル実装**であり、プラットフォーム API には注入された `transport` 経由でのみ触れる：

```
connect(options) -> deviceDescriptor
getCharacteristic(uuid) -> handle
subscribe(handle, handler)     handler は DataView を受け取る
write(handle, bytes)
disconnect()
```

利点：無線なしでプロトコルをテストできる。デスクトップではネイティブ実装に差し替えられる。

### 2. 既定実装が Web Bluetooth である理由と、使えない場所
PF には 3 つの実行形態があり、`navigator.bluetooth` の可否が異なる：

| 実行形態 | コマンド | Web Bluetooth |
|---|---|---|
| ブラウザ開発 | `npm run dev` | ✅（Chromium 系：Chrome / Edge） |
| ホスティング | `npm run hosted:serve` | ✅（同上、HTTPS または localhost） |
| **Tauri デスクトップ** | `npm run desktop:dev` | ❌ WebView2 は当 API を公開しない |

そのため `supportsWebBluetooth()` はデスクトップで `false` を返し、アダプタは暗黙の失敗ではなく明示的なエラーを投げる。デスクトップで BLE を使う場合はネイティブプラグイン由来の transport を注入する（例：`tauri-plugin-web-bluetooth-api`、内部は btleplug）。**本項ではその Rust 依存を導入していない**——ビルド構成と依存ツリーを変えるため独立した判断事項。transport インタフェースはその差し替えを見越してある。

### 3. 通知ストリーム → サンプリング・キュー
Muse は**プッシュ型**（BLE 通知、46.9 ms ごとに 1 パケット＝12 点/チャンネル）だが、`DeviceConnectorSession` の契約は**ポーリング型**（`read(channelId)`）。アダプタは電極ごとに**有界キュー**を持ち、`read()` は最古のサンプルを取り出す。上限は 4096（256 Hz で約 16 秒/チャンネル）で、超過時は最古を破棄する——サンプラーがデバイスより遅い場合でもメモリが無制限に増えない。

### 4. タイムスタンプの再構成
デバイスは時計を持たず uint16 のパケット番号のみを送る。muse-js と同じ方式で、番号の差分 × パケット時間から導出し、16 ビットのラップアroundも処理する。サンプルのタイムスタンプ = パケット時刻 + サンプル位置 × (1000/256) ms。

### 5. Athena ファームウェアは明示的に除外
Muse S Athena（Gen 3, MS_03）は全センサーを単一キャラクタリスティック `273e0013` に多重化し、14-bit LSB-first パッキングと未公開の `dc001` 二重ハンドシェイクを用いる（Classic とは別物）。アダプタは**このキャラクタリスティックを検出したら接続を失敗させる**——推測でデコードして、もっともらしいが誤った EEG 値を出すことを避けるため。

## 実装

| ファイル | 説明 |
|---|---|
| `src/devices/museProtocol.js` | プロトコル定数と純粋なデコード関数（プラットフォーム非依存） |
| `src/devices/transports/webBluetooth.js` | Web Bluetooth の transport 実装と環境判定 |
| `src/devices/museConnector.js` | コネクタ定義とアダプタ（キュー/タイムスタンプ/コマンド手順） |
| `src/devices/index.js` | Muse コネクタ・アダプタ・transport の公開 |
| `src/GraphRuntimeRunnerPage.jsx` | 実行時に `transport` でアダプタを選択（従来は `simulated` のみ） |
| `tests/muse-connector.test.js` | 単体テスト 12 件 |

### コネクタのチャンネル

| チャンネル | 方向 | 型 | 単位 | サンプリングレート |
|---|---|---|---|---|
| `TP9` / `AF7` / `AF8` / `TP10` | input | number | `uV` | 256 Hz |
| `marker` | output | string | — | — |

単位は `µV` ではなく `uV`（JSON/CSV での非 ASCII 文字の符号化差を避けるため）。`includeAux` で `AUX` 電極を追加できる。

### プロトコル要点（Classic ファームウェア）

- サービス UUID：`0xfe8d`
- EEG キャラクタリスティック：`273e0003`（TP9）/ `0004`（AF7）/ `0005`（AF8）/ `0006`（TP10）/ `0007`（AUX）、名前空間 `-4c4d-454d-96be-f03bac821358`
- EEG 通知レイアウト：**uint16 パケット番号（ビッグエンディアン）+ 18 バイトのペイロード**。ペイロードは 12 個の 12-bit ビッグエンディアン・パック済みサンプル（3 バイトごとに 2 サンプル）
- マイクロボルト換算：`uV = 0.48828125 * (raw - 0x800)`（12-bit ADC、中心 2048）
- 制御コマンドは長さ前置フレーム：`[len, ...ASCII, '\n']`。開始手順は `h` → `p21`（EEG のみ、AUX ありは `p20`）→ `s` → `d`
- 実装済みだがサンプラーには未接続：PPG（24-bit、64 Hz）、加速度/ジャイロ（52 Hz、3 点/パケット）、テレメトリ（電池/電圧/温度）

**出典**：デコードと定数は muse-js（`urish/muse-js`、MIT）の実装および muse-rs のプロトコル定数に照合。両者は 12-bit ADC の中心値（2048）とスケール（0.48828125 µV/LSB）で一致する。

## 検証

`tests/muse-connector.test.js`（12 件、全て PASS）：

- 12-bit パック/アンパックのラウンドトリップ（構成バイト、`0x000`/`0x800`/`0xfff` の境界を含む）
- マイクロボルト換算（`0x800` 中心）
- EEG 通知のパケット番号とサンプル数
- テレメトリ / 加速度 / ジャイロのデコードとスケール
- 制御コマンドのフレーム（`d` → `[0x02, 0x64, 0x0a]`）
- コネクタ定義が `validateDeviceConnector` を通ること
- 通知サンプルが `read()` で順番に取り出せること、空キューではエラー
- 開始コマンド列が `['h','p21','s','d']`
- Athena キャラクタリスティック検出時に接続を拒否
- marker はローカル記録（デバイスにハードウェア marker 入力なし）
- キューが有界（上限 8 なら 8 個のみ保持）
- **D5→D4 連携**：Muse コネクタ導入後、`channelDataDictionary()` が 4 つの EEG チャンネル（`uV` / 256 Hz）を正しく生成し、`dictionaryPayload()` がそのまま BioDB へ推送できること

`npm run build` 成功。全テスト 257 件中 256 pass / 0 fail / 1 skipped。新規ファイルの lint は警告なし（`bioDBClient.js` の `btoa`/`Buffer` エラーは D2/D3 からの既存課題で、今回は未着手）。

## 実機入手後の対応（未完了）

1. Chromium 系ブラウザで参加者実行ページを開き、Muse コネクタを導入したプロトコルを実行して接続できることを確認する。
2. デコード値の桁を確認：閉眼安静時に `AF7`/`AF8` で ~10 Hz の α リズム、振幅は数十 µV 程度。全体が ~725 µV ずれていたら中点処理が誤り。
3. 4 チャンネルのクロストークがないこと（各電極が独立キュー）を確認する。
4. フルセッションを通す：収集 → 書き出し（`channel_dictionary.json` に 4 つの `uV` チャンネル）→ BioDB 推送（辞書が実験に反映）。
5. デスクトップで BLE を使う場合はネイティブプラグイン transport の導入を評価する。

## 既知の制約

- 実機検証は未実施（冒頭の警告を参照）。
- デスクトップ（Tauri）では現状利用不可。ブラウザ形態かネイティブ transport の注入が必要。
- Athena（Gen 3）ファームウェアは非対応。
- `read()` はキュー空のときエラーを投げる。サンプラーは 256 Hz 駆動でデバイスの生成レートと整合するが、最初のパケット到着までは一時的にエラーが出る。
- marker はローカル記録のみでデバイスへは書かれない。

## ファイル一覧

| ファイル（PF demo ブランチ） | 種別 |
|---|---|
| `src/devices/museProtocol.js` | 新規 |
| `src/devices/transports/webBluetooth.js` | 新規 |
| `src/devices/museConnector.js` | 新規 |
| `src/devices/index.js` | 変更（公開） |
| `src/GraphRuntimeRunnerPage.jsx` | 変更（transport でアダプタ選択） |
| `tests/muse-connector.test.js` | 新規（12 件） |
