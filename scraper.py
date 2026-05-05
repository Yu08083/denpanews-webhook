import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

import site_builder

NEWS_URL = "https://newdenpafree.ap-gs.com/news"
TOP_URL = "https://newdenpafree.ap-gs.com/top"
BASE = "https://newdenpafree.ap-gs.com"
STATE_FILE = Path("state.json")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "")  # 例: https://yu08083.github.io/denpanews-webhook
DEBUG = os.environ.get("DEBUG") == "1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

CATEGORY_COLORS = {
    "配信情報": 0x5EC27E,
    "イベント情報": 0xF5D547,
    "その他": 0x9AA0A6,
    "不明": 0xE8E6E1,
}

SKIP_TEXTS = {
    "Search this site", "Embedded Files",
    "Skip to main content", "Skip to navigation",
    "Report abuse", "ENGLISH", "トップページへ",
    "利用規約", "プライバシーポリシー",
    "二次創作ガイドライン", "お問い合わせ",
}

# 1行に複数のナビ語が含まれていたらフッター行とみなす
NAV_KEYWORDS = ["トップページへ", "利用規約", "プライバシーポリシー",
                "二次創作ガイドライン", "お問い合わせ", "Report abuse"]


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
    news_re = re.compile(r"/news/(news_\d{4}\d{2}\d{2}\d*)")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = news_re.search(href)
        if not m:
            continue
        slug = m.group(1)
        date_m = re.match(r"news_(\d{4})(\d{2})(\d{2})", slug)
        if not date_m:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        full_url = href if href.startswith("http") else f"{BASE}{href}"
        if full_url in seen:
            continue
        seen.add(full_url)

        date = f"{date_m.group(1)}/{date_m.group(2)}/{date_m.group(3)}"
        category = "不明"
        line = a.sourceline or 0
        candidates = [(ln, cat) for ln, cat in category_ranges if ln <= line]
        if candidates:
            category = max(candidates, key=lambda x: x[0])[1]

        items.append({
            "date": date,
            "title": title,
            "url": full_url,
            "slug": slug,
            "category": category,
        })

    items.sort(key=lambda x: (x["date"], x["url"]), reverse=True)
    return items


# ---------- 記事ページ ----------
def is_skippable_text(text: str) -> bool:
    if not text:
        return True
    if text in SKIP_TEXTS:
        return True
    if "©" in text and "Genius Sonority" in text:
        return True
    if re.fullmatch(r"/[a-z0-9_/-]+", text):
        return True
    if re.search(r"\[JST\]\s*(?:更新|配信|公開)", text):
        return True
    # 1行に複数のナビキーワードが含まれていたらフッター行
    nav_count = sum(1 for kw in NAV_KEYWORDS if kw in text)
    if nav_count >= 2:
        return True
    # 「/path /path /path」のようにパスばかりが並ぶ行
    if re.fullmatch(r"(\s*/[a-z0-9_-]+\s*)+", text):
        return True
    return False


HEADING_PATTERNS = [
    re.compile(r"^イベント[ァ-ヴー一-龠a-zA-Z]+$"),
    re.compile(r".+(情報|お知らせ|キャンペーン|アップデート)$"),
    re.compile(r"^(機能追加|調整|不具合修正|新機能|変更点|改修|追加要素|主な変更)"),
    re.compile(r"^【.+】$"),
    re.compile(r"^■.+"),
    re.compile(r"^◆.+"),
    re.compile(r"^▼.+"),
]


def looks_like_heading(text: str) -> bool:
    if not text or len(text) > 30:
        return False
    if text[-1] in "。、！？!?…」』）)":
        return False
    for pat in HEADING_PATTERNS:
        if pat.search(text):
            return True
    return False


def promote_headings(elements):
    """素テキストの中で大見出しっぽい行をheading(level=2)に昇格"""
    new = []
    for item in elements:
        kind, val = item[0], item[1]
        if kind == "text" and looks_like_heading(val):
            # 昇格した見出しは大見出し扱い (level=2)
            new.append(("heading", val, 2))
        else:
            new.append(item)
    return new


