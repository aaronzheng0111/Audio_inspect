"""Serve session audio files for in-browser playback.

:class:`SessionAudioStreamer` resolves a dataset row to its on-disk audio file
using the same path logic as metric computation.
"""
from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

from .audio_path_resolver import resolve_audio_file
from .session_store import Session


class SessionAudioError(Exception):
    """Raised when a row's audio cannot be resolved or opened."""


@dataclass
class AudioFile:
    """An opened audio file ready to stream to the client."""

    path: str
    content_type: str
    handle: BinaryIO

    def close(self) -> None:
        self.handle.close()


class SessionAudioStreamer:
    """Resolve and open one row's audio from a working session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    _MIME_BY_EXT = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
    }

    def open_row(self, row_pos: int) -> AudioFile:
        """Return an :class:`AudioFile` for ``row_pos`` (0-based iloc index)."""
        path = self.resolve_row_path(row_pos)
        content_type = self.content_type_for(path)
        return AudioFile(path=path, content_type=content_type, handle=open(path, "rb"))

    def content_type_for(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in self._MIME_BY_EXT:
            return self._MIME_BY_EXT[ext]
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

    def resolve_row_path(self, row_pos: int) -> str:
        if row_pos < 0 or row_pos >= len(self.session.dataframe):
            raise SessionAudioError("row_index out of range.")
        audio_col = self.session.canonical_to_column("audio_path") or "audio_path"
        if audio_col not in self.session.dataframe.columns:
            raise SessionAudioError("No 'audio_path' column mapped; cannot read audio files.")
        audio_path = self.session.dataframe.iloc[row_pos][audio_col]
        if audio_path is None or (isinstance(audio_path, float) and pd.isna(audio_path)):
            raise SessionAudioError("No audio path for this row.")
        base_dir = self.session.audio_root or os.path.dirname(self.session.csv_path)
        resolved = resolve_audio_file(audio_path, self.session.csv_path, base_dir)
        if not os.path.isfile(resolved):
            raise SessionAudioError(f"Audio file not found: {resolved}")
        return resolved
