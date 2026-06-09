"""Dynamic range metric (real implementation)."""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class DynamicRangeMetric(BaseMetric):
    """Loudness dynamic range in dB.

    Computed as the gap between a loud and a quiet percentile of the short-time
    energy envelope (95th minus 10th percentile of frame RMS, in dB). This is a
    robust, real measure of how much the level varies across the clip.
    """

    key = "dynamic_range"
    label = "Dynamic Range"
    unit = "dB"
    cost = 1.5
    approximate = False
    description = "Spread between loud and quiet frame levels (95th-10th pct)."

    frame_length = 2048
    hop_length = 512

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        n = waveform.shape[0]
        if n < self.frame_length:
            return 0.0
        frames = []
        for start in range(0, n - self.frame_length + 1, self.hop_length):
            frame = waveform[start : start + self.frame_length]
            frames.append(np.sqrt(np.mean(np.square(frame))))
        frame_rms = np.asarray(frames)
        frame_rms = frame_rms[frame_rms > 0]
        if frame_rms.size == 0:
            return 0.0
        frame_db = 20.0 * np.log10(frame_rms)
        loud = np.percentile(frame_db, 95)
        quiet = np.percentile(frame_db, 10)
        return float(loud - quiet)
