import html
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DOCS_DIR = Path("docs")
NEWS_DIR = DOCS_DIR / "news"
ASSETS_DIR = DOCS_DIR / "assets"

SITE_TITLE = "電波人間 News"
SITE_TAGLINE = "公式お知らせアーカイブ"
SOURCE_BASE = "https://newdenpafree.ap-gs.com"

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Kosugi+Maru&family=Mochiy+Pop+One&family=Zen+Maru+Gothic:wght@500;700;900&display=swap');

:root {
    /* 背景・基調 */
    --bg: #fff7e8;           
    --bg-soft: #fff1d6;
    --bg-card: #ffffff;
    --ink: #2a2046;        
    --ink-soft: #5b4f7a;
    --ink-faint: #9b91b8;
    --line: #e8d9b8;
    --line-soft: #f1e5c8;

    --pop-orange: #ff7e3d;
    --pop-pink:   #ff5a8a;
    --pop-yellow: #ffc73a;
    --pop-cyan:   #39c5bb;
    --pop-green:  #7ed957;
    --pop-blue:   #4cb6ff;
    --pop-purple: #b586ff;

    --cat-stream: var(--pop-blue);
    --cat-event:  var(--pop-pink);
    --cat-other:  var(--pop-green);

    --font-display: "Mochiy Pop One", "Zen Maru Gothic", sans-serif;
    --font-title:   "Zen Maru Gothic", "Kosugi Maru", sans-serif;
    --font-body:    "Zen Maru Gothic", "Kosugi Maru", "ヒラギノ丸ゴ ProN", sans-serif;

    --max-w: 880px;
    --radius: 18px;
    --radius-sm: 12px;
    --shadow: 0 4px 0 #e8d9b8;
    --shadow-lift: 0 6px 0 #d4c39a;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
    background: var(--bg);
    background-image:
        radial-gradient(circle at 10% 20%, rgba(76, 182, 255, 0.08), transparent 30%),
        radial-gradient(circle at 90% 80%, rgba(255, 90, 138, 0.06), transparent 35%),
        radial-gradient(circle at 50% 50%, rgba(126, 217, 87, 0.04), transparent 50%);
    background-attachment: fixed;
    color: var(--ink);
    font-family: var(--font-body);
    font-feature-settings: "palt" 1;
    line-height: 1.85;
    letter-spacing: 0.02em;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
}

a { color: var(--pop-orange); text-decoration: none; transition: color 0.2s, transform 0.2s; }
a:hover { color: var(--pop-pink); }

img { max-width: 100%; height: auto; display: block; }


/* ───────── ヘッダー ───────── */
.site-header {
    padding: 24px 24px 20px;
    background:
        repeating-linear-gradient(
            -45deg,
            #fff7e8 0,
            #fff7e8 12px,
            #fff1d6 12px,
            #fff1d6 24px
        );
    border-bottom: 4px solid var(--ink);
    position: relative;
}
.site-header::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -10px;
    height: 6px;
    background: var(--pop-yellow);
    border-bottom: 2px solid var(--ink);
}
.site-header__inner {
    max-width: var(--max-w);
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}
.site-title {
    font-family: var(--font-display);
    font-size: 28px;
    line-height: 1;
    letter-spacing: 0.06em;
    color: var(--ink);
    display: flex;
    align-items: center;
    gap: 12px;
}
.site-title__icon {
    display: inline-block;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--pop-yellow);
    border: 3px solid var(--ink);
    position: relative;
    flex-shrink: 0;
}
.site-title__icon::before,
.site-title__icon::after {
    content: "";
    position: absolute;
    border: 2px solid var(--ink);
    border-radius: 50%;
    border-bottom: none;
    border-left: none;
    border-right: none;
}
.site-title__icon::before {
    width: 18px;
    height: 9px;
    top: 5px;
    left: 6px;
}
.site-title__icon::after {
    width: 26px;
    height: 13px;
    top: -1px;
    left: 2px;
}
.site-title a { color: var(--ink); }

