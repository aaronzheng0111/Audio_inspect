"""DRF views wiring HTTP endpoints to the ``core`` domain logic.

Each view is thin: it validates input with a serializer, calls into the
appropriate ``core`` object, and returns JSON. All dataset state is kept in the
in-memory :data:`core.session_store.session_store` keyed by ``session_id``.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.attribute_mapper import ALIASES, AttributeMapper
from core.audio_path_resolver import resolve_audio_file, resolve_audio_root
from core.csv_inspector import REQUIRED_CANONICAL_COLUMNS, CsvInspector
from core.filtering import DatasetFilter, FilterRule
from core.metric_engine import MetricEngine
from core.metrics import registry
from core.report import ReportGenerator
from core.session_audio import SessionAudioError, SessionAudioStreamer
from core.session_store import Session, session_store
from core.statistics import StatisticsBuilder

from .serializers import (
    ComputeSerializer,
    EstimateSerializer,
    FilterSerializer,
    LoadDatasetSerializer,
    MapAttributesSerializer,
    PlotDataSerializer,
)

_engine = MetricEngine()


def _pending_metrics(session: Session, requested: list) -> list:
    """Metric keys requested but not yet computed into the session dataframe."""
    done = set(session.computed_metrics or [])
    return [m for m in requested if m not in done]


def _pending_row_count(session: Session, pending_metrics: list) -> int:
    """How many rows still need values for at least one pending metric."""
    if not pending_metrics:
        return 0
    df = session.dataframe
    cols = [m for m in pending_metrics if m in df.columns]
    if not cols:
        return len(df)
    return int(df[cols].isna().any(axis=1).sum())


def _effective_row_limit(
    session: Session, pending_metrics: list, row_limit: Optional[int]
) -> int:
    """Rows that will be processed this run (respecting optional cap)."""
    pending_rows = _pending_row_count(session, pending_metrics)
    if row_limit is None:
        return pending_rows
    return min(row_limit, pending_rows)


def _atomic_write_csv(dataframe, csv_path: str) -> None:
    """Write a DataFrame to ``csv_path`` atomically (temp file + rename).

    Writing to a temp file in the same directory and then renaming avoids
    leaving a half-written / corrupt CSV if the process is interrupted mid-write
    (important for long incremental jobs).
    """
    directory = os.path.dirname(csv_path) or "."
    fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=directory)
    try:
        with os.fdopen(fd, "w", newline="") as handle:
            dataframe.to_csv(handle, index=False)
        os.replace(tmp_path, csv_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _probe_audio(session: Session, audio_col: str, max_samples: int = 25) -> dict:
    """Detect the best filesystem root for relative audio paths in this session."""
    series = session.dataframe[audio_col]
    n = len(series)
    if n <= max_samples:
        samples = series.tolist()
    else:
        # Avoid materialising millions of path strings on huge datasets.
        step = max(1, n // max_samples)
        samples = series.iloc[::step].head(max_samples).tolist()
    root, found, checked = resolve_audio_root(session.csv_path, samples)
    session.audio_root = root
    session.audio_probe = {"found": found, "checked": checked}
    example = ""
    if samples:
        example = resolve_audio_file(samples[0], session.csv_path, root)
    payload = {
        "audio_root": root,
        "audio_probe": session.audio_probe,
        "example_resolved_path": example,
    }
    if checked and found == 0:
        payload["warning"] = (
            f"No audio files found on disk (checked {checked} sample paths). "
            f"Resolved audio root: {root}. "
            f"Example path tried: {example}. "
            "Place the audio files there or fix the path column in your CSV."
        )
    elif checked and found < checked:
        payload["warning"] = (
            f"Only {found}/{checked} sample audio files were found under {root}. "
            "Some rows may produce empty metrics."
        )
    return payload


def _error(message: str, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": message}, status=code)


@api_view(["GET"])
def list_metrics(request):
    """GET /api/metrics — metadata for every available metric."""
    return Response({"metrics": [m.to_dict() for m in registry.all()]})


@api_view(["POST"])
def load_dataset(request):
    """POST /api/dataset/load (Task 1+2)."""
    serializer = LoadDatasetSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    inspector = CsvInspector(data["csv_path"], sample_rows=data["sample_rows"])
    try:
        df = inspector.load()
    except (FileNotFoundError, ValueError) as exc:
        return _error(str(exc))

    session = session_store.create(inspector.csv_path, df)

    # Detect metric columns already present in the CSV (written back from a
    # previous session) so we never recompute them unnecessarily. A column only
    # counts as fully computed if it exists AND has no missing values; a column
    # with NaNs is a partially-finished run and will be resumed (only the
    # missing rows recomputed) rather than skipped.
    all_metric_keys = {m.key for m in registry.all()}
    present = [k for k in all_metric_keys if k in df.columns]
    pre_computed = sorted(
        k for k in present
        if not pd.to_numeric(df[k], errors="coerce").isna().any()
    )
    partial_metrics = sorted(set(present) - set(pre_computed))
    if pre_computed:
        session.computed_metrics = pre_computed

    mapper = AttributeMapper(list(df.columns))
    return Response(
        {
            "session_id": session.session_id,
            "csv_path": inspector.csv_path,
            "n_rows": int(len(df)),
            "columns": [c.to_dict() for c in inspector.describe_columns()],
            "sample": inspector.sample(),
            "required_columns": REQUIRED_CANONICAL_COLUMNS,
            "suggested_mapping": mapper.suggest(),
            "alias_hints": ALIASES,
            "pre_computed_metrics": pre_computed,
            "partial_metrics": partial_metrics,
        }
    )


@api_view(["POST"])
def map_attributes(request):
    """POST /api/dataset/map (Task 3)."""
    serializer = MapAttributesSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)

    mapping = {k: v for k, v in data["mapping"].items() if v}
    mapper = AttributeMapper(list(session.dataframe.columns))
    try:
        session.dataframe = mapper.apply(session.dataframe, mapping)
    except ValueError as exc:
        return _error(str(exc))
    session.column_mapping = mapping
    audio_col = session.canonical_to_column("audio_path") or "audio_path"
    probe = _probe_audio(session, audio_col) if audio_col in session.dataframe.columns else {}
    return Response(
        {
            "session_id": session.session_id,
            "columns": list(session.dataframe.columns),
            "mapping": mapping,
            **probe,
        }
    )


@api_view(["POST"])
def estimate_metrics(request):
    """POST /api/metrics/estimate (Task 4)."""
    serializer = EstimateSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    try:
        registry.select(data["metrics"])
    except KeyError as exc:
        return _error(str(exc))
    audio_col = session.canonical_to_column("audio_path") or "audio_path"
    if audio_col not in session.dataframe.columns:
        return _error("No 'audio_path' column mapped; cannot read audio files.")
    probe = _probe_audio(session, audio_col)
    pending = _pending_metrics(session, data["metrics"])
    skipped = [m for m in data["metrics"] if m not in pending]
    row_limit = data.get("row_limit")
    compute_rows = _effective_row_limit(session, pending, row_limit)
    estimate = _engine.predict_time(compute_rows, pending)
    return Response(
        {
            **estimate.to_dict(),
            **probe,
            "pending_metrics": pending,
            "skipped_metrics": skipped,
            "computed_metrics": list(session.computed_metrics or []),
            "total_rows": int(len(session.dataframe)),
            "pending_rows": _pending_row_count(session, pending),
            "compute_rows": compute_rows,
            "row_limit": row_limit,
            "row_strategy": data.get("row_strategy", "first"),
        }
    )


@api_view(["POST"])
def compute_metrics(request):
    """POST /api/metrics/compute (Task 3+4)."""
    serializer = ComputeSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)

    audio_col = session.canonical_to_column("audio_path") or "audio_path"
    if audio_col not in session.dataframe.columns:
        return _error("No 'audio_path' column mapped; cannot read audio files.")
    if len(session.dataframe) > settings.MAX_AUDIO_FILES:
        return _error(
            f"Dataset too large (> {settings.MAX_AUDIO_FILES} rows) for one run."
        )
    try:
        registry.select(data["metrics"])
    except KeyError as exc:
        return _error(str(exc))

    requested = data["metrics"]
    pending = _pending_metrics(session, requested)
    skipped = [m for m in requested if m not in pending]
    row_limit = data.get("row_limit")
    row_strategy = data.get("row_strategy", "first")
    compute_rows = _effective_row_limit(session, pending, row_limit)

    if not session.audio_root:
        _probe_audio(session, audio_col)

    try:
        stats = {"compute_rows": 0, "pending_compute_rows": 0, "computed_rows": 0}
        if pending:
            stats = _run_compute_on_session(
                session,
                pending,
                row_limit=row_limit,
                row_strategy=row_strategy,
            )
    except ValueError as exc:
        return _error(str(exc))

    all_metrics = registry.select(requested)

    # Report how many rows produced a valid value per metric.
    coverage = {}
    for m in all_metrics:
        col = session.dataframe[m.key]
        coverage[m.key] = int(col.notna().sum())
    total_valid = max(coverage.values()) if coverage else 0
    probe = _probe_audio(session, audio_col)
    base_dir = session.audio_root or os.path.dirname(session.csv_path)
    response = {
        "session_id": session.session_id,
        "computed_metrics": session.computed_metrics,
        "computed_now": pending,
        "skipped_metrics": skipped,
        "n_rows": int(len(session.dataframe)),
        "compute_rows": compute_rows,
        "row_limit": row_limit,
        "row_strategy": row_strategy,
        "valid_counts": coverage,
        "approximate": [m.key for m in all_metrics if m.approximate],
        "audio_root": base_dir,
        "audio_probe": probe.get("audio_probe"),
        "example_resolved_path": probe.get("example_resolved_path"),
    }
    if total_valid == 0:
        response["warning"] = probe.get("warning") or (
            "Metric computation finished but no audio files could be read. "
            "Charts will be empty until the audio files are available on disk."
        )
    elif probe.get("warning"):
        response["warning"] = probe["warning"]
    return Response(response)


@api_view(["GET"])
def analysis_summary(request):
    """GET /api/analysis/summary (Task 5)."""
    session_id = request.query_params.get("session_id")
    if not session_id:
        return _error("session_id is required.")
    try:
        session = session_store.get(session_id)
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    builder = StatisticsBuilder(session.dataframe)
    metric_cols = session.computed_metrics or None
    return Response(
        {
            "session_id": session_id,
            "numeric_columns": builder.numeric_columns(),
            "summary": builder.summary(columns=metric_cols),
        }
    )


@api_view(["GET"])
def plot_data(request):
    """GET /api/analysis/plot-data (Task 5)."""
    serializer = PlotDataSerializer(data=request.query_params)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    dataframe = session.dataframe
    rules_raw = (data.get("rules") or "").strip()
    if rules_raw:
        try:
            rules_payload = json.loads(rules_raw)
        except json.JSONDecodeError:
            return _error("rules must be a JSON array.")
        if not isinstance(rules_payload, list):
            return _error("rules must be a JSON array.")
        rules = _rules_from({"rules": rules_payload})
        if rules:
            dataframe = DatasetFilter(dataframe).apply(rules)
    builder = StatisticsBuilder(dataframe)
    columns_param = data.get("columns") or ""
    if columns_param:
        columns = [c.strip() for c in columns_param.split(",") if c.strip()]
    else:
        columns = builder.numeric_columns()
    result = builder.plot_data(
        columns, limit=data["limit"], strategy=data["strategy"]
    )
    return Response(
        {
            "session_id": data["session_id"],
            "columns": columns,
            "total_rows": result.total_rows,
            "returned_rows": result.returned_rows,
            "row_indices": result.row_indices,
            "rows": result.rows,
            "metadata_columns": result.metadata_columns,
            "data": result.metric_data,
        }
    )


@api_view(["GET"])
def stream_audio(request):
    """GET /api/audio/stream — serve one row's audio file for in-browser playback."""
    session_id = request.query_params.get("session_id")
    row_index = request.query_params.get("row_index")
    if not session_id or row_index is None:
        return _error("session_id and row_index are required.")
    try:
        row_pos = int(row_index)
    except (TypeError, ValueError):
        return _error("row_index must be an integer.")
    try:
        session = session_store.get(session_id)
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)

    try:
        audio = SessionAudioStreamer(session).open_row(row_pos)
    except SessionAudioError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)

    response = FileResponse(audio.handle, content_type=audio.content_type)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "no-cache"
    return response


