"""Threshold-based dataset filtering with before/after accounting.

:class:`DatasetFilter` applies a set of numeric min/max rules (one per metric
column) and reports how many rows survive, so the UI can show the user the
effect of their filter rules (Task 5: "use the new filter rules to check the
differences").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class FilterRule:
    """A single inclusive [min, max] range applied to one column."""

    column: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterRule":
        return cls(
            column=data["column"],
            min_value=_to_float(data.get("min")),
            max_value=_to_float(data.get("max")),
        )


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DatasetFilter:
    """Apply :class:`FilterRule` objects to a DataFrame."""

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe

    def _evaluated_mask(self, rules: List[FilterRule]) -> pd.Series:
        """Rows that have a numeric value for every column being filtered."""
        mask = pd.Series(True, index=self.dataframe.index)
        for rule in rules:
            if rule.column not in self.dataframe.columns:
                continue
            series = pd.to_numeric(self.dataframe[rule.column], errors="coerce")
            mask &= series.notna()
        return mask

    def build_mask(self, rules: List[FilterRule]) -> pd.Series:
        """Return a boolean mask of rows that satisfy *all* rules.

        Rows with NaN in a filtered column are excluded by that rule (they
        cannot be confirmed to fall inside the range).
        """
        mask = pd.Series(True, index=self.dataframe.index)
        for rule in rules:
            if rule.column not in self.dataframe.columns:
                continue
            series = pd.to_numeric(self.dataframe[rule.column], errors="coerce")
            rule_mask = series.notna()
            if rule.min_value is not None:
                rule_mask &= series >= rule.min_value
            if rule.max_value is not None:
                rule_mask &= series <= rule.max_value
            mask &= rule_mask
        return mask

    def evaluation_mask(self, rules: List[FilterRule]) -> pd.Series:
        """Rows that have a value for every column covered by *rules*."""
        if not rules:
            return pd.Series(True, index=self.dataframe.index)
        mask = pd.Series(True, index=self.dataframe.index)
        for rule in rules:
            if rule.column not in self.dataframe.columns:
                continue
            series = pd.to_numeric(self.dataframe[rule.column], errors="coerce")
            mask &= series.notna()
        return mask

    def apply(self, rules: List[FilterRule]) -> pd.DataFrame:
        """Return the filtered DataFrame."""
        return self.dataframe[self.build_mask(rules)]

    def summary(self, rules: List[FilterRule]) -> Dict[str, Any]:
        """Return before/after counts and per-rule drop information.

        ``before`` counts only rows that have values for every filtered column
        (the evaluation population). Rows without computed metrics are reported
        separately as ``unevaluated`` so threshold drops are not confused with
        missing data.
        """
        total = len(self.dataframe)
        evaluated_mask = self.evaluation_mask(rules)
        evaluated = int(evaluated_mask.sum())
        pass_mask = self.build_mask(rules)
        kept = int(pass_mask.sum())
        per_rule = []
        for rule in rules:
            if rule.column not in self.dataframe.columns:
                continue
            series = pd.to_numeric(self.dataframe[rule.column], errors="coerce")
            single = series.notna()
            if rule.min_value is not None:
                single &= series >= rule.min_value
            if rule.max_value is not None:
                single &= series <= rule.max_value
            per_rule.append(
                {
                    "column": rule.column,
                    "min": rule.min_value,
                    "max": rule.max_value,
                    "kept": int(single.sum()),
                    "dropped": int(evaluated - single.sum()),
                }
            )
        return {
            "total_rows": total,
            "before": evaluated,
            "after": kept,
            "removed": evaluated - kept,
            "unevaluated": total - evaluated,
            "kept_ratio": round(kept / evaluated, 4) if evaluated else 0.0,
            "per_rule": per_rule,
        }
