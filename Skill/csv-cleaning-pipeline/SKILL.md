---
name: csv-cleaning-pipeline
description: >
  Apply the project's standard cleaning rules to multi-source German audio
  dataset metadata (Common Voice, SPS Corpus, OpenSLR Thorsten, Kaggle
  archive) and produce one unified-schema CSV per source under `CSV/`, then
  optionally convert N sample clips per source to 16 kHz mono WAV for human
  spot-checking. Use when the user asks to clean / filter dataset TSVs,
  generate the unified CSVs in `CSV/`, drop empty transcripts, cap durations,
  or sample audio for QA listening.
---

# CSV cleaning pipeline (raw TSV → unified CSV + sample WAVs)

## When to use

Use this skill whenever the user wants to:

- **clean and unify** the per-dataset metadata TSVs (Common Voice
  `validate_final.tsv`, SPS `ss-corpus-de.tsv`, OpenSLR Thorsten
  `metadata_with_header.tsv`, Kaggle `transcript.txt`),
- regenerate the **unified CSVs** in `CSV/<source>_<YYYYmmdd-HHMMSS>.csv`,
- pick **N sample rows per source** and convert them to **16 kHz mono WAV**
  for human spot-checking,
- update / re-apply the documented cleaning rules below.

This skill is **upstream** of:
- `Skill/filtered-csv-report/` — multi-source comparison report from these CSVs
- `Skill/audio-metadata-report/` — per-dataset deep-dive (works on the raw TSVs)

## Documented cleaning rules

These rules are encoded in `scripts/generate_filtered_csvs.py`. Do not change
them silently — anyone reading the unified CSV should be able to trust them.

| Rule | Applied to | Reason |
|---|---|---|
| `0 ≤ duration_s ≤ 20` (drop > 20 s and missing/non-positive) | **all sources** | Long clips are nearly always concatenations or truncated splits; > 20 s also breaks downstream batching |
| Drop empty / whitespace-only transcripts | **sps**, **openslr-thorsten**, **kaggle** | These corpora ship valid clip-level transcripts; empty rows are pipeline artifacts |
| Keep empty transcripts | **cv-corpus-de** (`validate_final.tsv`) | Common Voice German `validate_final` already has 0% empty rows — no filtering needed; leaving the rule off keeps `enforce_transcription=False` honest |
| Unified leading columns | **all sources** | Downstream tools (the report skill, the sample-converter) only need to know `audio_name`, `source`, `path`, `duration_s` |

Unified column layout (always in this exact order):

```
audio_name, source, path, duration_s, <all original metadata columns>
```

- `audio_name` — bare filename with extension (e.g. `common_voice_de_25289452.mp3`,
  `a939f2ca060905f79b40a8328d119b40.wav`). For OpenSLR Thorsten the raw `path`
  column stores a hash without `.wav`; the script appends the extension.
- `source` — short canonical name (`cv-corpus-25.0-2026-03-09-de`,
  `sps-corpus-3.0-2026-03-09-de`, `openslr-thorsten-de`, `kaggle-archive-de`).
- `path` — workspace-relative path that resolves under `WORKSPACE_ROOT` (e.g.
  `Mozilla/cv-corpus-25.0-2026-03-09/de/clips/common_voice_de_xxx.mp3`).
- `duration_s` — float seconds, joined from `clip_durations.tsv` (CV / Thorsten)
  or computed from `duration_ms / 1000` (SPS) or read directly from the
  Kaggle `transcript.txt` 4th pipe-separated column.

## Quick workflow

1. **(Optional) re-clean** if any raw TSV changed or you want fresh
   timestamps. From workspace root:

   ```bash
   python "Skill/csv-cleaning-pipeline/scripts/generate_filtered_csvs.py"
   ```

   - Output: `CSV/<source>_<YYYYmmdd-HHMMSS>.csv` (one per source).
   - Console summary table shows `total / kept / dropped_empty_text /
     dropped_duration / missing_audio_files` per source.
   - Add `--check-files` to verify every kept clip exists on disk (slower —
     a full filesystem stat per row).

2. **(Optional) sample for human QA**. Pick N clips per source and convert
   them to 16 kHz mono WAV for spot-checking:

   ```bash
   python "Skill/csv-cleaning-pipeline/scripts/convert_samples_ffmpeg.py" \
       --samples 10 --seed 42
   ```

   - Output: `sample_audio/<source>/<audio_name_stem>.wav` plus
     `sample_audio/<source>/_manifest.csv` so you can map every sample back
     to its source row (path, duration_s, transcription).

3. **Hand off** the freshest CSVs (latest timestamp per source) to the
   `filtered-csv-report` skill for a comparison dashboard, or directly to
   downstream training / serving pipelines.

