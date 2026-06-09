"""Tests for core.statistics.StatisticsBuilder."""
import unittest

import numpy as np
import pandas as pd

from core.statistics import StatisticsBuilder


class StatisticsBuilderTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "a": [1.0, 2.0, 3.0, 4.0, 5.0],
                "b": [10.0, np.nan, 30.0, np.inf, 50.0],
                "name": ["x", "y", "z", "p", "q"],
            }
        )
        self.builder = StatisticsBuilder(self.df)

    def test_numeric_columns_excludes_text(self):
        self.assertEqual(set(self.builder.numeric_columns()), {"a", "b"})

    def test_summary_values(self):
        rows = {r["column"]: r for r in self.builder.summary()}
        self.assertEqual(rows["a"]["count"], 5)
        self.assertEqual(rows["a"]["min"], 1.0)
        self.assertEqual(rows["a"]["max"], 5.0)
        self.assertEqual(rows["a"]["median"], 3.0)

    def test_summary_ignores_inf_and_nan(self):
        rows = {r["column"]: r for r in self.builder.summary()}
        # b has one NaN and one inf -> only 3 valid values (10, 30, 50)
        self.assertEqual(rows["b"]["count"], 3)
        self.assertEqual(rows["b"]["max"], 50.0)

    def test_plot_data_first_strategy_limits(self):
        payload = self.builder.plot_data(["a"], limit=3, strategy="first")
        self.assertEqual(payload["a"], [1.0, 2.0, 3.0])
        self.assertEqual(payload["__count__"], [5])

    def test_plot_data_random_is_deterministic_with_seed(self):
        p1 = self.builder.plot_data(["a"], limit=3, strategy="random", seed=42)
        p2 = self.builder.plot_data(["a"], limit=3, strategy="random", seed=42)
        self.assertEqual(p1["a"], p2["a"])

    def test_plot_data_serialises_inf_as_none(self):
        payload = self.builder.plot_data(["b"], limit=10, strategy="first")
        self.assertIn(None, payload["b"])  # inf and nan both become None


if __name__ == "__main__":
    unittest.main()
