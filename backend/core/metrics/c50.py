"""C50 clarity metric (APPROXIMATE implementation).

C50 is a room-acoustics clarity index: the energy ratio (in dB) between the
first 50 ms of a room impulse response and the remainder. Properly it requires
a measured impulse response, which a dataset clip does not provide.

This approximation derives a pseudo energy-decay curve from the signal's own
short-time energy envelope: it treats the global energy peak as the "direct
sound" onset and compares energy within 50 ms after the peak against the energy
that arrives later. It trends the right way (more reverberant/decaying signals
yield lower C50) but is not a calibrated acoustic measurement. Flagged
``approximate`` and isolated behind the standard metric interface so a true
impulse-response implementation can replace it later.
"""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class C50Metric(BaseMetric):
    """Approximate clarity index C50 in dB (early/late energy split at 50 ms)."""

    key = "c50"
    label = "C50"
    unit = "dB"
    cost = 2.0
    approximate = True
    description = "APPROX: early(<=50ms)/late energy ratio around the energy peak."

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        n = waveform.shape[0]
        if n < int(0.1 * sample_rate):
            return float("nan")
        energy = np.square(waveform)
        peak = int(np.argmax(energy))
        split = peak + int(0.05 * sample_rate)  # 50 ms after the peak
        early = float(np.sum(energy[peak:split]))
        late = float(np.sum(energy[split:])) + 1e-12
        if early <= 0:
            return float("nan")
        return float(10.0 * np.log10(early / late))
