# 電波人間 News

[New 電波人間のRPG FREE！](https://newdenpafree.ap-gs.com/) 公式サイトのお知らせを定期スクレイピングし、

1. **読みやすく再構成した HTML サイトを GitHub Pages で公開**
2. **新着があれば Discord Webhook に通知**

する Bot です。GitHub Actions で完全自動運用。

## 公開サイト

スクレイピング結果は GitHub Pages 上で公開されます:
`https://<ユーザー名>.github.io/<リポジトリ名>/`

## 機能

- 公式サイトから全Newsを取得しカテゴリ判定 (配信情報 / イベント情報 / その他)
- 各記事の本文・画像・動画を取得して、洗練されたダークテーマの HTML として再構成
- 新着があれば Discord にタイトル+リード+サムネ画像+リンクを送信
- 集中監視時間帯 (JST 10:59-11:02 / 14:59-15:02) は1分間隔で4回チェック
- 通常時間帯は毎時14分(JST)に1回チェック
- 状態は `state.json` で管理、サイトは `docs/` に出力、どちらも GitHub Actions が自動コミット

## ファイル構成

```
denpa-news-bot/
├── .github/workflows/check-news.yml   # GitHub Actions ワークフロー
├── scraper.py                          # スクレイピング & Discord 送信 & サイト生成呼び出し
├── site_builder.py                     # HTML サイト生成
├── runner.py                           # 通常/集中モードの実行制御
├── requirements.txt
├── state.json                          # 自動生成 (送信済みURL)
├── docs/                               # 自動生成 (GitHub Pages 公開対象)
│   ├── index.html
│   ├── news/news_xxx.html
│   └── assets/style.css
├── .gitignore
└── README.md
```

## セットアップ

### 1. リポジトリ作成 & ファイル配置

このフォルダの内容を GitHub の新規リポジトリに push してください。

### 2. Discord Webhook URL を取得 → GitHub Secrets に登録

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

- Name: `DISCORD_WEBHOOK_URL`
- Secret: Discord で発行した Webhook URL

### 3. GitHub Pages を有効化

`Settings` → `Pages`

- **Source**: `Deploy from a branch`
- **Branch**: `main` / `/docs`
- 「Save」をクリック

数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` でアクセス可能になります。

### 4. ワークフローを有効化 → 手動実行

`Actions` タブを開いてワークフローを有効化 → `Run workflow` で動作確認。

初回実行で:
- 全Newsをスクレイピング
- HTML サイトを `docs/` に生成
- `state.json` を初期化(初回は通知なし)
- 全部まとめてコミット

サイトが Pages に公開されたら、リポジトリの「About」欄にURLを設定しておくと便利です。

## 実行スケジュール

| トリガー | UTC | JST | 動作 |
|---|---|---|---|
| 通常 | 毎時 5分 | 毎時 14分 | 1回チェック |
| 集中 ① | 01:57 | 10:57 | 10:59 まで待機 → 10:59-11:02 を1分間隔で4回 |
| 集中 ② | 05:57 | 14:57 | 14:59 まで待機 → 14:59-15:02 を1分間隔で4回 |

## ローカルで試す

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export SITE_BASE_URL="https://yu08083.github.io/denpanews-webhook"
python scraper.py
```

`docs/` 以下を `python -m http.server` で配信すれば、生成サイトをローカルプレビューできます。

```bash
cd docs && python -m http.server 8000
# → http://localhost:8000/
```

## トラブルシューティング

### Pages のサイトに 404

- Pages が `main` / `/docs` を参照する設定になっているか確認
- 初回はビルドに数分かかることがあります
- `docs/` 内に `.nojekyll` ファイルが存在することを確認 (自動生成されます)

### state.json をリセットしたい

リポジトリから `state.json` を削除して push → 次回実行時に再度初回扱いとなり、現状の全Newsを既知化(通知なし)。

### ワークフローが動かない

`Actions` タブで実行履歴を確認。失敗していればステップごとのログでエラー内容を確認。