.site-nav {
    display: flex;
    gap: 8px;
}
.site-nav a {
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 14px;
    color: var(--ink);
    background: var(--bg-card);
    padding: 8px 16px;
    border: 2px solid var(--ink);
    border-radius: 999px;
    box-shadow: 0 3px 0 var(--ink);
    transition: transform 0.1s, box-shadow 0.1s;
}
.site-nav a:hover {
    color: var(--ink);
    transform: translateY(2px);
    box-shadow: 0 1px 0 var(--ink);
}


.list-hero {
    max-width: var(--max-w);
    margin: 56px auto 32px;
    padding: 0 24px;
    text-align: center;
}
.list-hero__title {
    font-family: var(--font-display);
    font-size: 40px;
    color: var(--ink);
    line-height: 1.3;
    letter-spacing: 0.04em;
    text-shadow: 4px 4px 0 var(--pop-yellow);
}
.list-hero__sub {
    margin-top: 20px;
    font-size: 14px;
    color: var(--ink-soft);
    line-height: 1.8;
}

.news-list {
    max-width: var(--max-w);
    margin: 0 auto 96px;
    padding: 0 24px;
    list-style: none;
    display: grid;
    gap: 16px;
}
.news-item {
    background: var(--bg-card);
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    transition: transform 0.15s, box-shadow 0.15s;
}
.news-item:hover {
    transform: translate(-2px, -2px);
    box-shadow: var(--shadow-lift);
}
.news-item__link {
    display: grid;
    grid-template-columns: 110px 1fr auto;
    gap: 20px;
    align-items: center;
    padding: 20px 24px;
    color: var(--ink);
}
.news-item__link:hover { color: var(--ink); }

.news-item__date {
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 13px;
    color: var(--ink-soft);
    line-height: 1.4;
    text-align: center;
    padding: 4px 0;
    background: var(--bg-soft);
    border: 2px solid var(--ink);
    border-radius: var(--radius-sm);
}
.news-item__title {
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 17px;
    line-height: 1.6;
    letter-spacing: 0.03em;
}
.news-item__cat {
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 11px;
    color: #fff;
    padding: 6px 12px;
    border: 2px solid var(--ink);
    border-radius: 999px;
    box-shadow: 2px 2px 0 var(--ink);
    letter-spacing: 0.1em;
    white-space: nowrap;
}
.news-item__cat[data-cat="配信情報"] { background: var(--cat-stream); }
.news-item__cat[data-cat="イベント情報"] { background: var(--cat-event); }
.news-item__cat[data-cat="その他"] { background: var(--cat-other); }
.news-item__cat[data-cat="不明"] { background: var(--ink-faint); }


/* ───────── 詳細ページ ───────── */
.article {
    max-width: var(--max-w);
    margin: 0 auto;
    padding: 36px 24px 96px;
}
.article__back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 13px;
    color: var(--ink);
    background: var(--bg-card);
    padding: 8px 16px;
    border: 2px solid var(--ink);
    border-radius: 999px;
    box-shadow: 0 3px 0 var(--ink);
    margin-bottom: 32px;
    transition: transform 0.1s, box-shadow 0.1s;
}
.article__back:hover {
    color: var(--ink);
    transform: translateY(2px);
    box-shadow: 0 1px 0 var(--ink);
}

.article__header {
    background: var(--bg-card);
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 28px 28px 24px;
    margin-bottom: 32px;
    position: relative;
}
.article__cat {
    display: inline-block;
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 12px;
    color: #fff;
    padding: 6px 14px;
    border: 2px solid var(--ink);
    border-radius: 999px;
    box-shadow: 2px 2px 0 var(--ink);
    letter-spacing: 0.12em;
    margin-bottom: 16px;
}
.article__cat[data-cat="配信情報"] { background: var(--cat-stream); }
.article__cat[data-cat="イベント情報"] { background: var(--cat-event); }
.article__cat[data-cat="その他"] { background: var(--cat-other); }
.article__cat[data-cat="不明"] { background: var(--ink-faint); }

.article__title {
    font-family: var(--font-display);
    font-size: 30px;
    line-height: 1.5;
    color: var(--ink);
    letter-spacing: 0.03em;
}

.article__meta {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 18px;
    font-family: var(--font-title);
    font-weight: 500;
    font-size: 13px;
    color: var(--ink-soft);
}
.article__meta span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-soft);
    padding: 4px 12px;
    border-radius: 999px;
    border: 2px solid var(--line);
}
.article__meta strong {
    color: var(--ink);
    font-weight: 700;
}

