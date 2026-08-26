# .envについて

## 概要

リポジトリ直下の `.env` は、Compose が API コンテナと WebUI のビルドへ渡す秘密値・環境固有値だけを置くファイルである。テンプレートは [`.env.example`](../.env.example) を参照する。

必要な値は以下の3つである。

| 変数 | 用途 |
| --- | --- |
| `APP_SECRET_KEY` | Flask のセッション署名鍵 |
| `APP_JWT_SECRET_KEY` | Auth、Sensor、Event API 間で共有する JWT 署名鍵 |
| `GOOGLE_CLIENT_ID` | Google ID トークンの検証と WebUI の Google Sign-In ボタン |

DB の接続情報と VictoriaMetrics の接続先は `compose.yaml` で固定している。`.env` は Git 管理せず、Docker イメージにもコピーしない。Compose がコンテナの実行時に環境変数として渡す。
