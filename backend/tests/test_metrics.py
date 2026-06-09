"""Tests for the acoustic metrics and the registry.

These run on synthetic numpy waveforms, so they need no audio files or codecs.
"""
import math
import unittest

import numpy as np

from core.metrics import registry
from core.metrics.dynamic_range import DynamicRangeMetric
from core.metrics.rms import RmsMetric
from core.metrics.spectral_flatness import SpectralFlatnessMetric
from core.metrics.zcr import ZcrMetric
from tests.utils import sine_wave, white_noise


class RegistryTest(unittest.TestCase):
    def test_eight_metrics_registered(self):
        self.assertEqual(len(registry.all()), 8)

    def test_expected_keys_present(self):
        keys = set(registry.keys())
        self.assertSetEqual(
            keys,
            {
                "rms", "lufs", "dynamic_range", "zcr", "spectral_flatness",
                "segmental_snr", "srmr", "c50",
            },
        )

    def test_approximate_flags(self):
        approx = {m.key for m in registry.all() if m.approximate}
        self.assertSetEqual(approx, {"segmental_snr", "srmr", "c50"})

    def test_select_preserves_order(self):
        chosen = registry.select(["zcr", "rms"])
        self.assertEqual([m.key for m in chosen], ["zcr", "rms"])

    def test_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            registry.get("nope")


class MetricValueTest(unittest.TestCase):
    def test_rms_of_known_amplitude(self):
        wave, sr = sine_wave(amplitude=0.5)
        # RMS of a sine with amplitude a is a/sqrt(2) -> dBFS value.
        expected = 20 * math.log10(0.5 / math.sqrt(2))
        self.assertAlmostEqual(RmsMetric().compute(wave, sr), expected, places=1)

    def test_rms_silence_uses_floor_not_inf(self):
        value = RmsMetric().compute(np.zeros(16000), 16000)
        self.assertTrue(math.isfinite(value))
        self.assertEqual(value, RmsMetric.SILENCE_FLOOR_DB)

    def test_zcr_in_unit_range(self):
        wave, sr = sine_wave()
        z = ZcrMetric().compute(wave, sr)
        self.assertGreaterEqual(z, 0.0)
        self.assertLessEqual(z, 1.0)

    def test_noise_has_higher_zcr_than_tone(self):
        tone, sr = sine_wave(freq=200.0)
        noise, _ = white_noise()
        self.assertLess(
            ZcrMetric().compute(tone, sr), ZcrMetric().compute(noise, sr)
        )

    def test_spectral_flatness_noise_vs_tone(self):
        tone, sr = sine_wave(freq=440.0)
        noise, _ = white_noise()
        flat_tone = SpectralFlatnessMetric().compute(tone, sr)
        flat_noise = SpectralFlatnessMetric().compute(noise, sr)
        self.assertGreaterEqual(flat_tone, 0.0)
        self.assertLessEqual(flat_noise, 1.0)
        self.assertLess(flat_tone, flat_noise)

    def test_dynamic_range_non_negative(self):
        wave, sr = sine_wave()
        self.assertGreaterEqual(DynamicRangeMetric().compute(wave, sr), 0.0)

    def test_safe_compute_handles_empty(self):
        self.assertTrue(math.isnan(RmsMetric().safe_compute(np.array([]), 16000)))


if __name__ == "__main__":
    unittest.main()
