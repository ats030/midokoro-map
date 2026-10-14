"""Publication eligibility and reproducible output checks, without inference."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("publisher", HERE / "publish-story-pages.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationChecks(unittest.TestCase):
    def bundle(self):
        return json.loads((publisher.ROOT / "docs/published-stories/generated/oki-erosion-comparison.json").read_text())

    def reject(self, mutate):
        bundle = self.bundle()
        mutate(bundle)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bundle.json"
            path.write_text(json.dumps(bundle))
            with self.assertRaises(publisher.writer.StoryError):
                publisher.load_bundle(path)

    def test_raw_draft_or_unverified_coordinates_cannot_publish(self):
        self.reject(lambda b: b['provenance'].update(editorial_status='pending'))
        self.reject(lambda b: b['packet']['places'][0].update(location_status='pending'))
        self.reject(lambda b: b['packet']['places'][0].update(coordinate_source_url='file:///secret'))
        self.reject(lambda b: b['packet']['places'][0].update(coordinate_scope='model-invented'))

    def test_each_edited_bundle_is_valid_and_matches_published_html(self):
        for slug in publisher.SLUGS:
            with self.subTest(slug=slug):
                bundle = publisher.load_bundle(publisher.ROOT / f'docs/published-stories/generated/{slug}.json')
                html = publisher.render(bundle)
                self.assertEqual(html, (publisher.ROOT / f'frontend/stories/{slug}.html').read_text())
                self.assertNotIn('noindex', html)
                self.assertNotIn('data-story-preview', html)
                self.assertNotIn('・下書き', html)
                self.assertIn('data-site="midokoro-map"', html)
                self.assertIn('rel="canonical"', html)
                self.assertEqual(html.count('data-number='), 3)
                self.assertEqual(html.count('data-from='), 2)
                self.assertEqual(html.count('位置の出典：'), 3)
                self.assertIn('<script src="/stories/story.js"', html)
                self.assertNotIn('文化的なつながり', html)

    def test_bad_reference_and_nonfinite_coordinate_fail(self):
        self.reject(lambda b: b['draft']['relations'][0].update(evidence_ids=['invented']))
        self.reject(lambda b: b['packet']['places'][0].update(lat=float('nan')))

    def test_photo_requires_local_verified_licensed_bytes(self):
        for change in ({'src': 'https://example.com/photo.jpg'},
                       {'src': '/stories/photos/../secret.jpg'},
                       {'license': 'CC BY-NC 4.0'}, {'author': ''},
                       {'sha256': '0' * 64}, {'reuse_status': 'pending'},
                       {'license_url': 'https://example.com/license'}):
            with self.subTest(change=change):
                self.reject(lambda b: b['packet']['places'][0]['photo'].update(change))

    def test_photos_and_attribution_survive_static_render(self):
        for slug in publisher.SLUGS:
            bundle = publisher.load_bundle(publisher.ROOT / f'docs/published-stories/generated/{slug}.json')
            photo = next(p['photo'] for p in bundle['packet']['places'] if 'photo' in p)
            html = publisher.render(bundle)
            self.assertEqual(html.count('<figure class="story-photo">'), 1)
            for text in (photo['src'], photo['source_url'], photo['license_url'], photo['author'], 'loading="lazy"'):
                self.assertIn(text, html)

    def test_selection_features_only_the_four_new_articles(self):
        bundles = [publisher.load_bundle(publisher.ROOT / f'docs/published-stories/generated/{slug}.json') for slug in publisher.SLUGS]
        html = publisher.index_page(bundles)
        self.assertEqual(html, (publisher.ROOT / 'frontend/stories/index.html').read_text())
        for slug in publisher.SLUGS:
            self.assertIn(f'/stories/{slug}?from=home', html)
        for slug in ('arita-porcelain', 'kusatsu-yumomi', 'kawagoe-festival'):
            self.assertNotIn(f'/stories/{slug}', html)


if __name__ == '__main__':
    unittest.main()
