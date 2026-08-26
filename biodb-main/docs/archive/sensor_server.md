# Sensor_server endpoint

## 概要

このドキュメントはセンサ情報を取り扱うSensor Serverについてのドキュメントです．

## JWTの付与について

[jwt.md](./jwt.md)を参照すること

## タイムスタンプについて

[time.md](./time.md)を参照すること

## エンドポイント一覧

現状ではread,writeの二つのみ用意している．nginxにて/sensorで振り分けているので，実装では/sensorは省略されているが，ここでは実利用を想定して，/sensor付きで掲載する．

| エンドポイント | 説明 | 使えるメソッド | 必要なJWTの種類 |
| -- | -- | -- | -- |
| /sensor/data/write | データの書き込み用エンドポイント | POST | sensor write JWT |
| /sensor/data/read | データの読み込み用エンドポイント | POST | sensor read JWT |

## 各エンドポイントの詳細説明

### /sensor/data/write

sensor write属性のJWTが必要

```json
{
  "compression": "gzip",
  "data": "H4sIAAAAAAAAE8tIzcnJBwCGphA2BQAAAA==",
  "format": "json"
}
```

| key | 説明 |
| -- | -- |
| compression | 圧縮方式(["gzip", "lz4", "brotli", "none"]) |
| format | データ形式(["json", "messagepack"]) |
| data | 圧縮後のデータ(b64encode) |

dataの中身

```json
{
    "time": ["", "", ...],
    "data1": [0.1, 0.2, ...],
    "data2": [0.3, null, ...],
    ....
}
```

timeはタイムスタンプかISOフォーマットの文字列のリスト．

他のkeyはtimeと同じ長さのリスト，仮に欠損値の場合はnullを入れてください．他のkeyの名前は自由です．keyの名前はreadでのrowsでの指定に使います．

データのJsonが出来たら，formatとcompressionをPOSTボディに書いたとおりにします．

1. formatによって以下の動作を行う

| format | 動作 |
| -- | -- |
| json | json文字列にutf-8エンコードをかけバイトオブジェクトにする |
| messagepack | messagepack形式のバイトオブジェクトにする |

2. compressionによって以下の動作を行う

| compression | 動作 |
| -- | -- |
| gzip | 上記のバイトオブジェクトをgzip方式で圧縮 |
| lz4 | 上記のバイトオブジェクトをlz4方式で圧縮 |
| brotli | 上記のバイトオブジェクトをbrotli方式で圧縮 |
| none | 圧縮しない |

3. 圧縮後のデータをutf-8デコードして文字列に変換．POSTのボディに含めて送信

### /sensor/data/read

sensor read属性のJWTが必要

```json
{
  "compression": "gzip",
  "end_time": "2025-01-01T01:00:00Z",
  "format": "json",
  "rows": [
    "EEG_MuseS_TP10",
    "PPG_MuseS_IR16"
  ],
  "start_time": "2025-01-01T00:00:00Z"
}
```

| key | 説明 |
| -- | -- |
| compression | 圧縮方式(["gzip", "lz4", "brotli", "none"]) |
| format | データ形式(["json", "messagepack"]) |
| start_time | 読み取りたいデータの範囲の開始時刻 |
| end_time | 読み取りたいデータの範囲の終了時刻 |
| rows | 読み取りたいデータの名前 |

クライアントはデータを利用するために圧縮済みのデータをwriteの手順の逆で復元を行う必要があります．

1. 送られてきたデータをutf-8エンコードでバイトオブジェクトにする

2. compressionによって以下の動作を行う

| compression | 動作 |
| -- | -- |
| gzip | バイトオブジェクトをgzip方式でデコード |
| lz4 | バイトオブジェクトをlz4方式でデコード |
| brotli | バイトオブジェクトをbrotli方式でデコード |
| none | 何もしない |

3. formatによって以下の動作を行う

| format | 動作 |
| -- | -- |
| json | バイトオブジェクトをutf-8方式でデコード．Jsonとして読み込み |
| messagepack | バイトオブジェクトをmessagepack方式で読み込み |