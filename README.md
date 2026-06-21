# 電波人間 Twitter News

電波人間 公式X **[@denpaningen](https://x.com/denpaningen)** の新着ツイートを定期チェックし、
新着があれば **Discord Webhook に通知**する Bot です。GitHub Actions で完全自動運用。

[denpanews-webhook](https://github.com/Yu08083/denpanews-webhook)(公式サイト版)の Twitter 通知版。
運用フロー(`state.json` 管理・初回は既知化して無通知・集中監視モード)はそのまま踏襲しています。

## 取得方法

公式 X API は有料(月100ドル〜)なので使いません。代わりに
**Yahoo!リアルタイム検索のバックエンド API** を利用します。認証不要・レート制限なし、
User-Agent の偽装だけで動きます。

```
GET https://search.yahoo.co.jp/realtime/api/v1/pagination?p=ID:denpaningen&results=40
```

`ID:ユーザー名` 演算子で特定アカウントの投稿だけを取得しています。
(参考: <https://qiita.com/maebahesioru/items/4fc4e6baf5b96aa84061>)

## 機能

- `ID:denpaningen` で @denpaningen の最新ツイートを取得
- 新着があれば Discord に 本文 + 画像 + いいね/RT数 + ツイートリンク を送信
- 投稿者が本人のエントリだけ通す(引用・メンション混入を除外)
- 集中監視時間帯は1分間隔でチェック (JST 10:59-11:02 は4回 / JST 14:55-15:15 は21回・広め)
- 通常時間帯は毎時14分(JST)に1回チェック
- 状態は `state.json` で管理(送信済みツイートID、直近500件保持)、GitHub Actions が自動コミット

## ファイル構成

```
denpa-tweet-webhook/
├── .github/workflows/check-tweets.yml   # GitHub Actions ワークフロー
├── scraper.py                            # Yahoo API 取得 & Discord 送信
├── runner.py                             # 通常/集中モードの実行制御 (公式サイト版と共通)
├── requirements.txt
├── state.json                            # 自動生成 (送信済みツイートID)
└── README.md
```

## セットアップ

### 1. リポジトリ作成 & ファイル配置

このフォルダの内容を GitHub の新規リポジトリに push してください。

### 2. Discord Webhook URL を取得 → GitHub Secrets に登録

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

- Name: `DISCORD_WEBHOOK_URL`
- Secret: Discord で発行した Webhook URL

### 3. ワークフローを有効化 → 手動実行

`Actions` タブを開いてワークフローを有効化 → `Run workflow` で動作確認。

初回実行で:

- 現在取得できる全ツイートを `state.json` に既知化(**初回は通知なし**)
- 次回以降、新しく出たツイートだけ通知

## ローカルで試す

```
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python scraper.py
```

## 環境変数

| 変数                   | 既定値             | 説明                                              |
| -------------------- | --------------- | ----------------------------------------------- |
| `DISCORD_WEBHOOK_URL`| (必須)           | 通知先 Discord Webhook                             |
| `TWITTER_USERNAME`   | `denpaningen`   | 監視対象のXアカウント (@なし)                     |
| `SEARCH_QUERY`       | `ID:{username}` | Yahoo検索クエリ。下記の取りこぼし対策で上書き可 |
| `RESULTS`            | `40`            | 1回の取得件数 (最大40)                            |
| `INTENSIVE`          | `0`             | `1` で集中監視モード                              |
| `DEBUG`              | -               | `1` で生レスポンスのキー構造を stderr に出力     |

## 既知の制約・注意点

- **Yahoo インデックスのバイアス**: Yahoo!リアルタイム検索は日本語ツイート + エンゲージメント
  重視のインデックスです。公式 API のような完全性はなく、エンゲージメントの低いツイートは
  取りこぼし・遅延が起こり得ます。お知らせ系は概ね拾えますが、100%保証ではありません。
- **`mtype` は付けていません**: 付けると画像なしツイート(テキストのみのお知らせ)が落ちて
  通知漏れになるためです。
- **`ID:denpaningen` で0件になる場合**: 演算子やインデックス事情で本人投稿が引けないことが
  あります。その場合は `SEARCH_QUERY` を `@denpaningen` や `電波人間` 等に変えて試してください
  (本人以外の投稿は投稿者フィルタで自動除外されます)。
- **JSON スキーマのフィールド名揺れ**: Yahoo の内部 API はフィールド名が一部非公開です。
  `scraper.py` は本文・ID・投稿者などを複数候補キーで総当たり取得する防御的パーサにしています。
  想定外の構造で本文や画像が空になる場合は、`DEBUG=1` で一度実行すると先頭エントリのキー一覧が
  stderr に出るので、`scraper.py` 冒頭の `*_KEYS` 候補リストに実際のキーを足してください。

## state.json をリセットしたい

`state.json` を `{"sent": []}` に戻して push → 次回実行が再び初回扱いになり、現状の全ツイートを
既知化(通知なし)します。
