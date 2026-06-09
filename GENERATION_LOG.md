# Generation Log

This file records what was generated for the Audio Inspect web-app and any
fixes applied along the way, as required by `Generater/04 Implement.md`.

## Initial generation

### Scaffold
- `environment.yml` — conda env `audio_visual_web` (python 3.10 + nodejs 20 +
  scientific/audio stack + Django/DRF pip deps).
- `start.sh` — one-shot launcher that runs the Django backend and the Vite
  front-end inside the conda env.
- `README.md`, `.gitignore`.
- `backend/` — Django project `audio_visual_web` + `api` app + `core` package.
- `frontend/` — React + Vite + MUI + Plotly app.

### Backend — data channel (Task 1+2, 3)
- `core/session_store.py` — `SessionStore`: in-memory, thread-safe per-session
  storage of the working DataFrame + mapping/metric state.
- `core/csv_inspector.py` — `CsvInspector`: robust CSV parsing, column type
  inference, and a capped row sample (default 15 rows).
- `core/attribute_mapper.py` — `AttributeMapper`: maps non-standard column names
  onto the required canonical names and renames the DataFrame.

### Backend — metrics (Task 3+4)
- `core/metrics/base.py` — `BaseMetric` abstract class (name/unit/cost/compute,
  `approximate` flag).
- `core/metrics/registry.py` — `MetricRegistry` for registration/lookup.
- Real metrics: `rms.py`, `lufs.py`, `dynamic_range.py`, `zcr.py`,
  `spectral_flatness.py`.
- Approximate metrics (documented): `segmental_snr.py`, `srmr.py`, `c50.py`.
- `core/audio_loader.py` — `AudioLoader`: cached mono waveform loading.
- `core/metric_engine.py` — `MetricEngine`: `predict_time()` + `compute()`
  orchestration over the selected metrics and dataset rows.

### Backend — analysis & export (Task 5)
- `core/statistics.py` — `StatisticsBuilder`: full-dataset numeric summary.
- `core/filtering.py` — `DatasetFilter`: threshold filtering + before/after.
- `core/report.py` — `ReportGenerator`: PDF comparison report (reportlab +
  matplotlib).
- `api/` — DRF `views.py`, `serializers.py`, `urls.py` exposing all endpoints.

### Frontend (Task 1-5)
- MUI Material-Design theme with layered surfaces + subtle background texture.
- `WizardContext` for cross-page state, `api/client.js` axios wrapper.
- Pages: PathInput, CsvPreview, AttributeMapping, MetricSelection, Analysis.
- Components: StepperBar, CsvTable, AttributeMapper, MetricSelector, PlotCard,
  FilterSlider, StatTable.

## Verification
- All backend Python modules compile cleanly (`python -m compileall` -> exit 0).
- No linter errors reported for `backend/` or `frontend/src/`.
- Approximate metrics (`segmental_snr`, `srmr`, `c50`) carry an `approximate`
  flag that is propagated through `/api/metrics` and `/api/metrics/compute`
  responses and surfaced as an "approx" badge in the metric picker.

## How to run
1. `conda env create -f environment.yml`
2. `conda run -n audio_visual_web pip install -r backend/requirements.txt`
   (only needed if the pip section of environment.yml did not install them)
3. `bash start.sh` (or `./start.sh` after `chmod +x start.sh`)
   - Backend: http://localhost:8000/api/
   - Frontend: http://localhost:5173/

## Fixes
- Re-saved `frontend/src/components/StatTable.jsx` and
  `frontend/src/pages/MetricSelectionPage.jsx` after their initial writes were
  interrupted; both verified present and lint-clean afterwards.
- Switched the front-end scaffold from Create-React-App to Vite (CRA is
  deprecated); `start.sh` runs `npm run dev` and Vite proxies `/api` to Django
  to avoid CORS friction during local development.

