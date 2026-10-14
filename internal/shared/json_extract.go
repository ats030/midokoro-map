package shared

// FirstJSONObject returns the first balanced {...} object block within s.
//
// It tracks brace depth while honoring JSON string literals (double quotes and
// backslash escapes) so that a brace inside a string value, or the closing brace
// of a nested object, does not truncate the extraction. This is the extraction
// the per-map LLM clients use to pull a single heading-resolution response out
// of a model output that may be wrapped in a code fence or a brief sentence.
func FirstJSONObject(s string) (string, bool) {
	start := -1
	depth := 0
	inString := false
	escaped := false
	for i := 0; i < len(s); i++ {
		c := s[i]
		if start < 0 {
			if c == '{' {
				start = i
				depth = 1
			}
			continue
		}
		if inString {
			if escaped {
				escaped = false
			} else if c == '\\' {
				escaped = true
			} else if c == '"' {
				inString = false
			}
			continue
		}
		switch c {
		case '"':
			inString = true
		case '{':
			depth++
		case '}':
			depth--
			if depth == 0 {
				return s[start : i+1], true
			}
		}
	}
	return "", false
}
