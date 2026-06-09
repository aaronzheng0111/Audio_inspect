"""Generate a PDF comparison report (before vs after filtering).

:class:`ReportGenerator` renders distribution comparison charts with matplotlib
and assembles them, along with a summary table, into a single PDF using
reportlab (Task 5: "generate a pdf report with the comparison").
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")  # headless backend for server-side rendering
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ReportGenerator:
    """Build a PDF that compares the dataset before and after filtering."""

    def __init__(self, before: pd.DataFrame, after: pd.DataFrame) -> None:
        self.before = before
        self.after = after
        self.styles = getSampleStyleSheet()

    def generate(self, output_path: str, columns: Optional[List[str]] = None) -> str:
        """Write the PDF to ``output_path`` and return that path."""
        cols = columns or self._default_columns()
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            title="Audio Inspect Report",
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        story = []
        story.append(Paragraph("Audio Inspect — Filtering Report", self.styles["Title"]))
        story.append(
            Paragraph(
                datetime.now().strftime("Generated %Y-%m-%d %H:%M:%S"),
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.6 * cm))
        story.append(self._overview_table())
        story.append(Spacer(1, 0.6 * cm))

        story.append(Paragraph("Per-metric distribution (before vs after)", self.styles["Heading2"]))
        for col in cols:
            chart = self._distribution_chart(col)
            if chart is not None:
                story.append(Image(chart, width=16 * cm, height=6 * cm))
                story.append(Spacer(1, 0.3 * cm))

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("Summary statistics (after filtering)", self.styles["Heading2"]))
        story.append(self._stats_table(cols))

        doc.build(story)
        return output_path

    # -- pieces ----------------------------------------------------------
    def _default_columns(self) -> List[str]:
        return [
            c
            for c in self.after.columns
            if pd.api.types.is_numeric_dtype(self.after[c])
        ][:8]

    def _overview_table(self) -> Table:
        before_n = len(self.before)
        after_n = len(self.after)
        removed = before_n - after_n
        ratio = f"{(after_n / before_n * 100):.1f}%" if before_n else "n/a"
        data = [
            ["Metric", "Value"],
            ["Rows before filtering", str(before_n)],
            ["Rows after filtering", str(after_n)],
            ["Rows removed", str(removed)],
            ["Kept ratio", ratio],
        ]
        table = Table(data, colWidths=[8 * cm, 6 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                ]
            )
        )
        return table

    def _distribution_chart(self, column: str) -> Optional[io.BytesIO]:
        if column not in self.after.columns:
            return None
        before = pd.to_numeric(self.before.get(column), errors="coerce")
        after = pd.to_numeric(self.after.get(column), errors="coerce")
        before = before.replace([np.inf, -np.inf], np.nan).dropna() if before is not None else pd.Series(dtype=float)
        after = after.replace([np.inf, -np.inf], np.nan).dropna()
        if before.empty and after.empty:
            return None
        fig, ax = plt.subplots(figsize=(8, 3))
        bins = 30
        if not before.empty:
            ax.hist(before, bins=bins, alpha=0.5, label="before", color="#90a4ae")
        if not after.empty:
            ax.hist(after, bins=bins, alpha=0.7, label="after", color="#1976d2")
        ax.set_title(column)
        ax.legend()
        ax.grid(True, alpha=0.2)
        buffer = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format="png", dpi=120)
        plt.close(fig)
        buffer.seek(0)
        return buffer

    def _stats_table(self, columns: List[str]) -> Table:
        header = ["Column", "Count", "Mean", "Std", "Min", "Median", "Max"]
        data = [header]
        for col in columns:
            series = pd.to_numeric(self.after.get(col), errors="coerce")
            valid = series.replace([np.inf, -np.inf], np.nan).dropna() if series is not None else pd.Series(dtype=float)
            if valid.empty:
                data.append([col, "0", "-", "-", "-", "-", "-"])
                continue
            data.append(
                [
                    col,
                    str(int(valid.size)),
                    f"{valid.mean():.3g}",
                    f"{valid.std():.3g}",
                    f"{valid.min():.3g}",
                    f"{valid.median():.3g}",
                    f"{valid.max():.3g}",
                ]
            )
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                ]
            )
        )
        return table
