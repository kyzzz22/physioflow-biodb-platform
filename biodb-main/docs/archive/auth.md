# 認証サーバについて

## 注意

jwt発行以外のAPIについてはWebUIから叩くことを想定しており，一般クライアントは叩くことは少ないAPIとなります．

## 動機

実はこのEmoDBの実装や検討において，一番手間をかけた部分が認証周りとなります．センサ情報に関しては応答を早くしつつも，権限を持たないデータに対するアクセスは禁止できるような仕組みが必要になるためです．

基本的にDBとしての機能しか提供していないこのアプリケーションに於いて認証認可をしっかり作りこむのにはいろいろ理由があります．とりあえず，以下の通り

- 生体情報は個人情報
    - 生体情報は被計測者に帰属する個人情報である
    - システム管理者を除く，許可を与えていない他人がデータにアクセス出来てはまずい
- サービスとしてインターネット上からアクセスできる必要がある
    - 生体情報は移動中であっても，発生しうる
        - ウェアラブル計測機器の台頭
            - スマートウォッチ
            - スマートリング
            - バンド型の装置
    - リアルタイムな生体情報利用には世界中からアクセスできるシステムである必要性
        - アプリ例
            - EEGフィードバックシステム
            - 感情推定と利用

そして，生体情報は膨大になる可能性が非常に高い，現状だとサーバの分散化までは行えていないが，バックエンドとして分散DBの利用や，k8sの利用まで考えると，分散させやすい認証システムである必要性がある．

そのため，このプロジェクトでは認証は通常のフローで行うが，認可にはJWT[./jwt.md](./jwt.md)を利用することでサーバを機能的に分割して，機能ごとにリソース割り当てなどをやりやすいように実装を行うものとした．

## エンドポイント

nginxにて/authで振り分けているので，実装では/authは省略されているが，ここでは実利用を想定して，/auth付きで掲載する．

| エンドポイント | 説明 | HTTPメソッド | 必要なJWTの種類 |
| -- | -- | -- | -- |
| /auth/user/info | ユーザ情報の返却 | GET | WebUI or WebService |
| /auth/user/info | ユーザ情報の更新 | POST | WebUI |
| /auth/user | ユーザの作成 | POST | WebUI(admin only) |
| /auth/participant | 被計測者の作成 | POST | WebUI |
| /auth/participant | 被計測者一覧の返却 | GET | WebUI |
| /auth/participant/<participant_id> | 被計測者の更新 | POST | WebUI |
| /auth/participant/<participant_id> | 被計測者の返却 | GET | WebUI |
| /auth/google/callback | GoogleのOAuth用 | POST | None |
| /auth/token | 長期トークン生成用エンドポイント| POST | WebUI |
| /auth/token | ユーザが作成したトークン一覧の返却 | GET | WebUI |
| /auth/token/<token_id> | token_idのトークンの更新(有効無効の切り替え) | POST | WebUI |
| /auth/token/<token_id> | token_idのトークンの削除 | DELETE | WebUI |
| /auth/jwt/sensors/writejwt | センサデータ書き込み用JWTの発行 | POST | トークン認証 |
| /auth/jwt/sensors/readjwt | センサデータ読み込み用のJWTの発行 | POST | トークン認証 |
| /auth/jwt/events | イベント管理用JWTの発行 | POST | トークン認証 |
| /auth/jwt/service/sensors/readjwt | センサデータ読み込み用のJWTの発行 | POST | WebService |
| /auth/jwt/service/events | イベント管理用JWTの発行 | POST | WebService |

## 各エンドポイントの詳細

### /auth/user/info GET

WebUIまたはWebService属性を持つJWTが必要

JWTを発行したユーザのユーザ情報を返却

**ResponseBody**

```json
{
  "birthdate": "1990-01-01",
  "email": "user@example.com",
  "id": "nanoid",
  "name": "John Doe",
  "sex": 1
}
```
| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列 |
| email | emailアドレスの文字列 |
| id | ユーザIDの文字列 |
| name | ユーザの名前 |
| sex | ISO5218に基づいた性別 |

### /auth/user/info POST

