---
name: audio-metadata-report
description: >
  Generate a polished analysis report (Markdown + PDF + charts) for speech/audio dataset metadata
  in CSV/TSV form. Use when the user asks to analyze a dataset TSV/CSV (e.g., Common Voice
  validate_final.tsv / validated.tsv, or SPS corpus ss-corpus-de.tsv) and produce a report with
  charts (duration/text/ratio histograms), anomaly rates, outlier examples with full transcript
  text, speaker/gender/age/accent distributions, and total audio hours.
---

# Audio metadata report (CSV/TSV → MD + PDF)

## When to use

Use this skill when the user asks to:
- analyze an audio dataset **CSV/TSV** (Common Voice-style, SPS corpus, or similar),
- generate **charts** (duration, transcript length, ratios — with median lines + clean styling),
- produce an **analysis report** as **Markdown + PDF**,
- surface **outliers** with **full transcript text** ("audio long but text short", and the reverse),
- see **speaker count**, **empty-transcription rate**, **total audio hours**, or **demographic breakdowns**.

Default assumption: input is a **dataset folder** containing:
- a main metadata TSV/CSV (e.g. `validate_final.tsv`, `validated.tsv`, `train.tsv`, `ss-corpus-de.tsv` …)
- an optional durations table (Common Voice: `clip_durations.tsv` with `clip` and `duration[ms]`)

> **Duration auto-detection**: if no separate durations file exists, the script automatically
> uses `duration_ms` or `duration_s` columns found in the main metadata (e.g. SPS corpus).

## Quick workflow (optimized)

1. **Inspect columns** (header + a couple of rows) and determine:
   - clip identifier column (Common Voice: `path`; SPS corpus: `audio_file`)
   - transcript column (Common Voice: `sentence`; SPS corpus: `transcription`)
   - if durations exist in a separate file: join key (`clip` ↔ `path`) and duration units (ms vs s)
   - if durations exist in the main file: pass `--durations-file ""` to skip the join
2. **Compute core stats** (chunked scan if file is big):
   - row count, unique clips, unique speakers, missing/empty transcription rates
   - transcript length quantiles (chars + words)
   - duration quantiles + total hours
   - demographic distributions (split / gender / age / accent) if columns present
3. **Compute per-clip derived columns**:
   - `char_len`, `word_len`
   - `ratio_sec_per_char = duration_s / max(char_len, 1)`  (audio long vs text short)
   - `ratio_sec_per_word = duration_s / max(word_len, 1)`
   - `chars_per_sec = char_len / duration_s` (text long vs audio short)
   - `words_per_sec = word_len / duration_s`
4. **Charts** (all with median line + clean grid) — 8 files total:
   - duration histogram
   - transcript length histogram
   - ratio histograms (log-x): `ratio_sec_per_char`, `ratio_sec_per_word`
   - long-text histograms (log-x): `chars_per_sec`, `words_per_sec`  (filter: `char_len ≥ threshold`)
   - **boxplot grid** — `duration_s`, `char_len`, `word_len`  (capped at p99.5, shows IQR + mean ◆)
   - **boxplot grid** — `ratio_sec_per_char`, `ratio_sec_per_word`, `chars_per_sec`, `words_per_sec`  (log scale)
5. **Anomaly rates** (percentages + counts):
   - high tail: `ratio_sec_per_char > p99 / p99.9 / Tukey upper fence`
   - low tail: `ratio_sec_per_char < p1 / Tukey lower fence`
6. **Outlier exports**:
   - Top N by `ratio_sec_per_char` (full transcript text)
   - Top N by `chars_per_sec` among `char_len ≥ threshold` (full transcript text)
7. **PDF rendering**:
   - **Cover page**: navy hero block with title + dataset path + generation date, 3-column key-metrics grid
   - **Section 1 – Dataset Overview**: full-detail table with speaker count, total hours, distributions
   - **Section 2 – Distribution Statistics**: quantile table (rows = metrics, cols = percentiles)
   - **Section 3 – Anomaly Analysis**: table with threshold, count, and rate per condition
   - **Section 4a/b – Outlier Samples**: color-coded cards (blue = long-audio, amber = dense-text) with full transcript
   - **Section 5 – Charts**: full-width, labelled charts
   - **Page header/footer** on every page after cover: dataset name + page number
   - **Font**: Helvetica (default, proper Latin letter-spacing); switches to `STSong-Light` CID font
     **only if > 1 % of transcripts contain CJK characters** — see font rules below

