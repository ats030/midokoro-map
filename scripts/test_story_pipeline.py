"""Source drift, attempt limits, concurrency, abstention and legacy regressions."""
import copy
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import story_pipeline as pipeline


class PipelineChecks(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((pipeline.ROOT / "docs/story-candidates.json").read_text())["candidates"]
        self.candidate = copy.deepcopy(self.catalog[0])
        self.sections = {}
        for site in self.candidate["sites"]:
            passage = " ".join(site["anchors"])
            site["section_sha256"] = pipeline.digest(passage)
            self.sections[site["section"]] = passage

    def packet(self):
        return pipeline.packet_for(self.candidate, self.sections, "2026-10-14")

    def draft(self, packet):
        facts = {f["id"]: f for f in packet["facts"]}
        result = {"error": "", "title": packet["title"], "lead": "岩の違いを読みます。",
                  "intro": "出典にある地形を比較します。", "reading_title": "場所の解説"}
        for kind in ("places", "relations"):
            result[kind] = []
            for row in packet[kind]:
                body = " ".join(facts[f]["text"] for f in row["fact_ids"])
                if packet["schema_version"] == 1:
                    body += "見比べる視点を確かめます。" * max(0, (80-len(body)+11)//12)
                item = {"id": row["id"], "body": body, "evidence_ids": row["fact_ids"]}
                if kind == "relations":
                    item["title"] = "場所を比較する"
                result[kind].append(item)
        result["questions"] = [{"relation_id": r["id"], "label": "何が違う？"} for r in packet["relations"][:3]]
        return result

    def test_source_change_stops_packet_even_when_keywords_survive(self):
        self.sections[self.candidate["sites"][0]["section"]] += "変更された文"
        with self.assertRaisesRegex(pipeline.writer.StoryError, "出典の変更"):
            self.packet()

    def test_short_variable_draft_and_no_unverified_map(self):
        packet = self.packet()
        draft = self.draft(packet)
        pipeline.writer.validate_draft(draft, packet)
        rendered = pipeline.writer.render(draft, packet)
        self.assertIn("3地点", rendered)
        self.assertNotIn("5地点", rendered)
        self.assertNotIn('data-lat="None"', rendered)
        self.assertNotIn('<script src="/stories/story.js"', rendered)
        self.assertNotIn("ubuntu-server-app", rendered)
        self.assertIn("座標の確認待ち", rendered)

    def test_three_legacy_packets_render_without_schema_migration(self):
        for name in ("arita-porcelain", "kusatsu-yumomi", "kawagoe-festival"):
            with self.subTest(name=name):
                packet = json.loads((pipeline.ROOT / f"docs/story-packets/{name}.json").read_text())
                pipeline.writer.validate_packet(packet)
                rendered = pipeline.writer.render(self.draft(packet), packet)
                self.assertIn("5地点", rendered)
                self.assertIn('<script src="/stories/story.js"', rendered)

    def harness(self, local, generate):
        return (patch.object(pipeline, "LOCAL", Path(local)),
                patch.object(pipeline, "fetch_sections", return_value=(self.sections, b"synthetic")),
                patch.object(pipeline, "fingerprint", side_effect=lambda c, m: c["slug"]),
                patch.object(pipeline.writer, "request_json", return_value={"models": [{"name": "gemma4:12b", "digest": "test"}]}),
                patch.object(pipeline.writer, "generate", generate),
                patch.object(pipeline, "packet_for", return_value=self.packet()))

    def test_one_call_and_identical_input_is_not_retried(self):
        from unittest.mock import Mock
        generate = Mock(return_value={"model_digest": "test", "elapsed_seconds": 1, "eval_count": 1})
        with tempfile.TemporaryDirectory() as local:
            a,b,c,d,e,f = self.harness(local, generate)
            with a,b,c,d,e,f:
                self.assertEqual(pipeline.run(self.candidate["slug"])["status"], "draft")
                self.assertEqual(pipeline.run(self.candidate["slug"])["status"], "unchanged")
                self.assertEqual(generate.call_count, 1)

    def test_timeout_blocks_following_invocations(self):
        from unittest.mock import Mock
        generate = Mock(side_effect=TimeoutError("unknown server completion"))
        with tempfile.TemporaryDirectory() as local:
            a,b,c,d,e,f = self.harness(local, generate)
            with a,b,c,d,e,f:
                self.assertEqual(pipeline.run()["status"], "transport-unknown")
                with self.assertRaisesRegex(pipeline.writer.StoryError, "前回の処理"):
                    pipeline.run()
                self.assertEqual(generate.call_count, 1)

    def test_previous_draft_does_not_hide_source_drift(self):
        from unittest.mock import Mock
        generate = Mock(return_value={"model_digest": "test", "elapsed_seconds": 1, "eval_count": 1})
        with tempfile.TemporaryDirectory() as local:
            a,b,c,d,e,f = self.harness(local, generate)
            with a,b,c,d,e,f:
                self.assertEqual(pipeline.run(self.candidate["slug"])["status"], "draft")
                with patch.object(pipeline, "packet_for", side_effect=pipeline.writer.StoryError("出典の変更")):
                    result = pipeline.run(self.candidate["slug"])
                self.assertEqual(result["status"], "source-rejected")
                self.assertFalse(result["generation_attempted"])
                self.assertEqual(generate.call_count, 1)

    def test_rejected_source_does_not_starve_next_candidate(self):
        from unittest.mock import Mock
        generate = Mock(return_value={"model_digest": "test", "elapsed_seconds": 1, "eval_count": 1})
        with tempfile.TemporaryDirectory() as local:
            a,b,c,d,e,f = self.harness(local, generate)
            with a,b,c,d,e,f:
                with patch.object(pipeline, "packet_for", side_effect=[pipeline.writer.StoryError("出典の変更"), self.packet()]):
                    result = pipeline.run()
                self.assertEqual(result["status"], "draft")
                self.assertEqual(result["slug"], self.catalog[1]["slug"])
                self.assertEqual(len(result["source_rejections"]), 1)
                self.assertEqual(generate.call_count, 1)

    def test_concurrent_invocation_cannot_call_model(self):
        with tempfile.TemporaryDirectory() as local:
            with (Path(local) / "lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(pipeline, "LOCAL", Path(local)), patch.object(pipeline.writer, "request_json") as api:
                    with self.assertRaises(BlockingIOError):
                        pipeline.run()
                    api.assert_not_called()

    def test_source_url_redirect_and_parser_boundaries(self):
        with self.assertRaises(pipeline.writer.StoryError):
            pipeline.fetch_sections("http://localhost/private")
        self.assertIsNone(pipeline.NoRedirect().redirect_request(None, None, None, None, None, None))
        parser = pipeline.Sections()
        parser.feed('<h4>A</h4><p>one</p><script>ignore</script><h4>B</h4><p>two</p><h3>end</h3>')
        parser.finish()
        self.assertEqual(parser.sections, {"A": "one", "B": "two"})


if __name__ == "__main__":
    unittest.main()
