"""Serve actual UI with fixed, fictional responses; never proxy external APIs."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from demo_fixtures import LABEL, ROOT, geo, rows

STATIC_NAMES = frozenset(item['path'].removeprefix('frontend/')
                        for item in json.loads((ROOT / 'docs/source-manifest.json').read_text())['files']
                        if item['path'].startswith('frontend/') and not item['path'].startswith('frontend/stories/'))

class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'frontend'), **kwargs)

    def log_message(self, *args):
        pass

    def respond(self, body, content_type='application/json; charset=utf-8', status=200):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def do_GET(self):
        path = '/' + unquote(urlparse(self.path).path).lstrip('/')
        if path == '/health':
            return self.respond({'status': 'ok', 'profile': 'fictional-demo'})
        if path == '/api/config':
            return self.respond({'defaultKind': 'explore', 'affiliateOrigins': [], 'summariesOnly': False})
        if path == '/stories' or path.startswith('/stories/'):
            return self.respond({'error': 'Themed pages are source references, not part of this offline demo'}, status=404)
        if path in {'/geo/geoparks.json', '/geo/geosites.json', '/geo/nationalparks.json'}:
            return self.respond(geo(Path(path).stem))
        if path.startswith('/demo-tiles/'):
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#edf1e9"/><path d="M0 128H256M128 0V256" stroke="#d4ddce"/><path d="M0 80Q100 130 256 45M40 0Q150 130 210 256" fill="none" stroke="#c1d2c6" stroke-width="6"/></svg>'
            return self.respond(svg.encode(), 'image/svg+xml')
        if path.startswith('/api/'):
            parts = path.strip('/').split('/')
            if len(parts) >= 3 and parts[1] in {'shiseki', 'omatsuri', 'onsen', 'tokusan'}:
                kind, endpoint = parts[1:3]
                collection = {'shiseki': 'shiseki', 'omatsuri': 'festivals', 'onsen': 'onsen', 'tokusan': 'tokusan'}[kind]
                if endpoint == collection and len(parts) == 3:
                    return self.respond(rows(kind))
                if endpoint in {'prefectures', 'categories', 'spring-types'}:
                    return self.respond([])
                if endpoint in {'wiki', 'wikiimage', 'wikidata'}:
                    return self.respond({'sections': {}, 'summary': '', 'sections_unavailable': False})
                if endpoint in {'hotel-area', 'jalan'}:
                    return self.respond({'hotels': []})
                if endpoint in {'sections', 'summary'}:
                    return self.respond({'sections': {'about': {'blocks': [{'type': 'paragraph', 'text': '架空の展示用説明です。実在する産品の情報ではありません。'}], 'source_url': 'https://example.invalid/demo', 'summary': ''}}, 'sections_unavailable': False, 'sections_retry': False})
            return self.respond({'error': 'Endpoint not used in this fixed-response demo'}, status=404)
        if path.endswith('/regions.json'):
            return self.respond([])
        if path.endswith('/images.json'):
            return self.respond({'photos': {}, 'blocked_fallback': []})
        if path.endswith('/furusato-affiliate.json'):
            return self.respond({})
        name = 'index.html' if path == '/' else 'changelog.html' if path == '/changelog' else path.lstrip('/')
        target = (ROOT / 'frontend' / name).resolve()
        if not target.is_relative_to(ROOT / 'frontend') or not target.is_file() or target.relative_to(ROOT / 'frontend').as_posix() not in STATIC_NAMES:
            return self.respond({'error': 'Not found'}, status=404)
        if target.name == 'runtime.js':
            source = target.read_text().replace('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', '/demo-tiles/{z}/{x}/{y}.svg')
            source = source.replace('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', '展示用の合成背景（地図データではありません）')
            return self.respond(source.encode(), 'text/javascript; charset=utf-8')
        if target.suffix == '.html':
            source = target.read_text()
            source = source.replace('<script src="http://ubuntu-server-app:8526/v.js" data-site="midokoro-map" defer></script>', '')
            source = source.replace('</head>', '<style>body{padding-top:32px}.demo-label{position:fixed;top:0;left:0;right:0;z-index:100000;background:#20382b;color:white;padding:7px;text-align:center;font:12px sans-serif}</style></head>')
            source = source.replace('<body>', '<body><div class="demo-label">' + LABEL + '</div>')
            return self.respond(source.encode(), 'text/html; charset=utf-8')
        # Only files explicitly imported into the publication can be served.
        return self.respond(target.read_bytes(), self.guess_type(str(target)))

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path.endswith('/geocoding/reverse'):
            return self.respond({'success': True, 'location': '展示用の架空住所', 'full_location': '展示用の架空住所'})
        return self.respond({'error': 'This demo does not store events or data'}, status=405)


def main():
    print('Fictional demonstration UI: http://127.0.0.1:8541/ (not the Go production API)', flush=True)
    with ThreadingHTTPServer(('127.0.0.1', 8541), DemoHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