def parse_article(html_text: str, fallback_title: str = ""):
    soup = BeautifulSoup(html_text, "html.parser")

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
    m3 = re.search(r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*\[JST\]\s*(?:更新|配信|公開)", html_text)
    if m3:
        updated = m3.group(1).replace(".", "/")

    body_root = soup.body or soup

    elements = []
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
            # h2は大見出し、h3/h4は小見出し
            level = 2 if el.name == "h2" else 3
            elements.append(("heading", text, level))
        elif el.name in ("p", "li"):
            text = el.get_text(" ", strip=True)
            if is_skippable_text(text):
                continue
            if text == title:
                continue
            if not text and el.find("img"):
                continue
            text = re.sub(r"\s{2,}", "\n", text)
            if el.name == "li":
                text = f"・{text}"
            elements.append(("text", text, None))
        elif el.name == "img":
            src = el.get("src", "")
            if "googleusercontent.com/sitesv/" not in src:
                continue
            if src in seen_imgs:
                continue
            seen_imgs.add(src)
            elements.append(("image", src, None))

    elements = promote_headings(elements)

    # 重複除去
    deduped = []
    for item in elements:
        if item[0] == "text" and deduped and deduped[-1][0] == "text" and deduped[-1][1] == item[1]:
            continue
        deduped.append(item)
    elements = deduped

    # セクション化
    # セクション化 (大見出し → サブ見出しの階層構造)
    lead_lines = []
    lead_images = []
    sections = []
    current_section = None  # 大セクション
    current_sub = None      # サブセクション

    def push_to_current(kind, val):
        """テキストや画像を現在の最深セクションへ追加"""
        nonlocal current_sub, current_section
        target = current_sub or current_section
        if target is None:
            if kind == "text":
                lead_lines.append(val)
            elif kind == "image":
                lead_images.append(val)
            return
        if kind == "text":
            target["body"].append(val)
        elif kind == "image":
            target["images"].append(val)

    for item in elements:
        kind = item[0]
        val = item[1]
        level = item[2] if len(item) > 2 else None

        if kind == "heading":
            if level == 2 or current_section is None:
                # 大見出し: 新しい大セクション開始
                if current_section:
                    if current_sub:
                        current_section["subsections"].append(current_sub)
                        current_sub = None
                    sections.append(current_section)
                current_section = {
                    "heading": val,
                    "body": [],
                    "images": [],
                    "subsections": [],
                }
            else:
                # 小見出し: サブセクション開始
                if current_sub:
                    current_section["subsections"].append(current_sub)
                current_sub = {
                    "heading": val,
                    "body": [],
                    "images": [],
                }
        else:
            push_to_current(kind, val)

    if current_section:
        if current_sub:
            current_section["subsections"].append(current_sub)
        sections.append(current_section)

    # bodyを文字列化 + 画像振り分け
    cleaned_sections = []
    for s in sections:
        cleaned_subs = []
        for sub in s["subsections"]:
            cleaned_subs.append({
                "heading": sub["heading"],
                "body": "\n".join(sub["body"]).strip(),
                "images": list(sub["images"]),
            })

        section_images = list(s["images"])

        # === 画像の自動振り分け ===
        # Google Sites の構造上、サブセクションの「キャラ画像」が h3 より前に
        # 並んでいることがある。サブセクションに画像が無く、親セクション直下に
        # 「集合絵 + キャラ画像数枚」が固まっている場合、各キャラに割り当てる。
        subs_without_img = [sub for sub in cleaned_subs if not sub["images"]]
        if cleaned_subs and len(subs_without_img) == len(cleaned_subs):
            # サブセクションが全て画像なし
            n_subs = len(cleaned_subs)
            # 親セクションの画像数が「サブセクション数」または「サブセクション数+1」のとき振り分ける
            # +1 のときは先頭1枚を集合絵として残す
            if len(section_images) == n_subs:
                # 全部キャラ画像 → 先頭から順に各キャラへ
                for i, sub in enumerate(cleaned_subs):
                    sub["images"] = [section_images[i]]
                section_images = []
            elif len(section_images) == n_subs + 1:
                # 集合絵1枚 + キャラ画像N枚
                for i, sub in enumerate(cleaned_subs):
                    sub["images"] = [section_images[i + 1]]
                section_images = [section_images[0]]
            elif len(section_images) > n_subs:
                # 集合絵が複数 + キャラ画像N枚 (末尾N枚をキャラに割り当て)
                offset = len(section_images) - n_subs
                for i, sub in enumerate(cleaned_subs):
                    sub["images"] = [section_images[offset + i]]
                section_images = section_images[:offset]

        cleaned_sections.append({
            "heading": s["heading"],
            "body": "\n".join(s["body"]).strip(),
            "images": section_images,
            "subsections": cleaned_subs,
        })

    # 全画像 (サムネ用)
    all_images = list(lead_images)
    for s in cleaned_sections:
        all_images.extend(s["images"])
        for sub in s["subsections"]:
            all_images.extend(sub["images"])

    return {
        "title": title,
        "lead": "\n".join(lead_lines).strip(),
        "lead_images": lead_images,
        "sections": cleaned_sections,
        "videos": videos,
        "updated": updated,
        "all_images": all_images,
    }


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


# ---------- Discord ----------
def post_webhook(payload: dict) -> bool:
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        return False
    try:
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
        res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if res.status_code >= 300:
        print(f"Discord送信失敗: {res.status_code} {res.text[:300]}", file=sys.stderr)
        return False
    return True


def send_news(item: dict, article: dict, site_url: str) -> bool:
    """シンプルな通知: カテゴリ・タイトル・リード・サムネ・リンク"""
    category = item.get("category", "不明")
    color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["不明"])
    title = article.get("title") or item["title"]

    # リード文 (最大250字)
    lead = article.get("lead", "")
    if not lead and article.get("sections"):
        # リードがなければ最初のセクションの先頭を使う
        lead = article["sections"][0]["body"]
    if len(lead) > 250:
        lead = lead[:247].rstrip() + "…"

    # サムネ画像 (Discord用は元のGoogle URLを使う、ローカルパスはサイト内のみ有効)
    thumbnail = None
    originals = article.get("all_images_original") or article.get("all_images") or []
    if originals:
        thumbnail = originals[0]

    embed = {
        "color": color,
        "author": {"name": category},
        "title": title,
        "url": site_url if site_url else item["url"],
        "description": lead or "(本文なし)",
        "fields": [
            {"name": "POSTED", "value": item["date"], "inline": True},
        ],
        "footer": {"text": "電波人間 News"},
    }
    if article.get("updated"):
        embed["fields"].append({"name": "UPDATED", "value": article["updated"], "inline": True})
    if thumbnail:
        embed["image"] = {"url": thumbnail}

    payload = {
        "username": "電波人間 News",
        "embeds": [embed],
    }
    return post_webhook(payload)


