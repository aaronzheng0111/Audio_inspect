"""Integrated loudness (LUFS) metric (real implementation via pyloudnorm)."""
from __future__ import annotations

import numpy as np

from .base import BaseMetric

try:  # pyloudnorm is an optional-at-import dependency
    import pyloudnorm as pyln

    _HAS_PYLN = True
except Exception:  # pragma: no cover
    _HAS_PYLN = False


class LufsMetric(BaseMetric):
    """ITU-R BS.1770 integrated loudness in LUFS.

    Uses :mod:`pyloudnorm` when available. Very short clips (shorter than the
    400 ms gating block) cannot be measured and yield NaN.
    """

    key = "lufs"
    label = "LUFS"
    unit = "LUFS"
    cost = 2.0
    approximate = False
    description = "Integrated loudness (ITU-R BS.1770) in LUFS."

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        if not _HAS_PYLN:
            raise RuntimeError("pyloudnorm is not installed")
        # BS.1770 gating needs at least one 400 ms block.
        if waveform.shape[0] < int(0.4 * sample_rate):
            return float("nan")
        meter = pyln.Meter(sample_rate)
        return float(meter.integrated_loudness(waveform))
