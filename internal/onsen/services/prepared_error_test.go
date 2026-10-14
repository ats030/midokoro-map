package services

import (
	"context"
	"encoding/json"
	"io"
	"midokoro-map/internal/shared"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// A section whose generation failed must surface its cause; otherwise the
// worker records a retry checkpoint with an empty error.
func TestPrepareSummaryReportsSectionGenerationError(t *testing.T) {
	useTempSummaryCache(t, 100)
	t.Setenv("ONSEN_SUMMARY_DISABLE", "")
	lines := []string{"概要の原文。"}
	headings := []map[string]string{}
	for _, spec := range sectionSpecs {
		lines = append(lines, spec.candidates[0], "原文。")
		headings = append(headings, map[string]string{"line": spec.candidates[0], "level": "2"})
	}
	text := strings.Join(lines, "\n")
	wiki := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("action") == "parse" {
			_ = json.NewEncoder(w).Encode(map[string]any{"parse": map[string]any{"sections": headings}})
		} else {
			_ = json.NewEncoder(w).Encode(map[string]any{"query": map[string]any{"pages": []map[string]string{{"title": "温泉", "extract": text}}}})
		}
	}))
	defer wiki.Close()
	withWikipediaBase(t, wiki)
	model := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"message": map[string]string{"content": `{"summary":`}})
	}))
	defer model.Close()
	old := OllamaBaseURL
	OllamaBaseURL = model.URL
	defer func() { OllamaBaseURL = old }()
	saveSummary("midokoro-about-v1::"+shared.SourceHash(lines[0]), "概要の要約。")
	sections, err := PrepareSummary(context.Background(), "温泉", "", "", "")
	if err == nil {
		t.Fatalf("section failure returned no error: %+v", sections)
	}
	for _, spec := range sectionSpecs {
		if !strings.Contains(err.Error(), spec.key+":") {
			t.Fatalf("error %q does not name section %s", err, spec.key)
		}
		if sections[spec.key].Status != "retry" {
			t.Fatalf("failed section %s not marked retry", spec.key)
		}
	}
}

// A food/tourism failure on the onsen article is not an error once the
// municipality fallback fills that section.
func TestPrepareSummaryFallbackClearsSectionError(t *testing.T) {
	useTempSummaryCache(t, 100)
	t.Setenv("ONSEN_SUMMARY_DISABLE", "")
	withPlaces(t, map[string]string{
		"Q1":  fakePlace("Q1", []string{"Q40434727"}, "Q10", ""),
		"Q10": fakePlace("Q10", []string{"Q1059478"}, "", "古里町"),
	})
	lines := []string{"概要の原文。"}
	headings := []map[string]string{}
	for _, spec := range sectionSpecs {
		lines = append(lines, spec.candidates[0], "温泉側原文。")
		headings = append(headings, map[string]string{"line": spec.candidates[0], "level": "2"})
	}
	text := strings.Join(lines, "\n")
	muniText := "古里町は町。\n名産\n町側原文。\n観光スポット\n町側原文。"
	muniHeadings := []map[string]string{{"line": "名産", "level": "2"}, {"line": "観光スポット", "level": "2"}}
	wiki := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		title, body, hs := "温泉", text, headings
		if strings.Contains(r.URL.RawQuery, "%E5%8F%A4%E9%87%8C%E7%94%BA") {
			title, body, hs = "古里町", muniText, muniHeadings
		}
		if r.URL.Query().Get("action") == "parse" {
			_ = json.NewEncoder(w).Encode(map[string]any{"parse": map[string]any{"sections": hs}})
		} else {
			_ = json.NewEncoder(w).Encode(map[string]any{"query": map[string]any{"pages": []map[string]string{{"title": title, "extract": body}}}})
		}
	}))
	defer wiki.Close()
	withWikipediaBase(t, wiki)
	model := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, _ := io.ReadAll(r.Body)
		content := `{"summary":`
		if strings.Contains(string(req), "町側原文") {
			content = `{"summary":"町の要約。","items":[{"label":"名産","value":"町側原文"}]}`
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"message": map[string]string{"content": content}})
	}))
	defer model.Close()
	old := OllamaBaseURL
	OllamaBaseURL = model.URL
	defer func() { OllamaBaseURL = old }()
	for _, spec := range sectionSpecs {
		if spec.key == "food" || spec.key == "tourism" {
			continue
		}
		key := summaryCacheKey("温泉", spec.label+" v3")
		saveSummary(key, "既存の要約。")
		saveSummary("midokoro-source-v1:"+key, shared.SourceHash(text))
	}
	saveSummary("midokoro-about-v1:Q1:"+shared.SourceHash(lines[0]), "概要の要約。")
	sections, err := PrepareSummary(context.Background(), "温泉", "Q1", "", "")
	if err != nil {
		t.Fatalf("filled section kept its error: %v", err)
	}
	for _, key := range []string{"food", "tourism"} {
		if sections[key].Status == "retry" || len(sections[key].Items) == 0 {
			t.Fatalf("%s not filled by municipality: %+v", key, sections[key])
		}
	}
}