# ---------- 画像ダウンロード ----------
IMG_DIR = Path("docs/assets/img")


def download_images_for_article(article: dict, slug: str) -> dict:
    """記事内の全画像URLをローカルにダウンロードし、URLを差し替える。
    既存ファイルがあればスキップ(キャッシュ)。
    """
    article_dir = IMG_DIR / slug
    article_dir.mkdir(parents=True, exist_ok=True)

    # 全画像URLを収集 (subsections含む)
    all_urls = list(article.get("lead_images", []))
    for sec in article.get("sections", []):
        all_urls.extend(sec.get("images", []))
        for sub in sec.get("subsections", []):
            all_urls.extend(sub.get("images", []))

    # URL → ローカル相対パス のマッピング
    url_to_local = {}
    for i, url in enumerate(all_urls, 1):
        if url in url_to_local:
            continue

        # URLから拡張子を推定
        ext = "jpg"
        local_name = f"{i:02d}.{ext}"
        local_path = article_dir / local_name

        # 既にDL済みならスキップ
        if local_path.exists() and local_path.stat().st_size > 0:
            url_to_local[url] = f"../assets/img/{slug}/{local_name}"
            continue

        try:
            res = requests.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                    "Referer": "https://newdenpafree.ap-gs.com/",
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "cross-site",
                },
                timeout=30,
            )
            res.raise_for_status()
            content = res.content
            ctype = res.headers.get("Content-Type", "").lower()

            if "png" in ctype:
                ext = "png"
            elif "gif" in ctype:
                ext = "gif"
            elif "webp" in ctype:
                ext = "webp"
            elif "jpeg" in ctype or "jpg" in ctype:
                ext = "jpg"

            if ext != "jpg":
                local_name = f"{i:02d}.{ext}"
                local_path = article_dir / local_name

            local_path.write_bytes(content)
            url_to_local[url] = f"../assets/img/{slug}/{local_name}"
            time.sleep(0.2)  
        except requests.RequestException as e:
            print(f"  画像DL失敗: {url[:60]}... {e}", file=sys.stderr)
            url_to_local[url] = url

    new_article = dict(article)
    new_article["lead_images"] = [url_to_local.get(u, u) for u in article.get("lead_images", [])]
    new_sections = []
    for sec in article.get("sections", []):
        new_sec = dict(sec)
        new_sec["images"] = [url_to_local.get(u, u) for u in sec.get("images", [])]
        new_subs = []
        for sub in sec.get("subsections", []):
            new_sub = dict(sub)
            new_sub["images"] = [url_to_local.get(u, u) for u in sub.get("images", [])]
            new_subs.append(new_sub)
        new_sec["subsections"] = new_subs
        new_sections.append(new_sec)
    new_article["sections"] = new_sections
    new_article["all_images"] = [url_to_local.get(u, u) for u in article.get("all_images", [])]
    new_article["all_images_original"] = list(article.get("all_images", []))

    return new_article


