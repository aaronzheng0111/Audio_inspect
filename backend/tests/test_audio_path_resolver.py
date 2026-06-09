"""Tests for core.audio_path_resolver."""
import os
import shutil
import tempfile
import unittest

from core.audio_path_resolver import candidate_roots, resolve_audio_file, resolve_audio_root


class AudioPathResolverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="audio_root_test_")
        self.dataset_root = os.path.join(self.tmp, "German Audio Dataset")
        self.csv_dir = os.path.join(self.dataset_root, "CSV")
        self.audio_dir = os.path.join(self.dataset_root, "kaggle", "archive", "book")
        os.makedirs(self.csv_dir)
        os.makedirs(self.audio_dir)
        self.wav = os.path.join(self.audio_dir, "clip_0000.wav")
        with open(self.wav, "wb") as fh:
            fh.write(b"RIFF")  # placeholder bytes; existence check only
        self.csv_path = os.path.join(self.csv_dir, "kaggle-archive.csv")
        self.rel_path = "kaggle/archive/book/clip_0000.wav"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_candidate_roots_includes_csv_parent_and_dataset_root(self):
        roots = candidate_roots(self.csv_path)
        self.assertIn(self.csv_dir, roots)
        self.assertIn(self.dataset_root, roots)

    def test_resolve_audio_root_picks_dataset_root_not_csv_dir(self):
        root, found, checked = resolve_audio_root(self.csv_path, [self.rel_path])
        self.assertEqual(os.path.realpath(root), os.path.realpath(self.dataset_root))
        self.assertEqual(found, 1)
        self.assertEqual(checked, 1)

    def test_resolve_audio_file_relative(self):
        resolved = resolve_audio_file(self.rel_path, self.csv_path, self.dataset_root)
        self.assertEqual(os.path.realpath(resolved), os.path.realpath(self.wav))


if __name__ == "__main__":
    unittest.main()
