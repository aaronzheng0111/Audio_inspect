---
name: filtered-csv-report
description: >
  Generate a polished report set from the unified CSVs produced by the
  `csv-cleaning-pipeline` skill (`CSV/<source>_<ts>.csv`): one **overview**
  PDF/MD comparing every source side-by-side, **plus one PDF/MD per source**
  with full distribution charts, outlier counts/thresholds/ranges, and
  outlier samples. Reports cover four ratio metrics together
  (`ratio_sec_per_char`, `ratio_sec_per_word`, `chars_per_sec`,
  `words_per_sec`) so you can see both pacing (s/char, s/word) and speaking
  rate (chars/s, words/s) at the same time. Use when the user asks for a
  side-by-side view of the cleaned German audio datasets, a per-dataset
  distribution PDF after cleaning, or wants to know the count + threshold +
  actual range of outliers (`> p99`, `> p99.9`, `> Tukey high`, `< p1`,
  `< Tukey low`) on any of the four ratio metrics.
---

# Filtered CSV report (unified CSVs → overview + per-source MD/PDF)

## When to use

Use this skill when the user wants to:

- compare the **cleaned, unified CSVs** (one per source) side-by-side,
- see a **dashboard** with clip counts, total hours, duration / transcript
  distributions, and outliers across sources,
- generate **one PDF per source** (deep-dive on the cleaned data) **plus**
  one cross-source overview PDF in the same run,
- know **how many outliers** each source contains, **at what thresholds**
  (p99, p99.9, Tukey fences, p1) and **the actual min..max range** of the
  matched values,
- produce snapshots they can hand to teammates without exposing the raw TSVs.

This skill is **downstream** of `Skill/csv-cleaning-pipeline/`. It reads
**only** the unified CSVs in `CSV/<source>_<YYYYmmdd-HHMMSS>.csv` and
expects the leading columns documented there:

```
audio_name, source, path, duration_s, <original metadata…>
```

If the upstream cleaner has changed those leading columns, fix the cleaner
first — do not patch this skill to work around a different schema.

## Quick workflow

1. Make sure `CSV/` contains the latest cleaned CSVs (re-run
   `csv-cleaning-pipeline` if needed).
2. Run the report from workspace root:

   ```bash
   python "Skill/filtered-csv-report/scripts/generate_filtered_csv_report.py" \
       --csv-dir "CSV" \
       --out-dir "report/filtered-csv-comparison"
   ```

3. Open the **overview PDF** at the top of `report/filtered-csv-comparison/`
   and the **per-source PDF** under each `<source>/` subfolder. Every chart
   is also saved as a PNG under the matching `assets/` folder so you can
   drop them into slides directly.

## The four ratio metrics

All quantile tables, outlier statistics tables, and per-source ratio
boxplots iterate the same `RATIO_METRICS` list (defined at the top of
`scripts/generate_filtered_csv_report.py`):

| Metric | Formula | What it captures |
|---|---|---|
| `ratio_sec_per_char` | `duration_s / char_len` | per-character pacing — high = audio long & text short |
| `ratio_sec_per_word` | `duration_s / word_len` | per-word pacing — high = drawn-out delivery |
| `chars_per_sec`      | `char_len / duration_s` | char-level speaking rate — high = fast/dense |
| `words_per_sec`      | `word_len / duration_s` | word-level speaking rate |

To add or rename a metric, edit `RATIO_METRICS` once — the quantile tables,
outlier tables, overview boxplot grid, per-source boxplot grid, and per-source
log-x histograms all pick it up automatically.

## Output layout

```
<out-dir>/
├── filtered_csv_comparison.pdf            ← overview (cross-source)
├── filtered_csv_comparison.md
├── assets/                                ← overview charts
│   ├── clip_counts_per_source.png
│   ├── total_hours_per_source.png
│   ├── duration_boxplot_grid.png
│   ├── char_len_boxplot_grid.png
│   ├── duration_overlay_hist.png
│   ├── ratio_sec_per_char_boxplot_grid.png
│   ├── ratio_sec_per_word_boxplot_grid.png
│   ├── chars_per_sec_boxplot_grid.png
│   └── words_per_sec_boxplot_grid.png
└── <source>/                              ← one folder per source
    ├── <source>_filtered_report.pdf       ← per-source deep-dive
    ├── <source>_filtered_report.md
    └── assets/
        ├── duration_hist.png
        ├── sentence_length_chars_hist.png
        ├── boxplot_distributions.png      ← duration_s / char_len / word_len
        ├── boxplot_ratios.png             ← 4-panel: every RATIO_METRIC (log y)
        ├── ratio_sec_per_char_hist_logx.png
        ├── ratio_sec_per_word_hist_logx.png
        ├── chars_per_sec_hist_logx.png
        ├── words_per_sec_hist_logx.png
        └── long_text_chars_per_second_hist_logx.png   ← chars/s, char_len ≥ 30
```

