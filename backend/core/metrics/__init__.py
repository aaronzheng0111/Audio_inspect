"""Pluggable acoustic-quality metrics.

Importing this package populates a shared :data:`registry` with every metric so
the rest of the backend can look them up by key. Each metric subclasses
:class:`core.metrics.base.BaseMetric` and lives in its own file.
"""
from __future__ import annotations

from .base import BaseMetric
from .c50 import C50Metric
from .dynamic_range import DynamicRangeMetric
from .lufs import LufsMetric
from .registry import MetricRegistry
from .rms import RmsMetric
from .segmental_snr import SegmentalSnrMetric
from .spectral_flatness import SpectralFlatnessMetric
from .srmr import SrmrMetric
from .zcr import ZcrMetric

#: The canonical metric registry, pre-populated on import.
registry = MetricRegistry()
for _metric_cls in (
    RmsMetric,
    LufsMetric,
    DynamicRangeMetric,
    ZcrMetric,
    SpectralFlatnessMetric,
    SegmentalSnrMetric,
    SrmrMetric,
    C50Metric,
):
    registry.register(_metric_cls())

__all__ = ["BaseMetric", "MetricRegistry", "registry"]