def _rules_from(data) -> list:
    return [FilterRule.from_dict(r) for r in data.get("rules", [])]


def _session_metrics(session: Session) -> list:
    return list(session.computed_metrics or [])


def _pending_rows_mask(session: Session, metric_keys: list) -> pd.Series:
    """True for rows missing at least one value in *metric_keys*."""
    df = session.dataframe
    cols = [m for m in metric_keys if m in df.columns]
    if not cols:
        return pd.Series(False, index=df.index)
    return df[cols].isna().any(axis=1)


def _export_queue_status(session: Session, rules: list) -> dict:
    """Summarise the queued export filter and remaining metric work."""
    metrics = _session_metrics(session)
    flt = DatasetFilter(session.dataframe)
    filter_summary = flt.summary(rules)
    pending_mask = _pending_rows_mask(session, metrics)
    pending_rows = int(pending_mask.sum())
    return {
        "metrics": metrics,
        "pending_compute_rows": pending_rows,
        "filter": filter_summary,
    }


def _run_compute_on_session(
    session: Session,
    metric_keys: list,
    *,
    row_limit: Optional[int] = None,
    row_strategy: str = "first",
    subset_mask: Optional[pd.Series] = None,
) -> dict:
    """Compute metrics into ``session.dataframe`` (in place) and persist CSV."""
    audio_col = session.canonical_to_column("audio_path") or "audio_path"
    if audio_col not in session.dataframe.columns:
        raise ValueError("No 'audio_path' column mapped; cannot read audio files.")
    if not metric_keys:
        return {"compute_rows": 0, "pending_compute_rows": 0}
    registry.select(metric_keys)
    if not session.audio_root:
        _probe_audio(session, audio_col)
    base_dir = session.audio_root or os.path.dirname(session.csv_path)

    _BATCH_SIZE = 2000
    _WRITE_EVERY = 10000
    last_write = {"done": 0}

    def _persist(df, done, total):
        if done - last_write["done"] >= _WRITE_EVERY or done >= total:
            last_write["done"] = done
            try:
                _atomic_write_csv(df, session.csv_path)
            except Exception:
                pass

    pending_before = int(_pending_rows_mask(session, metric_keys).sum())
    compute_rows = pending_before
    if row_limit is not None:
        compute_rows = min(row_limit, pending_before)

    session.dataframe = _engine.compute(
        session.dataframe,
        metric_keys,
        audio_path_column=audio_col,
        base_dir=base_dir,
        batch_size=_BATCH_SIZE,
        on_batch=_persist,
        resume=True,
        row_limit=row_limit,
        row_strategy=row_strategy,
        subset_mask=subset_mask,
    )
    session.computed_metrics = sorted(set(session.computed_metrics or []) | set(metric_keys))
    try:
        _atomic_write_csv(session.dataframe, session.csv_path)
    except Exception:
        pass

    pending_after = int(_pending_rows_mask(session, metric_keys).sum())
    return {
        "compute_rows": compute_rows,
        "pending_compute_rows": pending_after,
        "computed_rows": pending_before - pending_after,
    }


