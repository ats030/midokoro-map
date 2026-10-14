"""Record real map UI against the offline fictional demonstration server."""
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlparse

from PIL import Image
from playwright.sync_api import sync_playwright

from demo_fixtures import ROOT
from run_demo import DemoHandler

MEDIA = ROOT / 'docs/media'


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    raw = MEDIA / 'raw'
    raw.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    errors, external, requests, frames = [], [], [], []
    try:
        with sync_playwright() as playwright, tempfile.TemporaryDirectory(prefix='midokoro-video-') as directory:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='ja-JP',
                                          record_video_dir=directory, record_video_size={'width': 1280, 'height': 900})

            def guard(route):
                url = urlparse(route.request.url)
                if f'{url.scheme}://{url.netloc}' != origin:
                    external.append(url.netloc)
                    route.abort()
                else:
                    requests.append({'method': route.request.method, 'path': url.path})
                    route.continue_()

            context.route('**/*', guard)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def screenshot(name):
                page.wait_for_timeout(1300)
                page.screenshot(path=str(MEDIA / name))
                frame = raw / f'{len(frames):02}.png'
                page.screenshot(path=str(frame))
                frames.append(frame)

            def ready(kind):
                page.wait_for_function('kind => window.midokoro?.kind === kind && document.querySelector("#status").hidden', arg=kind)

            page.goto(origin)
            ready('explore')
            root = page.locator('#view-explore')
            page.wait_for_function('Number(document.querySelector("#view-explore").shadowRoot.querySelector("#result-count").textContent) === 19')
            screenshot('01-explore.png')
            root.locator('#prefecture').select_option('熊本県')
            assert int(root.locator('#result-count').inner_text()) == 11
            screenshot('02-region.png')
            root.locator('#keyword').fill('架空の史跡')
            assert root.locator('#result-count').inner_text() == '2'
            root.locator('.explore-card').first.click()
            page.locator('#explore-detail').wait_for(state='visible')
            page.locator('#explore-detail #detail-title').wait_for(state='visible')
            screenshot('03-detail.png')
            page.keyboard.press('Escape')
            assert not page.locator('#explore-detail').is_visible()
            assert root.locator('#prefecture').input_value() == '熊本県'
            root.locator('#keyword').fill('存在しない展示用の名称')
            assert root.locator('#result-count').inner_text() == '0'
            assert root.locator('#explore-empty').is_visible()
            screenshot('04-empty.png')
            root.locator('#clear-filters').click()
            page.locator('#tab-onsen').click()
            ready('onsen')
            page.wait_for_function('document.querySelector("#view-onsen").shadowRoot.querySelector("#result-count").textContent === "4"')
            before = page.evaluate('({center:midokoro.map.getCenter(), zoom:midokoro.map.getZoom()})')
            screenshot('05-category.png')
            for kind in ['shiseki', 'omatsuri', 'tokusan', 'geo', 'explore']:
                page.locator('#tab-' + kind).click()
                ready(kind)
                expected = 3 if kind == 'geo' else 19 if kind == 'explore' else 4
                page.wait_for_function('({kind, expected}) => Number(document.querySelector("#view-"+kind).shadowRoot.querySelector("#result-count").textContent) === expected', arg={'kind': kind, 'expected': expected})
            after = page.evaluate('({center:midokoro.map.getCenter(), zoom:midokoro.map.getZoom()})')
            assert abs(before['center']['lat'] - after['center']['lat']) < 1e-6
            assert abs(before['center']['lng'] - after['center']['lng']) < 1e-6
            assert before['zoom'] == after['zoom']
            page.set_viewport_size({'width': 390, 'height': 844})
            root.locator('#mobile-prefecture').select_option('熊本県')
            assert root.locator('#prefecture').input_value() == '熊本県'
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            screenshot('06-mobile.png')
            page.set_viewport_size({'width': 1280, 'height': 900})
            page.reload()
            ready('explore')
            assert root.locator('#prefecture').input_value() == '熊本県', 'URL state was not restored'
            context.close()
            page.video.save_as(str(MEDIA / 'walkthrough.webm'))
            checks = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='ja-JP')
            checks.route('**/*', guard)
            page = checks.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            response = page.goto(origin + '/changelog')
            assert response.status == 200
            assert "connect-src 'self'" in response.headers['content-security-policy']
            assert 'ubuntu-server-app:8526' not in page.content()
            response = page.goto(origin + '/stories/arita-porcelain.html')
            assert response.status == 404, 'Non-demo story page was exposed'
            response = page.goto(origin + '/%2Fstories/arita-porcelain.html')
            assert response.status == 404, 'Encoded story alias bypassed the demo scope'
            assert not external, external
            assert not errors, errors
            checks.close()
            browser.close()
        images = [Image.open(frame).convert('RGB') for frame in frames]
        # Keep GIF canvas consistent when the final frame has a mobile viewport.
        images = [image if image.size == (1280, 900) else letterbox(image) for image in images]
        images[0].save(MEDIA / 'walkthrough.gif', save_all=True, append_images=images[1:], duration=1800, loop=0)
        report = {'profile': 'actual frontend with fixed fictional server responses and synthetic background tiles',
                  'assertions': ['19 synthetic entries', 'prefecture filter', 'keyword filter', 'detail and Escape',
                                 'empty results', 'six views switch', 'shared map position preserved',
                                 '390px no page overflow', 'URL state restored', 'changelog stays offline',
                                 'non-demo stories and encoded aliases rejected', 'no external requests', 'no page errors'],
                  'screenshots': 6, 'requests': requests, 'external_requests': external, 'page_errors': errors}
        (MEDIA / 'capture-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print('PASS: six labelled screenshots, GIF, WebM; regional search, details, shared map, mobile and URL restoration; no external requests')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def letterbox(image):
    canvas = Image.new('RGB', (1280, 900), '#edf1e9')
    canvas.paste(image, ((1280 - image.width) // 2, 0))
    return canvas


if __name__ == '__main__':
    main()
