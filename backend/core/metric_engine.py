"""Orchestrate metric computation over a dataset and estimate runtime.

:class:`MetricEngine` ties together the :class:`AudioLoader` and the metric
:data:`registry`. It can (a) predict how long a computation will take so the UI
can warn the user (Task 4), and (b) actually compute the selected metrics for
every row, writing one new column per metric into the DataFrame.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .audio_loader import AudioLoader, AudioLoadError
from .metrics import registry


@dataclass
class TimeEstimate:
    """Result of :meth:`MetricEngine.predict_time`."""

    n_rows: int
    metric_keys: List[str]
    seconds: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_rows": self.n_rows,
            "metric_keys": self.metric_keys,
            "estimated_seconds": round(self.seconds, 2),
            "estimated_human": _humanize(self.seconds),
        }


def _humanize(seconds: float) -> str:
    if seconds < 1:
        return "< 1 second"
    if seconds < 60:
        return f"~{round(seconds)} seconds"
    minutes = seconds / 60.0
    if minutes < 60:
        return f"~{minutes:.1f} minutes"
    return f"~{minutes / 60.0:.1f} hours"


class MetricEngine:
    """Compute acoustic metrics for a dataset of audio files."""

    #: Rough seconds of overhead per file (decode + I/O), tuned empirically.
    PER_FILE_OVERHEAD = 0.03
    #: Seconds of compute per relative cost unit per second of audio.
    COST_PER_AUDIO_SECOND = 0.004
    #: Assumed average clip length (s) used when audio durations are unknown.
    ASSUMED_CLIP_SECONDS = 6.0

    def __init__(self, audio_loader: Optional[AudioLoader] = None) -> None:
        self.audio_loader = audio_loader or AudioLoader()

    # -- estimation ------------------------------------------------------
    def predict_time(self, n_rows: int, metric_keys: List[str]) -> TimeEstimate:
        """Estimate wall-clock seconds to compute ``metric_keys`` for n rows."""
        metrics = registry.select(metric_keys)
        total_cost = sum(m.cost for m in metrics)
        per_file = (
            self.PER_FILE_OVERHEAD
            + total_cost * self.COST_PER_AUDIO_SECOND * self.ASSUMED_CLIP_SECONDS
        )
        return TimeEstimate(
            n_rows=n_rows,
            metric_keys=list(metric_keys),
            seconds=per_file * max(n_rows, 0),
        )

    # -- computation -----------------------------------------------------
    def compute(
        self,
        dataframe: pd.DataFrame,
        metric_keys: List[str],
        audio_path_column: str = "audio_path",
        base_dir: Optional[str] = None,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> pd.DataFrame:
        """Compute metrics for each row, returning a new DataFrame with columns.

        Rows whose audio cannot be read get NaN for every requested metric so
        the rest of the dataset still processes. ``progress(done, total)`` is
        invoked after each row when provided.
        """
        if audio_path_column not in dataframe.columns:
            raise ValueError(
                f"audio path column {audio_path_column!r} not found in dataset."
            )
        metrics = registry.select(metric_keys)
        result = dataframe.copy()
        columns: Dict[str, List[float]] = {m.key: [] for m in metrics}

        total = len(result)
        for done, (_, row) in enumerate(result.iterrows(), start=1):
            audio_path = row[audio_path_column]
            try:
                waveform, sr = self.audio_loader.load(audio_path, base_dir=base_dir)
            except (AudioLoadError, Exception):
                waveform, sr = None, 0
            for metric in metrics:
                if waveform is None:
                    columns[metric.key].append(float("nan"))
                else:
                    columns[metric.key].append(metric.safe_compute(waveform, sr))
            if progress is not None:
                progress(done, total)

        for key, values in columns.items():
            result[key] = values
        return result