## What the overview report contains

| Section | Content |
|---|---|
| **Cover** | Navy hero block, 4-column metric grid (sources, total clips, total hours, mean clip duration) |
| **1. Source roster** | Per-source table: source, rows, unique clips, total hours, mean duration, % empty transcripts, transcript col, latest CSV filename + mtime |
| **2. Cross-source quantiles** | Side-by-side quantile tables for `duration_s`, `char_len`, `word_len` **and every metric in RATIO_METRICS** — rows = source, cols = p25/p50/p75/p90/p99 |
| **3. Outlier counts & ranges (per ratio metric)** | One subsection per metric. Inside each metric subsection: one block per source containing a 5-rule table (`> p99`, `> p99.9`, `> Tukey high`, `< p1`, `< Tukey low`) with `threshold`, `count`, `%`, and `actual range = [min, max]` of the matched values |
| **4. Charts** | Cross-source charts: clip counts bar, total hours bar, duration boxplot grid, char_len boxplot grid, duration overlay histogram, **plus one boxplot grid per `RATIO_METRIC` (log y)** |
| **5. Per-source highlights** | One short page per source showing top N audio-long / text-short and top N text-long / audio-short outliers (with full transcript) |

## What each per-source report contains

| Section | Content |
|---|---|
| **Cover** | Navy hero block, 4-column metric grid (rows, total audio, mean duration, empty %) |
| **1. Overview** | Two-column key/value table: csv path + mtime, transcript col, rows, unique clips, total audio, mean duration, empty transcripts |
| **2. Distribution quantiles** | One table: rows = `duration_s` / `char_len` / `word_len` **+ every metric in RATIO_METRICS**; cols = p0/p25/p50/p75/p90/p99/p100 |
| **3. Outlier counts & ranges (per ratio metric)** | One subsection per `RATIO_METRIC` — each contains the 5-rule outlier table for this single source |
| **4. Charts** | Distribution charts: duration histogram, char_len histogram, distribution boxplot (`duration_s` / `char_len` / `word_len`), ratio boxplot grid (4 panels, log y), one log-x histogram per `RATIO_METRIC`, plus the "long-text/short-audio" `chars_per_sec` view (`char_len ≥ 30`) |
| **5. Outlier samples** | Top N audio-long / text-short and top N text-long / audio-short outlier cards with full transcript |

## Outlier statistics (counts + thresholds + ranges)

This is the section the user usually wants when they ask "how many outliers
do I have, and what range do they fall in?". The script auto-computes it
for **each source × every metric in `RATIO_METRICS`** (currently four):

- `ratio_sec_per_char` (s/char) — main "audio long / text short" indicator
- `ratio_sec_per_word` (s/word) — per-word pacing
- `chars_per_sec` (chars/s) — char-level speaking rate
- `words_per_sec` (words/s) — word-level speaking rate

For each metric the script reports five rules:

| rule | threshold | what it catches |
|---|---|---|
| `> p99` | 99th percentile | top 1 % heaviest tail |
| `> p99.9` | 99.9th percentile | very-extreme tail |
| `> Tukey high` | `Q3 + 1.5 × IQR` | classic boxplot outlier (high side) |
| `< p1` | 1st percentile | bottom 1 % |
| `< Tukey low` | `Q1 − 1.5 × IQR` | classic boxplot outlier (low side) |

For every rule the row in the table contains:

- `threshold` — the boundary value
- `count` — number of rows that satisfy the rule
- `%` — `count / n × 100`
- `actual range` — the **observed `[min, max]`** of values that fell into
  the rule (so a `> p99` row with range `[0.505, 5.232]` immediately tells
  you the actual extreme reaches 5.232 s/char)