## Font rules (critical — read before editing)

The PDF font is selected inside `_build_pdf` as follows:

```python
cjk  = "Helvetica"        # primary — correct spacing for Latin/European text
bold = "Helvetica-Bold"

_cjk_count = df["sentence"].astype(str).str.contains(
    r"[\u4e00-\u9fff\u3040-\u30ff]", regex=True
).sum()

# Switch to STSong-Light ONLY when CJK is a meaningful share of the corpus
if _cjk_count / max(len(df), 1) > 0.01:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    cjk = bold = "STSong-Light"
```

**Why the 1 % threshold matters:**
- `STSong-Light` is a CJK CID font. It renders Latin characters with very tight letter-spacing
  and hairline strokes — the entire PDF looks cramped when it is used for a European corpus.
- A corpus like Common Voice German has 950 000 sentences; 13 of them quote Chinese radicals.
  Without the threshold, those 13 rows force the whole document into `STSong-Light`.
- The 1 % threshold (≈ 9 500 rows for CV-de) ensures only genuinely multilingual corpora
  (where CJK is a significant portion) get the CJK font.
- **Never remove or lower this threshold.**

## Preferred implementation

Use the utility script in this skill:
- `scripts/generate_audio_metadata_report.py`

### Common Voice run example

```bash
python "Skill/audio-metadata-report/scripts/generate_audio_metadata_report.py" \
  --dataset-dir "Mozilla/cv-corpus-25.0-2026-03-09/de" \
  --meta-file "validate_final.tsv" \
  --out-dir "report/cv-corpus-25.0-de-validate_final"
```

### SPS corpus run example

```bash
python "Skill/audio-metadata-report/scripts/generate_audio_metadata_report.py" \
  --dataset-dir "Mozilla/sps-corpus-3.0-2026-03-09-de" \
  --meta-file "ss-corpus-de.tsv" \
  --out-dir "report/sps-corpus-3.0-2026-03-09-de" \
  --path-col "audio_file" \
  --text-col "transcription" \
  --durations-file ""
```

### All CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--dataset-dir` | *(required)* | Path to dataset folder |
| `--meta-file` | *(required)* | Main metadata filename inside dataset-dir |
| `--out-dir` | *(required)* | Output folder; its name becomes the output file stem |
| `--meta-sep` | `\t` | Separator (`\t` for TSV, `,` for CSV) |
| `--path-col` | `path` | Clip filename column (SPS: `audio_file`) |
| `--text-col` | `sentence` | Transcript column (SPS: `transcription`) |
| `--durations-file` | `clip_durations.tsv` | Set `""` if duration is already in main metadata |
| `--durations-sep` | `\t` | Separator for durations file |
| `--durations-clip-col` | `clip` | Clip column in durations file |
| `--durations-dur-col` | `duration[ms]` | Duration column in durations file |
| `--outlier-csv-n` | `50` | How many outliers to export to CSV |
| `--pdf-fulltext-n` | `10` | Outlier samples shown in PDF |
| `--md-fulltext-n` | `20` | Outlier samples shown in Markdown |
| `--long-text-min-chars` | `30` | Min char_len for "long-text/short-audio" analysis |

### What it produces

In `--out-dir` (files are named after the output directory):
- `{name}_initial_analysis.md` — Markdown summary with inline image links
- `{name}_initial_analysis.pdf` — Polished PDF: cover page, tables, outlier cards, all charts
- `assets/` — **8 chart PNGs**:
  - `duration_seconds_hist.png`
  - `sentence_length_chars_hist.png`
  - `ratio_sec_per_char_hist_logx.png`
  - `ratio_sec_per_word_hist_logx.png`
  - `long_text_chars_per_second_hist_logx.png`
  - `long_text_words_per_second_hist_logx.png`  ← new
  - `boxplot_distributions.png`  ← new (duration / char_len / word_len)
  - `boxplot_ratios.png`  ← new (ratio_sec_per_char / ratio_sec_per_word / chars_per_sec / words_per_sec, log scale)