## Scripts

### `scripts/generate_filtered_csvs.py`

Main cleaning + unification pass. Reads the four raw datasets, applies the
rules above, and writes one timestamped CSV per source.

Important defaults:

| Flag | Default | Notes |
|---|---|---|
| `--out-dir` | `CSV/` | Write target |
| `--check-files` | off | Verify every kept clip exists on disk |
| `--only` | all 4 sources | Repeat with one or more source names to restrict |

Adding a new source is a 4-step process inside the script:

1. Add a new `_load_<source>(...)` function that returns a `SourceResult`.
2. Apply the same `mask_dur` filter (`0 ≤ duration_s ≤ 20`).
3. Decide on an empty-transcript rule (drop or keep) and document it in the
   table above.
4. Append the source to the `jobs` list inside `build_all`.

### `scripts/convert_samples_ffmpeg.py`

Picks N rows from each unified CSV and converts the referenced clip to
16 kHz mono WAV via `ffmpeg`. Always reads the **newest** timestamped CSV
per source from `--csv-dir` (default `CSV/`).

Important defaults:

| Flag | Default | Notes |
|---|---|---|
| `--samples` | `10` | Per-source row count |
| `--seed` | `42` | Reproducible sampling |
| `--ffmpeg` | `which ffmpeg` | Override binary path on systems without it on PATH |
| `--overwrite` | off | If on, re-encodes existing WAVs; otherwise reports them as `skipped` |
| `--only` | all sources | Restrict to one or more sources |

Each source folder gets a `_manifest.csv` with: `audio_name`, `source`,
`sample_path` (the new WAV), `original_path` (the source clip),
`duration_s`, `transcription`. The manifest is the canonical link between
sample and source row.

## Output conventions

- **CSV filename**: `<source>_<YYYYmmdd-HHMMSS>.csv` — keeping the timestamp
  lets you regenerate without overwriting older snapshots; downstream
  scripts always pick the newest by mtime.
- **No NaN by default**: scripts read with `keep_default_na=False` to keep
  empty cells as empty strings rather than `NaN`. Don't change this — the
  report skill relies on string-typed cells for safe rendering.
- **Sample dir**: `sample_audio/<source>/`; manifest is always
  `_manifest.csv` (leading underscore so it sorts first and is easy to spot).

## Adjusting the duration cap

The 20 s cap is intentional and conservative. To change it:

1. Edit `DURATION_MAX_S` in `scripts/generate_filtered_csvs.py`.
2. Update the rule table at the top of this SKILL.md so the document
   reflects reality.
3. Re-run the cleaner — the timestamp on the new CSVs makes the change
   auditable.

Do **not** add a hard upper cap below 20 s without first checking the
duration histogram from `filtered-csv-report` — Common Voice German has a
long tail up to ~25 s and many of those rows are still valid speech.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError` on a raw TSV | Dataset folder not present at the documented path | Restore the dataset under `Mozilla/`, `openslr/`, or `kaggle/`, or call with `--only` to skip it |
| `missing_audio_files` > 0 | A row's `path` does not resolve under `WORKSPACE_ROOT` | Run with `--check-files` and inspect the source rows; usually a stale `clips/` folder or wrong filename casing |
| All rows dropped from one source | Wrong duration column / units in the loader | Confirm `duration_ms` (SPS) vs `duration[ms]` (CV / Thorsten) vs raw seconds (Kaggle) and the join key (`clip` ↔ `path`) |
| `ffmpeg` not found | Not installed on PATH | `brew install ffmpeg` (macOS) or pass `--ffmpeg /full/path/to/ffmpeg` |
| Sample WAVs look identical across runs | `--seed` is fixed at 42 | Pass a different `--seed` for a new draw; manifest captures whichever rows were actually picked |
| Two CSVs per source in `CSV/` | Older snapshots were not cleared | Safe to ignore — the converter and the report skill both pick the newest by mtime; delete the older file when you no longer need the audit trail |

## Relationship to neighbouring skills

```
raw TSVs ──► csv-cleaning-pipeline ──► CSV/<source>_<ts>.csv
                                          │
                                          ├──► filtered-csv-report  (multi-source dashboard)
                                          └──► convert_samples_ffmpeg  (sample_audio/<source>/)

raw TSVs ──► audio-metadata-report  (per-dataset deep-dive, separate skill)
                  │
                  └──► outlier-inspection-list  (listening list)
```

The four skills are deliberately decoupled: cleaning is reproducible from
raw inputs, the comparison report is reproducible from the cleaned CSVs,
the per-dataset deep-dive runs straight off the raw TSVs, and the listening
list is built from the per-dataset deep-dive's outlier exports.