WebUI属性を持つJWTが必要

JWTを発行したユーザのユーザ情報を更新する

誕生日と名前，性別を更新可能．

**POST Body**

```json
{
  "birthdate": "1990-01-01",
  "name": "John Doe",
  "sex": 1
}
```

| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列 |
| name | ユーザの名前 |
| sex | ISO5218に基づいた性別 |

### /auth/user POST

管理者ユーザのWebUI属性を持つJWTが必要．

新しいユーザを作成する．

**POST Body**

```json
{
  "email": "user@example.com",
  "role": "normal"
}
```

| key | 説明 |
| -- | -- |
| email | emailアドレスの文字列 |
| role | 権限(現在はnormalのみ受け付け) |

### /auth/participant POST

WebUI属性のJWTが必要．

新しい被計測者を作成する．

**POST Body**

```json
{
  "birthdate": "1990-01-01",
  "email": "user@example.com",
  "name": "John Doe",
  "sex": 1
}
```

| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列 |
| email | emailアドレス文字列 |
| name | 被計測者の名前 |
| sex | ISO5218に基づいた性別 |

### /auth/participant GET

WebUI属性のJWTが必要．

全ての被計測者の一覧を取得する．participantsにリストで格納される．

**ResponseBody**

```json
{
  "code": 200,
  "message": "success",
  "participants": [{
    "birth_date": "1990-01-01",
    "email": "user@example.com",
    "id": "nanoid",
    "is_enable": true,
    "name": "John Doe",
    "sex": 1
  }]
}
```

| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列 |
| email | emailアドレス文字列 |
| id | 被計測者ID |
| is_enable | 有効かどうか |
| name | 被計測者の名前 |
| sex | ISO5218に基づいた性別 |

### /auth/participant/<participant_id> POST

管理者ユーザのWebUI属性のJWTが必要．

対象の被計測者の情報を更新する．更新したい項目のみでも受け付ける．

**POST Body**

```json
{
  "birth_date": "1990-01-01",
  "is_enable": false,
  "name": "John Doe",
  "sex": 1
}
```

| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列(オプション) |
| is_enable | 有効かどうか(オプション) |
| name | 被計測者の名前(オプション) |
| sex | ISO5218に基づいた性別(オプション) |

### /auth/participant/<participant_id> GET

WebUI属性のJWTが必要．

対象の被計測者の情報を取得する．

**Response Body**

```json
{
  "code": 200,
  "message": "success",
  "participant": {
    "birth_date": "1990-01-01",
    "email": "user@example.com",
    "id": "nanoid",
    "is_enable": true,
    "name": "John Doe",
    "sex": 1
  }
}
```

| key | 説明 |
| -- | -- |
| birthdate | ISOフォーマットの日時の文字列 |
| email | emailアドレス文字列 |
| id | 被計測者ID |
| is_enable | 有効かどうか |
| name | 被計測者の名前 |
| sex | ISO5218に基づいた性別 |

### /auth/google/callback POST

Google認証を使った，認証用のエンドポイント

認証に成功したら，WebUIまたはWebService属性のJWTを返却

Googleの認証コードをBearerトークンとして付加

**POST Body**

```json
{
  "role": "manage"
}
```

### /auth/token POST

WebUI属性のJWTが必要

JWTのユーザの長期トークン生成を行うエンドポイント

**POST Body**

```json
{
  "description": "This is an API token for data access",
  "expiration_days": 30,
  "scopes": [
    "all"
  ]
}
```

| key | 説明 |
| -- | -- |
| description(Optional) | トークンの補足文用．任意 |
| expiration_days | トークンの有効期間(日)．1-365まで |
| scopes | トークンの権限範囲．現状はallのみ |

#### TODO

- 権限範囲を細かく設定できるようにする
    - eventとかsensor readとか

### /auth/token GET

WebUI属性のJWTが必要

JWTのユーザの長期トークンの一覧を返却

**Response Body**

