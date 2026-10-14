package shared

import "testing"

func TestFirstJSONObject(t *testing.T) {
	cases := []struct {
		name   string
		in     string
		want   string
		wantOk bool
	}{
		{
			name:   "plain flat object",
			in:     `{"access":"yes","match":"x"}`,
			want:   `{"access":"yes","match":"x"}`,
			wantOk: true,
		},
		{
			name:   "nested object is not truncated at inner close",
			in:     `{"a":"1","b":{"c":"2"}}`,
			want:   `{"a":"1","b":{"c":"2"}}`,
			wantOk: true,
		},
		{
			name:   "close brace inside string value does not truncate",
			in:     `{"note":"see { and } here","k":"v"}`,
			want:   `{"note":"see { and } here","k":"v"}`,
			wantOk: true,
		},
		{
			name:   "escaped quote inside string is honored",
			in:     `{"note":"say \"hi\" ok","k":"v"}`,
			want:   `{"note":"say \"hi\" ok","k":"v"}`,
			wantOk: true,
		},
		{
			name:   "json wrapped in backtick fence with preamble",
			in:     "The answer is:\n```json\n{\"access\":\"no\"}\n```\nDone.",
			want:   `{"access":"no"}`,
			wantOk: true,
		},
		{
			name:   "leading sentence before object",
			in:     `Result {"ok":true} note`,
			want:   `{"ok":true}`,
			wantOk: true,
		},
		{
			name:   "stray close brace before object still finds object",
			in:     `} weird } then {"a":"1"}`,
			want:   `{"a":"1"}`,
			wantOk: true,
		},
		{
			name:   "no object at all",
			in:     "no json here at all",
			want:   "",
			wantOk: false,
		},
		{
			name:   "unclosed object returns false",
			in:     `{"a":"1"`,
			want:   "",
			wantOk: false,
		},
		{
			name:   "only the first object is returned",
			in:     `{"a":"1"} then {"b":"2"}`,
			want:   `{"a":"1"}`,
			wantOk: true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := FirstJSONObject(tc.in)
			if ok != tc.wantOk {
				t.Fatalf("ok = %v, want %v", ok, tc.wantOk)
			}
			if !ok {
				return
			}
			if got != tc.want {
				t.Fatalf("got  %q\nwant %q", got, tc.want)
			}
		})
	}
}