@api_view(["POST"])
def apply_filter(request):
    """POST /api/analysis/filter (Task 5)."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    flt = DatasetFilter(session.dataframe)
    return Response(flt.summary(_rules_from(data)))


@api_view(["POST"])
def queue_export(request):
    """POST /api/analysis/queue-export — save filter rules for the export pipeline."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    rules = _rules_from(data)
    session.queued_export_rules = [
        {"column": r.column, "min": r.min_value, "max": r.max_value} for r in rules
    ]
    status_payload = _export_queue_status(session, rules)
    return Response(
        {
            "session_id": session.session_id,
            "queued": True,
            "rules": session.queued_export_rules,
            **status_payload,
        }
    )


@api_view(["POST"])
def compute_queued(request):
    """POST /api/analysis/compute-queued — fill missing metrics before export."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    if not session.queued_export_rules:
        return _error("Queue an export filter first (POST /api/analysis/queue-export).")
    metrics = _session_metrics(session)
    if not metrics:
        return _error("No metrics have been computed for this session yet.")
    rules = _rules_from({"rules": session.queued_export_rules})
    pending_before = int(_pending_rows_mask(session, metrics).sum())
    if pending_before == 0:
        status_payload = _export_queue_status(session, rules)
        return Response(
            {
                "session_id": session.session_id,
                "message": "All rows already have metric values.",
                "computed_rows": 0,
                **status_payload,
            }
        )
    try:
        stats = _run_compute_on_session(session, metrics, row_limit=None)
    except ValueError as exc:
        return _error(str(exc))
    status_payload = _export_queue_status(session, rules)
    return Response(
        {
            "session_id": session.session_id,
            **stats,
            **status_payload,
        }
    )


@api_view(["POST"])
def finalize_export(request):
    """POST /api/export/finalize — compute remaining metrics, then write filtered CSV."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    rules_payload = data.get("rules") or session.queued_export_rules
    if not rules_payload:
        return _error("Queue an export filter first (POST /api/analysis/queue-export).")
    rules = _rules_from({"rules": rules_payload})
    session.queued_export_rules = [
        {"column": r.column, "min": r.min_value, "max": r.max_value} for r in rules
    ]
    metrics = _session_metrics(session)
    if not metrics:
        return _error("No metrics have been computed for this session yet.")
    compute_stats = {"computed_rows": 0, "pending_compute_rows": 0}
    if int(_pending_rows_mask(session, metrics).sum()) > 0:
        try:
            compute_stats = _run_compute_on_session(session, metrics, row_limit=None)
        except ValueError as exc:
            return _error(str(exc))
    filtered = DatasetFilter(session.dataframe).apply(rules)
    out_path = os.path.join(
        settings.WORKSPACE_DIR, f"filtered_{session.session_id}.csv"
    )
    filtered.to_csv(out_path, index=False)
    filter_summary = DatasetFilter(session.dataframe).summary(rules)
    return Response(
        {
            "session_id": session.session_id,
            "path": out_path,
            "rows": int(len(filtered)),
            "rules": session.queued_export_rules,
            **compute_stats,
            "filter": filter_summary,
        }
    )


