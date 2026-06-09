"""Tests for core.metric_engine.MetricEngine (estimate + compute)."""
import math
import os
import shutil
import unittest

import pandas as pd

from core.metric_engine import MetricEngine
from tests.utils import build_dataset


class PredictTimeTest(unittest.TestCase):
    def test_estimate_scales_with_rows(self):
        engine = MetricEngine()
        small = engine.predict_time(10, ["rms"]).seconds
        large = engine.predict_time(100, ["rms"]).seconds
        self.assertAlmostEqual(large, small * 10, places=4)

    def test_more_metrics_costs_more(self):
        engine = MetricEngine()
        one = engine.predict_time(50, ["rms"]).seconds
        many = engine.predict_time(50, ["rms", "lufs", "spectral_flatness"]).seconds
        self.assertGreater(many, one)

    def test_estimate_serialises(self):
        d = MetricEngine().predict_time(5, ["rms"]).to_dict()
        self.assertIn("estimated_seconds", d)
        self.assertIn("estimated_human", d)


class ComputeTest(unittest.TestCase):
    def setUp(self):
        self.dir, self.csv_path, self.wavs = build_dataset(n=6)
        self.df = pd.read_csv(self.csv_path).rename(columns={"file": "audio_path"})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_compute_adds_metric_columns(self):
        out = MetricEngine().compute(self.df, ["rms", "zcr"])
        self.assertIn("rms", out.columns)
        self.assertIn("zcr", out.columns)
        self.assertEqual(len(out), len(self.df))
        # Every clip is readable, so values should be finite.
        self.assertTrue(out["rms"].notna().all())

    def test_missing_audio_yields_nan_not_crash(self):
        df = self.df.copy()
        df.loc[0, "audio_path"] = "/does/not/exist.wav"
        out = MetricEngine().compute(df, ["rms"])
        self.assertTrue(math.isnan(out.loc[0, "rms"]))
        self.assertTrue(out["rms"].iloc[1:].notna().all())

    def test_missing_audio_path_column_raises(self):
        with self.assertRaises(ValueError):
            MetricEngine().compute(self.df.drop(columns=["audio_path"]), ["rms"])


if __name__ == "__main__":
    unittest.main()