- `exports/outliers_high_ratio_sec_per_char_top.csv`
- `exports/outliers_long_text_short_duration_top.csv`

**Boxplot design notes:**
- Box spans Q1–Q3 (IQR); whiskers = 1.5 × IQR
- **Outlier dots always shown** — values outside the Tukey fence are plotted as grey scatter points
  with slight horizontal jitter; for large datasets a random sample of up to **400 points** is drawn
  so rendering stays fast without losing visual information about outlier density
- Yellow diamond ◆ = mean; red horizontal line = median
- Distribution boxplots (`boxplot_distributions.png`):
  - `char_len` / `word_len` panels **exclude rows where `char_len == 0`** (empty transcriptions) and note
    the excluded count in the panel title — this prevents a long lower whisker to 0 from compressing the box
  - y-axis extends to the **actual whisker endpoint** (last data point within Tukey fence) + 15 % padding —
    the whisker is **never cut off**; do **not** cap the axis at p99.5 (that truncates the upper whisker)
- Ratio / rate boxplots: log y-scale to reveal the full spread of heavy-tailed distributions

## Output conventions

- **File naming**: `{out-dir name}_initial_analysis.{pdf,md}` — set `--out-dir` to the dataset name
- **Charts**: log-x for heavy-tailed distributions; red dashed median line on every chart
- **Outlier cards in PDF**: blue = audio-long/text-short; amber = text-long/audio-short
- **Outliers**: full transcript text in CSV (no truncation); PDF shows up to `--pdf-fulltext-n` samples
- **Safety**: never reads audio files; only joins by metadata + optional durations TSV

## Troubleshooting checklist

| Symptom | Cause | Fix |
|---|---|---|
| **Multi-panel boxplot shows only one panel in PDF** | `Image(path, width=w, height=h)` stretches image to fixed dimensions, cropping panels that don't fit the forced aspect ratio | Use `im = Image(path); im.drawWidth = img_w; im.drawHeight = im.imageHeight * (img_w / im.imageWidth)` — see "PDF image sizing rules" above |
| **`LayoutError: Flowable Image (w x ???) too large`** | `Image(path, width=w)` without height triggers ReportLab height auto-calculation that overflows the page frame | Same fix — always set both `drawWidth` and `drawHeight` explicitly using the aspect-ratio formula |
| **Table cell text overflows / gets cut off** | Raw Python strings in ReportLab table cells never word-wrap | Wrap every potentially-long cell value in a `Paragraph` object (`_pval()` / `_plbl()`). Raw strings only work safely for short, fixed-width content like numbers or the header row |
| **PDF font looks cramped / thin** | `STSong-Light` being used for a Latin corpus | Check `_cjk_count / len(df)` — must be > 1 % to switch; verify the guard in `_build_pdf` |
| **PDF font looks cramped after editing** | Someone removed or lowered the 1 % CJK threshold | Restore `> 0.01` threshold in `_build_pdf` |
| **`--durations-file ""` needed** | Dataset stores duration inside the main TSV (`duration_ms` / `duration_s` column) | Pass `--durations-file ""` to skip the external join |
| **No durations join** | Wrong join key or units | Confirm `clip` vs `path` column name and ms vs s units |
| **Charts look "empty"** | Non-finite or zero values not filtered | Already handled; check that `duration_s > 0` rows exist |
| **Outliers dominated by empty transcriptions** | Normal — empty transcripts get `ratio = duration_s` (highest possible) | These are valid QA signals; raise `--long-text-min-chars` for the dense-text view |
| **Boxplot upper whisker appears cut off at top of y-axis** | y-axis cap set to p99.5 which can be lower than the Tukey upper fence (Q3 + 1.5 × IQR) | Set axis top to `max(whisker endpoint, p99.5 of sampled outliers) + 15 % padding`. Never cap at a fixed percentile for linear boxplots |
| **Outlier dots missing on large datasets** | Old code used `showfliers=(v.size <= 50_000)` which hides all dots for big corpora | Always use `showfliers=False` in `ax.boxplot()` and draw outliers manually: compute points outside Tukey fence, sample ≤ 400 with `rng.choice`, then `ax.scatter(1 + jitter, pts)` |
| **Boxplot box compressed at top, long lower whisker stretching to 0** | Empty transcriptions (`char_len == 0`) included in `char_len` / `word_len` panels; the minimum value 0 pulls the lower whisker all the way down | Filter empty rows before building the panel: `df_nz = df[df["char_len"] > 0]`; annotate the excluded count in the panel title so the reader knows |
| **`multiple values for keyword argument 'fontName'`** | `S()` helper conflict | Ensure `S()` uses `kw.setdefault("fontName", cjk)` not a positional default |
| **PDF 乱码 on a genuine CJK corpus** | `STSong-Light` not available in ReportLab install | Run `pip install reportlab` to get the bundled CID fonts |