This is reported as a navy-header table both in the **per-source PDF**
(section 3, four subsections — one per metric) and the **overview PDF**
(section 3, four subsections — one per metric, each containing one block
per source). The Markdown mirrors the same structure.

**Note on `chars_per_sec`**: the **outlier statistics** use the full
`chars_per_sec` distribution (every row with `duration_s > 0`). The
**top-N outlier samples** at the end of the per-source PDF and the
"text long, audio short" sample cards in the overview keep the older
`char_len ≥ 30` filter (`--long-text-min-chars`) — that filter only exists
to avoid flagging tiny-text artifacts when *picking individual rows to
listen to*, not for the population-level statistics.

## Chart conventions

| Chart family | Where | Notes |
|---|---|---|
| `clip_counts_per_source.png`, `total_hours_per_source.png` | overview | Bars sorted descending; per-bar value label |
| `duration_boxplot_grid.png`, `char_len_boxplot_grid.png` | overview | One panel per source; mean ◆, median line, manual outlier dots (≤ 400 sampled with jitter) |
| `<metric>_boxplot_grid.png` (one per `RATIO_METRIC`) | overview | One panel per source, **log y** axis so heavy tails are visible |
| `duration_overlay_hist.png` | overview | One translucent histogram per source on shared axes (xlim = 0–20 s) |
| `duration_hist.png`, `sentence_length_chars_hist.png` | per-source | Linear histogram, red dashed median |
| `<metric>_hist_logx.png` (one per `RATIO_METRIC`) | per-source | Log-x histogram for heavy-tailed distributions |
| `long_text_chars_per_second_hist_logx.png` | per-source | Same chart filtered to `char_len ≥ 30` — kept for the "text long, audio short" investigation |
| `boxplot_distributions.png` | per-source | 3-panel grid: `duration_s` / `char_len` / `word_len`; char_len & word_len exclude 0 rows (annotated) |
| `boxplot_ratios.png` | per-source | 4-panel grid (log y): every `RATIO_METRIC` in declaration order |

All charts use the same palette and style as `audio-metadata-report`:
- Off-white axes background `#FAFBFF`, navy titles `#1E3A5F`
- Red dashed median lines (`#DC2626`) for single-distribution panels
- Distinct categorical colors per source pinned by name hash (so the same
  source always renders in the same color across runs)

## Font rules (critical — same as audio-metadata-report)

The PDF font is selected inside `_build_pdf` like this:

```python
cjk  = "Helvetica"
bold = "Helvetica-Bold"

_cjk_count = combined_text.str.contains(
    r"[\u4e00-\u9fff\u3040-\u30ff]", regex=True
).sum()
if _cjk_count / max(len(combined_text), 1) > 0.01:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    cjk = bold = "STSong-Light"
```

`combined_text` is the concatenation of every detected transcript column
across every source. The 1 % threshold is identical to `audio-metadata-report`
and exists for the same reason: STSong-Light renders Latin with very tight
letter-spacing, so a Latin-only multi-source corpus must never trigger it.
**Never lower or remove the threshold.**

## Transcript column auto-detection

Each source uses a different transcript column name:

| Source | Transcript column |
|---|---|
| `cv-corpus-25.0-2026-03-09-de` | `sentence` |
| `sps-corpus-3.0-2026-03-09-de` | `transcription` |
| `openslr-thorsten-de` | `sentence` |
| `kaggle-archive-de` | `sentence` |

The script auto-detects in this order and reports its choice in the
console + the source roster table:

1. `transcription`
2. `sentence`
3. first remaining string column (tie-broken by length on the first 1k
   rows — picks the column with the highest mean length, since that is
   almost always the transcript)

If the detected column is wrong, override it with `--text-col` (applies
globally; for per-source overrides edit `_TEXT_COLS` in the script).

## CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--csv-dir` | `CSV` | Folder containing `<source>_<ts>.csv` |
| `--out-dir` | *(required)* | Output folder; receives the overview files at the root and one subfolder per source |
| `--text-col` | *(auto)* | Force a transcript column name across all sources |
| `--top-n-outliers` | `5` | Outlier rows shown per source per category in PDF / MD |
| `--long-text-min-chars` | `30` | Minimum `char_len` for the "text long, audio short" view (also the population for the `chars_per_sec` outlier table) |
| `--exclude` | *(none)* | Source names to skip (repeatable) |
| `--only` | *(none)* | If set, restrict to the listed source names |
| `--no-overview` | off | Skip the overview MD/PDF (only render per-source reports) |
| `--no-per-source` | off | Skip per-source MD/PDF (only render the overview) |

## Output conventions

- **One overview PDF + one PDF per source per run**: the overview lives at
  `<out-dir>/filtered_csv_comparison.pdf` (with a sibling MD); each
  per-source PDF lives at `<out-dir>/<source>/<source>_filtered_report.pdf`
  (with its own sibling MD and `assets/`).
- **Latest-CSV selection**: when multiple timestamped CSVs exist for a
  single source, the script picks the newest by mtime (matches the
  `convert_samples_ffmpeg.py` convention).
- **Sort order in tables and bar charts**: by total hours descending so the
  reader sees the biggest contributor first; ties broken by row count.
- **Boxplot outlier dots**: `showfliers=False` in matplotlib; outliers are
  drawn manually as a sampled (≤ 400) grey scatter with horizontal jitter
  — same fast-rendering pattern as `audio-metadata-report`.
- **Empty-transcript handling**: rows with empty / whitespace-only
  transcript still count toward `total clips` and `total hours` but are
  excluded from `char_len` / `word_len` panels (and the panel title shows
  the excluded count).
- **Outlier "actual range"**: always the **observed** `[min, max]` of the
  matched values — not the threshold. Use this column to know how far
  beyond the cut-off the worst case really is.

## Derived metrics

Computed once per row, identical to `audio-metadata-report`:

```
char_len            = len(transcript)
word_len            = transcript.split() count
ratio_sec_per_char  = duration_s / max(char_len, 1)
chars_per_sec       = char_len   / duration_s    # for duration_s > 0
```

Tables and charts reference exactly these names so the two reports are
directly comparable when reviewed side-by-side.

## Dependencies

The script reuses the same libraries as `audio-metadata-report`:

- `pandas`, `numpy` — data
- `matplotlib` — charts (`Agg` backend, no display required)
- `reportlab` — PDF rendering (cover page, tables, KeepTogether outlier
  cards, page header/footer, font registration)

If the import fails, install them inside the project venv:

```bash
. .venv/bin/activate
python -m pip install pandas numpy matplotlib reportlab
```

## PDF image sizing rules (apply whenever editing `_build_pdf`)

Same rule as `audio-metadata-report` — copying the rule verbatim because
the failure mode is hard to debug:

```python
im = Image(str(p))
scale = img_w / im.imageWidth
im.drawWidth  = img_w
im.drawHeight = im.imageHeight * scale
story.append(im)
```

**Never use `Image(path, width=w, height=h)` for charts** — multi-panel
boxplots get cropped to a single panel because `Image(path, width=w)`
forces an aspect-ratio that doesn't match the figure.

## Table cell rules (apply whenever editing `_build_pdf`)

| Cell content | Word-wraps? | TableStyle FONT/TEXTCOLOR applies? |
|---|---|---|
| Plain Python `str` | **No** — overflows or clips silently | **Yes** |
| `Paragraph(text, style)` | **Yes** — wraps at cell boundary | **No** — style comes from `ParagraphStyle` |

- **Header rows** → plain strings (so `BACKGROUND`/`TEXTCOLOR`/`FONT`
  TableStyle commands actually apply).
- **Data rows that may wrap** (source path, transcript text, distribution
  strings) → wrap in `Paragraph` via `_pval()` / `_plbl()`.
