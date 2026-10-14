package shared

import "testing"

func TestBlankItemsDoNotBlockCompletion(t *testing.T) {
	// Document-level audit is kept: a section marked summarized must carry
	// actual content.
	section := PreparedSection{Status: "summarized", Items: []PreparedItem{}}
	if SummaryComplete(map[string]PreparedSection{"about": section}, []string{"about"}) {
		t.Fatal("empty summary/items passed")
	}
	// Blank item rows are dropped from the output and no longer force a
	// retry: retrying would re-read the cached degenerate answer and never
	// recover, so the section's actual content decides the status.
	section = Prepared("", []map[string]string{{}}, true, "source", "text", true)
	if section.Status != "no_source" || len(section.Items) != 0 {
		t.Fatalf("blank-only rows blocked completion: %+v", section)
	}
	section = Prepared("有効な要約", []map[string]string{{}}, true, "source", "text", true)
	if section.Status != "summarized" || section.Summary != "有効な要約" || len(section.Items) != 0 {
		t.Fatalf("valid summary with blank rows must be summarized: %+v", section)
	}
}