```json
{
  "tokens": [
    {
      "created_at": "Thu, 16 Jan 2025 09:07:38 GMT",
      "description": "testtoken",
      "expired_at": "Wed, 16 Apr 2025 09:07:38 GMT",
      "is_active": true,
      "scopes": [
        "all"
      ],
      "token_id": "7897a60bf9edb707aa66dabb4d03829f313e958f856b9ef7cff5dac83b6c58a2",
      "user_id": "Av5IbAJxwxv7IaU3nlczT"
    }
  ]
}
```

tokenのリストとして返却

tokenの構造

| key | 説明 |
| -- | -- |
| created_at | トークン作成日時 |
| expired_at | トークンの失効日時 |
| description(Optional) | トークンの説明．任意 |
| is_active | トークンが現在有効かどうか |
| scopes | 権限範囲を表現する文字列のリスト |
| token_id | トークンのID(生トークン文字列のハッシュ化したもの) |
| user_id | トークンの所有者のID |

### /auth/token/<token_id> POST

WebUI属性のJWTが必要

JWTのユーザのトークンの有効無効を切り替え

**POST Body**

```json
{
  "is_active": true
}
```

| key | 説明 |
| -- | -- |
| is_active | 有効ならTrue,無効ならFalse |

### /auth/token/<token_id> DELETE

WebUI属性のJWTが必要

JWTのユーザのトークンの削除

### /auth/jwt/sensor/writejwt POST

トークン認証のみ

sensor serverにデータを書き込みするためのJWTを発行する(sensor write属性)

**POST Body**

```json
{
  "end_time": "2025-01-01T01:00:00Z",
  "participant_id": "Av5IbA...",
  "start_time": "2025-01-01T00:00:00Z",
  "token": "a7b6c5d4e3f2g1h0...",
  "user_id": "Av5IbA..."
}
```

| key | 説明 |
| -- | -- |
| start_time | 書き込み許可の開始時間 |
| end_time | 書き込み許可の終了時間 |
| user_id | 書き込みを行うユーザのID |
| participant_id | 被計測者のユーザID |
| token | 生のトークン文字列 |

### /auth/jwt/sensor/readjwt POST

トークン認証のみ

sensor serverからデータを読み出すためのJWTを発行する(sensor read属性)

**POST Body**

```json
{
  "end_time": "2025-01-01T01:00:00Z",
  "participant_id": "Av5IbA...",
  "start_time": "2025-01-01T00:00:00Z",
  "token": "a7b6c5d4e3f2g1h0...",
  "user_id": "Av5IbA..."
}
```

| key | 説明 |
| -- | -- |
| start_time | 書き込み許可の開始時間 |
| end_time | 書き込み許可の終了時間 |
| user_id | 書き込みを行うユーザのID |
| participant_id | 被計測者のユーザID |
| token | 生のトークン文字列 |

### /auth/jwt/events POST

トークン認証のみ

event serverのイベントデータのCRUDを行うためのJWTを発行する(event属性)

**POST Body**

```json
{
  "end_time": "2025-01-01T01:00:00Z",
  "participant_id": "Av5IbA...",
  "start_time": "2025-01-01T00:00:00Z",
  "token": "a7b6c5d4e3f2g1h0...",
  "user_id": "Av5IbA..."
}
```

| key | 説明 |
| -- | -- |
| start_time | 書き込み許可の開始時間 |
| end_time | 書き込み許可の終了時間 |
| user_id | 書き込みを行うユーザのID |
| participant_id | 被計測者のユーザID |
| token | 生のトークン文字列 |

### /auth/jwt/service/sensors/readjwt POST

WebService属性のJWTが必要

sensor serverからデータを読み出すためのJWTを発行(sensor read属性)

googleのOAuthを使ったwebAppを作りたい場合はこっちの方が都合がいい

**POST Body**

```json
{
  "end_time": "2025-01-01T01:00:00Z",
  "participant_id": "Av5IbA...",
  "start_time": "2025-01-01T00:00:00Z",
  "user_id": "Av5IbA..."
}
```

| key | 説明 |
| -- | -- |
| start_time | 書き込み許可の開始時間 |
| end_time | 書き込み許可の終了時間 |
| user_id | 書き込みを行うユーザのID |
| participant_id | 被計測者のユーザID |
