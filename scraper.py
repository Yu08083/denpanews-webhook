"""
New 電波人間のRPG FREE！ 公式サイトのNewsをスクレイピングし、
新しいニュースを記事内容ごとDiscord Webhookに送信する。

レイアウト方針 (レイアウト1):
- 1ニュース = 複数メッセージ
  1. ヘッダー: タイトル / カテゴリ / 投稿日 / リード文
  2. セクション(見出し+本文+画像) ごとに1メッセージ
  3. フッター: 動画リンク + 公式サイトリンク

画像処理:
- Google Sites の画像URLは Content-Type を確認
- PNG透過画像のときだけPillowで白背景合成し、Discordへ multipart アップロード
- それ以外は画像URLをそのまま Embed.image に指定
"""

import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

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

CATEGORY_COLORS = {
    "配信情報": 0x2ECC71,
    "イベント情報": 0xF1C40F,
    "その他": 0x95A5A6,
    "不明": 0x00B0F0,
}
CATEGORY_EMOJIS = {
    "配信情報": "🟢",
    "イベント情報": "🟡",
    "その他": "⚪",
}

SKIP_TEXTS = {
    "Search this site", "Embedded Files",
    "Skip to main content", "Skip to navigation",
    "Report abuse", "ENGLISH", "トップページへ",
    "利用規約", "プライバシーポリシー",
    "二次創作ガイドライン", "お問い合わせ",
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


# ---------- News一覧 ----------
def parse_news_list(html: str):
    soup = BeautifulSoup(html, "html.parser")

    category_ranges = []
    for h in soup.find_all(["h2", "h3"]):
        text = h.get_text(" ", strip=True)
        for cat in ("配信情報", "イベント情報", "その他"):
            if cat in text:
                category_ranges.append((h.sourceline or 0, cat))
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
        category = "不明"
        line = a.sourceline or 0
        candidates = [(ln, cat) for ln, cat in category_ranges if ln <= line]
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


# ---------- 記事ページパース (順序保持) ----------
def is_skippable_text(text: str) -> bool:
    if not text:
        return True
    if text in SKIP_TEXTS:
        return True
    if "©" in text and "Genius Sonority" in text:
        return True
    if re.fullmatch(r"/[a-z0-9_/-]+", text):
        return True
    if re.search(r"\[JST\]\s*更新", text):
        return True
    return False


def parse_article(html: str, fallback_title: str = ""):
    """記事ページから順序保持でセクション化。

    戻り値:
      {
        "title": str,
        "lead": str,                 # 最初の見出しより前の文章 (リード文)
        "sections": [
          {"heading": "イベントステージ", "body": "...", "images": [url, url]},
          ...
        ],
        "videos": [url, ...],
        "updated": "2026.05.01",
      }
    """
    soup = BeautifulSoup(html, "html.parser")

    # タイトル
    page_title = (soup.title.string or "").strip() if soup.title else ""
    title = fallback_title or page_title
    m = re.match(r"[^\-]+-\d+_(.+?)\s*[｜|]", page_title)
    if m:
        title = m.group(1).strip()

    # YouTube
    videos = []
    seen_videos = set()
    yt_re = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{6,})")
    for tag in soup.find_all(["iframe", "a"]):
        attr = tag.get("src") or tag.get("href") or ""
        m2 = yt_re.search(attr)
        if m2:
            vid = m2.group(1)
            if vid not in seen_videos:
                seen_videos.add(vid)
                videos.append(f"https://www.youtube.com/watch?v={vid}")

    # 更新日
    updated = ""
    m3 = re.search(r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*\[JST\]\s*更新", html)
    if m3:
        updated = m3.group(1)

    # 順序保持で要素を集める
    # main ぽい領域を選ぶのが理想だが、Google Sitesは構造が定まらないので
    # body 全体を走査して h2/h3/h4/p/li/img を順に取る
    body_root = soup.body or soup

    elements = []  # [("heading", text)|("text", text)|("image", url)]
    seen_imgs = set()

    for el in body_root.descendants:
        if not isinstance(el, Tag):
            continue
        if el.name in ("h2", "h3", "h4"):
            text = el.get_text(" ", strip=True)
            if is_skippable_text(text):
                continue
            if text == title:
                continue
            elements.append(("heading", text))
        elif el.name in ("p", "li"):
            text = el.get_text(" ", strip=True)
            if is_skippable_text(text):
                continue
            if text == title:
                continue
            # imgしか含まないpタグはテキスト追加しない
            if not text and el.find("img"):
                continue
            elements.append(("text", text))
        elif el.name == "img":
            src = el.get("src", "")
            if "googleusercontent.com/sitesv/" not in src:
                continue
            if src in seen_imgs:
                continue
            seen_imgs.add(src)
            elements.append(("image", src))

    # 連続した text の重複除去 (Google Sitesがネスト構造で同テキストを2重に出すことがある)
    deduped = []
    for kind, val in elements:
        if kind == "text" and deduped and deduped[-1] == ("text", val):
            continue
        deduped.append((kind, val))
    elements = deduped

    # セクション化
    lead_lines = []
    lead_images = []
    sections = []
    current = None  # {"heading": str, "body": [str], "images": [url]}

    for kind, val in elements:
        if kind == "heading":
            if current:
                sections.append(current)
            current = {"heading": val, "body": [], "images": []}
        elif kind == "text":
            if current is None:
                lead_lines.append(val)
            else:
                current["body"].append(val)
        elif kind == "image":
            if current is None:
                lead_images.append(val)
            else:
                current["images"].append(val)

    if current:
        sections.append(current)

    # セクションを整形
    cleaned_sections = []
    for s in sections:
        body_text = "\n".join(s["body"]).strip()
        cleaned_sections.append({
            "heading": s["heading"],
            "body": body_text,
            "images": s["images"],
        })

    return {
        "title": title,
        "lead": "\n".join(lead_lines).strip(),
        "lead_images": lead_images,
        "sections": cleaned_sections,
        "videos": videos,
        "updated": updated,
    }


# ---------- 画像処理 ----------
def fetch_image(url: str):
    """画像をDLしてバイナリ返す。失敗したら None."""
    try:
        res = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        res.raise_for_status()
        return res.content, res.headers.get("Content-Type", "")
    except Exception as e:
        print(f"  画像取得失敗: {url[:80]}... {e}", file=sys.stderr)
        return None, None


def needs_white_background(content: bytes, content_type: str) -> bool:
    """PNGかつアルファチャンネルを持っていれば True"""
    if "png" not in (content_type or "").lower() and not content[:8].startswith(b"\x89PNG"):
        return False
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        # P (パレット) や RGBA, LA など透過を持ちうるモード
        if img.mode in ("RGBA", "LA"):
            return True
        if img.mode == "P":
            return "transparency" in img.info
        return False
    except Exception:
        return False


def composite_on_white(content: bytes) -> bytes:
    """PNG透過画像を白背景に合成してPNGバイナリで返す"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])  # アルファをマスクに
        out = io.BytesIO()
        bg.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception as e:
        print(f"  画像合成失敗: {e}", file=sys.stderr)
        return content


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
def post_webhook(payload: dict = None, files: dict = None) -> bool:
    """通常POST or マルチパートPOST."""
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        return False
    try:
        if files:
            # multipart: payload_json + files
            data = {"payload_json": json.dumps(payload, ensure_ascii=False)}
            res = requests.post(WEBHOOK_URL, data=data, files=files, timeout=60)
        else:
            res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"Discord送信例外: {e}", file=sys.stderr)
        return False

    if res.status_code == 429:
        try:
            retry = res.json().get("retry_after", 1)
        except Exception:
            retry = 1
        time.sleep(float(retry) + 0.5)
        if files:
            data = {"payload_json": json.dumps(payload, ensure_ascii=False)}
            res = requests.post(WEBHOOK_URL, data=data, files=files, timeout=60)
        else:
            res = requests.post(WEBHOOK_URL, json=payload, timeout=30)

    if res.status_code >= 300:
        print(f"Discord送信失敗: {res.status_code} {res.text[:300]}", file=sys.stderr)
        return False
    return True


def chunk_text(text: str, limit: int = 4000):
    """4096字制限を考慮して安全に分割."""
    if not text:
        return [""]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return chunks


def send_embed_with_images(
    *,
    color: int,
    title: str = None,
    description: str = None,
    images: list = None,
    author_name: str = None,
    fields: list = None,
    footer: str = None,
    article_url: str = None,
):
    """
    1メッセージ = 1つのEmbed (テキスト) + 最大10個の画像 を送信。
    画像はPNG透過なら白背景合成してアップロード、それ以外はURLでEmbed指定。
    """
    images = images or []

    # 画像処理: 透過PNGならローカル合成→ファイルアップ
    files = {}
    embed_image_urls = []  # Embedに添付する画像URL or attachment://
    file_index = 0

    for img_url in images[:10]:  # Discordは1メッセージ最大10embed = 10画像
        content, ctype = fetch_image(img_url)
        if not content:
            continue
        if needs_white_background(content, ctype):
            new_content = composite_on_white(content)
            fname = f"image_{file_index}.png"
            files[f"files[{file_index}]"] = (fname, new_content, "image/png")
            embed_image_urls.append(f"attachment://{fname}")
            file_index += 1
        else:
            embed_image_urls.append(img_url)

    # Embed構築
    # メインEmbed: title/description/最初の画像
    embeds = []
    main_embed = {"color": color}
    if author_name:
        main_embed["author"] = {"name": author_name}
    if title:
        main_embed["title"] = title
        if article_url:
            main_embed["url"] = article_url
    if description:
        main_embed["description"] = description
    if fields:
        main_embed["fields"] = fields
    if footer:
        main_embed["footer"] = {"text": footer}
    if embed_image_urls:
        main_embed["image"] = {"url": embed_image_urls[0]}
    embeds.append(main_embed)

    # 追加画像はサブEmbed (article_urlを共通にすると Discord がギャラリー表示)
    for img_ref in embed_image_urls[1:]:
        sub = {"color": color, "image": {"url": img_ref}}
        if article_url:
            sub["url"] = article_url
        embeds.append(sub)

    payload = {
        "username": "電波人間 News Bot",
        "embeds": embeds[:10],
    }
    return post_webhook(payload, files=files if files else None)


def send_news_to_discord(item: dict, article: dict) -> bool:
    """
    1ニュースを複数メッセージで送信。
    1) ヘッダーメッセージ (タイトル / リード文 / リード画像)
    2) 各セクション (見出し / 本文 / 画像)
    3) フッターメッセージ (動画 / 詳細リンク)
    """
    category = item.get("category", "不明")
    color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["不明"])
    cat_emoji = CATEGORY_EMOJIS.get(category, "📢")

    title = article["title"] or item["title"]
    lead = article.get("lead", "")
    lead_images = article.get("lead_images", [])
    sections = article.get("sections", [])
    videos = article.get("videos", [])
    updated = article.get("updated") or item["date"]

    # --- 1) ヘッダー ---
    header_desc_parts = []
    if lead:
        header_desc_parts.append(lead)
    header_desc = "\n\n".join(header_desc_parts)
    # 4096字制限
    header_chunks = chunk_text(header_desc, 4000)
    ok = send_embed_with_images(
        color=color,
        author_name=f"{cat_emoji} {category}",
        title=f"📢 {title}",
        description=header_chunks[0] if header_chunks else "",
        images=lead_images,
        fields=[
            {"name": "📅 投稿日", "value": item["date"], "inline": True},
            {"name": "🔄 更新", "value": updated, "inline": True},
        ],
        article_url=item["url"],
    )
    if not ok:
        return False
    # 残りリード文
    for chunk in header_chunks[1:]:
        ok = send_embed_with_images(color=color, description=chunk)
        if not ok:
            return False
        time.sleep(0.5)

    # --- 2) 各セクション ---
    for sec in sections:
        sec_title = f"▼ {sec['heading']}"
        body_chunks = chunk_text(sec["body"], 4000) if sec["body"] else [""]

        # 1セクションは: 最初のチャンク+画像 → 残りチャンク
        ok = send_embed_with_images(
            color=color,
            title=sec_title,
            description=body_chunks[0],
            images=sec["images"],
            article_url=item["url"],
        )
        if not ok:
            return False
        time.sleep(0.7)  # レート制限対策

        for chunk in body_chunks[1:]:
            ok = send_embed_with_images(color=color, description=chunk)
            if not ok:
                return False
            time.sleep(0.5)

    # --- 3) フッター ---
    footer_lines = []
    if videos:
        footer_lines.append("**🎬 動画**")
        footer_lines.extend(videos)
    footer_lines.append(f"\n[🔗 公式サイトで詳細を見る]({item['url']})")
    footer_desc = "\n".join(footer_lines)

    ok = send_embed_with_images(
        color=color,
        description=footer_desc,
        footer="New 電波人間のRPG FREE！",
    )
    return ok


# ---------- 取得 ----------
def fetch_news():
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
    new_items = [it for it in items if it["url"] not in sent_keys]

    if first_run:
        print(f"初回実行: {len(new_items)}件を既知化(通知なし)")
        for it in new_items:
            sent_keys.add(it["url"])
    else:
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
                time.sleep(1.0)

    state["sent"] = sorted(sent_keys)
    save_state(state)
    print(f"完了。既知News件数: {len(sent_keys)}")


if __name__ == "__main__":
    main()