## PDF image sizing rules (apply whenever editing `_build_pdf`)

ReportLab's `Image` flowable has a subtle but critical rule for sizing:

| How you call `Image(path, ...)` | Result |
|---|---|
| `Image(path, width=w, height=h)` | Image is **stretched/squashed** to exactly w × h — ignores aspect ratio |
| `Image(path, width=w)` | Tries to auto-calculate height, but **can raise `LayoutError: too large`** if the calculated height overflows the frame |
| Set `drawWidth` / `drawHeight` explicitly | **Correct** — always preserves aspect ratio, never overflows unexpectedly |

**Always use this pattern for every chart image:**

```python
im = Image(str(p))
scale = img_w / im.imageWidth      # im.imageWidth is in points (72 DPI basis)
im.drawWidth  = img_w              # full page-content width
im.drawHeight = im.imageHeight * scale   # proportional height
story.append(im)
```

**Why this matters for multi-panel charts (boxplots):**
- Histograms are single-panel at 10 × 4.5 in → aspect ratio ≈ 2.2 : 1
- Boxplots with 3–4 panels at 3.5 in/panel → aspect ratio ≈ 2.1–2.8 : 1
- If you force a fixed height that doesn't match the actual aspect ratio, multi-panel
  images get cropped to a single panel or raise a `LayoutError` with `height = ???`
- The `drawWidth / drawHeight` pattern works for **all** chart types without
  needing to know their panel count or figure dimensions in advance

**Never use `Image(path, width=w, height=h)` for charts.** The only safe place for
fixed-height images is UI thumbnails or decorative elements with known fixed dimensions.

## Table cell rules (apply whenever editing `_build_pdf`)

ReportLab tables have a critical rendering rule that causes hard-to-spot bugs:

| Cell content | Word-wraps? | TableStyle FONT/TEXTCOLOR applies? |
|---|---|---|
| Plain Python `str` | **No** — overflows or clips silently | **Yes** |
| `Paragraph(text, style)` | **Yes** — wraps at cell boundary | **No** — style comes from `ParagraphStyle` |

**Always follow these conventions:**

1. **Header rows** → plain strings. TableStyle `BACKGROUND`, `TEXTCOLOR`, and `FONT` commands work on them, giving the navy background + white text.
2. **Data rows with potentially long content** → `Paragraph` objects via `_pval(text)` (regular) or `_plbl(text)` (bold label). This applies to **any** field whose value length is unpredictable: distribution strings, file paths, transcript text, condition descriptions.
3. **Short fixed values** (counts, percentages, short flags) → plain strings are acceptable *only if* the column is wide enough to guarantee no overflow.
4. **Set `VALIGN=TOP`** on data rows that contain multi-line Paragraphs so that row alignment looks clean when one cell wraps to multiple lines.

**Pattern to follow when adding a new table:**

```python
# Header: plain strings (TableStyle will colour them)
rows = [["Label", "Value"]]

# Data: Paragraph objects for any value that can be long
for key, val in data.items():
    rows.append([_plbl(key), _pval(val)])   # both wrap-safe

tbl = _tbl(rows, col_widths, [
    ("FONT",       (0, 0), (-1, 0), bold, 10),   # header font
    ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),      # header bg
    ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),     # header text
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAYF]),
    ("GRID",       (0, 0), (-1, -1), 0.25, C_GRAY2),
    ("VALIGN",     (0, 1), (-1, -1), "TOP"),      # multi-line rows
])
```
