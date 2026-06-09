"""Shared helpers for the backend test-suite.

Provides synthetic waveform generators and a builder that writes a small set of
WAV files plus a CSV describing them, so engine/API tests can exercise the real
audio-reading code path without committing binary fixtures to the repo.
"""
from __future__ import annotations

import csv
import os
import tempfile
import unittest
from typing import List, Tuple

import numpy as np


def sine_wave(freq: float = 440.0, seconds: float = 1.0, sr: int = 16000,
              amplitude: float = 0.5) -> Tuple[np.ndarray, int]:
    """Return a mono sine wave and its sample rate."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64), sr


def white_noise(seconds: float = 1.0, sr: int = 16000, amplitude: float = 0.3,
                seed: int = 0) -> Tuple[np.ndarray, int]:
    """Return mono white noise and its sample rate."""
    rng = np.random.default_rng(seed)
    return (amplitude * rng.standard_normal(int(sr * seconds))).astype(np.float64), sr


def require_soundfile():
    """Return the soundfile module or skip the calling test if unavailable."""
    try:
        import soundfile as sf  # noqa: WPS433

        return sf
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest(f"soundfile not available: {exc}")


def build_dataset(n: int = 6, sr: int = 16000) -> Tuple[str, str, List[str]]:
    """Create ``n`` WAV files + a CSV in a temp dir.

    Returns ``(temp_dir, csv_path, wav_paths)``. The CSV uses non-standard
    column names (``file`` / ``transcript`` / ``utt``) so the AttributeMapper is
    exercised. The caller is responsible for cleaning up ``temp_dir``.
    """
    sf = require_soundfile()
    temp_dir = tempfile.mkdtemp(prefix="audio_inspect_test_")
    wav_paths: List[str] = []
    rows = []
    for i in range(n):
        # Alternate sine / noise so metrics produce a spread of values.
        if i % 2 == 0:
            wave, _ = sine_wave(freq=220.0 * (i + 1), seconds=1.0, sr=sr)
        else:
            wave, _ = white_noise(seconds=1.0, sr=sr, seed=i)
        path = os.path.join(temp_dir, f"clip_{i}.wav")
        sf.write(path, wave, sr)
        wav_paths.append(path)
        rows.append({"utt": f"id_{i}", "transcript": f"text {i}", "file": path})

    csv_path = os.path.join(temp_dir, "dataset.csv")
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["utt", "transcript", "file"])
        writer.writeheader()
        writer.writerows(rows)
    return temp_dir, csv_path, wav_paths
