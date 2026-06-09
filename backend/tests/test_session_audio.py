"""Tests for core.session_audio.SessionAudioStreamer."""
import os
import shutil
import unittest

from django.test import SimpleTestCase

from core.session_audio import SessionAudioError, SessionAudioStreamer
from core.session_store import Session
from tests.utils import build_dataset


class SessionAudioStreamerTest(SimpleTestCase):
    def setUp(self):
        self.dir, self.csv_path, self.wavs = build_dataset(n=3)
        import pandas as pd

        df = pd.read_csv(self.csv_path).rename(
            columns={"file": "audio_path", "transcript": "text", "utt": "audio_name_id"}
        )
        self.session = Session(session_id="test", csv_path=self.csv_path, dataframe=df)
        self.session.audio_root = self.dir

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_resolve_row_path(self):
        streamer = SessionAudioStreamer(self.session)
        self.assertTrue(os.path.isfile(streamer.resolve_row_path(0)))

    def test_open_row_returns_readable_file(self):
        audio = SessionAudioStreamer(self.session).open_row(0)
        self.assertTrue(audio.content_type.startswith("audio/"))
        self.assertTrue(audio.handle.read(4))
        audio.close()

    def test_invalid_row_raises(self):
        with self.assertRaises(SessionAudioError):
            SessionAudioStreamer(self.session).resolve_row_path(99)
