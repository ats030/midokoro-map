#!/usr/bin/env python3
"""Render explicitly edited story bundles; never reads raw experiment drafts."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ("muroto-sea-and-land", "oki-erosion-comparison",
         "shimabara-different-volcanoes", "hakusan-rock-and-water")
ORIGIN = "https://midokoro-map.ats030.workers.dev"
spec = importlib.util.spec_from_file_location("story_writer", ROOT / "scripts/generate-story.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)

PHOTO_LICENSES = {
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}


def validate_photo(photo):
    writer.require(isinstance(photo, dict), "写真情報はobjectです")
    writer.require(photo.get("reuse_status") == "approved" and photo.get("commercial_use") is True,
                   "写真の利用条件の確認が必要です")
    writer.require(isinstance(photo.get("src"), str) and
                   re.fullmatch(r"/stories/photos/[a-z0-9]+(?:-[a-z0-9]+)*\.jpg", photo["src"]),
                   "写真は確認済みのローカルJPEGを指定してください")
    for field in ("alt", "caption", "author", "source_file", "modification"):
        writer.text(photo.get(field), "photo." + field, 500)
    writer.date(photo.get("checked_at"), "photo.checked_at")
    writer.require(photo.get("license") in PHOTO_LICENSES and
                   photo.get("license_url") == PHOTO_LICENSES[photo["license"]], "写真のライセンスが不正です")
    url = writer.urllib.parse.urlsplit(photo.get("source_url", ""))
    writer.require(url.scheme == "https" and url.netloc == "commons.wikimedia.org" and
                   url.path.startswith("/wiki/File:") and not url.query and not url.fragment,
                   "写真ごとのCommons出典が必要です")
    for field in ("width", "height"):
        writer.require(type(photo.get(field)) is int and 0 < photo[field] <= 1920, "画像寸法が不正です")
    path = ROOT / "frontend" / photo["src"].lstrip("/")
    writer.require(path.is_file(), "写真ファイルがありません")
    raw = path.read_bytes()
    writer.require(raw.startswith(b"\xff\xd8\xff") and len(raw) <= 2 * 1024 * 1024 and
                   hashlib.sha256(raw).hexdigest() == photo.get("sha256"), "写真の形式・サイズ・ハッシュが一致しません")


def photo_figure(photo):
    e = writer.e
    return (f'<figure class="story-photo"><img src="{e(photo["src"])}" alt="{e(photo["alt"])}" '
            f'width="{photo["width"]}" height="{photo["height"]}" loading="lazy" decoding="async">'
            f'<figcaption><span>{e(photo["caption"])}</span><span class="photo-credit">'
            f'写真：{e(photo["author"])} / <a href="{e(photo["license_url"])}" target="_blank" rel="noopener noreferrer">'
            f'{e(photo["license"])}</a> / <a href="{e(photo["source_url"])}" target="_blank" rel="noopener noreferrer">'
            f'Wikimedia Commons</a>。{e(photo["modification"])}</span></figcaption></figure>')


def load_bundle(path):
    bundle = json.loads(Path(path).read_text())
    packet, draft, provenance = bundle["packet"], bundle["draft"], bundle["provenance"]
    writer.require(provenance.get("editorial_status") == "edited-for-publication",
                   "公開用に編集した資料だけを指定してください")
    writer.require(provenance.get("authorization") and provenance.get("editorial_actor"),
                   "編集者と公開指示の記録が必要です")
    writer.validate_draft(draft, packet)
    writer.date(provenance.get("published_at"), "published_at")
    for place in packet["places"]:
        if "photo" in place:
            validate_photo(place["photo"])
        writer.require(place.get("location_status") == "representative" and
                       place.get("coordinate_scope") in {"official-map-marker", "official-map-center"},
                       "代表座標の確認が必要です")
        writer.date(place.get("coordinate_checked_at"), "coordinate_checked_at")
        url = writer.urllib.parse.urlsplit(place.get("coordinate_source_url", ""))
        writer.require(url.scheme == "https" and url.hostname and not url.username and not url.password,
                       "座標の出典URLが必要です")
    return bundle


def render(bundle):
    packet, draft = bundle["packet"], bundle["draft"]
    page = writer.render(draft, packet)
    if 'data-site="midokoro-map"' not in page:
        page = page.replace('</head>', '  <script src="http://ubuntu-server-app:8526/v.js" data-site="midokoro-map" defer></script>\n</head>')
    page = page.replace('  <meta name="robots" content="noindex,nofollow">\n', '')
    page = page.replace("みどころマップ・下書き", "みどころマップ")
    page = page.replace(' data-story-preview="true"', '')
    canonical = ORIGIN + "/stories/" + packet["slug"]
    page = page.replace('</head>', f'  <link rel="canonical" href="{canonical}">\n'
                        f'  <meta property="og:type" content="article">\n'
                        f'  <meta property="og:url" content="{canonical}">\n</head>')
    page = page.replace('</header>', '<nav class="story-nav" aria-label="サイト"><a href="/stories">テーマを選ぶ</a><a href="/">全国の地図</a></nav></header>')
    page = page.replace('Ollamaで執筆した下書きです。出典・年代・因果関係を確認してから公開してください。',
                        'Ollamaで作成した下書きを、出典と照合して編集しています。')
    page = page.replace('      <p>下書きの探索操作は集客評価用の操作件数に含めません。</p>\n', '')
    for place in packet["places"]:
        if "photo" in place:
            heading = '<h3>' + writer.e(place["name"]) + '</h3>'
            page = page.replace(heading, heading + photo_figure(place["photo"]), 1)
        label = '公式案内の地図中心を代表位置として使用' if place['coordinate_scope'] == 'official-map-center' else '公式案内の地図で示された代表位置'
        anchor = f'<p class="source">位置の出典：<a href="{writer.e(place["coordinate_source_url"])}" target="_blank" rel="noopener noreferrer">{label}</a></p>'
        page = page.replace(f'<a class="select-place" href="#{place["id"]}"', anchor + f'\n  <a class="select-place" href="#{place["id"]}"', 1)
    return page


def index_page(bundles):
    cards = []
    # Canonical order breaks same-day ties independently of caller input order.
    ordered = sorted(bundles, key=lambda b: SLUGS.index(b["packet"]["slug"]))
    for bundle in ordered:
        writer.date(bundle["provenance"].get("published_at"), "published_at")
    ordered.sort(key=lambda b: b["provenance"]["published_at"], reverse=True)
    for bundle in ordered:
        packet, draft = bundle['packet'], bundle['draft']
        link = '/stories/' + packet['slug'] + '?from=home'
        photo = next((p["photo"] for p in packet["places"] if "photo" in p), None)
        cards.append(f'<article class="story-index-entry">'
                     + (photo_figure(photo) if photo else '') +
                     f'<div class="story-index-copy"><p class="place-kicker">{writer.e(packet["region"])} · <time datetime="{bundle["provenance"]["published_at"]}">{bundle["provenance"]["published_at"]} 公開</time></p><h2><a href="{link}">{writer.e(draft["title"])}</a></h2>'
                     f'<p>{writer.e(draft["lead"])}</p>'
                     f'<a class="select-place" href="{link}">{len(packet["places"])}地点のつながりをたどる →</a></div></article>')
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>土地のつながりをたどる｜みどころマップ</title>
<meta name="description" content="室戸、隠岐、島原半島、手取川。岩や地形に残る記録を、3地点の比較から読む4つの地図。">
<link rel="canonical" href="{ORIGIN}/stories"><meta property="og:type" content="website"><meta property="og:title" content="土地のつながりをたどる">
<meta property="og:description" content="室戸、隠岐、島原半島、手取川。気になる問いから、地形の違いをたどる。"><meta property="og:url" content="{ORIGIN}/stories">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/tokens.css"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/stories/story.css">
<script src="http://ubuntu-server-app:8526/v.js" data-site="midokoro-map" defer></script></head>
<body class="story-page story-index"><a class="skip-link" href="#story-main">本文へ</a><header class="site-header"><a class="brand" href="/"><img src="/favicon.svg" alt="" width="28" height="28"><span>みどころマップ</span></a><nav class="story-nav" aria-label="サイト"><a href="/">全国の地図</a></nav></header>
<main id="story-main"><header class="story-index-heading"><h1>土地のつながりをたどる</h1><p>岩や地形に残る記録を、土地を見比べながら読む。</p><p>新しい記事から掲載しています。</p></header><section class="story-index-list" aria-label="記事一覧">{''.join(cards)}</section></main></body></html>
'''


def build():
    bundles = [load_bundle(ROOT / f"docs/published-stories/generated/{slug}.json") for slug in SLUGS]
    for slug, bundle in zip(SLUGS, bundles):
        writer.require(bundle["packet"]["slug"] == slug, "ファイル名とslugが異なります")
    # Validate/render every article before touching any output file.
    pages = {slug + ".html": render(bundle) for slug, bundle in zip(SLUGS, bundles)}
    pages["index.html"] = index_page(bundles)
    for name, page in pages.items():
        (ROOT / "frontend/stories" / name).write_text(page)
    return pages


if __name__ == "__main__":
    print(json.dumps({"rendered": list(build())}, ensure_ascii=False))
