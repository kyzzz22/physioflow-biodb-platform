# JWTの詳細について

## JWTとは

JSON Web Token (JWT) は，認証や情報の安全なやり取りに使われるトークンフォーマットです．

詳細は [公式ドキュメント](https://jwt.io/) を参照してください．

## このアプリケーションにおけるJWTの立ち位置

このアプリケーションではJWTはセンサデータのやり取りや，イベントデータのやり取りをステートレスに行える手法として採用しています．

もっと端的に表現すると，JWTは短期トークンとして利用されています．

基本的に，JWTの有効期限は5分や10分程度で切れるようになっています．なので漏洩したとしても，攻撃者が用いることができるのはその期間中のみとなります．

ただし，だからといって漏洩していいわけではありません．

emoDBを使ったクライアントアプリ開発では，JWTの管理には細心の注意を払ってください．

## JWTの使い方

JWTはHTTPヘッダに含めて送信します．以下はPythonスクリプトの例です．

```python
import requests

jwt = requests.get("https://example.com/auth/jwt/sensor/readjwt")
request_body = {} # ここでは例なのでリクエストボディは省略
response = requests.post("https://example.com/sensor/data/read", json=request_body, headers = {"Authorization": f"Bearer: {jwt}"})
```

基本的にJWTはファイルに保存しないでください．