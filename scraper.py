"""
New 電波人間のRPG FREE！ 公式サイトのNewsをスクレイピングし、
新しいニュースを記事内容ごとDiscord Webhookに送信する。

機能:
- /news ページから全Newsリンクを抽出 (カテゴリ: 配信情報/イベント情報/その他)
- 各記事ページを取得し、本文・画像URL・YouTube動画URLを抜き出す
- Discord Webhookに、サイトを開かなくても内容が読める形で送信
- 既知のニュースは state.json で管理。初回は通知せず既知化のみ
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

NEWS_URL = "https://newdenpafree.ap-gs.com/news"
TOP_URL = "https://newdenpafree.ap-gs.com/top"
BASE = "https://newdenpafree.ap-gs.com"
STATE_FILE = Path("state.json")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DEBUG = os.environ.get("DEBUG") == "1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# カテゴリ識別 (Newsページのアンカー#hash → カテゴリ名)
CATEGORY_ANCHORS = {
    "qmv6nf7xhjqy": "配信情報",
    "fl4njortdox4": "イベント情報",
    "axj59m55504p": "その他",
}

CATEGORY_COLORS = {
    "配信情報": 0x2ECC71,   # 緑
    "イベント情報": 0xF1C40f, # 黄
    "その他": 0x95A5A6,     # 灰
    "不明": 0x00B0F0,
}


# ---------- HTTP ----------
def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    res = requests.get(url, headers=headers, timeout=30)
    res.raise_for_status()
    return res.text


# ---------- News一覧パース ----------
def parse_news_list(html: str):
    """/news ページから記事リンクを抽出。
    戻り値: [{date, title, url, category}]
    """
    soup = BeautifulSoup(html, "html.parser")

    # 各h2(カテゴリ見出し)の位置を取得し、カテゴリ範囲を決定する
    # h2が見つからない場合のフォールバックも持つ
    category_ranges = []  # [(start_index_in_doc, category_name)]
    for h2 in soup.find_all(["h2", "h3"]):
        text = h2.get_text(" ", strip=True)
        for cat in ("配信情報", "イベント情報", "その他"):
            if cat in text:
                category_ranges.append((h2.sourceline or 0, cat, h2))
                break

    items = []
    seen = set()
    news_re = re.compile(r"/news/news_(\d{4})(\d{2})(\d{2})")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = news_re.search(href)
        if not m:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        full_url = href if href.startswith("http") else f"{BASE}{href}"
        if full_url in seen:
            continue
        seen.add(full_url)

        date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

        # カテゴリ判定: aタグのソース行番号と、各h2のソース行番号を比較
        category = "不明"
        line = a.sourceline or 0
        # h2行番号より大きいものの中で最大のものに属する
        candidates = [(ln, cat) for ln, cat, _ in category_ranges if ln <= line]
        if candidates:
            category = max(candidates, key=lambda x: x[0])[1]

        items.append({
            "date": date,
            "title": title,
            "url": full_url,
            "category": category,
        })

    items.sort(key=lambda x: (x["date"], x["url"]), reverse=True)
    return items


# ---------- 記事ページパース ----------
def parse_article(html: str, fallback_title: str = "") -> dict:
    """記事ページから内容を抽出。
    戻り値: {title, body_text, images, videos, updated}
    """
    soup = BeautifulSoup(html, "html.parser")

    # タイトル: <title>タグ から「カテゴリ-スラグ_xxx ｜...」を整形
    page_title = (soup.title.string or "").strip() if soup.title else ""
    # 「イベント情報-20260501001_こどもイベント開催 ｜New 電波人間のRPG FREE！ - 公式サイト」
    title = fallback_title or page_title
    m = re.match(r"[^\-]+-\d+_(.+?)\s*[｜|]", page_title)
    if m:
        title = m.group(1).strip()

    # 本文を構造化して抽出
    # h2/h3/h4 は見出しとしてマークし、Discord Markdownの太字+▼で装飾する
    skip_words = {
        "Search this site", "Embedded Files",
        "Skip to main content", "Skip to navigation",
        "Report abuse", "ENGLISH", "トップページへ",
        "利用規約", "プライバシーポリシー", "二次創作ガイドライン", "お問い合わせ",
    }

    body_lines = []
    last_was_heading = False
    for el in soup.find_all(["h2", "h3", "h4", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if text in skip_words:
            continue
        if "©" in text and "Genius Sonority" in text:
            continue
        if re.fullmatch(r"/[a-z0-9_/-]+", text):
            continue
        # 「JST] 更新」行は別フィールドで扱うので本文からは除外
        if re.search(r"\[JST\]\s*更新", text):
            continue
        # タイトル(h1)と同じテキストは除外
        if text == title:
            continue

        is_heading = el.name in ("h2", "h3", "h4")
        if is_heading:
            # 見出しは Discord Markdown の太字+▼ で装飾
            formatted = f"\n**▼ {text}**"
            # 直前も見出しなら改行を減らす
            if last_was_heading and body_lines:
                body_lines[-1] = formatted.lstrip()
            else:
                body_lines.append(formatted)
            last_was_heading = True
        else:
            # 重複除去
            if body_lines and body_lines[-1].strip() == text:
                continue
            body_lines.append(text)
            last_was_heading = False

    # 改行で連結。見出しの前は空行を入れて区切りを明確に
    body_text = "\n".join(body_lines).strip()
    # 連続改行整理
    body_text = re.sub(r"\n{3,}", "\n\n", body_text)

    # 画像URL (Google Sites のサーブ用URL)
    images = []
    seen_imgs = set()
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if "googleusercontent.com/sitesv/" not in src:
            continue
        if src in seen_imgs:
            continue
        seen_imgs.add(src)
        images.append(src)

    # YouTube動画 (iframe / リンク)
    videos = []
    seen_videos = set()
    yt_re = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{6,})")
    for tag in soup.find_all(["iframe", "a"]):
        attr = tag.get("src") or tag.get("href") or ""
        m = yt_re.search(attr)
        if m:
            vid = m.group(1)
            if vid not in seen_videos:
                seen_videos.add(vid)
                videos.append(f"https://www.youtube.com/watch?v={vid}")

    # 更新日 (例: "2026.05.01 [JST] 更新")
    updated = ""
    m = re.search(r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*\[JST\]\s*更新", html)
    if m:
        updated = m.group(1)

    return {
        "title": title,
        "body_text": body_text,
        "images": images,
        "videos": videos,
        "updated": updated,
    }


def fetch_news():
    """/news から取得。失敗したら /top にフォールバック。"""
    html = ""
    try:
        html = fetch_html(NEWS_URL)
    except requests.RequestException as e:
        print(f"/news 取得失敗: {e}", file=sys.stderr)

    if DEBUG and html:
        Path("debug_news.html").write_text(html, encoding="utf-8")

    items = parse_news_list(html) if html else []

    if not items:
        print("/news からNews取得失敗。/top で再試行", file=sys.stderr)
        try:
            html_top = fetch_html(TOP_URL)
            if DEBUG:
                Path("debug_top.html").write_text(html_top, encoding="utf-8")
            items = parse_news_list(html_top)
        except requests.RequestException as e:
            print(f"/top 取得失敗: {e}", file=sys.stderr)

    return items


# ---------- 状態管理 ----------
def load_state():
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "sent" in data:
                return data
        except json.JSONDecodeError:
            pass
    return {"sent": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- Discord 送信 ----------
def chunk_text(text: str, limit: int = 4000):
    """Discord embed description は 4096文字制限。安全のため4000でチャンク。"""
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # 改行で区切る
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return chunks


def post_webhook(payload: dict) -> bool:
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        return False
    res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if res.status_code == 429:
        # レート制限
        retry = res.json().get("retry_after", 1)
        time.sleep(float(retry) + 0.5)
        res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if res.status_code >= 300:
        print(f"Discord送信失敗: {res.status_code} {res.text}", file=sys.stderr)
        return False
    return True


def send_news_to_discord(item: dict, article: dict) -> bool:
    """
    1ニュースを1リクエストで送信(可能な限り)。
    レイアウト方針:
      - メイン Embed: タイトル / 本文(長すぎる場合は要約) / メイン画像1枚 / 詳細リンク
      - 追加 Embed: サブ画像 (最大2枚まで)
      - 本文が長い場合は「続きはサイトで」リンクで誘導
    """
    category = item.get("category", "不明")
    color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["不明"])
    cat_emoji = {
        "配信情報": "🟢",
        "イベント情報": "🟡",
        "その他": "⚪",
    }.get(category, "📢")

    title = article.get("title") or item["title"]
    body = article.get("body_text", "").strip()
    images = article.get("images", [])
    videos = article.get("videos", [])
    updated = article.get("updated") or item["date"]

    # 本文を整形: 段落間に空行を入れて見やすくする
    # parse_articleで見出しに改行が入っているのでそれを活かす
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # 動画リンクを本文末尾に追加
    if videos:
        body += "\n\n**🎬 動画**\n" + "\n".join(videos)

    # 詳細リンクを末尾に追加
    body += f"\n\n[🔗 公式サイトで詳細を見る]({item['url']})"

    # Discord embed description は最大4096文字。安全のため3800で切り詰めて
    # 「(本文が長いため省略...)」を追加
    MAX_DESC = 3800
    if len(body) > MAX_DESC:
        # 末尾のリンク部分は残す
        link_suffix = f"\n\n[🔗 公式サイトで全文を見る]({item['url']})"
        truncated = body[: MAX_DESC - len(link_suffix) - 30]
        # 不自然な途中切れを避けるため改行で区切る
        cut = truncated.rfind("\n")
        if cut > MAX_DESC // 2:
            truncated = truncated[:cut]
        body = truncated + "\n\n…(本文が長いため省略)" + link_suffix

    # メインEmbed
    embeds = [{
        "author": {"name": f"{cat_emoji} {category}"},
        "title": f"📢 {title}",
        "url": item["url"],
        "description": body,
        "color": color,
        "fields": [
            {"name": "📅 投稿日", "value": item["date"], "inline": True},
            {"name": "🔄 更新", "value": updated, "inline": True},
        ],
        "footer": {"text": "New 電波人間のRPG FREE！"},
    }]
    if images:
        embeds[0]["image"] = {"url": images[0]}

    # サブ画像 (最大2枚追加 = 合計3枚まで表示)
    # 同じURLを指定すると Discord が画像をギャラリー風にまとめてくれる
    for img_url in images[1:3]:
        embeds.append({
            "url": item["url"],
            "image": {"url": img_url},
            "color": color,
        })

    payload = {
        "username": "電波人間 News Bot",
        "embeds": embeds,
    }
    return post_webhook(payload)


# ---------- メイン ----------
def main():
    state = load_state()
    sent_keys = set(state.get("sent", []))

    items = fetch_news()
    if not items:
        print("Newsが1件も取得できませんでした", file=sys.stderr)
        sys.exit(1)

    print(f"取得したNews件数: {len(items)}")
    if DEBUG:
        for it in items[:10]:
            print(f"  [{it['category']}] {it['date']} {it['title']}")

    first_run = len(sent_keys) == 0

    # 新規 = 既知に無いもの
    new_items = [it for it in items if it["url"] not in sent_keys]

    if first_run:
        print(f"初回実行: {len(new_items)}件を既知化(通知なし)")
        for it in new_items:
            sent_keys.add(it["url"])
    else:
        # 古い→新しい順で送信
        for it in reversed(new_items):
            print(f"新規News: [{it['category']}] {it['date']} {it['title']}")
            try:
                article_html = fetch_html(it["url"])
            except requests.RequestException as e:
                print(f"  記事取得失敗: {e}", file=sys.stderr)
                continue
            article = parse_article(article_html, fallback_title=it["title"])
            if send_news_to_discord(it, article):
                sent_keys.add(it["url"])
                # Webhookレート制限対策の小休止
                time.sleep(1.0)

    state["sent"] = sorted(sent_keys)
    save_state(state)
    print(f"完了。既知News件数: {len(sent_keys)}")


if __name__ == "__main__":
    main()
