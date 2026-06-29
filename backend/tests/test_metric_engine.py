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

    def test_parallel_matches_serial(self):
        engine = MetricEngine()
        serial = engine.compute(self.df, ["rms", "zcr"], max_workers=1)
        parallel = engine.compute(self.df, ["rms", "zcr"], max_workers=4)
        pd.testing.assert_series_equal(serial["rms"], parallel["rms"])
        pd.testing.assert_series_equal(serial["zcr"], parallel["zcr"])

    def test_compute_adds_only_new_metrics(self):
        engine = MetricEngine()
        once = engine.compute(self.df, ["rms"])
        rms_before = once["rms"].copy()
        twice = engine.compute(once, ["zcr"])
        pd.testing.assert_series_equal(twice["rms"], rms_before)
        self.assertTrue(twice["zcr"].notna().all())

    def test_predict_time_empty_metrics(self):
        est = MetricEngine().predict_time(10, [])
        self.assertEqual(est.seconds, 0.0)
        self.assertEqual(est.metric_keys, [])

    def test_resume_only_fills_missing_rows(self):
        engine = MetricEngine()
        full = engine.compute(self.df, ["rms"])
        # Simulate a partially-finished run: blank out rms for the last 3 rows.
        partial = full.copy()
        partial.loc[partial.index[-3:], "rms"] = float("nan")
        preserved = partial["rms"].iloc[:-3].tolist()

        resumed = engine.compute(partial, ["rms"], resume=True)
        # Previously-computed rows are untouched; missing rows are filled.
        self.assertEqual(resumed["rms"].iloc[:-3].tolist(), preserved)
        self.assertTrue(resumed["rms"].notna().all())

    def test_resume_noop_when_complete(self):
        engine = MetricEngine()
        full = engine.compute(self.df, ["rms"])
        calls = []
        again = engine.compute(
            full, ["rms"], resume=True, progress=lambda d, t: calls.append((d, t))
        )
        pd.testing.assert_series_equal(again["rms"], full["rms"])

    def test_on_batch_invoked_with_partial_progress(self):
        engine = MetricEngine()
        seen = []
        engine.compute(
            self.df,
            ["rms"],
            batch_size=2,
            on_batch=lambda df, done, total: seen.append((done, total)),
        )
        self.assertTrue(seen)
        # Last callback reports completion of all rows.
        self.assertEqual(seen[-1], (len(self.df), len(self.df)))
        # Batches of 2 over 6 rows -> progress reported at 2, 4, 6.
        self.assertEqual([d for d, _ in seen], [2, 4, 6])

    def test_row_limit_caps_processed_rows(self):
        engine = MetricEngine()
        out = engine.compute(self.df, ["rms"], row_limit=3, row_strategy="first")
        self.assertEqual(int(out["rms"].notna().sum()), 3)

    def test_row_limit_random_is_deterministic(self):
        engine = MetricEngine()
        a = engine.compute(
            self.df, ["rms"], row_limit=3, row_strategy="random", row_seed=7
        )
        b = engine.compute(
            self.df, ["rms"], row_limit=3, row_strategy="random", row_seed=7
        )
        pd.testing.assert_series_equal(a["rms"], b["rms"])


if __name__ == "__main__":
    unittest.main()
