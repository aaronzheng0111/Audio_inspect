"""SRMR metric (APPROXIMATE implementation).

The reference SRMR (Speech-to-Reverberation Modulation energy Ratio) uses a
gammatone filterbank followed by a modulation filterbank (see the `SRMRpy`
package). Implementing that faithfully is heavy; here we approximate the
*modulation-energy ratio* directly from the broadband temporal envelope:

    ratio = energy in low modulation bands (3-20 Hz, speech)
          / energy in high modulation bands (20-160 Hz, reverb/noise)

This captures the same qualitative behaviour (lower SRMR => more reverberant)
while staying lightweight. Flagged ``approximate`` so it can be swapped for the
real filterbank version later without changing the API.
"""
from __future__ import annotations

import numpy as np

from .base import BaseMetric


class SrmrMetric(BaseMetric):
    """Approximate speech-to-reverberation modulation energy ratio."""

    key = "srmr"
    label = "SRMR"
    unit = "ratio"
    cost = 3.0
    approximate = True
    description = "APPROX: modulation-energy ratio from the broadband envelope."

    def compute(self, waveform: np.ndarray, sample_rate: int) -> float:
        n = waveform.shape[0]
        if n < sample_rate // 4:  # need at least ~250 ms
            return float("nan")
        # Temporal amplitude envelope, low-pass smoothed and downsampled.
        envelope = np.abs(waveform)
        env_sr = 200  # Hz, enough for modulation up to 100 Hz
        decim = max(1, int(round(sample_rate / env_sr)))
        env = envelope[::decim]
        env = env - np.mean(env)
        if env.size < 8:
            return float("nan")
        spectrum = np.abs(np.fft.rfft(env)) ** 2
        freqs = np.fft.rfftfreq(env.size, d=decim / sample_rate)
        speech_band = (freqs >= 3) & (freqs <= 20)
        reverb_band = (freqs > 20) & (freqs <= 160)
        speech_energy = float(np.sum(spectrum[speech_band]))
        reverb_energy = float(np.sum(spectrum[reverb_band])) + 1e-12
        return float(speech_energy / reverb_energy)
