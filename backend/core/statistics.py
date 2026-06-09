"""Build full-dataset statistical summaries.

:class:`StatisticsBuilder` produces compact per-column aggregates over the
*entire* dataset (Task 5 asks for a summary table computed on all rows, since it
is only aggregate numbers and not heavy to render). It also provides sampled
plot data for the charts so the front-end never has to render hundreds of
thousands of points.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class PlotDataResult:
    """Sampled metric values plus per-point metadata for chart interaction."""

    metric_data: Dict[str, List[Any]] = field(default_factory=dict)
    row_indices: List[int] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    metadata_columns: List[str] = field(default_factory=list)
    total_rows: int = 0

    @property
    def returned_rows(self) -> int:
        if not self.metric_data:
            return 0
        return len(next(iter(self.metric_data.values())))

    def to_payload(self) -> Dict[str, Any]:
        """Serialise to the dict shape expected by plot_data()."""
        payload = dict(self.metric_data)
        payload["row_indices"] = self.row_indices
        payload["rows"] = self.rows
        payload["metadata_columns"] = self.metadata_columns
        payload["__count__"] = [self.total_rows]
        return payload


class StatisticsBuilder:
    """Summaries and plot-ready samples for a metrics-augmented DataFrame."""

    #: Metadata columns shown first in scatter-plot detail panels.
    _TEXT_COLUMNS = frozenset(
        {"text", "transcription", "transcript", "sentence", "label", "content"}
    )
    _NAME_COLUMNS = frozenset({"audio_name_id", "audio_name", "id", "name", "filename"})
    _PATH_COLUMNS = frozenset({"audio_path", "path", "sample_path", "original_path", "wav", "file"})

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe

    # -- numeric summary -------------------------------------------------
    def numeric_columns(self) -> List[str]:
        return [
            c
            for c in self.dataframe.columns
            if pd.api.types.is_numeric_dtype(self.dataframe[c])
        ]

    def summary(self, columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return per-column aggregate statistics over the full dataset."""
        cols = columns or self.numeric_columns()
        rows: List[Dict[str, Any]] = []
        for col in cols:
            series = pd.to_numeric(self.dataframe[col], errors="coerce")
            valid = series.replace([np.inf, -np.inf], np.nan).dropna()
            if valid.empty:
                rows.append(self._empty_row(col))
                continue
            rows.append(
                {
                    "column": col,
                    "count": int(valid.size),
                    "missing": int(series.isna().sum()),
                    "mean": self._round(valid.mean()),
                    "std": self._round(valid.std()),
                    "min": self._round(valid.min()),
                    "p25": self._round(valid.quantile(0.25)),
                    "median": self._round(valid.median()),
                    "p75": self._round(valid.quantile(0.75)),
                    "max": self._round(valid.max()),
                }
            )
        return rows

    # -- plot data -------------------------------------------------------
    def plot_data(
        self,
        columns: List[str],
        limit: int = 200,
        strategy: str = "first",
        seed: int = 0,
    ) -> PlotDataResult:
        """Return a down-sampled plot payload for charting.

        ``strategy`` is ``"first"`` (first N rows) or ``"random"`` (random N).
        """
        present = [c for c in columns if c in self.dataframe.columns]
        sample = self._sample_rows(present, limit, strategy, seed)
        meta_cols = self._ordered_metadata_columns(
            [c for c in self.dataframe.columns if c not in present]
        )
        return PlotDataResult(
            metric_data=self._serialize_metric_columns(sample, present),
            row_indices=self._row_positions(sample),
            rows=[self._serialize_metadata_row(label, meta_cols) for label in sample.index],
            metadata_columns=meta_cols,
            total_rows=len(self.dataframe[present]) if present else 0,
        )

    def _sample_rows(
        self,
        columns: List[str],
        limit: int,
        strategy: str,
        seed: int,
    ) -> pd.DataFrame:
        df = self.dataframe[columns] if columns else self.dataframe.iloc[:, :0]
        if limit and len(df) > limit:
            if strategy == "random":
                return df.sample(n=limit, random_state=seed)
            return df.head(limit)
        return df

    def _serialize_metric_columns(
        self, sample: pd.DataFrame, columns: List[str]
    ) -> Dict[str, List[Any]]:
        out: Dict[str, List[Any]] = {}
        for col in columns:
            series = sample[col]
            if pd.api.types.is_numeric_dtype(series):
                out[col] = [self._round(v) for v in series.tolist()]
            else:
                out[col] = [None if pd.isna(v) else str(v) for v in series.tolist()]
        return out

    def _row_positions(self, sample: pd.DataFrame) -> List[int]:
        return [int(self.dataframe.index.get_loc(label)) for label in sample.index]

    def _ordered_metadata_columns(self, columns: List[str]) -> List[str]:
        def priority(col: str) -> tuple:
            if col in self._TEXT_COLUMNS:
                return (0, col)
            if col in self._NAME_COLUMNS:
                return (1, col)
            if col in self._PATH_COLUMNS:
                return (3, col)
            return (2, col)

        return sorted(columns, key=priority)

    def _serialize_metadata_row(self, label: Any, meta_cols: List[str]) -> Dict[str, Any]:
        full_row = self.dataframe.loc[label]
        entry: Dict[str, Any] = {}
        for col in meta_cols:
            val = full_row[col]
            if pd.isna(val):
                entry[col] = None
            elif pd.api.types.is_numeric_dtype(self.dataframe[col]):
                entry[col] = self._round(val)
            else:
                entry[col] = str(val)
        return entry

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _round(value: Any) -> Optional[float]:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)

    @staticmethod
    def _empty_row(col: str) -> Dict[str, Any]:
        return {
            "column": col,
            "count": 0,
            "missing": 0,
            "mean": None,
            "std": None,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
        }
