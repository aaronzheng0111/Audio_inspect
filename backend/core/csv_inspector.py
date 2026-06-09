"""CSV ingestion and inspection.

:class:`CsvInspector` is responsible for turning a local CSV path into a clean
:class:`pandas.DataFrame`, inferring per-column types, and producing a small row
sample for the preview step (Task 1+2). It deliberately knows nothing about
audio or metrics -- that separation keeps each module focused.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

#: Canonical columns the rest of the pipeline expects to find (after mapping).
REQUIRED_CANONICAL_COLUMNS = ["audio_name_id", "text", "audio_path"]

DEFAULT_SAMPLE_ROWS = 15


@dataclass
class ColumnInfo:
    """Lightweight description of a single CSV column."""

    name: str
    dtype: str  # one of: numeric, text, boolean, datetime, unknown
    non_null: int
    null: int
    unique: int
    example: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "non_null": self.non_null,
            "null": self.null,
            "unique": self.unique,
            "example": self.example,
        }


class CsvInspector:
    """Parse a CSV file and describe its structure."""

    def __init__(self, csv_path: str, sample_rows: int = DEFAULT_SAMPLE_ROWS) -> None:
        self.csv_path = os.path.expanduser(csv_path.strip())
        self.sample_rows = sample_rows
        self._dataframe: pd.DataFrame | None = None

    # -- loading ---------------------------------------------------------
    def load(self) -> pd.DataFrame:
        """Read the CSV into a DataFrame, raising clear errors on failure."""
        if not self.csv_path:
            raise ValueError("CSV path must not be empty.")
        if not os.path.isfile(self.csv_path):
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        try:
            df = pd.read_csv(self.csv_path)
        except Exception as exc:  # pragma: no cover - surfaced to the user
            raise ValueError(f"Failed to parse CSV: {exc}") from exc
        if df.empty:
            raise ValueError("CSV file contains no rows.")
        df.columns = [str(c).strip() for c in df.columns]
        self._dataframe = df
        return df

    @property
    def dataframe(self) -> pd.DataFrame:
        if self._dataframe is None:
            return self.load()
        return self._dataframe

    # -- inspection ------------------------------------------------------
    @staticmethod
    def _classify(series: pd.Series) -> str:
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        # Attempt a soft numeric coercion to catch numeric-looking text columns.
        coerced = pd.to_numeric(series, errors="coerce")
        if coerced.notna().mean() > 0.9:
            return "numeric"
        return "text"

    def describe_columns(self) -> List[ColumnInfo]:
        """Return :class:`ColumnInfo` for every column in the dataframe."""
        df = self.dataframe
        infos: List[ColumnInfo] = []
        for name in df.columns:
            series = df[name]
            example = None
            non_null_series = series.dropna()
            if not non_null_series.empty:
                example = self._json_safe(non_null_series.iloc[0])
            infos.append(
                ColumnInfo(
                    name=name,
                    dtype=self._classify(series),
                    non_null=int(series.notna().sum()),
                    null=int(series.isna().sum()),
                    unique=int(series.nunique(dropna=True)),
                    example=example,
                )
            )
        return infos

    def sample(self) -> List[Dict[str, Any]]:
        """Return up to ``sample_rows`` JSON-safe rows for the preview table."""
        df = self.dataframe.head(self.sample_rows)
        records = df.to_dict(orient="records")
        return [
            {k: self._json_safe(v) for k, v in record.items()} for record in records
        ]

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Convert numpy/pandas scalars and NaNs into JSON-serialisable values."""
        if value is None:
            return None
        if isinstance(value, (np.floating, float)):
            return None if np.isnan(value) else float(value)
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        if pd.isna(value):
            return None
        return str(value) if not isinstance(value, (int, str, bool)) else value