@api_view(["POST"])
def export_csv(request):
    """POST /api/export/csv (Task 5)."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    rules_payload = data.get("rules") or session.queued_export_rules or []
    rules = _rules_from({"rules": rules_payload})
    filtered = DatasetFilter(session.dataframe).apply(rules)
    out_path = os.path.join(
        settings.WORKSPACE_DIR, f"filtered_{session.session_id}.csv"
    )
    filtered.to_csv(out_path, index=False)
    return Response(
        {
            "session_id": session.session_id,
            "path": out_path,
            "rows": int(len(filtered)),
        }
    )


@api_view(["POST"])
def export_report(request):
    """POST /api/export/report (Task 5)."""
    serializer = FilterSerializer(data=request.data)
    if not serializer.is_valid():
        return _error(str(serializer.errors))
    data = serializer.validated_data
    try:
        session = session_store.get(data["session_id"])
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    before = session.dataframe
    after = DatasetFilter(before).apply(_rules_from(data))
    out_path = _report_path(session.session_id)
    columns = session.computed_metrics or None
    try:
        ReportGenerator(before, after).generate(out_path, columns=columns)
    except Exception as exc:  # pragma: no cover - surfaced to user
        return _error(f"Failed to generate report: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(
        {
            "session_id": session.session_id,
            "path": out_path,
            "before": int(len(before)),
            "after": int(len(after)),
        }
    )


def _report_path(session_id: str) -> str:
    return os.path.join(settings.WORKSPACE_DIR, f"report_{session_id}.pdf")


@api_view(["GET"])
def preview_report(request):
    """GET /api/export/report/preview — inline PDF for in-browser preview."""
    session_id = request.query_params.get("session_id")
    if not session_id:
        return _error("session_id is required.")
    try:
        session_store.get(session_id)
    except KeyError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    out_path = _report_path(session_id)
    if not os.path.isfile(out_path):
        return _error("Report not found. Export the PDF first.", status.HTTP_404_NOT_FOUND)
    response = FileResponse(open(out_path, "rb"), content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="audio_inspect_report.pdf"'
    return response


# -- filesystem browser ---------------------------------------------------

_HOME = str(Path.home())

#: CSV-friendly file extensions shown in the browser (case-insensitive).
_CSV_EXTENSIONS = frozenset({".csv", ".tsv", ".txt"})


def _visible_entries(path: str):
    """Return (directories, files) under *path*, excluding dot-files."""
    try:
        names = os.listdir(path)
    except PermissionError:
        return [], []
    dirs, files = [], []
    for name in names:
        if name.startswith("."):
            continue
        full = os.path.join(path, name)
        try:
            if os.path.isdir(full):
                dirs.append(name)
            elif os.path.isfile(full) and os.path.splitext(name)[1].lower() in _CSV_EXTENSIONS:
                files.append(name)
        except OSError:
            continue
    dirs.sort(key=str.lower)
    files.sort(key=str.lower)
    return dirs, files


@api_view(["GET"])
def browse_filesystem(request):
    """GET /api/filesystem/browse — list directories and CSV files under a path.

    Query params:
        path (str, optional): directory to browse. Defaults to the user's home.

    Returns:
        {
            "path": "<canonical absolute path>",
            "parent": "<parent path or null>",
            "roots": ["/home/user", "/", ...],   // only when path == home
            "directories": [{"name": "...", "path": "..."}, ...],
            "files": [{"name": "...", "path": "..."}, ...],
        }
    """
    raw = (request.query_params.get("path") or "").strip()
    target = str(Path(raw).expanduser().resolve()) if raw else _HOME

    if not os.path.isdir(target):
        return _error(f"Not a directory: {target}")

    dirs, files = _visible_entries(target)
    parent = str(Path(target).parent) if target != "/" and Path(target).parent != Path(target) else None

    payload = {
        "path": target,
        "parent": parent,
        "directories": [
            {"name": d, "path": os.path.join(target, d)} for d in dirs
        ],
        "files": [
            {"name": f, "path": os.path.join(target, f)} for f in files
        ],
    }

    # On the initial request (no path given), also return common roots so the
    # UI can offer quick-jump targets.
    if not raw:
        roots = [_HOME]
        if os.path.exists("/Volumes"):
            try:
                for v in os.listdir("/Volumes"):
                    vp = os.path.join("/Volumes", v)
                    if os.path.isdir(vp) and not v.startswith("."):
                        roots.append(vp)
            except OSError:
                pass
        payload["roots"] = roots

    return Response(payload)
