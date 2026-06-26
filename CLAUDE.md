# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Audio Inspect is a local web app that helps researchers/data engineers clean and filter audio datasets (ASR/TTS) by inspecting CSV metadata and computing acoustic quality metrics. It implements a 5-step wizard: Input CSV → Preview → Map columns & select metrics → Compute → Analyse & export.

- **Backend**: Django + DRF on port 9081, Python 3.10 via conda env `audio_visual_web`
- **Frontend**: React 18 + MUI 5 + Plotly on port 9173, Vite dev server with `/api` proxy
- **Launcher**: `./start.sh` starts both services (uses `conda run -n audio_visual_web`)

## Build / test / run commands

```bash
# One-time setup
conda env create -f environment.yml
conda run -n audio_visual_web pip install -r backend/requirements.txt

# Launch both services
./start.sh

# Run all backend tests (43 tests)
cd backend
conda run -n audio_visual_web python manage.py test tests

# Run a single test file
conda run -n audio_visual_web python manage.py test tests.test_metric_engine

# Run a single test case or method
conda run -n audio_visual_web python manage.py test tests.test_metric_engine.PredictTimeTest
conda run -n audio_visual_web python manage.py test tests.test_metric_engine.ComputeTest.test_parallel_matches_serial

# Frontend dev (standalone, backend must also be running)
cd frontend
npm install
AUDIO_INSPECT_BACKEND_PORT=9081 npm run dev
```

## Architecture

### Backend layering

Views (`api/views.py`) are **thin wiring** — each validates input via a DRF serializer (`api/serializers.py`), then delegates to a `core/` module. Responses are plain dicts, not model instances. The app has **no database models**; all working state lives in an in-memory `SessionStore` (thread-safe dict keyed by `session_id`, singleton at `core.session_store.session_store`).

```
api/views.py   ← HTTP layer, calls core modules
api/serializers.py   ← DRF request validation
core/   ← all domain logic (single-responsibility OOP modules)
```

### Core module responsibilities

| Module | Purpose |
|---|---|
| `csv_inspector.py` | Parse CSV, infer column types, produce 15-row sample (Task 1+2) |
| `attribute_mapper.py` | Map user's column names → canonical `audio_name_id` / `text` / `audio_path` |
| `audio_path_resolver.py` | Find the correct filesystem root for relative audio paths by probing candidate directories |
| `audio_loader.py` | Load mono float64 waveforms via librosa (or soundfile fallback), with LRU cache |
| `metric_engine.py` | Compute selected metrics in parallel (`ThreadPoolExecutor`), estimate runtime |
| `metrics/` | Pluggable metric registry: `BaseMetric` ABC → individual metric files, auto-registered on import |
| `statistics.py` | Full-dataset summary table + down-sampled plot data for charts |
| `filtering.py` | Apply per-column [min, max] filter rules, report before/after counts |
| `report.py` | Generate PDF comparison report (matplotlib charts + reportlab tables) |
| `session_store.py` | In-memory session state — holds the working DataFrame, column mapping, computed metrics |
| `session_audio.py` | Serve one row's audio file for in-browser playback (same path resolution as metric compute) |

### Metric system

Every metric subclasses `BaseMetric` (in `core/metrics/base.py`), declaring `key`, `label`, `unit`, `cost`, `approximate`, `description`. New metrics are registered by adding the class to the loop in `core/metrics/__init__.py`. The registry is a module-level singleton (`core.metrics.registry`).

Three metrics are documented **approximations** flagged with `approximate=True`: Segmental SNR, SRMR, C50. They follow the same interface so they can be swapped for reference implementations without changing callers.

### Data flow through the wizard

1. `POST /api/dataset/load` → `CsvInspector` parses CSV, `SessionStore` creates session, returns column info + sample rows
2. `POST /api/dataset/map` → `AttributeMapper` renames columns to canonical names, `_probe_audio` finds audio root
3. `POST /api/metrics/compute` → `MetricEngine.compute()` reads audio per row (parallel), writes one new column per metric into the DataFrame (stored in session)
4. `GET /api/analysis/summary` and `plot-data` → `StatisticsBuilder` produces aggregates and sampled chart data
5. `POST /api/analysis/filter`, `/api/export/csv`, `/api/export/report` → `DatasetFilter` applies threshold rules, `ReportGenerator` builds PDF

### Frontend

React app with MUI Material Design and Plotly scatter plots. State is shared across the 5-step wizard via `WizardContext` (`frontend/src/context/WizardContext.jsx`). The API client (`frontend/src/api/client.js`) wraps axios with error normalisation. Vite proxies `/api` to the Django backend so the browser sees a same-origin URL.

Page components: `PathInputPage` → `CsvPreviewPage` → `AttributeMappingPage` → `MetricSelectionPage` → `AnalysisPage` (steps 1–5).

### Test suite

Tests live in `backend/tests/`. `tests/utils.py` generates synthetic WAV files (sine waves, white noise) and a CSV on-the-fly — no binary fixtures committed to the repo. Tests exercise real audio-reading code paths. The test CSV uses non-standard column names (`utt`, `transcript`, `file`) so the `AttributeMapper` path is covered.

### Key configuration points

- `backend/audio_visual_web/settings.py`: `MAX_AUDIO_FILES = 100000`, `WORKSPACE_DIR = backend/workspace/`, `CORS_ALLOW_ALL_ORIGINS = True`
- Ports are in the 9xxx range (9081 backend, 9173 frontend) to avoid conflicts with common local dev ports
- The `start.sh` launcher frees stale listeners on these ports before starting
- `environment.yml` defines the conda env with both Python 3.10 and Node.js 20
