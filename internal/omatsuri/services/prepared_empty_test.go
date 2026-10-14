package services

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestEmptyAnswerAndExplicitNoneBothCompleteAsNoSource(t *testing.T) {
	for _, content := range []string{`{"summary":"","items":[]}`, `なし`} {
		t.Run(content, func(t *testing.T) {
			model := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				_ = json.NewEncoder(w).Encode(map[string]any{"message": map[string]string{"content": content}})
			}))
			defer model.Close()
			old := OllamaBaseURL
			OllamaBaseURL = model.URL
			defer func() { OllamaBaseURL = old }()
			got, err := generateSectionContent(context.Background(), "概要", "要約する", "原文。")
			// A well-formed empty object and the explicit なし token both mean the
			// model found nothing to structure for this section. Treat both as the
			// no_source (none) verdict, not an error, so thin sections complete
			// instead of retrying forever.
			if err != nil || got.Summary != SummaryNone {
				t.Fatalf("empty answer %q should complete as no_source, got err=%v got=%+v", content, err, got)
			}
		})
	}
}
