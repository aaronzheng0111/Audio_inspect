"""Orchestrate metric computation over a dataset and estimate runtime.

:class:`MetricEngine` ties together the :class:`AudioLoader` and the metric
:data:`registry`. It can (a) predict how long a computation will take so the UI
can warn the user (Task 4), and (b) actually compute the selected metrics for
every row, writing one new column per metric into the DataFrame.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from .audio_loader import AudioLoader, AudioLoadError
from .metrics import registry
from .metrics.base import BaseMetric


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


def _default_max_workers() -> int:
    return min(32, (os.cpu_count() or 1) + 4)


def _compute_row(
    audio_path: str,
    metrics: List[BaseMetric],
    base_dir: Optional[str],
    loader: AudioLoader,
) -> Dict[str, float]:
    """Load one clip and compute all requested metrics for a single row."""
    try:
        waveform, sr = loader.load(audio_path, base_dir=base_dir)
    except (AudioLoadError, Exception):
        waveform, sr = None, 0
    values: Dict[str, float] = {}
    for metric in metrics:
        if waveform is None:
            values[metric.key] = float("nan")
        else:
            values[metric.key] = metric.safe_compute(waveform, sr)
    return values


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
        max_workers: Optional[int] = None,
    ) -> pd.DataFrame:
        """Compute metrics for each row, returning a new DataFrame with columns.

        Rows whose audio cannot be read get NaN for every requested metric so
        the rest of the dataset still processes. ``progress(done, total)`` is
        invoked after each row when provided.

        Rows are processed in parallel via a thread pool (I/O-bound audio
        decode benefits most). Each worker uses its own :class:`AudioLoader` so
        the LRU cache stays thread-safe.
        """
        if audio_path_column not in dataframe.columns:
            raise ValueError(
                f"audio path column {audio_path_column!r} not found in dataset."
            )
        metrics = registry.select(metric_keys)
        result = dataframe.copy()
        total = len(result)
        if total == 0:
            for m in metrics:
                result[m.key] = pd.Series(dtype=float)
            return result

        workers = max_workers if max_workers is not None else _default_max_workers()
        workers = max(1, min(workers, total))

        indices = list(result.index)
        audio_paths = result[audio_path_column].tolist()
        row_values: Dict[object, Dict[str, float]] = {}

        thread_local = threading.local()

        def _loader_for_thread() -> AudioLoader:
            loader = getattr(thread_local, "loader", None)
            if loader is None:
                loader = AudioLoader(
                    target_sr=self.audio_loader.target_sr,
                    cache_size=self.audio_loader.cache_size,
                )
                thread_local.loader = loader
            return loader

        def _task(pos: int) -> Tuple[int, Dict[str, float]]:
            values = _compute_row(
                audio_paths[pos],
                metrics,
                base_dir,
                _loader_for_thread(),
            )
            return pos, values

        if workers == 1:
            for pos in range(total):
                _, values = _task(pos)
                row_values[indices[pos]] = values
                if progress is not None:
                    progress(pos + 1, total)
        else:
            # map() batches submissions (chunksize) so large datasets do not
            # queue one Future per row in memory at once.
            chunksize = max(1, total // (workers * 4))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for pos, values in pool.map(_task, range(total), chunksize=chunksize):
                    row_values[indices[pos]] = values
                    if progress is not None:
                        progress(pos + 1, total)

        for m in metrics:
            result[m.key] = [row_values[idx][m.key] for idx in indices]
        return result
