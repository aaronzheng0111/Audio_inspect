"""Tests for core.filtering.DatasetFilter."""
import unittest

import numpy as np
import pandas as pd

from core.filtering import DatasetFilter, FilterRule


class DatasetFilterTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({"rms": [-30.0, -20.0, -10.0, -5.0, np.nan]})
        self.flt = DatasetFilter(self.df)

    def test_min_filter(self):
        rules = [FilterRule("rms", min_value=-20.0)]
        out = self.flt.apply(rules)
        self.assertEqual(len(out), 3)  # -20, -10, -5

    def test_min_max_window(self):
        rules = [FilterRule("rms", min_value=-25.0, max_value=-8.0)]
        out = self.flt.apply(rules)
        self.assertEqual(sorted(out["rms"].tolist()), [-20.0, -10.0])

    def test_nan_rows_excluded(self):
        rules = [FilterRule("rms", min_value=-100.0)]
        out = self.flt.apply(rules)
        self.assertEqual(len(out), 4)  # NaN row dropped

    def test_summary_counts(self):
        summary = self.flt.summary([FilterRule("rms", min_value=-20.0)])
        self.assertEqual(summary["before"], 5)
        self.assertEqual(summary["after"], 3)
        self.assertEqual(summary["removed"], 2)
        self.assertAlmostEqual(summary["kept_ratio"], 0.6)

    def test_unknown_column_ignored(self):
        out = self.flt.apply([FilterRule("missing", min_value=0)])
        self.assertEqual(len(out), 5)

    def test_rule_from_dict(self):
        rule = FilterRule.from_dict({"column": "rms", "min": "-15", "max": None})
        self.assertEqual(rule.column, "rms")
        self.assertEqual(rule.min_value, -15.0)
        self.assertIsNone(rule.max_value)


if __name__ == "__main__":
    unittest.main()
