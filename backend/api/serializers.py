"""Request serializers/validators for the API endpoints.

These validate and normalise incoming JSON before the views hand work off to the
``core`` modules. Responses are built as plain dicts in the views (the payloads
are dynamic, dataset-shaped data rather than fixed model instances).
"""
from __future__ import annotations

from rest_framework import serializers


class LoadDatasetSerializer(serializers.Serializer):
    """POST /api/dataset/load"""

    csv_path = serializers.CharField(max_length=4096)
    sample_rows = serializers.IntegerField(required=False, default=15, min_value=1, max_value=200)


class MapAttributesSerializer(serializers.Serializer):
    """POST /api/dataset/map"""

    session_id = serializers.CharField()
    #: canonical-name -> actual-column, e.g. {"audio_path": "wav"}
    mapping = serializers.DictField(child=serializers.CharField(allow_blank=True))


class EstimateSerializer(serializers.Serializer):
    """POST /api/metrics/estimate"""

    session_id = serializers.CharField()
    metrics = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    row_limit = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    row_strategy = serializers.ChoiceField(
        choices=["first", "random"], required=False, default="first"
    )


class ComputeSerializer(serializers.Serializer):
    """POST /api/metrics/compute"""

    session_id = serializers.CharField()
    metrics = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    row_limit = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    row_strategy = serializers.ChoiceField(
        choices=["first", "random"], required=False, default="first"
    )


class PlotDataSerializer(serializers.Serializer):
    """GET /api/analysis/plot-data (query params)"""

    session_id = serializers.CharField()
    columns = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, default=200, min_value=1, max_value=5000)
    strategy = serializers.ChoiceField(choices=["first", "random"], required=False, default="first")
    #: JSON array of {column, min?, max?} — when set, sample only rows passing all rules.
    rules = serializers.CharField(required=False, allow_blank=True, default="")


class FilterRuleSerializer(serializers.Serializer):
    column = serializers.CharField()
    min = serializers.FloatField(required=False, allow_null=True)
    max = serializers.FloatField(required=False, allow_null=True)


class FilterSerializer(serializers.Serializer):
    """POST /api/analysis/filter and /api/export/*"""

    session_id = serializers.CharField()
    rules = FilterRuleSerializer(many=True, required=False, default=list)
