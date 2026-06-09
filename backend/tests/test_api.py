"""End-to-end API tests exercising the full 5-step wizard flow.

Uses DRF's APIClient against the real views and core logic. No database is
touched (state lives in the in-memory SessionStore), so SimpleTestCase is used.
"""
import os
import shutil

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from tests.utils import build_dataset


class ApiFlowTest(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.dir, self.csv_path, self.wavs = build_dataset(n=6)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_list_metrics(self):
        res = self.client.get("/api/metrics")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["metrics"]), 8)

    def test_full_flow(self):
        # 1+2: load
        res = self.client.post(
            "/api/dataset/load", {"csv_path": self.csv_path}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        session_id = body["session_id"]
        self.assertEqual(body["n_rows"], 6)
        self.assertLessEqual(len(body["sample"]), 15)
        # the non-standard names should be auto-suggested
        self.assertEqual(body["suggested_mapping"]["audio_path"], "file")

        # 3: map attributes
        res = self.client.post(
            "/api/dataset/map",
            {
                "session_id": session_id,
                "mapping": {
                    "audio_path": "file",
                    "text": "transcript",
                    "audio_name_id": "utt",
                },
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn("audio_path", res.json()["columns"])

        # 4: estimate
        metrics = ["rms", "zcr", "spectral_flatness"]
        res = self.client.post(
            "/api/metrics/estimate",
            {"session_id": session_id, "metrics": metrics},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["n_rows"], 6)

        # 3+4: compute
        res = self.client.post(
            "/api/metrics/compute",
            {"session_id": session_id, "metrics": metrics},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        compute = res.json()
        self.assertEqual(set(compute["computed_metrics"]), set(metrics))
        self.assertEqual(compute["valid_counts"]["rms"], 6)

        # 5: summary
        res = self.client.get(
            "/api/analysis/summary", {"session_id": session_id}
        )
        self.assertEqual(res.status_code, 200, res.content)
        summary_cols = {r["column"] for r in res.json()["summary"]}
        self.assertTrue({"rms", "zcr"}.issubset(summary_cols))

        # 5: plot-data
        res = self.client.get(
            "/api/analysis/plot-data",
            {"session_id": session_id, "columns": "rms,zcr", "limit": 5},
        )
        self.assertEqual(res.status_code, 200, res.content)
        plot = res.json()
        self.assertEqual(plot["total_rows"], 6)
        self.assertLessEqual(plot["returned_rows"], 5)
        self.assertEqual(len(plot["row_indices"]), plot["returned_rows"])
        self.assertEqual(len(plot["rows"]), plot["returned_rows"])
        self.assertIn("text", plot["metadata_columns"])

        # audio stream for first plotted row
        row_index = plot["row_indices"][0]
        res = self.client.get(
            "/api/audio/stream",
            {"session_id": session_id, "row_index": row_index},
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res["Content-Type"].startswith("audio/"))

        # 5: filter
        res = self.client.post(
            "/api/analysis/filter",
            {
                "session_id": session_id,
                "rules": [{"column": "rms", "min": -200, "max": 0}],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["before"], 6)

        # 5: export CSV
        res = self.client.post(
            "/api/export/csv",
            {"session_id": session_id, "rules": []},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(os.path.isfile(res.json()["path"]))

        # 5: export PDF report
        res = self.client.post(
            "/api/export/report",
            {"session_id": session_id, "rules": []},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(os.path.isfile(res.json()["path"]))

    def test_load_missing_file_returns_400(self):
        res = self.client.post(
            "/api/dataset/load", {"csv_path": "/no/file.csv"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_unknown_session_returns_404(self):
        res = self.client.get(
            "/api/analysis/summary", {"session_id": "deadbeef"}
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "audio_visual_web.settings")
    django.setup()
