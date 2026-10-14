package services

import (
	"path/filepath"
	"strings"
	"testing"
)

func useTempGeoSummaryCache(t *testing.T) *SummaryCache {
	t.Helper()
	cache := newSummaryCache(filepath.Join(t.TempDir(), "summaries.json"), 16)
	GeoProfile.cache() // run the lazy load first so cleanup restores a loaded cache
	orig := geoSummaryCache
	geoSummaryCache = cache
	t.Cleanup(func() { geoSummaryCache = orig })
	return cache
}

func TestGeoProfileUsesLandformHeadingsAndItsOwnCache(t *testing.T) {
	useTempSummaryCache(t, 16)
	geoCache := useTempGeoSummaryCache(t)
	fw := newFakeWikipedia(t,
		[]wikipediaHeading{{Line: "成因", Level: 2}, {Line: "特徴", Level: 2}, {Line: "アクセス", Level: 2}, {Line: "天然記念物", Level: 2}},
		"概要\n\n成因\n\n約1万年前の噴火で溶岩が流れた。\n\n特徴\n\n柱状節理が並ぶ。\n\nアクセス\n\nJR駅から徒歩15分。\n\n天然記念物\n\n1931年に国の天然記念物に指定。")
	withWikipediaBase(t, fw)
	withFakeOllama(t, newFakeOllama(t, `溶岩が冷えて柱状節理ができた。`))
	t.Setenv("SHISEKI_SUMMARY_DISABLE", "")

	origin, features, access, protection, transient, err := GeoProfile.FetchPanelSections(t.Context(), "テスト史跡")
	if err != nil || transient {
		t.Fatalf("FetchPanelSections: err=%v transient=%v", err, transient)
	}
	for name, section := range map[string]PanelSection{"成り立ち": origin, "特徴・見どころ": features, "アクセス": access, "指定・保護": protection} {
		if section.Summary == "" {
			t.Errorf("%s: expected a summary", name)
		}
	}
	if len(geoCache.byKey) == 0 {
		t.Error("geo summaries should be stored in the geo cache")
	}
	if len(summaryCache.byKey) != 0 {
		t.Errorf("geo summaries leaked into the shiseki cache: %d entries", len(summaryCache.byKey))
	}
}

func TestShisekiProfileKeepsShisekiHeadings(t *testing.T) {
	useTempSummaryCache(t, 16)
	useTempGeoSummaryCache(t)
	fw := newFakeWikipedia(t, []wikipediaHeading{{Line: "成因", Level: 2}}, "概要\n\n成因\n\n約1万年前の噴火。")
	withWikipediaBase(t, fw)
	t.Setenv("SHISEKI_SUMMARY_DISABLE", "1")

	history, _, _, _, _, err := FetchPanelSections(t.Context(), "テスト史跡")
	if err != nil {
		t.Fatal(err)
	}
	if len(history.Blocks) != 0 {
		t.Errorf("shiseki 歴史 must not match the geo-only heading 成因: %+v", history)
	}
	origin, _, _, _, _, err := GeoProfile.FetchPanelSections(t.Context(), "テスト史跡")
	if err != nil {
		t.Fatal(err)
	}
	if len(origin.Blocks) == 0 {
		t.Error("geo 成り立ち should match 成因")
	}
}

// The shiseki prompts must stay byte-identical so existing shiseki behavior and
// cache expectations are unchanged; only GeoProfile uses the landform framing.
func TestProfilePromptsFrameTheirApp(t *testing.T) {
	const shisekiSummary = "日本語の史跡アプリの情報編集者です。記事本文から指示された情報を抜き出して、自然な日本語で簡潔な要約を1つの段落にまとめてください。記事の事実のみを用い、推測や追加の情報は含めません。該当する記述が全くないと判断できる場合は、1語で「" + SummaryNone + "」とだけ答えてください。"
	const shisekiHeading = "あなたは日本語の史跡アプリの編集者です。記事の見出しと内容を照らして、指定されたセクションへ見出しを割り当ててください。推測は含めません。該当しないセクションの値は空文字列にしてください。出力はJSONオブジェクト1行のみです。"
	if got := summaryPromptSystem(ShisekiProfile.appName); got != shisekiSummary {
		t.Errorf("shiseki summary prompt changed: %q", got)
	}
	if got := headingPromptSystem(ShisekiProfile.appName); got != shisekiHeading {
		t.Errorf("shiseki heading prompt changed: %q", got)
	}
	for _, prompt := range []string{summaryPromptSystem(GeoProfile.appName), headingPromptSystem(GeoProfile.appName)} {
		if !strings.Contains(prompt, "地形・地質") || strings.Contains(prompt, "史跡") {
			t.Errorf("geo prompt should frame landforms, not shiseki: %q", prompt)
		}
	}
}

func TestGeoProfileSendsLandformSystemPrompt(t *testing.T) {
	useTempSummaryCache(t, 16)
	useTempGeoSummaryCache(t)
	fw := newFakeWikipedia(t, []wikipediaHeading{{Line: "地形の成り立ち", Level: 2}}, "概要\n\n地形の成り立ち\n\n約1万年前の噴火で溶岩が流れた。")
	withWikipediaBase(t, fw)
	ollama := newFakeOllama(t, `溶岩が冷えて柱状節理ができた。`)
	ollama.headingBody = `{"origin":"地形の成り立ち","features":"","access":"","protection":""}`
	withFakeOllama(t, ollama)
	t.Setenv("SHISEKI_SUMMARY_DISABLE", "")

	// 地形の成り立ち is not a candidate heading, so the LLM heading pass runs too.
	if _, _, _, _, _, err := GeoProfile.FetchPanelSections(t.Context(), "テスト地形"); err != nil {
		t.Fatal(err)
	}
	systems := ollama.systemPrompts()
	var headings, summaries int
	for _, system := range systems {
		switch {
		case strings.HasPrefix(system, headingPromptSystem(geoAppName)):
			headings++
		case system == summaryPromptSystem(geoAppName):
			summaries++
		default:
			t.Errorf("geo request used a non-geo system prompt: %q", system)
		}
	}
	if headings == 0 || summaries == 0 {
		t.Errorf("want geo heading and summary requests, got %d heading / %d summary of %d", headings, summaries, len(systems))
	}
}
