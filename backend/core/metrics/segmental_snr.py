"""Segmental SNR metric (APPROXIMATE implementation).

A true segmental SNR requires a clean reference signal (or a separate noise
estimate). We don't have a reference here, so this is a *no-reference*
approximation: per-frame energies are split into a "speech" set (high-energy
frames) and a "noise floor" set (low-energy frames) and the average per-frame
log ratio between them is reported. The interface matches the real metrics so a
reference-based implementation can be dropped in later without changing callers.
"""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class SegmentalSnrMetric(BaseMetric):
    """No-reference segmental SNR approximation in dB."""

    key = "segmental_snr"
    label = "Segmental SNR"
    unit = "dB"
    cost = 2.0
    approximate = True
    description = "APPROX: per-frame speech-vs-noise-floor energy ratio (no reference)."

    frame_length = 1024
    hop_length = 512

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        n = waveform.shape[0]
        if n < self.frame_length:
            return float("nan")
        energies = []
        for start in range(0, n - self.frame_length + 1, self.hop_length):
            frame = waveform[start : start + self.frame_length]
            energies.append(float(np.sum(np.square(frame))) + 1e-12)
        energies = np.asarray(energies)
        # Noise floor: bottom 15% of frame energies; speech: top 50%.
        noise_floor = np.percentile(energies, 15)
        speech = energies[energies >= np.percentile(energies, 50)]
        if noise_floor <= 0 or speech.size == 0:
            return float("nan")
        seg_snr = 10.0 * np.log10(speech / noise_floor)
        # Clip per ITU-style segmental SNR convention to a sane range.
        seg_snr = np.clip(seg_snr, -10.0, 60.0)
        return float(np.mean(seg_snr))
