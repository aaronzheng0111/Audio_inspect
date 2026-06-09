"""Build full-dataset statistical summaries.

:class:`StatisticsBuilder` produces compact per-column aggregates over the
*entire* dataset (Task 5 asks for a summary table computed on all rows, since it
is only aggregate numbers and not heavy to render). It also provides sampled
plot data for the charts so the front-end never has to render hundreds of
thousands of points.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class StatisticsBuilder:
    """Summaries and plot-ready samples for a metrics-augmented DataFrame."""

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
    ) -> Dict[str, List[Any]]:
        """Return a down-sampled column dict for charting.

        ``strategy`` is ``"first"`` (first N rows) or ``"random"`` (random N).
        """
        present = [c for c in columns if c in self.dataframe.columns]
        df = self.dataframe[present] if present else self.dataframe.iloc[:, :0]
        n = len(df)
        if limit and n > limit:
            if strategy == "random":
                df = df.sample(n=limit, random_state=seed)
            else:
                df = df.head(limit)
        out: Dict[str, List[Any]] = {}
        for col in present:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                out[col] = [self._round(v) for v in series.tolist()]
            else:
                out[col] = [None if pd.isna(v) else str(v) for v in series.tolist()]
        out["__count__"] = [n]  # total rows available before sampling
        return out

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
