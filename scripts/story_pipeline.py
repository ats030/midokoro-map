#!/usr/bin/env python3
"""One bounded, evidence-pinned draft attempt; never publishes or schedules."""
import argparse
import datetime as dt
import fcntl
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/story-experiment"
SPEC = importlib.util.spec_from_file_location("story_writer", ROOT / "scripts/generate-story.py")
writer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writer)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class Sections(HTMLParser):
    """Extract h4 sections, ignoring executable/style content and navigation."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
        self.in_heading = False
        self.heading = []
        self.current = None
        self.sections = {}

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if self.skip:
            return
        if tag in {"h2", "h3", "h4"}:
            self.finish()
        if tag == "h4":
            self.in_heading = True
            self.heading = []
        if tag in {"p", "br", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag == "h4":
            self.in_heading = False
            self.current = "".join(self.heading).strip()
        elif tag in {"p", "li", "div"} and not self.skip:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_heading:
            self.heading.append(data)
        elif self.current:
            self.parts.append(data)

    def finish(self):
        if self.current:
            self.sections[self.current] = re.sub(r"\s+", " ", "".join(self.parts)).strip()
        self.current = None
        self.parts = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_sections(url):
    # This experiment admits only this already-reviewed source family.
    writer.require(re.fullmatch(r"https://geopark\.jp/geopark/[a-z_]+/", url), "出典URLが許可範囲外です")
    request = urllib.request.Request(url, headers={"User-Agent": "midokoro-map-story-experiment/1.0"})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        writer.require(response.headers.get_content_type() == "text/html", "出典がHTMLではありません")
        raw = response.read(1024 * 1024 + 1)
        writer.require(len(raw) <= 1024 * 1024, "出典が大きすぎます")
        charset = response.headers.get_content_charset() or "utf-8"
    parser = Sections()
    parser.feed(raw.decode(charset))
    parser.finish()
    return parser.sections, raw


def packet_for(candidate, sections, today):
    facts, places = [], []
    for i, site in enumerate(candidate["sites"]):
        passage = sections.get(site["section"], "")
        writer.require(passage and digest(passage) == site["section_sha256"],
                       site["name"] + ": 出典の変更・欠落。材料の再確認が必要です")
        writer.require(all(term in passage for term in site["anchors"]), "出典の照合語がありません")
        fid, pid = f"fact-{i+1}", f"place-{i+1}"
        facts.append({"id": fid, "text": site["claim"], "source_ids": ["official"]})
        places.append({"id": pid, "name": site["name"], "lat": None, "lng": None,
                       "location_status": "pending", "role": site["role"],
                       "visit_note": "所在地・見学条件は公式情報で確認してください。", "fact_ids": [fid]})
    relations = []
    for i in range(len(places)-1):
        relations.append({"id": f"relation-{i+1}", "from": places[i]["id"], "to": places[i+1]["id"],
                          "kind": "thematic", "note": "テーマによる比較です。同じ成因・時代・移動経路を示すものではありません。",
                          "fact_ids": [facts[i]["id"], facts[i+1]["id"]]})
    packet = {"schema_version": 2, "slug": candidate["slug"], "title": candidate["title"],
              "region": candidate["region"], "checked_at": today,
              "angle": candidate["angle"], "sources": [{"id": "official", "url": candidate["source_url"],
              "label": "日本ジオパークネットワーク・公式紹介", "checked_at": today}],
              "facts": facts, "places": places, "relations": relations,
              "forbidden_phrases": ["ぜひ訪れて", "歴史を感じる", "魅力を感じる"]}
    writer.validate_packet(packet)
    return packet


def fingerprint(candidate, model_digest):
    # Checking the clock or fetching identical evidence is not a new input.
    code = [(ROOT / "scripts" / file).read_text() for file in
            ("generate-story.py", "story-template.html", "story_pipeline.py")]
    return digest({"candidate": candidate, "model_digest": model_digest, "code": code,
                   "options": {"temperature": .2, "seed": 42, "num_ctx": 16384, "num_predict": 4096}})


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temp:
        json.dump(value, temp, ensure_ascii=False, indent=2)
        temp.write("\n")
    Path(temp.name).replace(path)


def run(slug=None, base="http://localhost:11434", model="gemma4:12b", timeout=600):
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_path = LOCAL / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {"attempts": []}
        writer.require(not any(a["status"] in {"running", "transport-unknown"} for a in state["attempts"]),
                       "前回の処理が未確定です。Ollamaの停止・結果を確認してstate.jsonを解決してください")
        candidates = json.loads((ROOT / "docs/story-candidates.json").read_text())["candidates"]
        if slug:
            candidates = [c for c in candidates if c["slug"] == slug]
            writer.require(candidates, "不明な候補です")
        tags = writer.request_json(base, "/api/tags", timeout=timeout)
        models = [m for m in tags.get("models", []) if m.get("name") == model and m.get("digest")]
        writer.require(len(models) == 1, "指定モデルのdigestを確認できません")
        rejected_sources = []
        for candidate in candidates:
            key = fingerprint(candidate, models[0]["digest"])
            try:
                sections, raw = fetch_sections(candidate["source_url"])
                packet = packet_for(candidate, sections, dt.datetime.now(dt.timezone.utc).date().isoformat())
            except (ValueError, OSError) as exc:
                check = {"slug": candidate["slug"], "status": "source-rejected", "error": str(exc),
                         "generation_attempted": False}
                state.setdefault("source_checks", {})[candidate["slug"]] = check
                save(state_path, state)
                if slug:
                    return check
                rejected_sources.append(check)
                continue
            state.setdefault("source_checks", {})[candidate["slug"]] = {
                "status": "matched", "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
            save(state_path, state)
            if any(a["fingerprint"] == key for a in state["attempts"]):
                continue
            attempt = {"slug": candidate["slug"], "fingerprint": key, "status": "running",
                       "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "human_review": "pending"}
            state["attempts"].append(attempt)
            save(state_path, state)  # Crash/timeout cannot trigger an automatic duplicate call.
            bundle = LOCAL / "runs" / key
            bundle.mkdir(parents=True, exist_ok=False)
            (bundle / "source.html").write_bytes(raw)
            save(bundle / "packet.json", packet)
            try:
                manifest = writer.generate(bundle / "packet.json", bundle / "draft", base, model, timeout)
                # /api/tags can change between selection and generation.
                writer.require(manifest["model_digest"] == models[0]["digest"], "モデルが処理中に変更されました")
                attempt.update(status="draft", elapsed_seconds=manifest["elapsed_seconds"],
                               eval_count=manifest["eval_count"], model_digest=manifest["model_digest"])
            except (ValueError, OSError) as exc:
                rejected = (bundle / "draft.failed.json").exists()
                attempt.update(status="output-rejected" if rejected else "transport-unknown", error=str(exc))
            save(state_path, state)
            attempt["source_rejections"] = rejected_sources
            return attempt  # At most one candidate and one generation per invocation.
        return {"status": "source-rejected" if rejected_sources else "unchanged",
                "attempts": 0, "source_rejections": rejected_sources}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model", default="gemma4:12b")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    try:
        result = run(args.slug, args.ollama_url, args.model, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["status"] in {"draft", "unchanged"} else 2)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"生成見送り: {exc}\n")
