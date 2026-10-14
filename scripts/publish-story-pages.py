#!/usr/bin/env python3
"""Render explicitly edited story bundles; never reads raw experiment drafts."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ("muroto-sea-and-land", "oki-erosion-comparison",
         "shimabara-different-volcanoes", "hakusan-rock-and-water")
ORIGIN = "https://midokoro-map.ats030.workers.dev"
spec = importlib.util.spec_from_file_location("story_writer", ROOT / "scripts/generate-story.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def load_bundle(path):
    bundle = json.loads(Path(path).read_text())
    packet, draft, provenance = bundle["packet"], bundle["draft"], bundle["provenance"]
    writer.require(provenance.get("editorial_status") == "edited-for-publication",
                   "公開用に編集した資料だけを指定してください")
    writer.require(provenance.get("authorization") and provenance.get("editorial_actor"),
                   "編集者と公開指示の記録が必要です")
    writer.validate_draft(draft, packet)
    for place in packet["places"]:
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
        label = '公式案内の地図中心を代表位置として使用' if place['coordinate_scope'] == 'official-map-center' else '公式案内の地図で示された代表位置'
        anchor = f'<p class="source">位置の出典：<a href="{writer.e(place["coordinate_source_url"])}" target="_blank" rel="noopener noreferrer">{label}</a></p>'
        page = page.replace(f'<a class="select-place" href="#{place["id"]}"', anchor + f'\n  <a class="select-place" href="#{place["id"]}"', 1)
    return page


def index_page(bundles):
    cards = []
    for i, bundle in enumerate(bundles, 1):
        packet, draft = bundle['packet'], bundle['draft']
        link = '/stories/' + packet['slug'] + '?from=home'
        cards.append(f'<article><p class="place-kicker">{i:02} / {writer.e(packet["region"])}</p>'
                     f'<h2><a href="{link}">{writer.e(draft["title"])}</a></h2>'
                     f'<p>{writer.e(draft["lead"])}</p>'
                     f'<a class="select-place" href="{link}">{len(packet["places"])}地点のつながりをたどる →</a></article>')
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>土地のつながりをたどる｜みどころマップ</title>
<meta name="description" content="室戸、隠岐、島原半島、手取川。岩や地形に残る記録を、3地点の比較から読む4つの地図。">
<link rel="canonical" href="{ORIGIN}/stories"><meta property="og:type" content="website"><meta property="og:title" content="土地のつながりをたどる">
<meta property="og:description" content="室戸、隠岐、島原半島、手取川。気になる問いから、地形の違いをたどる。"><meta property="og:url" content="{ORIGIN}/stories">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/tokens.css"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/stories/story.css">
<script src="http://ubuntu-server-app:8526/v.js" data-site="midokoro-map" defer></script></head>
<body class="story-page"><a class="skip-link" href="#story-main">本文へ</a><header class="site-header"><a class="brand" href="/"><img src="/favicon.svg" alt="" width="28" height="28"><span>みどころマップ</span></a><nav class="story-nav" aria-label="サイト"><a href="/">全国の地図</a></nav></header>
<main id="story-main"><section class="story-lead"><p class="eyebrow">土地のつながりをたどる</p><h1>その場所を、<br>もう一つの場所から知る。</h1><p class="lead-copy">岩は何を残し、水は何を動かした？<br>気になる問いから、3つの場所を見比べる地図へ。</p><p>点線はテーマによる比較です。同じ成因や時代、訪問順を示すものではありません。</p></section><section class="story-reading" aria-label="テーマを選ぶ"><div class="place-articles">{''.join(cards)}</div></section></main></body></html>
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