.article__lead {
    background: var(--bg-card);
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 24px 28px;
    margin-bottom: 32px;
    font-size: 16px;
    line-height: 1.95;
    color: var(--ink);
    position: relative;
}
.article__lead::before {
    content: "";
    position: absolute;
    top: -12px;
    left: 24px;
    width: 40px;
    height: 24px;
    background: var(--pop-yellow);
    border: 2px solid var(--ink);
    border-radius: 6px;
    transform: rotate(-3deg);
}

.article__video {
    margin-bottom: 32px;
    aspect-ratio: 16 / 9;
    background: #000;
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    overflow: hidden;
}
.article__video iframe {
    width: 100%;
    height: 100%;
    border: 0;
    display: block;
}

/* セクション */
.section {
    background: var(--bg-card);
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 28px;
    margin-bottom: 24px;
    position: relative;
}
.section__heading {
    font-family: var(--font-display);
    font-size: 20px;
    color: var(--ink);
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 3px dotted var(--line);
    letter-spacing: 0.03em;
    line-height: 1.4;
    display: flex;
    align-items: center;
    gap: 12px;
}
.section__heading::before {
    content: "";
    display: inline-block;
    width: 14px;
    height: 14px;
    background: var(--pop-pink);
    border: 2px solid var(--ink);
    border-radius: 50%;
    flex-shrink: 0;
}
.section:nth-child(4n+1) .section__heading::before { background: var(--pop-pink); }
.section:nth-child(4n+2) .section__heading::before { background: var(--pop-cyan); }
.section:nth-child(4n+3) .section__heading::before { background: var(--pop-orange); }
.section:nth-child(4n+4) .section__heading::before { background: var(--pop-green); }

.section__body {
    font-size: 15px;
    line-height: 1.95;
    color: var(--ink);
}
.section__body p {
    margin-bottom: 1.2em;
}
.section__body p:last-child { margin-bottom: 0; }
.section__body ul {
    list-style: none;
    padding-left: 0;
    margin-bottom: 1.2em;
}
.section__body li {
    position: relative;
    padding-left: 26px;
    margin-bottom: 0.6em;
}
.section__body li::before {
    content: "●";
    position: absolute;
    left: 0;
    top: 0;
    color: var(--pop-pink);
    font-size: 12px;
    line-height: 1.95em;
}

