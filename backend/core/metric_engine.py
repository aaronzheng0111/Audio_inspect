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

import numpy as np
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
    # Serial by default: several audio decoders (notably the MP3 path via
    # librosa/audioread/soundfile) are NOT thread-safe and crash the whole
    # process with a native SIGBUS when decoding concurrently. Serial decoding
    # is also fast in practice (~0.02s/row), so correctness wins over a small
    # speed-up. Callers can still opt into parallelism via ``max_workers`` for
    # datasets known to use thread-safe codecs (e.g. WAV).
    return 1


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
        if not metric_keys:
            return TimeEstimate(n_rows=n_rows, metric_keys=[], seconds=0.0)
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
        batch_size: Optional[int] = None,
        on_batch: Optional[Callable[[pd.DataFrame, int, int], None]] = None,
        resume: bool = False,
        row_limit: Optional[int] = None,
        row_strategy: str = "first",
        row_seed: int = 0,
        subset_mask: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """Compute metrics for each row, returning a new DataFrame with columns.

        Rows whose audio cannot be read get NaN for every requested metric so
        the rest of the dataset still processes. ``progress(done, total)`` is
        invoked after each row when provided.

        Audio is decoded serially by default because several decoders (the MP3
        path in particular) are not thread-safe; pass ``max_workers > 1`` only
        for datasets known to use thread-safe codecs.

        Large datasets can be processed incrementally:

        * ``batch_size`` — process rows in chunks of this many; after each chunk
          ``on_batch(result, done, total)`` is invoked so callers can persist
          partial progress (e.g. write the CSV back to disk).
        * ``resume`` — when True, rows that already have a value for *every*
          requested metric are skipped, so an interrupted run can continue where
          it left off instead of recomputing everything.
        * ``row_limit`` — cap how many pending rows to process this run (``None``
          = all pending rows). Useful on large datasets to avoid long runs/OOM.
        * ``row_strategy`` — ``"first"`` or ``"random"`` when applying
          ``row_limit``.
        * ``subset_mask`` — when set, only rows where this boolean Series is
          True are eligible for computation (aligned to ``dataframe.index``).
        """
        if audio_path_column not in dataframe.columns:
            raise ValueError(
                f"audio path column {audio_path_column!r} not found in dataset."
            )
        metrics = registry.select(metric_keys)
        # Mutate in place — avoid copying a 100k-row DataFrame (saves ~500 MB+).
        result = dataframe
        total = len(result)
        if not metrics:
            return result
        if total == 0:
            for m in metrics:
                if m.key not in result.columns:
                    result[m.key] = pd.Series(dtype=float)
            return result

        # Ensure every requested metric has a numeric column we can fill in
        # place. Existing columns are coerced to float so partial results from a
        # prior run are preserved (and resumable).
        for m in metrics:
            if m.key not in result.columns:
                result[m.key] = np.nan
            else:
                result[m.key] = pd.to_numeric(result[m.key], errors="coerce")

        metric_cols = [m.key for m in metrics]
        col_loc = {key: result.columns.get_loc(key) for key in metric_cols}
        audio_paths = result[audio_path_column].tolist()

        # Decide which row positions still need computing.
        if resume:
            needs = result[metric_cols].isna().any(axis=1).to_numpy()
            positions = [i for i, flag in enumerate(needs) if flag]
        else:
            positions = list(range(total))

        if subset_mask is not None:
            mask_values = subset_mask.reindex(result.index, fill_value=False).to_numpy()
            positions = [i for i in positions if mask_values[i]]

        done = total - len(positions)  # already-complete rows count as progress
        if progress is not None and done:
            progress(done, total)
        if not positions:
            return result

        if row_limit is not None and row_limit > 0 and len(positions) > row_limit:
            if row_strategy == "random":
                rng = np.random.default_rng(row_seed)
                pick = rng.choice(len(positions), size=row_limit, replace=False)
                positions = sorted(positions[i] for i in pick)
            else:
                positions = positions[:row_limit]

        workers = max_workers if max_workers is not None else _default_max_workers()
        workers = max(1, min(workers, len(positions)))
        bs = batch_size if batch_size and batch_size > 0 else len(positions)

        def _store(pos: int, values: Dict[str, float]) -> None:
            for key in metric_cols:
                result.iat[pos, col_loc[key]] = values[key]

        thread_local = threading.local()

        def _loader_for_thread() -> AudioLoader:
            loader = getattr(thread_local, "loader", None)
            if loader is None:
                loader = AudioLoader(
                    target_sr=self.audio_loader.target_sr,
                    cache_size=1,
                )
                thread_local.loader = loader
            return loader

        def _task(pos: int) -> Tuple[int, Dict[str, float]]:
            return pos, _compute_row(
                audio_paths[pos], metrics, base_dir, _loader_for_thread()
            )

        for start in range(0, len(positions), bs):
            chunk = positions[start : start + bs]
            if workers == 1:
                loader = self.audio_loader
                for pos in chunk:
                    _store(pos, _compute_row(audio_paths[pos], metrics, base_dir, loader))
                    done += 1
                    if progress is not None:
                        progress(done, total)
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for pos, values in pool.map(_task, chunk):
                        _store(pos, values)
                        done += 1
                        if progress is not None:
                            progress(done, total)
            if on_batch is not None:
                on_batch(result, done, total)

        return result
