"""Core domain logic for the Audio Inspect backend.

Each responsibility lives in its own module to keep things small and
testable (see ``Generater/04 Implement.md``):

- :mod:`core.csv_inspector`   -- parse/sample/type-infer dataset CSVs
- :mod:`core.attribute_mapper` -- map non-standard columns to canonical names
- :mod:`core.audio_loader`     -- load audio waveforms (cached)
- :mod:`core.session_audio`    -- stream row audio for scatter-plot playback
- :mod:`core.metric_engine`    -- orchestrate metric computation + time estimate
- :mod:`core.session_store`    -- in-memory per-session state
- :mod:`core.statistics`       -- full-dataset statistical summaries
- :mod:`core.filtering`        -- threshold filtering with before/after counts
- :mod:`core.report`           -- PDF comparison report generation
- :mod:`core.metrics`          -- pluggable acoustic metric implementations
"""
