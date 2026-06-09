"""Tests for core.csv_inspector.CsvInspector."""
import csv
import os
import tempfile
import unittest

from core.csv_inspector import CsvInspector


class CsvInspectorTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="csvtest_")
        self.csv_path = os.path.join(self.dir, "data.csv")
        rows = [{"id": i, "score": i * 1.5, "name": f"row{i}"} for i in range(40)]
        with open(self.csv_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["id", "score", "name"])
            writer.writeheader()
            writer.writerows(rows)

    def tearDown(self):
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        os.rmdir(self.dir)

    def test_load_returns_dataframe(self):
        df = CsvInspector(self.csv_path).load()
        self.assertEqual(len(df), 40)
        self.assertEqual(list(df.columns), ["id", "score", "name"])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            CsvInspector("/no/such/file.csv").load()

    def test_empty_path_raises(self):
        with self.assertRaises(ValueError):
            CsvInspector("   ").load()

    def test_sample_is_capped(self):
        inspector = CsvInspector(self.csv_path, sample_rows=15)
        sample = inspector.sample()
        self.assertEqual(len(sample), 15)
        # values must be JSON-safe primitives
        for cell in sample[0].values():
            self.assertIsInstance(cell, (int, float, str, type(None)))

    def test_column_type_inference(self):
        infos = {c.name: c for c in CsvInspector(self.csv_path).describe_columns()}
        self.assertEqual(infos["id"].dtype, "numeric")
        self.assertEqual(infos["score"].dtype, "numeric")
        self.assertEqual(infos["name"].dtype, "text")
        self.assertEqual(infos["id"].non_null, 40)


if __name__ == "__main__":
    unittest.main()