- **Set `VALIGN=TOP`** on data rows that contain multi-line Paragraphs.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Need only the overview, or only the per-source set | Default renders both | Pass `--no-per-source` (overview only) or `--no-overview` (per-source only) |
| `No CSVs found in CSV/` | Cleaning pipeline never ran | Run `csv-cleaning-pipeline` first; verify `CSV/<source>_<ts>.csv` exists |
| Source missing from the report | Either `--only` excluded it, or the auto-detected transcript column failed | Run with `--text-col sentence` (or `transcription`); confirm the column exists in the CSV's first row |
| All rows from one source dropped from char_len chart | The detected transcript column is empty for that source | Force a different `--text-col` or fix the cleaning pipeline (the SPS source has 82.5 % empty transcripts pre-cleaning — but the cleaner already drops those, so re-run upstream) |
| PDF font looks cramped after editing | Someone removed or lowered the 1 % CJK threshold | Restore `> 0.01` threshold inside `_build_pdf` |
| `LayoutError: Flowable Image too large` | Used `Image(path, width=w)` without setting both `drawWidth` and `drawHeight` | Apply the explicit `drawWidth / drawHeight` pattern above |
| Multi-panel chart shows only one panel | Used `Image(path, width=w, height=h)` which forces an aspect ratio | Same fix as above |
| Boxplot upper whisker cut off | y-axis cap below the Tukey upper fence | Set axis top to `max(whisker endpoint, p99.5 of sampled outliers) + 15 % padding` |
| Source colors flip between runs | Default matplotlib palette + insertion order | The script pins colors by source name (stable hash → tab10 index); re-run if you see flips |
| Table cell overflows | Long values rendered as plain `str` | Wrap in `_pval()` or `_plbl()` |
| `multiple values for keyword argument 'fontName'` | `S()` helper conflict | Ensure `S()` uses `kw.setdefault("fontName", cjk)` not a positional default |

## Companion script: outlier listening list (`list_outlier_audios.py`)

When the user wants to **listen to** the outliers — not just count them —
run the small companion script next to the main report generator:

```bash
python "Skill/filtered-csv-report/scripts/list_outlier_audios.py" \
    --metric words_per_sec \
    --top-n 10 \
    --out "report/outlier_words_per_sec_listen.txt" \
    --include-paths-only
```

What it does:

- Imports `RATIO_METRICS` and `load_sources` from `generate_filtered_csv_report.py`,
  so metric definitions, transcript-column detection, and outlier
  thresholds (p1 / p99 / p99.9 / Tukey low / Tukey high) are **identical**
  to the report.
- For the chosen metric (default `words_per_sec`, must be one of
  `RATIO_METRICS`), it iterates the five rules (`> p99`, `> p99.9`,
  `> Tukey high`, `< p1`, `< Tukey low`) and picks the **top-N most
  extreme rows per source × rule**:
  - high-side rules → `nlargest(N, metric)` (worst offenders first)
  - low-side rules → `nsmallest(N, metric)` (smallest values first)
- Writes a flat .txt grouped by source then rule. Each entry contains the
  metric value, `duration_s`, `word_len`, `char_len`, the **absolute**
  audio path, and the transcript — formatted so the path can be copied
  directly into `afplay`.
- With `--include-paths-only` it also writes a sibling `*.paths.txt`
  with one absolute path per line, so you can pipe through a player:
  `while read p; do afplay "$p"; done < report/outlier_words_per_sec_listen.paths.txt`

Use it whenever the user wants to **explore actual audio examples** for
any rule on any of the four ratio metrics — without re-running the full
PDF report. Output lives next to the report set, e.g.
`report/outlier_<metric>_listen.txt`.

CLI flags mirror the report where they overlap (`--csv-dir`, `--text-col`,
`--exclude`, `--only`) plus:

| Flag | Default | Notes |
|---|---|---|
| `--metric` | `words_per_sec` | Must be one of `RATIO_METRICS` |
| `--top-n` | `10` | Rows kept per (source × rule) |
| `--out` | *(required)* | Output `.txt` path |
| `--include-paths-only` | off | Also write `<out>.paths.txt`, one absolute path per line |

Empty buckets render as `(no rows)` (e.g. SPS with only 34 cleaned rows
will hit zero `> Tukey high` matches).

## Relationship to neighbouring skills

```
csv-cleaning-pipeline   ──►   filtered-csv-report   (this skill — comparison)

audio-metadata-report   ──►   outlier-inspection-list   (per-dataset deep-dive)
```

`filtered-csv-report` and `audio-metadata-report` are **complementary, not
competing**: the per-dataset report is for in-depth investigation of a
single corpus, while this skill is for cross-corpus comparison after
cleaning. Both share the same chart palette, font rules, and outlier
metrics so the two PDFs read like chapters of the same document.
