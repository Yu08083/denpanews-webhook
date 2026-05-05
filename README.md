# 電波人間 News Discord Bot

[New 電波人間のRPG FREE！ 公式サイト](https://newdenpafree.ap-gs.com/news) のNewsを定期的にスクレイピングし、新着があれば**記事の中身までDiscordに送信**するBotです。GitHub Actionsで動作します。

## 特徴

- 📰 `/news` ページから全Newsを **カテゴリ付き** (配信情報 / イベント情報 / その他) で取得
- 📝 各記事の本文・画像・YouTube動画リンクまで取得し、サイトを開かなくてもDiscordで内容が読める
- 🎨 カテゴリ別に色分けされたDiscord埋め込み (緑=配信情報 / 黄=イベント情報 / 灰=その他)
- ⏰ **集中監視時間帯** (JST 10:59-11:02 / 14:59-15:02) は1分間隔で4回チェック
- 🔁 通常時間帯は1時間ごとにチェック
- 🛡️ 初回実行時は通知せず既知化のみ(過去ニュースで通知が大量に飛ぶのを防止)
- 💾 状態は `state.json` で管理しGitHub Actionsが自動コミット

## ファイル構成

```
denpanews-webhook/
├── .github/
│   └── workflows/
│       └── check-news.yml    ← GitHub Actionsワークフロー
├── scraper.py                ← スクレイピング & Discord送信
├── runner.py                 ← 通常/集中モードの実行制御
├── requirements.txt          ← 必要なPythonライブラリ
├── state.json                ← 送信済みURLの記録(自動生成済み)
├── .gitignore
└── README.md
```

## セットアップ

### 1. リポジトリ作成

このフォルダの内容をGitHubの新規リポジトリにpushしてください。

### 2. Discord Webhook URL取得

1. Discordサーバーで通知先チャンネルを開く
2. チャンネル設定 → 連携サービス → ウェブフック → 新しいウェブフック
3. ウェブフックURLをコピー

### 3. GitHub Secretsに登録

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

- Name: `DISCORD_WEBHOOK_URL`
- Secret: コピーしたウェブフックURL

### 4. ワークフロー有効化 & 動作確認

`Actions` タブを開いてワークフローを有効化 → `Run workflow` で手動実行できます。

- 通常実行: そのまま `Run workflow`
- 集中監視テスト: `intensive` を `true` に
- HTML確認: `debug` を `true` に (artifactにHTMLが保存される)

## 実行スケジュール

| トリガー | UTC | JST | 動作 |
|---|---|---|---|
| 通常監視 | 毎時 5分 | 毎時 14分 | 1回チェック |
| 集中監視① | 01:57 | 10:57 | 10:59 まで待機後、10:59/11:00/11:01/11:02 と1分間隔で4回チェック |
| 集中監視② | 05:57 | 14:57 | 14:59 まで待機後、14:59/15:00/15:01/15:02 と1分間隔で4回チェック |

> GitHub Actions の cron は数分の遅延があるため、集中監視は**ウィンドウの2分前**に起動し、`runner.py` が正確な時刻まで `time.sleep()` で待機する設計になっています。

## ローカルで試す

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export DEBUG=1                # 取得HTMLや件数を詳細出力
python scraper.py             # 1回だけ実行
INTENSIVE=1 python runner.py  # 集中監視モード(時間帯外なら1回だけ)
```

## トラブルシューティング

### 取得件数が少ない・記事内容が空

`DEBUG=1` で実行すると `debug_news.html` などが保存されます。手動実行時に `debug: true` を選べば GitHub Actions の Artifact からダウンロードできます。

### state.jsonをリセットしたい

リポジトリから `state.json` を削除してpush → 次回実行時に再度初回扱いとなり、現状の全Newsが既知化されます(通知は飛びません)。

### 既存ニュースもDiscord通知させたい

`scraper.py` の `main()` 内 `first_run` 判定をコメントアウトしてください。`state.json` を空 (`{"sent": []}`) にしてpushすれば、すべて新規扱いで送信されます。

## 注意事項

- Discord Webhookはレート制限あり (1分間に約30リクエスト)。記事1件につき本文+画像+動画で最大4-5回POSTするため、新着が大量にある場合は時間がかかります
- GitHub Actions無料枠は月2,000分。1時間ごと + 集中監視2回 + 各回約3分とすると月60分程度
- 実行が重複しないよう `concurrency` で同時実行を防いでいます