/* 画像ギャラリー */
.gallery {
    display: grid;
    gap: 16px;
    margin-top: 20px;
}
.gallery--single { grid-template-columns: 1fr; }
.gallery--multi {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.gallery figure {
    background: #ffffff;
    border: 3px solid var(--ink);
    border-radius: var(--radius-sm);
    overflow: hidden;
    box-shadow: 0 4px 0 var(--ink-soft);
    transition: transform 0.15s, box-shadow 0.15s;
    padding: 0;
}
.gallery figure:hover {
    transform: translate(-2px, -2px);
    box-shadow: 0 6px 0 var(--ink-soft);
}
.gallery img {
    width: 100%;
    height: auto;
    display: block;
}

/* 公式リンク */
.article__source {
    margin-top: 32px;
    background: var(--bg-card);
    border: 3px solid var(--ink);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 22px 26px;
    font-size: 13px;
    color: var(--ink-soft);
    line-height: 1.8;
}
.article__source-label {
    font-family: var(--font-title);
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 6px;
}
.article__source-link {
    display: inline-block;
    margin-top: 12px;
    font-family: var(--font-title);
    font-weight: 700;
    font-size: 13px;
    color: #fff;
    background: var(--pop-orange);
    padding: 8px 18px;
    border: 2px solid var(--ink);
    border-radius: 999px;
    box-shadow: 0 3px 0 var(--ink);
    transition: transform 0.1s, box-shadow 0.1s;
}
.article__source-link:hover {
    color: #fff;
    transform: translateY(2px);
    box-shadow: 0 1px 0 var(--ink);
}


/* フッター */
.site-footer {
    background: var(--bg-soft);
    border-top: 4px solid var(--ink);
    padding: 32px 24px;
    color: var(--ink-soft);
    font-size: 12px;
    text-align: center;
    line-height: 2;
}
.site-footer a { color: var(--pop-orange); font-weight: 700; }
.site-footer__small {
    font-family: var(--font-title);
    font-size: 11px;
    color: var(--ink-faint);
    margin-top: 10px;
}


/* レスポンシブ */
@media (max-width: 600px) {
    .site-header__inner { flex-direction: column; align-items: flex-start; }
    .site-title { font-size: 22px; }
    .site-title__icon { width: 30px; height: 30px; }

    .list-hero { margin: 36px auto 24px; }
    .list-hero__title { font-size: 28px; text-shadow: 3px 3px 0 var(--pop-yellow); }

    .news-item__link {
        grid-template-columns: 1fr;
        gap: 12px;
        padding: 18px 20px;
    }
    .news-item__date {
        text-align: left;
        padding: 4px 12px;
        justify-self: start;
    }
    .news-item__cat {
        justify-self: start;
    }

    .article { padding: 24px 16px 64px; }
    .article__header { padding: 22px 22px 18px; }
    .article__title { font-size: 22px; }
    .article__lead { padding: 20px 22px; font-size: 15px; }
    .section { padding: 22px 22px; }
    .section__heading { font-size: 17px; }
    .gallery--multi { grid-template-columns: 1fr; }
}
"""


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def rel_path(from_url: str, to_path: str) -> str:
    """from_url(/news/xxx.html等)から to_path への相対パス"""
    from_dir = "/".join(from_url.split("/")[:-1])
    if from_dir == "" or from_dir == "/":
        return to_path.lstrip("/")
    depth = from_dir.count("/")
    return "../" * depth + to_path.lstrip("/")


def html_layout(title: str, body: str, *, page_url: str = "/") -> str:
    full_title = f"{esc(title)}｜{SITE_TITLE}" if title and title != SITE_TITLE else SITE_TITLE
    css_path = rel_path(page_url, "/assets/style.css")
    home_path = rel_path(page_url, "/index.html")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full_title}</title>
<meta name="description" content="{esc(SITE_TAGLINE)}">
<meta property="og:title" content="{full_title}">
<meta property="og:description" content="{esc(SITE_TAGLINE)}">
<meta property="og:type" content="article">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<header class="site-header">
  <div class="site-header__inner">
    <h1 class="site-title">
      <a href="{home_path}">
        <span class="site-title__icon"></span>
        <span>電波人間 News</span>
      </a>
    </h1>
    <nav class="site-nav">
      <a href="{home_path}">一覧</a>
      <a href="{SOURCE_BASE}/top" target="_blank" rel="noopener">公式</a>
    </nav>
  </div>
</header>

{body}

<footer class="site-footer">
  <div>
    出典: <a href="{SOURCE_BASE}/news" target="_blank" rel="noopener">newdenpafree.ap-gs.com</a>
  </div>
  <div>© Genius Sonority Inc.</div>
  <div class="site-footer__small">
    最終更新 {esc(datetime.now(JST).strftime("%Y年%m月%d日 %H:%M"))}
  </div>
</footer>
</body>
</html>
"""


def render_index(items: list) -> str:
    rows = []
    for it in items:
        page_url = f"news/{it['slug']}.html"
        rows.append(f"""
        <li class="news-item">
          <a class="news-item__link" href="{esc(page_url)}">
            <div class="news-item__date">{esc(it['date'])}</div>
            <div class="news-item__title">{esc(it['title'])}</div>
            <div class="news-item__cat" data-cat="{esc(it['category'])}">{esc(it['category'])}</div>
          </a>
        </li>""")

    body = f"""
<section class="list-hero">
  <h2 class="list-hero__title">お知らせ一覧</h2>
  <p class="list-hero__sub">公式の最新情報を新しい順に並べています。</p>
</section>
<ol class="news-list">
{''.join(rows)}
</ol>
"""
    return html_layout("お知らせ一覧", body, page_url="/index.html")


def render_article(item: dict, article: dict) -> str:
    cat = item.get("category", "不明")
    title = article.get("title") or item["title"]

    # リード文
    lead_html = ""
    if article.get("lead"):
        lead_lines = [esc(ln) for ln in article["lead"].split("\n") if ln.strip()]
        lead_html = "<div class=\"article__lead\">" + "<br>".join(lead_lines) + "</div>"

    # 動画
    video_html = ""
    for vid in article.get("videos", []):
        vid_id = vid.split("v=")[-1]
        video_html += f"""<div class="article__video">
  <iframe src="https://www.youtube.com/embed/{esc(vid_id)}" title="動画" allowfullscreen></iframe>
</div>"""

    # リード画像
    lead_images_html = ""
    if article.get("lead_images"):
        gallery_class = "gallery--single" if len(article["lead_images"]) == 1 else "gallery--multi"
        figs = "".join(
            f'<figure><img src="{esc(img)}" alt="" loading="lazy"></figure>'
            for img in article["lead_images"]
        )
        lead_images_html = f'<div class="gallery {gallery_class}">{figs}</div>'

    # セクション
    sections_html = []
    for sec in article.get("sections", []):
        body_html = render_section_body(sec["body"])
        gallery_html = ""
        if sec["images"]:
            gallery_class = "gallery--single" if len(sec["images"]) == 1 else "gallery--multi"
            figs = "".join(
                f'<figure><img src="{esc(img)}" alt="" loading="lazy"></figure>'
                for img in sec["images"]
            )
            gallery_html = f'<div class="gallery {gallery_class}">{figs}</div>'

        sections_html.append(f"""
<section class="section">
  <h3 class="section__heading">{esc(sec['heading'])}</h3>
  <div class="section__body">{body_html}</div>
  {gallery_html}
</section>""")

    meta_parts = [f"<span><strong>投稿</strong>{esc(item['date'])}</span>"]
    if article.get("updated"):
        meta_parts.append(f"<span><strong>更新</strong>{esc(article['updated'])}</span>")

    body = f"""
<article class="article">
  <a class="article__back" href="../index.html">← 一覧へ戻る</a>
  <header class="article__header">
    <span class="article__cat" data-cat="{esc(cat)}">{esc(cat)}</span>
    <h1 class="article__title">{esc(title)}</h1>
    <div class="article__meta">{''.join(meta_parts)}</div>
  </header>

  {lead_html}
  {video_html}
  {lead_images_html}
  {''.join(sections_html)}

  <div class="article__source">
    <div class="article__source-label">公式記事</div>
    最新の正確な情報は公式サイトで確認できます。
    <br><a class="article__source-link" href="{esc(item['url'])}" target="_blank" rel="noopener">公式記事を見る</a>
  </div>
</article>
"""
    return html_layout(title, body, page_url=f"/news/{item['slug']}.html")


def render_section_body(body: str) -> str:
    if not body:
        return ""
    lines = body.split("\n")
    result = []
    in_list = False
    para_lines = []

    def flush_para():
        if para_lines:
            text = "<br>".join(esc(ln) for ln in para_lines)
            result.append(f"<p>{text}</p>")
            para_lines.clear()

    for ln in lines:
        ln = ln.strip()
        if not ln:
            flush_para()
            if in_list:
                result.append("</ul>")
                in_list = False
            continue
        if ln.startswith("・"):
            flush_para()
            if not in_list:
                result.append("<ul>")
                in_list = True
            result.append(f"<li>{esc(ln[1:].strip())}</li>")
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            para_lines.append(ln)

    flush_para()
    if in_list:
        result.append("</ul>")
    return "\n".join(result)


def write_site(items_with_articles: list):
    DOCS_DIR.mkdir(exist_ok=True)
    NEWS_DIR.mkdir(exist_ok=True)
    ASSETS_DIR.mkdir(exist_ok=True)

    (ASSETS_DIR / "style.css").write_text(CSS, encoding="utf-8")

    items_only = [it for it, _ in items_with_articles]
    (DOCS_DIR / "index.html").write_text(
        render_index(items_only), encoding="utf-8"
    )

    for item, article in items_with_articles:
        if not article:
            continue
        page_path = NEWS_DIR / f"{item['slug']}.html"
        page_path.write_text(render_article(item, article), encoding="utf-8")

    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
