"""Tests for core.attribute_mapper.AttributeMapper."""
import unittest

import pandas as pd

from core.attribute_mapper import AttributeMapper


class AttributeMapperTest(unittest.TestCase):
    def test_suggest_matches_aliases(self):
        mapper = AttributeMapper(["utt_id", "transcript", "wav"])
        suggestion = mapper.suggest()
        self.assertEqual(suggestion["audio_name_id"], "utt_id")
        self.assertEqual(suggestion["text"], "transcript")
        self.assertEqual(suggestion["audio_path"], "wav")

    def test_validate_requires_audio_path(self):
        mapper = AttributeMapper(["a", "b"])
        with self.assertRaises(ValueError):
            mapper.validate({"text": "a"})

    def test_validate_rejects_unknown_column(self):
        mapper = AttributeMapper(["a", "b"])
        with self.assertRaises(ValueError):
            mapper.validate({"audio_path": "does_not_exist"})

    def test_apply_renames_to_canonical(self):
        df = pd.DataFrame({"wav": ["x.wav"], "transcript": ["hi"], "utt": ["1"]})
        mapper = AttributeMapper(list(df.columns))
        mapping = {"audio_path": "wav", "text": "transcript", "audio_name_id": "utt"}
        out = mapper.apply(df, mapping)
        self.assertIn("audio_path", out.columns)
        self.assertIn("text", out.columns)
        self.assertIn("audio_name_id", out.columns)
        self.assertEqual(out["audio_path"].iloc[0], "x.wav")

    def test_repeat_map_is_idempotent(self):
        """Re-submitting the same mapping after columns were renamed must not fail."""
        df = pd.DataFrame({"path": ["a.wav"], "sentence": ["hello"]})
        mapping = {"audio_path": "path", "text": "sentence"}
        mapper = AttributeMapper(list(df.columns))
        once = mapper.apply(df, mapping)
        self.assertIn("text", once.columns)
        again_mapper = AttributeMapper(list(once.columns))
        twice = again_mapper.apply(once, mapping)
        self.assertIn("text", twice.columns)
        self.assertIn("audio_path", twice.columns)

    def test_suggest_german_cv_columns(self):
        cols = ["audio_name", "path", "sentence", "duration_s"]
        suggestion = AttributeMapper(cols).suggest()
        self.assertEqual(suggestion["audio_name_id"], "audio_name")
        self.assertEqual(suggestion["text"], "sentence")
        self.assertEqual(suggestion["audio_path"], "path")


if __name__ == "__main__":
    unittest.main()
