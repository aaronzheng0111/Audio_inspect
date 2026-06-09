"""Load audio waveforms from local paths, with light caching.

:class:`AudioLoader` centralises file reading so the metric engine never touches
the filesystem directly. It returns mono float32 waveforms and remembers the
most recently loaded clips to avoid re-decoding when several metrics run over the
same file.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Optional, Tuple

import numpy as np

try:
    import librosa

    _HAS_LIBROSA = True
except Exception:  # pragma: no cover
    _HAS_LIBROSA = False

try:
    import soundfile as sf

    _HAS_SOUNDFILE = True
except Exception:  # pragma: no cover
    _HAS_SOUNDFILE = False


class AudioLoadError(Exception):
    """Raised when an audio file cannot be read."""


class AudioLoader:
    """Read mono waveforms from disk with a small LRU cache."""

    def __init__(self, target_sr: Optional[int] = None, cache_size: int = 8) -> None:
        #: If set, audio is resampled to this rate on load; otherwise native.
        self.target_sr = target_sr
        self.cache_size = cache_size
        self._cache: "OrderedDict[str, Tuple[np.ndarray, int]]" = OrderedDict()

    def resolve(self, audio_path: str, base_dir: Optional[str] = None) -> str:
        """Resolve a possibly-relative audio path against ``base_dir``."""
        path = os.path.expanduser(str(audio_path).strip())
        if not os.path.isabs(path) and base_dir:
            path = os.path.join(base_dir, path)
        return path

    def load(self, audio_path: str, base_dir: Optional[str] = None) -> Tuple[np.ndarray, int]:
        """Return ``(waveform, sample_rate)`` as mono float64.

        Raises :class:`AudioLoadError` if the file is missing or unreadable.
        """
        path = self.resolve(audio_path, base_dir)
        if path in self._cache:
            self._cache.move_to_end(path)
            return self._cache[path]
        if not os.path.isfile(path):
            raise AudioLoadError(f"Audio file not found: {path}")
        waveform, sr = self._read(path)
        waveform = np.asarray(waveform, dtype=np.float64)
        self._cache[path] = (waveform, sr)
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return waveform, sr

    def _read(self, path: str) -> Tuple[np.ndarray, int]:
        if _HAS_LIBROSA:
            waveform, sr = librosa.load(path, sr=self.target_sr, mono=True)
            return waveform, int(sr)
        if _HAS_SOUNDFILE:
            waveform, sr = sf.read(path, always_2d=False)
            if waveform.ndim > 1:
                waveform = np.mean(waveform, axis=1)
            return waveform, int(sr)
        raise AudioLoadError(
            "No audio backend available (install librosa or soundfile)."
        )

    def clear_cache(self) -> None:
        self._cache.clear()