def fetch_news_list():
    html_text = ""
    try:
        html_text = fetch_html(NEWS_URL)
    except requests.RequestException as e:
        print(f"/news 取得失敗: {e}", file=sys.stderr)

    items = parse_news_list(html_text) if html_text else []

    if not items:
        print("/news からNews取得失敗。/top で再試行", file=sys.stderr)
        try:
            items = parse_news_list(fetch_html(TOP_URL))
        except requests.RequestException as e:
            print(f"/top 取得失敗: {e}", file=sys.stderr)

    return items


def main():
    state = load_state()
    sent_keys = set(state.get("sent", []))

    items = fetch_news_list()
    if not items:
        print("Newsが1件も取得できませんでした", file=sys.stderr)
        sys.exit(1)

    print(f"取得したNews件数: {len(items)}")

    items_with_articles = []
    for it in items:
        try:
            article_html = fetch_html(it["url"])
            article = parse_article(article_html, fallback_title=it["title"])
            article = download_images_for_article(article, it["slug"])
            items_with_articles.append((it, article))
            time.sleep(0.3)
        except requests.RequestException as e:
            print(f"記事取得失敗: {it['url']} - {e}", file=sys.stderr)
            items_with_articles.append((it, None))

    # サイト生成
    print(f"サイト生成中... ({len(items_with_articles)}件)")
    site_builder.write_site(items_with_articles)
    print(f"サイト生成完了: docs/")

    # 新着判定 → Discord 通知
    first_run = len(sent_keys) == 0
    new_items = [it for it in items if it["url"] not in sent_keys]

    if first_run:
        print(f"初回実行: {len(new_items)}件を既知化(通知なし)")
        for it in new_items:
            sent_keys.add(it["url"])
    else:
        # 古い→新しい順で通知
        articles_map = {it["url"]: art for it, art in items_with_articles}
        for it in reversed(new_items):
            print(f"新規News: [{it['category']}] {it['date']} {it['title']}")
            article = articles_map.get(it["url"])
            if article is None:
                print(f"  記事内容が取得できなかったためスキップ", file=sys.stderr)
                continue
            site_url = (
                f"{SITE_BASE_URL}/news/{it['slug']}.html"
                if SITE_BASE_URL else it["url"]
            )
            if send_news(it, article, site_url):
                sent_keys.add(it["url"])
                time.sleep(1.0)

    state["sent"] = sorted(sent_keys)
    save_state(state)
    print(f"完了。既知News件数: {len(sent_keys)}")


if __name__ == "__main__":
    main()
