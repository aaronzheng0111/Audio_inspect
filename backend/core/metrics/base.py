"""Abstract base class shared by every acoustic metric."""
from __future__ import annotations

import abc
from typing import Any, Dict

import numpy as np


class BaseMetric(abc.ABC):
    """Contract for a single per-audio acoustic metric.

    Subclasses implement :meth:`compute` for one mono waveform and declare a
    handful of metadata attributes used by the UI and the time estimator.
    """

    #: Stable key used in the API and as the generated column name.
    key: str = ""
    #: Human-friendly display name.
    label: str = ""
    #: Physical unit (for axis labels / tooltips).
    unit: str = ""
    #: Relative compute cost per second of audio (used by predict_time()).
    #: 1.0 is a cheap time-domain metric; heavier transforms use larger values.
    cost: float = 1.0
    #: True when the implementation is an approximation rather than a reference
    #: algorithm. Surfaced to the user so results are interpreted with care.
    approximate: bool = False
    #: One-line description shown in the metric picker.
    description: str = ""

    @abc.abstractmethod
    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        """Return the metric value for a single mono ``waveform``."""

    def safe_compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        """Compute the metric, returning NaN instead of raising on bad audio."""
        try:
            if waveform is None or waveform.size == 0:
                return float("nan")
            value = self.compute(np.asarray(waveform, dtype=np.float64), sample_rate)
            return float(value)
        except Exception:
            return float("nan")

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the metric's metadata for the API."""
        return {
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "cost": self.cost,
            "approximate": self.approximate,
            "description": self.description,
        }
