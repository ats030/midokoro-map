"""Build/test the Go source in a temporary checkout with fictional SQLite data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from demo_fixtures import ROOT, write_test_databases


def main():
    go = os.getenv('MIDOKORO_GO') or shutil.which('go')
    node = os.getenv('MIDOKORO_NODE') or shutil.which('node')
    if not go or not node:
        raise SystemExit('Go 1.25 and Node.js are required; MIDOKORO_GO/MIDOKORO_NODE can select existing binaries')
    environment = {name: os.environ[name] for name in ('PATH', 'HOME', 'LANG', 'SYSTEMROOT') if name in os.environ}
    environment.update({'GOTOOLCHAIN': 'go1.25.0', 'TOKUSAN_AMAZON_URL': ''})
    for kind in ['SHISEKI', 'OMATSURI', 'ONSEN', 'TOKUSAN', 'GEO']:
        environment[kind + '_SUMMARY_DISABLE'] = '1'
    with tempfile.TemporaryDirectory(prefix='midokoro-portfolio-check-') as directory:
        checkout = Path(directory)
        for name in ['cmd', 'internal', 'frontend', 'cloudflare', 'go.mod', 'go.sum']:
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, checkout / name)
            else:
                shutil.copyfile(source, checkout / name)
        write_test_databases(checkout / 'data')
        result = subprocess.run([go, 'test', '-json', './...'], cwd=checkout, env=environment, capture_output=True, text=True, timeout=300)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        passes = [e for e in events if e.get('Test') and e.get('Action') == 'pass']
        skips = [e for e in events if e.get('Test') and e.get('Action') == 'skip']
        failed = [e for e in events if e.get('Action') == 'fail']
        if result.returncode:
            for event in events:
                if event.get('Action') == 'output' and ('FAIL' in event.get('Output','') or event.get('Test') in {e.get('Test') for e in failed}):
                    print(event.get('Output', ''), end='')
            print(result.stderr)
            raise SystemExit(result.returncode)
        subprocess.run([go, 'build', '-buildvcs=false', '-o', str(checkout / 'app-server'), './cmd/server'], cwd=checkout, env=environment, check=True)
        subprocess.run([node, '--test', 'scripts/test-explore.mjs', 'scripts/test-geo-media.mjs'], cwd=ROOT, env=environment, check=True)
        report = {'profile': 'isolated temporary checkout with synthetic SQLite; no production catalog',
                  'go_pass_events': len(passes), 'go_skips': [{'package':e['Package'], 'test':e['Test']} for e in skips],
                  'go_build': 'pass', 'javascript_tests': 'pass', 'go_version': subprocess.check_output([go, 'version'], env=environment, text=True).strip()}
        (ROOT / 'docs/check-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(f'PASS: Go {len(passes)} passing test/subtest events, {len(skips)} skipped optional production-data tests; Go server build and JS tests passed')


if __name__ == '__main__':
    main()
