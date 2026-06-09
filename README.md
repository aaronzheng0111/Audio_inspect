# Audio Inspect

A local web-app that helps **researchers / data engineers** clean and filter
audio datasets (ASR / TTS) by inspecting CSV metadata and computing acoustic
quality metrics directly from the referenced audio files.

It implements the 5-step wizard described in `Generater/`:

1. **Input** the path to a dataset CSV.
2. **Preview** the CSV (column types + a ~15 row sample).
3. **Map / select** the required columns (`audio_name_id`, `text`, `audio_path`)
   and pick which acoustic metrics to compute.
4. **Estimate** the compute time, then run the metric calculation.
5. **Analyse** with per-attribute Plotly cards, filter with sliders + numeric
   inputs, view a full-dataset statistics summary, and **export** a filtered CSV
   plus a PDF comparison report.

## Architecture

```
Audio_inspect/
  environment.yml      # conda env "audio_visual_web" (python + node)
  start.sh             # one-shot launcher for backend + frontend
  backend/             # Django + DRF REST API (OOP core modules)
  frontend/            # React + MUI (Material Design) + Plotly
```

The backend is organised as small, single-responsibility OOP modules under
`backend/core/` (CSV inspection, audio loading, a pluggable metric registry, a
metric engine, statistics, filtering, and PDF reporting). The front-end is a
wizard driven by a shared `WizardContext`.

### Acoustic metrics

| Metric | Implementation |
| --- | --- |
| RMS, LUFS, Dynamic Range, ZCR, Spectral Flatness | real algorithms |
| Segmental SNR, SRMR, C50 | documented **approximations** (same interface, swappable later) |

The approximate metrics are clearly flagged as `approximate` in both their
docstrings and the API responses so they can be replaced with reference
implementations without changing callers.

## Setup

```bash
# 1. Create the conda environment (python + node)
conda env create -f environment.yml

# 2. (Optional) install backend pip deps manually if not using environment.yml
conda run -n audio_visual_web pip install -r backend/requirements.txt

# 3. Launch everything
./start.sh
```

- Backend: <http://localhost:8000/api/>
- Frontend: <http://localhost:5173/>

## API overview

| Method & path | Step | Purpose |
| --- | --- | --- |
| `POST /api/dataset/load` | 1+2 | Load CSV, return session id, columns, types, 15-row sample |
| `POST /api/dataset/map` | 3 | Save required-column mapping / renames |
| `POST /api/metrics/estimate` | 4 | Predict compute time for selected metrics |
| `POST /api/metrics/compute` | 3+4 | Read audio, compute selected metric columns |
| `GET  /api/analysis/summary` | 5 | Full-dataset statistics summary table |
| `GET  /api/analysis/plot-data` | 5 | Sampled data for Plotly charts |
| `POST /api/analysis/filter` | 5 | Apply thresholds, return before/after counts |
| `POST /api/export/csv` | 5 | Export filtered CSV |
| `POST /api/export/report` | 5 | Export PDF comparison report |

See `GENERATION_LOG.md` for a record of what was generated and fixed.
