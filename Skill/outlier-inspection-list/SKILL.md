---
name: outlier-inspection-list
description: >
  Generate a human-inspection Markdown list that maps audio-dataset outlier
  clips (from `outliers_*.csv` produced by the `audio-metadata-report` skill)
  to playable absolute paths and full transcripts, so the user can listen
  through suspicious samples. Use when the user wants to inspect / listen to
  outlier audios (high `ratio_sec_per_char`, high `chars_per_sec`, empty
  transcripts, audio-long/text-short or text-long/audio-short) identified by
  the audio-metadata report.
---

# Outlier inspection list (CSV exports → Markdown)

## When to use

Use this skill when the user asks to:
- **listen to / inspect outlier clips** flagged by the `audio-metadata-report`
  skill,
- produce a **per-dataset Markdown list** of suspicious audios with their
  absolute path and transcript,
- **merge multiple datasets' outliers** into one inspection document.

Input: one or more folders containing
- `outliers_high_ratio_sec_per_char_top.csv`  (audio-long / text-short)
- `outliers_long_text_short_duration_top.csv` (text-long / audio-short)

These are produced automatically in the `exports/` folder of every
`audio-metadata-report` run.

## Quick workflow

1. Identify each dataset's triplet:
   - **name**: heading shown in the Markdown (e.g. `Common Voice 25.0 (de)`)
   - **export_dir**: folder with the two `outliers_*.csv` files
   - **clips_dir**: folder that actually holds the audio files
   - **path_suffix** *(optional)*: append when the CSV stores a bare stem,
     e.g. Thorsten clips are hashes without the `.wav` extension → pass
     `.wav` so the generated paths resolve correctly.
2. Run `scripts/generate_outlier_inspection_list.py` with one
   `--dataset "name::export_dir::clips_dir[::suffix]"` per dataset and a
   single `--out` path.
3. Open the resulting Markdown; every entry has a ✓ / ✗ MISSING check so
   broken paths are obvious.

## Command template

```bash
python "Skill/outlier-inspection-list/scripts/generate_outlier_inspection_list.py" \
  --dataset "Common Voice 25.0 (de)::report/cv-corpus-25.0-de-validate_final/exports::Mozilla/cv-corpus-25.0-2026-03-09/de/clips" \
  --dataset "SPS Corpus 3.0 (de)::report/sps-corpus-3.0-2026-03-09-de/exports::Mozilla/sps-corpus-3.0-2026-03-09-de/audios" \
  --dataset "OpenSLR Thorsten-de::report/openslr-thorsten-de/exports::openslr/thorsten-de/wavs::.wav" \
  --out "report/outlier_inspection_list.md"
```

### CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--dataset` | *(required, repeatable)* | `name::export_dir::clips_dir[::path_suffix]` |
| `--out`     | *(required)* | Output `.md` path (parent dirs created as needed) |
| `--top-n`   | `20` | Max entries per dataset × category |

## Output format

Per dataset, one section with two subsections (the two CSV categories).
Each entry:

```
**<rank>. `<filename>`**  ✓
- duration_s=…  char_len=…  <ratio_metric>=…
- path: `<absolute path>`
- text: <full transcript or _(empty)_>
```

## Output conventions

- **One Markdown file** covering all datasets (the user listens top-down).
- Every entry prints an **absolute path** — copy-paste into a player.
- **Existence check**: ✓ when the file is on disk, `✗ MISSING` when not
  (common causes: wrong `clips_dir`, missing suffix, CSV stored a bare stem).
- Empty / whitespace-only transcripts render as `_(empty)_` so the user
  notices them at a glance — these are candidates for re-transcription or
  dropping.

## Listening helpers (macOS)

```bash
# Play one clip
afplay "/absolute/path/to/clip.mp3"

# Top-5 Common-Voice paths, played back-to-back
rg -o '/Users/.+\.mp3' report/outlier_inspection_list.md \
  | awk '/cv-corpus/{print; n++} n==5{exit}' \
  | while read p; do echo "▶ $p"; afplay "$p"; done
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| All entries show `✗ MISSING` | Wrong `clips_dir`, or the CSV stores a stem without extension | Verify with `ls <clips_dir> \| head`; if files end in `.wav` but the CSV `path` column does not, add the suffix as the 4th `--dataset` field |
| Section shows `_CSV not found_` | `export_dir` does not contain the expected `outliers_*.csv` | Re-run the `audio-metadata-report` skill for that dataset so the CSVs are regenerated |
| Too many / too few entries per section | Default `--top-n` is 20 | Override with `--top-n 50` etc. |
| `_(empty)_` dominates one category | Dataset has many empty transcripts (e.g. SPS has 82.5 %) | Expected signal — decide whether to auto-transcribe (Whisper) or drop these rows |

## Relationship to `audio-metadata-report`

This skill is a **downstream consumer**: run the metadata report first, then
run this skill against the `exports/` folder(s) it produces. Nothing in this
skill re-reads the raw TSV/CSV metadata — it works exclusively from the
already-computed outlier CSVs.
