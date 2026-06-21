import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

JST = timezone(timedelta(hours=9))

TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME", "denpaningen")
SEARCH_QUERY = os.environ.get("SEARCH_QUERY", f"ID:{TWITTER_USERNAME}")
RESULTS = int(os.environ.get("RESULTS", "40"))

API_URL = "https://search.yahoo.co.jp/realtime/api/v1/pagination"
STATE_FILE = Path("state.json")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DEBUG = os.environ.get("DEBUG") == "1"

EMBED_COLOR = 0x1DA1F2
WEBHOOK_NAME = "電波人間 Twitter"
DISPLAY_NAME = "電波人間のRPG FREE"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

TEXT_KEYS = ["displayTextBody", "displayTextFragments", "text", "body",
             "description", "tweet", "content", "message"]
ID_KEYS = ["id", "tweetId", "statusId", "id_str", "idStr"]
TIME_KEYS = ["createdAt", "created_at", "time", "date", "timestamp", "postedAt"]
HANDLE_KEYS = ["screenName", "screen_name", "userScreenName",
               "username", "userName", "userId", "handle"]
NAME_KEYS = ["name", "displayName", "userName", "nickname"]
ICON_KEYS = ["profileImage", "icon", "profileImageUrl", "imageUrl",
             "iconUrl", "image"]
USER_OBJ_KEYS = ["user", "author", "account", "profile"]
LIKE_KEYS = ["likesCount", "favoriteCount", "likeCount", "favorites",
             "likes", "favCount"]
RT_KEYS = ["retweetCount", "retweetsCount", "rtCount", "retweets", "shareCount"]


def _first_present(d: dict, keys):
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _find_user_obj(entry: dict):
    for k in USER_OBJ_KEYS:
        v = entry.get(k)
        if isinstance(v, dict):
            return v
    return None


def _deep_find_handle(obj, depth=0):
    if depth > 4 or not isinstance(obj, dict):
        return None
    for k in ("screenName", "screen_name", "userScreenName"):
        v = obj.get(k)
        if isinstance(v, str) and v:
            return v.lstrip("@")
    for v in obj.values():
        if isinstance(v, dict):
            r = _deep_find_handle(v, depth + 1)
            if r:
                return r
    return None


def _extract_text(entry: dict) -> str:
    for k in TEXT_KEYS:
        v = entry.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, list):
            parts = []
            for f in v:
                if isinstance(f, str):
                    parts.append(f)
                elif isinstance(f, dict):
                    parts.append(str(f.get("text") or f.get("value") or ""))
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def _format_time(raw) -> str:
    s = str(raw).strip()
    if not s:
        return ""
    if s.isdigit():
        n = int(s)
        if n > 10_000_000_000:
            n //= 1000
        try:
            return datetime.fromtimestamp(n, JST).strftime("%Y/%m/%d %H:%M")
        except (OSError, ValueError, OverflowError):
            return s
    return s


def _clean_permalink(url: str) -> str:
    if url and ("x.com" in url or "twitter.com" in url) and "?" in url:
        return url.split("?", 1)[0]
    return url


def fetch_page(start: int = 1, oldest_tweet_id: str = "") -> list:
    params = {
        "p": SEARCH_QUERY,
        "results": str(RESULTS),
    }
    if oldest_tweet_id:
        params["oldestTweetId"] = oldest_tweet_id
    elif start > 1:
        params["start"] = str(start)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://search.yahoo.co.jp/realtime/search",
    }
    res = requests.get(API_URL, params=params, headers=headers, timeout=30)
    res.raise_for_status()
    data = res.json()
    entries = (data.get("timeline") or {}).get("entry") or []
    if DEBUG and entries:
        print("[DEBUG] entry[0] full:",
              json.dumps(entries[0], ensure_ascii=False, indent=2)[:2000],
              file=sys.stderr)
    return entries


