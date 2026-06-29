## Notes / conventions

### Column conventions (Common Voice)

- **clip id**: `path` (mp3 filename)
- **transcript**: `sentence`
- **durations**: `clip_durations.tsv` with columns:
  - `clip`: mp3 filename
  - `duration[ms]`: integer milliseconds

### “Audio long, text short” vs “Text long, audio short”

Two complementary derived metrics:

- **Audio long, text short**:
  - `ratio_sec_per_char = duration_s / max(char_len, 1)` (s/char)
  - larger ⇒ suspicious (e.g., 10s audio but “ja”)
- **Text long, audio short**:
  - `chars_per_sec = char_len / duration_s`
  - larger ⇒ suspicious (too many chars packed into too few seconds)

### Recommended thresholds

Prefer data-driven thresholds:
- upper tail: `> p99`, `> p99.9`, Tukey upper fence
- lower tail: `< p1`, `< p0.1`, Tukey lower fence

For the “text long, audio short” view, always add a minimum text length filter (e.g. `char_len ≥ 30`) to avoid tiny-text artifacts.

