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

    def test_summary_skips_boolean_columns(self):
        df = pd.DataFrame({"flag": [True, False, True], "value": [1.0, 2.0, 3.0]})
        builder = StatisticsBuilder(df)
        self.assertEqual(builder.numeric_columns(), ["value"])
        rows = {r["column"]: r for r in builder.summary()}
        self.assertNotIn("flag", rows)
        self.assertEqual(rows["value"]["median"], 2.0)

    def test_plot_data_first_strategy_limits(self):
        result = self.builder.plot_data(["a"], limit=3, strategy="first")
        self.assertEqual(result.metric_data["a"], [1.0, 2.0, 3.0])
        self.assertEqual(result.total_rows, 5)

    def test_plot_data_random_is_deterministic_with_seed(self):
        p1 = self.builder.plot_data(["a"], limit=3, strategy="random", seed=42)
        p2 = self.builder.plot_data(["a"], limit=3, strategy="random", seed=42)
        self.assertEqual(p1.metric_data["a"], p2.metric_data["a"])

    def test_plot_data_serialises_inf_as_none(self):
        result = self.builder.plot_data(["b"], limit=10, strategy="first")
        self.assertIn(None, result.metric_data["b"])  # inf and nan both become None

    def test_plot_data_includes_row_metadata(self):
        result = self.builder.plot_data(["a"], limit=3, strategy="first")
        self.assertEqual(result.row_indices, [0, 1, 2])
        self.assertEqual(len(result.rows), 3)
        self.assertIn("name", result.metadata_columns)
        self.assertEqual(result.rows[0]["name"], "x")

    def test_row_indices_preserve_parent_index_after_filter(self):
        filtered = self.df[self.df["a"] >= 3.0]
        builder = StatisticsBuilder(filtered)
        result = builder.plot_data(["a"], limit=2, strategy="first")
        # Parent rows 2 and 3 — not iloc 0 and 1 inside the filtered subset.
        self.assertEqual(result.row_indices, [2, 3])


if __name__ == "__main__":
    unittest.main()
