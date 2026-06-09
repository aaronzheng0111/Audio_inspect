"""Zero-crossing rate metric (real implementation)."""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class ZcrMetric(BaseMetric):
    """Mean zero-crossing rate (fraction of samples where the sign changes).

    A simple, fast time-domain feature correlated with noisiness / fricatives.
    """

    key = "zcr"
    label = "ZCR"
    unit = "rate"
    cost = 1.0
    approximate = False
    description = "Average zero-crossing rate of the waveform."

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        if waveform.shape[0] < 2:
            return 0.0
        signs = np.signbit(waveform)
        crossings = np.sum(signs[1:] != signs[:-1])
        return float(crossings / (waveform.shape[0] - 1))
