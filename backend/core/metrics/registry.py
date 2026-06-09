"""Registry that holds and looks up metric instances by key."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .base import BaseMetric


class MetricRegistry:
    """A simple ordered collection of :class:`BaseMetric` instances."""

    def __init__(self) -> None:
        self._metrics: Dict[str, BaseMetric] = {}

    def register(self, metric: BaseMetric) -> None:
        if not metric.key:
            raise ValueError(f"Metric {metric!r} has no key.")
        if metric.key in self._metrics:
            raise ValueError(f"Duplicate metric key: {metric.key!r}")
        self._metrics[metric.key] = metric

    def get(self, key: str) -> BaseMetric:
        try:
            return self._metrics[key]
        except KeyError as exc:
            raise KeyError(f"Unknown metric key: {key!r}") from exc

    def keys(self) -> List[str]:
        return list(self._metrics.keys())

    def all(self) -> List[BaseMetric]:
        return list(self._metrics.values())

    def select(self, keys: Iterable[str]) -> List[BaseMetric]:
        """Return metrics for ``keys`` preserving the requested order."""
        return [self.get(k) for k in keys]

    def __contains__(self, key: object) -> bool:
        return key in self._metrics