def extract_tweet(entry: dict) -> dict | None:
    tid = _first_present(entry, ID_KEYS)
    if tid is None:
        return None
    tid = str(tid)

    text = _extract_text(entry)
    created = _first_present(entry, TIME_KEYS) or ""

    user_obj = _find_user_obj(entry)
    handle = None
    name = None
    icon = None
    if user_obj:
        handle = _first_present(user_obj, HANDLE_KEYS)
        name = _first_present(user_obj, NAME_KEYS)
        icon = _first_present(user_obj, ICON_KEYS)
    handle = handle or _first_present(entry, ["screenName", "userId", "userScreenName"])
    handle = handle or _deep_find_handle(entry)
    name = name or _first_present(entry, ["userName", "displayName"])

    if isinstance(handle, str):
        handle = handle.lstrip("@")

    media_urls = []
    sensitive = bool(entry.get("possiblySensitive") or entry.get("sensitive"))
    for m in entry.get("media") or []:
        if not isinstance(m, dict):
            continue
        item = m.get("item") if isinstance(m.get("item"), dict) else m
        url = _first_present(item, ["mediaUrl", "url", "imageUrl", "thumbnailUrl"])
        if url:
            media_urls.append(url)

    permalink = _first_present(entry, ["permalink", "url", "tweetUrl", "link"])
    permalink = _clean_permalink(permalink) if permalink else permalink
    if not permalink:
        if handle and tid.isdigit():
            permalink = f"https://x.com/{handle}/status/{tid}"
        elif handle:
            permalink = f"https://x.com/{handle}"
        else:
            permalink = (
                "https://search.yahoo.co.jp/realtime/search?p="
                + requests.utils.quote(SEARCH_QUERY)
            )

    return {
        "id": tid,
        "text": text,
        "created": _format_time(created),
        "handle": handle or "",
        "name": name or (handle or TWITTER_USERNAME),
        "icon": icon or "",
        "media": media_urls,
        "sensitive": sensitive,
        "likes": _first_present(entry, LIKE_KEYS),
        "rt": _first_present(entry, RT_KEYS),
        "permalink": permalink,
    }


def fetch_tweets() -> list:
    try:
        entries = fetch_page()
    except requests.RequestException as e:
        print(f"Yahoo API 取得失敗: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"Yahoo API JSON 解析失敗: {e}", file=sys.stderr)
        return []

    tweets = []
    target = TWITTER_USERNAME.lstrip("@").lower()
    for entry in entries:
        t = extract_tweet(entry)
        if not t:
            continue
        h = (t["handle"] or "").lower()
        if h:
            if h != target:
                continue
        else:
            if not SEARCH_QUERY.lower().startswith(("id:", "@")):
                continue
        tweets.append(t)

    def sort_key(t):
        return (1, int(t["id"])) if t["id"].isdigit() else (0, t["id"])

    tweets.sort(key=sort_key, reverse=True)
    seen = set()
    uniq = []
    for t in tweets:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        uniq.append(t)
    return uniq


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


def build_payload(t: dict) -> dict:
    desc = t["text"] or "(本文なし)"
    if len(desc) > 1000:
        desc = desc[:997].rstrip() + "…"

    embed = {
        "color": EMBED_COLOR,
        "author": {
            "name": f"@{t['handle']}" if t["handle"] else f"@{TWITTER_USERNAME}",
        },
        "title": DISPLAY_NAME,
        "url": t["permalink"],
        "description": desc,
        "footer": {"text": "電波人間 Twitter"},
    }
    if t["icon"]:
        embed["author"]["icon_url"] = t["icon"]

    fields = []
    if t["created"]:
        fields.append({"name": "POSTED", "value": t["created"], "inline": True})
    eng = []
    if t["likes"] not in (None, ""):
        eng.append(f"♥ {t['likes']}")
    if t["rt"] not in (None, ""):
        eng.append(f"🔁 {t['rt']}")
    if eng:
        fields.append({"name": "ENGAGEMENT", "value": "  ".join(eng), "inline": True})
    if fields:
        embed["fields"] = fields

    if t["media"] and not t["sensitive"]:
        embed["image"] = {"url": t["media"][0]}
    elif t["media"] and t["sensitive"]:
        embed.setdefault("fields", []).append(
            {"name": "MEDIA", "value": "(センシティブ画像のため省略)", "inline": False}
        )

    return {"username": WEBHOOK_NAME, "embeds": [embed]}


def send_tweet(t: dict) -> bool:
    return post_webhook(build_payload(t))


def main():
    state = load_state()
    sent_ids = set(state.get("sent", []))

    tweets = fetch_tweets()
    if not tweets:
        print("ツイートが1件も取得できませんでした", file=sys.stderr)
        sys.exit(1)

    print(f"取得ツイート件数: {len(tweets)} (@{TWITTER_USERNAME})")

    first_run = len(sent_ids) == 0
    new_tweets = [t for t in tweets if t["id"] not in sent_ids]

    if first_run:
        print(f"初回実行: {len(new_tweets)}件を既知化(通知なし)")
        for t in new_tweets:
            sent_ids.add(t["id"])
    else:
        for t in reversed(new_tweets):
            preview = (t["text"] or "").replace("\n", " ")[:40]
            print(f"新規ツイート: {t['id']} {preview}")
            if send_tweet(t):
                sent_ids.add(t["id"])
                time.sleep(1.0)

    def k(x):
        return (1, int(x)) if str(x).isdigit() else (0, str(x))

    state["sent"] = sorted(sent_ids, key=k)[-500:]
    save_state(state)
    print(f"完了。既知ツイート件数: {len(state['sent'])}")


if __name__ == "__main__":
    main()
