"""RMS level metric (real implementation)."""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class RmsMetric(BaseMetric):
    """Root-mean-square level of the waveform, expressed in dBFS.

    0 dBFS corresponds to a full-scale RMS of 1.0; quieter signals are negative.
    """

    key = "rms"
    label = "RMS"
    unit = "dBFS"
    cost = 1.0
    approximate = False
    description = "Root-mean-square level in dBFS (loudness proxy)."

    #: Floor reported for digital silence, avoids non-serialisable -inf.
    SILENCE_FLOOR_DB = -120.0

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        rms = np.sqrt(np.mean(np.square(waveform)))
        if rms <= 0:
            return self.SILENCE_FLOOR_DB
        return float(max(20.0 * np.log10(rms), self.SILENCE_FLOOR_DB))
