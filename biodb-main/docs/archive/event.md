# イベントデータサーバ

## 概要

このドキュメントはイベントデータを取り扱うevent serverについてのドキュメントです．

## JWTの付与について

[jwt.md](./jwt.md)を参照すること

## タイムスタンプについて

[time.md](./time.md)を参照すること

## エンドポイント一覧

nginxにて/eventで振り分けているので，実装では/eventは省略されているが，ここでは実利用を想定して，/event付きで掲載する．

| エンドポイント | 説明 | メソッド | JWT属性 |
| -- | -- | -- | -- |
| /event/events | イベント作成 | POST | event |
| /event/events | イベント取得 | GET | event |
| /event/events/<event_id> | イベント削除 | DELETE | event |
| /event/events/<event_id> | イベント更新 | POST | event |

## 各エンドポイントの詳細

### /event/events POST

event属性のJWTが必要

イベントの作成を行う．

**POST Body**

```json
{
  "description": "Morning jogging session",
  "details": {
    "duration": "30min",
    "location": "park"
  },
  "end_time": "2025-01-01T12:30:00Z",
  "event": "Running",
  "start_time": "2025-01-01T12:00:00Z",
  "user_id": "nanoid"
}
```

| key | 説明 |
| -- | -- |
| event | イベントを説明する文字列．端的な表現を想定 |
| description | イベントに関する追加説明．長めの補足事項等を想定 |
| user_id | どのユーザIDのユーザのイベントなのか |
| start_time | イベントの開始時間 |
| end_time | イベントの終了時間 (オプション．ない場合は開始時刻と同じ時刻が入力される) |
| details | メタデータ等のその他の情報．辞書型 |

### /event/events GET

event属性のJWTが必要

イベントリストの取得を行う

クエリパラメータでフィルターをかけられる

#### role

roleによって，自身が作成したイベントか，自身を対象に作成されたイベントの一覧となる．

| role |  |
| -- | -- |
| experimenter | 実験者が被計測者を対象に作成したイベントの一覧を返却 |
| participant | 被計測者を対象に作成されたイベントの一覧を返却 |

#### start_time(Optional)

start_timeにはISOフォーマットの日時で指定できる．(任意)

start_timeより後の時刻のイベントを取得する．

#### end_time(Optional)

end_timeにはISOフォーマットの日時で指定できる．(任意)

end_timeより前の時刻のイベントを取得する．

### /event/events/<event_id> DELETE

event属性のJWTが必要

event_idのイベントを削除する．イベント作成者のみ実行可能．

### /event/events/<event_id> POST

event属性のJWTが必要

event_idのイベントを更新する．イベント作成者のみ実行可能．

**POST Body**

```json
{
  "description": "Morning jogging session",
  "details": {
    "duration": "30min",
    "location": "park"
  },
  "end_time": "2025-01-01T12:30:00Z",
  "event": "Running",
  "start_time": "2025-01-01T12:00:00Z"
}
```

| key | 説明 |
| -- | -- |
| event | イベントを説明する文字列．端的な表現を想定 |
| description | イベントに関する追加説明．長めの補足事項等を想定 |
| user_id | どのユーザIDのユーザのイベントなのか |
| start_time | イベントの開始時間 |
| end_time | イベントの終了時間 |
| details | メタデータ等のその他の情報．辞書型 |