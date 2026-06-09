"""DRF views wiring HTTP endpoints to the ``core`` domain logic.

Each view is thin: it validates input with a serializer, calls into the
appropriate ``core`` object, and returns JSON. All dataset state is kept in the
in-memory :data:`core.session_store.session_store` keyed by ``session_id``.
"""
from __future__ import annotations

import os

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.attribute_mapper import ALIASES, AttributeMapper
from core.csv_inspector import REQUIRED_CANONICAL_COLUMNS, CsvInspector
from core.filtering import DatasetFilter, FilterRule
from core.metric_engine import MetricEngine
from core.metrics import registry
from core.report import ReportGenerator
from core.session_store import session_store
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
    return Response(
        {
            "session_id": session.session_id,
            "columns": list(session.dataframe.columns),
            "mapping": mapping,
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
    estimate = _engine.predict_time(len(session.dataframe), data["metrics"])
    return Response(estimate.to_dict())


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
        metrics = registry.select(data["metrics"])
    except KeyError as exc:
        return _error(str(exc))

    base_dir = os.path.dirname(session.csv_path)
    try:
        session.dataframe = _engine.compute(
            session.dataframe,
            data["metrics"],
            audio_path_column=audio_col,
            base_dir=base_dir,
        )
    except ValueError as exc:
        return _error(str(exc))
    session.computed_metrics = sorted(set(session.computed_metrics) | set(data["metrics"]))

    # Report how many rows produced a valid value per metric.
    coverage = {}
    for m in metrics:
        col = session.dataframe[m.key]
        coverage[m.key] = int(col.notna().sum())
    return Response(
        {
            "session_id": session.session_id,
            "computed_metrics": session.computed_metrics,
            "n_rows": int(len(session.dataframe)),
            "valid_counts": coverage,
            "approximate": [m.key for m in metrics if m.approximate],
        }
    )


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
    return Response(
        {
            "session_id": session_id,
            "numeric_columns": builder.numeric_columns(),
            "summary": builder.summary(),
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
    builder = StatisticsBuilder(session.dataframe)
    columns_param = data.get("columns") or ""
    if columns_param:
        columns = [c.strip() for c in columns_param.split(",") if c.strip()]
    else:
        columns = builder.numeric_columns()
    payload = builder.plot_data(
        columns, limit=data["limit"], strategy=data["strategy"]
    )
    total = payload.pop("__count__", [len(session.dataframe)])[0]
    return Response(
        {
            "session_id": data["session_id"],
            "columns": columns,
            "total_rows": total,
            "returned_rows": len(next(iter(payload.values()), [])),
            "data": payload,
        }
    )


def _rules_from(data) -> list:
    return [FilterRule.from_dict(r) for r in data.get("rules", [])]


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
    filtered = DatasetFilter(session.dataframe).apply(_rules_from(data))
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
    out_path = os.path.join(
        settings.WORKSPACE_DIR, f"report_{session.session_id}.pdf"
    )
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
