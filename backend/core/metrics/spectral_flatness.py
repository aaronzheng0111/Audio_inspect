"""Spectral flatness metric (real implementation)."""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class SpectralFlatnessMetric(BaseMetric):
    """Spectral flatness (Wiener entropy), ratio of geometric to arithmetic
    mean of the power spectrum.

    Values near 1 indicate noise-like (flat) spectra; values near 0 indicate
    tonal signals. Averaged across short-time frames.
    """

    key = "spectral_flatness"
    label = "Spectral Flatness"
    unit = "ratio"
    cost = 2.5
    approximate = False
    description = "Geometric/arithmetic mean ratio of the power spectrum."

    frame_length = 2048
    hop_length = 512

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        n = waveform.shape[0]
        if n < self.frame_length:
            window = waveform * np.hanning(n)
            return self._frame_flatness(window)
        values = []
        win = np.hanning(self.frame_length)
        for start in range(0, n - self.frame_length + 1, self.hop_length):
            frame = waveform[start : start + self.frame_length] * win
            values.append(self._frame_flatness(frame))
        return float(np.mean(values)) if values else 0.0

    @staticmethod
    def _frame_flatness(frame: np.ndarray) -> float:
        spectrum = np.abs(np.fft.rfft(frame)) ** 2
        spectrum = spectrum[spectrum > 1e-12]
        if spectrum.size == 0:
            return 0.0
        geometric = np.exp(np.mean(np.log(spectrum)))
        arithmetic = np.mean(spectrum)
        if arithmetic <= 0:
            return 0.0
        return float(geometric / arithmetic)
