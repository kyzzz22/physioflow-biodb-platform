# Modifications

ユーザーに影響する修正を新しい順に記録する。

## 2026-08-26

- 大容量センサデータの読戻し（動的シャーディング）が全件 400 で空になる不具合を修正した
  - 原因: シャーディングで生成した分岐時刻が「小数秒・タイムゾーンなし」の ISO 文字列（例 `2026-08-25T00:01:26.400000`）となり、VictoriaMetrics の export API が解析できず 400 を返していた。
  - 対応: `p_victoria_metrics.py` に `_to_vm_iso()` を追加し、分岐時刻を UTC 付き ISO 形式に統一した。
- ML 解析（KMeans）の結果保存で MongoDB が整数キーを拒否する不具合を修正した
  - 原因: `label_distribution` が `{3: 123}` のような整数キーの dict を返し、BSON エンコードに失敗していた。
  - 対応: `pml.py` の `label_distribution()` をキー文字列化（`{str(int(k)): int(c)}`）に変更した（predict 端点も共用）。
- util 可視化ページの履歴/リアルタイム/イベントチャート/感情マップが「JWT Secret Key Error」でデータを読めない不具合を修正した
  - 原因: `Authorization` ヘッダに JWT 本体のみを渡しており、バックエンド `decode_jwt` が要求する `Bearer ` プレフィックスが欠落していた（プレフィックス欠落時は一律 400 "JWT Secret Key Error" を返す仕様）。
  - 対応: `bio_util/common.js`（readData / exportData / features の 3 箇所）と `bio_util/history.html`（quality の 1 箇所）で `Authorization: "Bearer " + jwt` に修正。nginx コンテナの静的配布先にも反映済み（ブラウザはキャッシュ回避のため強制リロードが必要）。

## 2026-07-24

- 実験協力者の新規登録
  - 新規登録時に入力した氏名・性別・生年月日が保存されず、画面上は失敗と表示される不具合を修正した。
  - 不具合の発生中に作成された協力者は、メールアドレスと有効状態のみは正しく保持していた。必要なプロフィール情報は既存の編集画面で補完できる。
