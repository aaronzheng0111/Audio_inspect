"""Generate the cleaned-CSV report set:

- one **overview** report (MD + PDF + charts) comparing every source side-by-side,
- one **per-source** report (MD + PDF + charts) for each source under
  ``<out-dir>/<source>/``.

Inputs: ``CSV/<source>_<YYYYmmdd-HHMMSS>.csv`` — one per source, picking the
newest by mtime when multiple exist (produced by ``csv-cleaning-pipeline``).

Each report covers four ratio/rate metrics together (kept in one place so the
overview and per-source PDFs stay in sync):

- ``ratio_sec_per_char`` = duration_s / char_len    (audio long, text short)
- ``ratio_sec_per_word`` = duration_s / word_len    (per-word pacing)
- ``chars_per_sec``      = char_len   / duration_s  (speaking rate, char-level)
- ``words_per_sec``      = word_len   / duration_s  (speaking rate, word-level)

Run from workspace root:
    python "Skill/filtered-csv-report/scripts/generate_filtered_csv_report.py" \
        --out-dir "report/filtered-csv-comparison"
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as _xml_escape

import numpy as np
import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_DIR = WORKSPACE_ROOT / "CSV"

LEADING_COLS = ("audio_name", "source", "path", "duration_s")
_TEXT_COL_PREFERENCE = ("transcription", "sentence")
_TIMESTAMP_SUFFIX_RE = re.compile(r"_\d{8}-\d{6}$")

# Pinned categorical palette (per-source color = hash → palette[i % N])
_PALETTE = [
    "#3B82F6", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6",
    "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#6366F1",
]

# Four ratio/rate metrics. Edit here to add or rename a metric — all PDFs,
# Markdown, charts and outlier tables iterate this list automatically.
RATIO_METRICS: List[Dict[str, Any]] = [
    {"name": "ratio_sec_per_char", "attr": "__ratio_sec_per_char",
     "unit": "seconds / char", "log_y": True},
    {"name": "ratio_sec_per_word", "attr": "__ratio_sec_per_word",
     "unit": "seconds / word", "log_y": True},
    {"name": "chars_per_sec",      "attr": "__chars_per_sec",
     "unit": "chars / second",    "log_y": True},
    {"name": "words_per_sec",      "attr": "__words_per_sec",
     "unit": "words / second",    "log_y": True},
]

_MPL_STYLE: Dict[str, Any] = {
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": "#FAFBFF",
    "figure.facecolor": "white",
    "grid.color": "#E5E7EB",
    "axes.edgecolor": "#CBD5E1",
    "xtick.color": "#4B5563",
    "ytick.color": "#4B5563",
    "axes.labelcolor": "#374151",
    "text.color": "#1F2937",
    "font.size": 10,
}


# ── Data model ────────────────────────────────────────────────────────────


@dataclass
class OutlierRule:
    name: str          # human-readable name, e.g. "> p99"
    side: str          # "high" | "low"
    threshold: float   # boundary value
    count: int
    pct: float         # 0..100
    val_min: float     # smallest matched value
    val_max: float     # largest matched value


@dataclass
class OutlierStats:
    metric: str
    n: int
    p1: float
    p99: float
    p999: float
    tukey_low: float
    tukey_high: float
    rules: List[OutlierRule] = field(default_factory=list)


@dataclass
class SourceData:
    name: str
    csv_path: Path
    csv_mtime: datetime.datetime
    df: pd.DataFrame
    text_col: str
    n_rows: int = 0
    n_unique_clips: int = 0
    total_hours: float = 0.0
    mean_duration: float = 0.0
    n_empty_text: int = 0
    # all distribution quantiles in one dict; keys include
    # "duration_s", "char_len", "word_len", and every metric in RATIO_METRICS
    quantiles: Dict[str, Dict[float, float]] = field(default_factory=dict)
    # outlier stats keyed by metric name (RATIO_METRICS[*]["name"])
    outliers: Dict[str, OutlierStats] = field(default_factory=dict)


# ── Loaders & basic stats ─────────────────────────────────────────────────


def _source_name_from_csv(csv_path: Path) -> str:
    return _TIMESTAMP_SUFFIX_RE.sub("", csv_path.stem)


def _latest_csv_per_source(csv_dir: Path) -> Dict[str, Path]:
    latest: Dict[str, Path] = {}
    for p in sorted(csv_dir.glob("*.csv")):
        if p.name.startswith("_"):
            continue
        src = _source_name_from_csv(p)
        prev = latest.get(src)
        if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
            latest[src] = p
    return latest


def _detect_text_col(df: pd.DataFrame, override: Optional[str]) -> str:
    if override and override in df.columns:
        return override
    for c in _TEXT_COL_PREFERENCE:
        if c in df.columns:
            return c
    candidates = [c for c in df.columns if c not in LEADING_COLS]
    if not candidates:
        raise ValueError("no transcript-like column available")
    sample = df.head(1000)
    best, best_len = candidates[0], -1.0
    for c in candidates:
        try:
            mean_len = sample[c].astype(str).str.len().mean() or 0.0
        except Exception:
            continue
        if mean_len > best_len:
            best, best_len = c, mean_len
    return best


def _quantiles(values: np.ndarray, qs: List[float]) -> Dict[float, float]:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return {q: float("nan") for q in qs}
    out = np.quantile(v, qs)
    return {q: float(x) for q, x in zip(qs, out)}


def _color_for(name: str) -> str:
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return _PALETTE[h % len(_PALETTE)]


def _compute_outlier_stats(
    values: np.ndarray,
    *,
    metric: str,
    rules: Optional[List[Tuple[str, str]]] = None,
) -> OutlierStats:
    """Count, threshold and actual value-range for the standard outlier rules.

    ``rules`` is a list of ``(name, kind)`` pairs; default = all five rules.
    Recognised kinds: ``high_p99``, ``high_p999``, ``high_tukey``,
    ``low_p1``, ``low_tukey``.
    """
    if rules is None:
        rules = [
            ("> p99", "high_p99"),
            ("> p99.9", "high_p999"),
            ("> Tukey high", "high_tukey"),
            ("< p1", "low_p1"),
            ("< Tukey low", "low_tukey"),
        ]
    v = values[np.isfinite(values)]
    n = int(v.size)
    if n == 0:
        return OutlierStats(metric=metric, n=0, p1=float("nan"),
                            p99=float("nan"), p999=float("nan"),
                            tukey_low=float("nan"), tukey_high=float("nan"))
    p1, q1, q3, p99, p999 = np.quantile(v, [0.01, 0.25, 0.75, 0.99, 0.999])
    iqr = q3 - q1
    tukey_low = q1 - 1.5 * iqr
    tukey_high = q3 + 1.5 * iqr
    stats = OutlierStats(
        metric=metric, n=n,
        p1=float(p1), p99=float(p99), p999=float(p999),
        tukey_low=float(tukey_low), tukey_high=float(tukey_high),
    )
    kind_map = {
        "high_p99": ("high", float(p99), v > p99),
        "high_p999": ("high", float(p999), v > p999),
        "high_tukey": ("high", float(tukey_high), v > tukey_high),
        "low_p1": ("low", float(p1), v < p1),
        "low_tukey": ("low", float(tukey_low), v < tukey_low),
    }
    for name, kind in rules:
        side, thr, mask = kind_map[kind]
        matched = v[mask]
        c = int(matched.size)
        if c == 0:
            stats.rules.append(OutlierRule(
                name=name, side=side, threshold=thr,
                count=0, pct=0.0, val_min=float("nan"), val_max=float("nan"),
            ))
        else:
            stats.rules.append(OutlierRule(
                name=name, side=side, threshold=thr,
                count=c, pct=100.0 * c / n,
                val_min=float(matched.min()), val_max=float(matched.max()),
            ))
    return stats


def load_sources(
    csv_dir: Path,
    *,
    text_col_override: Optional[str],
    only: Optional[set[str]],
    exclude: Optional[set[str]],
) -> List[SourceData]:
    paths = _latest_csv_per_source(csv_dir)
    if only:
        paths = {k: v for k, v in paths.items() if k in only}
    if exclude:
        paths = {k: v for k, v in paths.items() if k not in exclude}
    if not paths:
        raise SystemExit(
            f"No CSVs found in {csv_dir} after applying --only/--exclude. "
            "Run csv-cleaning-pipeline first."
        )

    sources: List[SourceData] = []
    for name, p in sorted(paths.items()):
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
        for col in ("audio_name", "path"):
            if col not in df.columns:
                raise SystemExit(
                    f"{p.name}: missing required leading column '{col}'. "
                    "Did the cleaning pipeline change?"
                )
        text_col = _detect_text_col(df, text_col_override)

        df["duration_s"] = pd.to_numeric(df.get("duration_s", ""), errors="coerce")
        text = df[text_col].astype(str).fillna("")
        df["__text_stripped"] = text.str.strip()
        df["__char_len"] = df["__text_stripped"].str.len().astype(int)
        df["__word_len"] = df["__text_stripped"].str.split().map(len).astype(int)

        dur = df["duration_s"].to_numpy(dtype=float)
        clen = df["__char_len"].to_numpy(dtype=float)
        wlen = df["__word_len"].to_numpy(dtype=float)
        df["__ratio_sec_per_char"] = np.where(
            clen > 0, dur / np.maximum(clen, 1.0), np.nan)
        df["__ratio_sec_per_word"] = np.where(
            wlen > 0, dur / np.maximum(wlen, 1.0), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            df["__chars_per_sec"] = np.where(dur > 0, clen / dur, np.nan)
            df["__words_per_sec"] = np.where(dur > 0, wlen / dur, np.nan)

        sd = SourceData(
            name=name,
            csv_path=p,
            csv_mtime=datetime.datetime.fromtimestamp(p.stat().st_mtime),
            df=df,
            text_col=text_col,
        )
        sd.n_rows = len(df)
        sd.n_unique_clips = int(df["path"].nunique())
        valid_dur = dur[np.isfinite(dur) & (dur > 0)]
        sd.total_hours = float(valid_dur.sum() / 3600.0)
        sd.mean_duration = float(valid_dur.mean()) if valid_dur.size else float("nan")
        sd.n_empty_text = int((df["__char_len"] == 0).sum())

        qs = [0.0, 0.25, 0.50, 0.75, 0.90, 0.99, 0.995, 1.0]
        sd.quantiles["duration_s"] = _quantiles(dur, qs)
        sd.quantiles["char_len"] = _quantiles(clen[clen > 0], qs)
        sd.quantiles["word_len"] = _quantiles(wlen[wlen > 0], qs)
        for m in RATIO_METRICS:
            v = df[m["attr"]].to_numpy(dtype=float)
            sd.quantiles[m["name"]] = _quantiles(v, qs)
            sd.outliers[m["name"]] = _compute_outlier_stats(v, metric=m["name"])
        sources.append(sd)

    sources.sort(key=lambda s: (s.total_hours, s.n_rows), reverse=True)
    return sources


# ── Charts (shared helpers) ───────────────────────────────────────────────


def _setup_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib as mpl
    mpl.rcParams.update(_MPL_STYLE)


def _chart_style(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10, color="#1E3A5F")
    ax.set_xlabel(xlabel, fontsize=10, color="#4B5563")
    ax.set_ylabel(ylabel, fontsize=10, color="#4B5563")
    ax.yaxis.grid(True, alpha=0.35, color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.tick_params(colors="#6B7280", labelsize=9)


def _save(fig: Any, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)


def _add_median_vline(ax: Any, data: np.ndarray) -> None:
    if data.size < 2:
        return
    med = float(np.median(data))
    ax.axvline(med, color="#DC2626", linewidth=1.5, linestyle="--", alpha=0.85,
               label=f"Median: {med:.3g}")
    ax.legend(fontsize=9, framealpha=0.75, edgecolor="#CBD5E1")


def _draw_box_panel(
    ax: Any,
    values: np.ndarray,
    label: str,
    color: str,
    *,
    log_y: bool = False,
    exclude_zero: bool = False,
) -> Tuple[int, float, float]:
    v = values[np.isfinite(values)]
    excluded = 0
    if exclude_zero:
        before = v.size
        v = v[v > 0]
        excluded = int(before - v.size)
    if log_y:
        v = v[v > 0]
    if v.size == 0:
        ax.text(0.5, 0.5, "no data", transform=ax.transAxes,
                ha="center", va="center", color="#9CA3AF")
        return excluded, 0.0, 0.0

    q1, q3 = np.quantile(v, [0.25, 0.75])
    iqr = q3 - q1
    lo_fence = q1 - 1.5 * iqr
    hi_fence = q3 + 1.5 * iqr
    inside = v[(v >= lo_fence) & (v <= hi_fence)]
    whisker_top = float(inside.max()) if inside.size else float(v.max())

    ax.boxplot(
        [v], showfliers=False, patch_artist=True, widths=0.55,
        medianprops=dict(color="#DC2626", linewidth=2.0),
        boxprops=dict(facecolor=color, alpha=0.55, edgecolor=color, linewidth=1.4),
        whiskerprops=dict(color=color, linewidth=1.2),
        capprops=dict(color=color, linewidth=1.2),
    )

    mean = float(v.mean())
    ax.scatter([1], [mean], s=46, marker="D", color="#FACC15",
               edgecolor="#92400E", linewidths=0.7, zorder=5,
               label=f"mean: {mean:.3g}")

    out = v[(v < lo_fence) | (v > hi_fence)]
    p995_outlier = float(np.quantile(out, 0.995)) if out.size else 0.0
    if out.size:
        rng = np.random.default_rng(42)
        if out.size > 400:
            out = rng.choice(out, size=400, replace=False)
        jitter = rng.uniform(-0.07, 0.07, size=out.size)
        ax.scatter(1 + jitter, out, s=10, alpha=0.35,
                   color="#6B7280", edgecolor="none", zorder=2)

    excl_note = f" (excl. {excluded} zero)" if excluded else ""
    ax.set_title(f"{label}{excl_note}", fontsize=11,
                 fontweight="bold", pad=8, color="#1E3A5F")
    ax.set_xticks([])
    if log_y:
        ax.set_yscale("log")
    ax.yaxis.grid(True, alpha=0.35, color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.tick_params(colors="#6B7280", labelsize=9)
    ax.legend(fontsize=8, framealpha=0.75, edgecolor="#CBD5E1", loc="upper right")
    return excluded, whisker_top, p995_outlier


# ── Cross-source charts ───────────────────────────────────────────────────


def _plot_bar(
    sources: List[SourceData],
    out_path: Path,
    *,
    value_fn,
    title: str,
    ylabel: str,
    fmt: str,
) -> None:
    _setup_mpl()
    import matplotlib.pyplot as plt
    pairs = [(s.name, value_fn(s)) for s in sources]
    pairs.sort(key=lambda x: x[1], reverse=True)
    names = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    colors_ = [_color_for(n) for n in names]
    fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
    bars = ax.bar(range(len(names)), values, color=colors_, alpha=0.85,
                  edgecolor="white", linewidth=0.6)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=18, ha="right", fontsize=9)
    _chart_style(ax, title, "", ylabel)
    for rect, v in zip(bars, values):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(),
                fmt.format(v), ha="center", va="bottom",
                fontsize=9, color="#1F2937")
    fig.tight_layout()
    _save(fig, out_path)


def _plot_box_grid(
    sources: List[SourceData],
    out_path: Path,
    *,
    value_attr: str,
    title: str,
    ylabel: str,
    log_y: bool = False,
    exclude_zero: bool = False,
) -> None:
    _setup_mpl()
    import matplotlib.pyplot as plt
    n = len(sources)
    fig, axes = plt.subplots(1, n, figsize=(3.5 * n, 4.6), dpi=150,
                             sharey=False)
    if n == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=13, fontweight="bold", color="#1E3A5F", y=1.02)
    whisker_tops: List[Tuple[Any, float, float]] = []
    for ax, s in zip(axes, sources):
        v = s.df[value_attr].to_numpy(dtype=float)
        _, w_top, p995 = _draw_box_panel(
            ax, v, s.name, _color_for(s.name),
            log_y=log_y, exclude_zero=exclude_zero,
        )
        whisker_tops.append((ax, w_top, p995))
    if not log_y:
        max_top = max((w + p for _, w, p in whisker_tops), default=1.0)
        for ax, w, p in whisker_tops:
            top = max(w, p) * 1.15 if (w or p) else max_top * 1.15
            ax.set_ylim(bottom=ax.get_ylim()[0], top=max(top, max_top * 1.05))
    axes[0].set_ylabel(ylabel, fontsize=10, color="#4B5563")
    fig.tight_layout()
    _save(fig, out_path)


def _plot_overlay_duration(sources: List[SourceData], out_path: Path) -> None:
    _setup_mpl()
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
    bins = np.linspace(0, 20, 81)
    for s in sources:
        v = s.df["duration_s"].to_numpy(dtype=float)
        v = v[np.isfinite(v) & (v > 0) & (v <= 20.0)]
        if v.size == 0:
            continue
        weights = np.full_like(v, 1.0 / max(v.size, 1))
        ax.hist(v, bins=bins, weights=weights,
                histtype="stepfilled", alpha=0.35,
                color=_color_for(s.name),
                edgecolor=_color_for(s.name), linewidth=1.0,
                label=f"{s.name} (n={v.size})")
    _chart_style(ax, "Duration distribution overlay (0–20 s)",
                 "duration_s", "share of clips")
    ax.set_xlim(0, 20)
    ax.legend(fontsize=9, framealpha=0.85, edgecolor="#CBD5E1", loc="upper right")
    fig.tight_layout()
    _save(fig, out_path)


def render_overview_charts(
    sources: List[SourceData], assets_dir: Path,
) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    out["clip_counts"] = assets_dir / "clip_counts_per_source.png"
    out["total_hours"] = assets_dir / "total_hours_per_source.png"
    out["dur_box"] = assets_dir / "duration_boxplot_grid.png"
    out["char_box"] = assets_dir / "char_len_boxplot_grid.png"
    out["dur_overlay"] = assets_dir / "duration_overlay_hist.png"

    _plot_bar(sources, out["clip_counts"],
              value_fn=lambda s: s.n_rows,
              title="Cleaned clip count per source",
              ylabel="rows", fmt="{:,.0f}")
    _plot_bar(sources, out["total_hours"],
              value_fn=lambda s: s.total_hours,
              title="Total audio hours per source",
              ylabel="hours", fmt="{:,.1f}")
    _plot_box_grid(sources, out["dur_box"],
                   value_attr="duration_s",
                   title="Duration (s) per source",
                   ylabel="duration_s")
    _plot_box_grid(sources, out["char_box"],
                   value_attr="__char_len",
                   title="Transcript length (chars) per source",
                   ylabel="char_len", exclude_zero=True)
    _plot_overlay_duration(sources, out["dur_overlay"])

    # one boxplot grid per ratio metric — log y so heavy tails are visible
    for m in RATIO_METRICS:
        key = f"ratio_box::{m['name']}"
        out[key] = assets_dir / f"{m['name']}_boxplot_grid.png"
        _plot_box_grid(
            sources, out[key],
            value_attr=m["attr"],
            title=f"{m['name']} per source (log y)",
            ylabel=m["unit"],
            log_y=m["log_y"],
        )
    return out


# ── Per-source charts ────────────────────────────────────────────────────


def _plot_hist(
    data: np.ndarray, title: str, xlabel: str, out_path: Path,
    *, bins: int = 80, color: str = "#3B82F6",
    xlim: Optional[Tuple[float, float]] = None,
) -> None:
    _setup_mpl()
    import matplotlib.pyplot as plt
    x = data[np.isfinite(data)]
    if x.size == 0:
        return
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    ax.hist(x, bins=bins, color=color, alpha=0.85,
            edgecolor="white", linewidth=0.4)
    _add_median_vline(ax, x)
    _chart_style(ax, title, xlabel, "Count")
    if xlim is not None:
        ax.set_xlim(*xlim)
    fig.tight_layout()
    _save(fig, out_path)


def _plot_logx_hist(
    data: np.ndarray, title: str, xlabel: str, out_path: Path,
    *, bins: int = 72, color: str = "#8B5CF6",
) -> None:
    _setup_mpl()
    import matplotlib.pyplot as plt
    v = data[np.isfinite(data)]
    v = v[v > 0]
    if v.size == 0:
        return
    edges = np.geomspace(v.min(), v.max(), bins + 1)
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    ax.hist(v, bins=edges, color=color, alpha=0.85,
            edgecolor="white", linewidth=0.4)
    ax.set_xscale("log")
    _add_median_vline(ax, v)
    _chart_style(ax, title, xlabel, "Count")
    fig.tight_layout()
    _save(fig, out_path)


def _plot_single_source_box_panels(
    panels: List[Tuple[str, np.ndarray, bool, bool]],
    out_path: Path,
    *,
    title: str,
    color: str,
) -> None:
    """``panels`` = list of (label, values, log_y, exclude_zero)."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(3.7 * n, 4.6), dpi=150,
                             sharey=False)
    if n == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=13, fontweight="bold",
                 color="#1E3A5F", y=1.02)
    whisker_tops: List[Tuple[Any, float, float, bool]] = []
    for ax, (label, v, log_y, exclude_zero) in zip(axes, panels):
        _, w_top, p995 = _draw_box_panel(
            ax, v, label, color, log_y=log_y, exclude_zero=exclude_zero,
        )
        whisker_tops.append((ax, w_top, p995, log_y))
    for ax, w, p, log_y in whisker_tops:
        if log_y:
            continue
        top = max(w, p) * 1.15 if (w or p) else 1.0
        ax.set_ylim(bottom=ax.get_ylim()[0], top=top)
    fig.tight_layout()
    _save(fig, out_path)


def render_per_source_charts(
    s: SourceData, assets_dir: Path, long_text_min_chars: int,
) -> Dict[str, Path]:
    color = _color_for(s.name)
    out: Dict[str, Path] = {}
    out["dur_hist"] = assets_dir / "duration_hist.png"
    out["char_hist"] = assets_dir / "sentence_length_chars_hist.png"
    out["box_dist"] = assets_dir / "boxplot_distributions.png"
    out["box_ratio"] = assets_dir / "boxplot_ratios.png"

    dur = s.df["duration_s"].to_numpy(dtype=float)
    clen = s.df["__char_len"].to_numpy(dtype=float)
    wlen = s.df["__word_len"].to_numpy(dtype=float)

    _plot_hist(dur, f"{s.name} · duration (s)",
               "duration_s", out["dur_hist"], color=color)
    _plot_hist(clen[clen > 0], f"{s.name} · transcript length (chars)",
               "char_len", out["char_hist"], color=color)

    _plot_single_source_box_panels(
        [("duration_s", dur, False, False),
         ("char_len", clen, False, True),
         ("word_len", wlen, False, True)],
        out["box_dist"],
        title=f"{s.name} · distribution boxplots",
        color=color,
    )

    # 4-panel ratio boxplot, in the order defined by RATIO_METRICS
    ratio_panels = []
    for m in RATIO_METRICS:
        v = s.df[m["attr"]].to_numpy(dtype=float)
        ratio_panels.append((m["name"], v, m["log_y"], False))
    _plot_single_source_box_panels(
        ratio_panels, out["box_ratio"],
        title=f"{s.name} · ratio metrics (log y)",
        color=color,
    )

    # one log-x histogram per ratio metric — emphasises the tail
    for m in RATIO_METRICS:
        key = f"ratio_hist::{m['name']}"
        out[key] = assets_dir / f"{m['name']}_hist_logx.png"
        v = s.df[m["attr"]].to_numpy(dtype=float)
        _plot_logx_hist(
            v, f"{s.name} · {m['name']} (log-x)",
            m["unit"], out[key], color=color,
        )

    # also keep the "long-text/short-audio" log-x view that filters char_len
    out["cps_long"] = assets_dir / "long_text_chars_per_second_hist_logx.png"
    cps_long = s.df.loc[s.df["__char_len"] >= long_text_min_chars,
                        "__chars_per_sec"].to_numpy(dtype=float)
    _plot_logx_hist(
        cps_long,
        f"{s.name} · chars/s (char_len ≥ {long_text_min_chars}, log-x)",
        "chars / second", out["cps_long"], color=color,
    )
    return out


# ── Outliers ──────────────────────────────────────────────────────────────


def _top_outliers(
    df: pd.DataFrame,
    text_col: str,
    *,
    top_n: int,
    long_text_min_chars: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    keep_cols = ["audio_name", "duration_s", "__char_len",
                 "__ratio_sec_per_char", "__chars_per_sec", text_col]
    keep_cols = [c for c in keep_cols if c in df.columns]

    high = df.copy()
    high = high[high["__ratio_sec_per_char"].notna()]
    high = high.nlargest(top_n, "__ratio_sec_per_char")[keep_cols]

    fast = df[df["__char_len"] >= long_text_min_chars].copy()
    fast = fast[fast["__chars_per_sec"].notna()]
    fast = fast.nlargest(top_n, "__chars_per_sec")[keep_cols]
    return high, fast


# ── Markdown rendering ────────────────────────────────────────────────────


def _fmt_h(hours: float) -> str:
    if not math.isfinite(hours):
        return "N/A"
    return f"{hours:.2f} h ({hours*60:.1f} min)"


def _fmt_q(q: Dict[float, float], keys: List[float]) -> str:
    parts = []
    for k in keys:
        v = q.get(k, float("nan"))
        if not math.isfinite(v):
            parts.append(f"p{int(k*100):02d}=—")
        else:
            parts.append(f"p{int(k*100):02d}={v:.3g}")
    return ", ".join(parts)


def _fmt_v(v: float) -> str:
    return "—" if not math.isfinite(v) else f"{v:.4g}"


def _fmt_range(lo: float, hi: float) -> str:
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "—"
    return f"[{_fmt_v(lo)}, {_fmt_v(hi)}]"


def _md_outlier_table(stats: OutlierStats) -> List[str]:
    if stats.n == 0:
        return [f"_no data for `{stats.metric}`_", ""]
    lines = []
    lines.append(f"- n = **{stats.n:,}**  ·  "
                 f"p1 = {_fmt_v(stats.p1)}  ·  "
                 f"p99 = {_fmt_v(stats.p99)}  ·  "
                 f"p99.9 = {_fmt_v(stats.p999)}  ·  "
                 f"Tukey low = {_fmt_v(stats.tukey_low)}  ·  "
                 f"Tukey high = {_fmt_v(stats.tukey_high)}")
    lines.append("")
    lines.append("| rule | side | threshold | count | % | actual range |")
    lines.append("|---|---|---:|---:|---:|---|")
    for r in stats.rules:
        lines.append(
            f"| {r.name} | {r.side} | {_fmt_v(r.threshold)} | "
            f"{r.count:,} | {r.pct:.3f}% | "
            f"{_fmt_range(r.val_min, r.val_max)} |"
        )
    lines.append("")
    return lines


def _qkeys_short() -> List[float]:
    return [0.25, 0.5, 0.75, 0.9, 0.99]


def render_overview_markdown(
    sources: List[SourceData],
    chart_paths: Dict[str, Path],
    out_md: Path,
    *,
    top_n_outliers: int,
    long_text_min_chars: int,
) -> None:
    lines: List[str] = []
    lines.append("# Filtered CSV comparison report\n")
    lines.append(f"Generated: {datetime.date.today().isoformat()}  ·  "
                 f"sources: {len(sources)}\n")

    lines.append("## 1. Source roster\n")
    lines.append("| source | rows | unique_clips | total_hours | "
                 "mean_duration_s | empty_text_pct | text_col | csv |")
    lines.append("|---|---:|---:|---:|---:|---:|---|---|")
    for s in sources:
        empty_pct = (100.0 * s.n_empty_text / max(s.n_rows, 1))
        lines.append(
            f"| `{s.name}` | {s.n_rows:,} | {s.n_unique_clips:,} | "
            f"{s.total_hours:.2f} | {s.mean_duration:.2f} | "
            f"{empty_pct:.2f}% | `{s.text_col}` | `{s.csv_path.name}` |"
        )
    lines.append("")

    lines.append("## 2. Cross-source quantiles\n")
    qkeys = _qkeys_short()
    metric_groups = [
        ("duration_s", "duration_s"),
        ("char_len (excluding char_len=0)", "char_len"),
        ("word_len (excluding word_len=0)", "word_len"),
    ] + [(m["name"], m["name"]) for m in RATIO_METRICS]
    for label, key in metric_groups:
        lines.append(f"### {label}\n")
        for s in sources:
            lines.append(
                f"- **{s.name}** — {_fmt_q(s.quantiles[key], qkeys)}"
            )
        lines.append("")

    lines.append("## 3. Outlier counts & ranges (per ratio metric)\n")
    lines.append("Per-source thresholds (`p99`, `p99.9`, `Tukey high/low`, "
                 "`p1`), the number of rows that satisfy each rule, and the "
                 "actual `[min, max]` of those matched values.\n")
    for m in RATIO_METRICS:
        lines.append(f"### {m['name']}  _({m['unit']})_\n")
        for s in sources:
            lines.append(f"#### {s.name}\n")
            lines.extend(_md_outlier_table(s.outliers[m["name"]]))
        lines.append("")

    lines.append("## 4. Charts\n")
    chart_keys = ["clip_counts", "total_hours", "dur_box", "char_box",
                  "dur_overlay"] + [f"ratio_box::{m['name']}" for m in RATIO_METRICS]
    for k in chart_keys:
        p = chart_paths[k]
        try:
            rel_path = p.relative_to(WORKSPACE_ROOT)
        except ValueError:
            rel_path = p
        lines.append(f"![{p.name}]({rel_path.as_posix()})")
    lines.append("")

    lines.append("## 5. Per-source highlights\n")
    for s in sources:
        lines.append(f"### {s.name}\n")
        lines.append(f"- rows: {s.n_rows:,}  ·  total: {_fmt_h(s.total_hours)}  ·  "
                     f"mean duration: {s.mean_duration:.2f} s  ·  "
                     f"empty transcripts: {s.n_empty_text:,} "
                     f"({100.0 * s.n_empty_text / max(s.n_rows, 1):.2f}%)\n")
        high, fast = _top_outliers(
            s.df, s.text_col, top_n=top_n_outliers,
            long_text_min_chars=long_text_min_chars,
        )
        lines.append(f"#### Audio long, text short — top {top_n_outliers}\n")
        for _, row in high.iterrows():
            lines.append(
                f"- `{row['audio_name']}` · "
                f"duration_s={float(row['duration_s']):.3f} · "
                f"char_len={int(row['__char_len'])} · "
                f"s/char={float(row['__ratio_sec_per_char']):.3f}"
            )
            lines.append(f"  > {row[s.text_col] or '_(empty)_'}")
        lines.append(f"\n#### Text long, audio short (char_len ≥ {long_text_min_chars}) — top {top_n_outliers}\n")
        for _, row in fast.iterrows():
            lines.append(
                f"- `{row['audio_name']}` · "
                f"duration_s={float(row['duration_s']):.3f} · "
                f"char_len={int(row['__char_len'])} · "
                f"chars/s={float(row['__chars_per_sec']):.2f}"
            )
            lines.append(f"  > {row[s.text_col] or '_(empty)_'}")
        lines.append("")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def render_per_source_markdown(
    s: SourceData, chart_paths: Dict[str, Path],
    out_md: Path, *, top_n_outliers: int, long_text_min_chars: int,
) -> None:
    lines: List[str] = []
    lines.append(f"# {s.name} — filtered CSV report\n")
    lines.append(f"Generated: {datetime.date.today().isoformat()}\n")

    lines.append("## Overview\n")
    lines.append(f"- csv: `{s.csv_path.name}`  (mtime: {s.csv_mtime:%Y-%m-%d %H:%M})")
    lines.append(f"- rows: **{s.n_rows:,}**  ·  unique clips: {s.n_unique_clips:,}")
    lines.append(f"- total: **{_fmt_h(s.total_hours)}**  ·  "
                 f"mean clip duration: **{s.mean_duration:.2f} s**")
    lines.append(f"- empty transcripts: {s.n_empty_text:,} "
                 f"({100.0 * s.n_empty_text / max(s.n_rows, 1):.2f}%)")
    lines.append(f"- transcript column: `{s.text_col}`\n")

    lines.append("## Quantiles\n")
    qkeys = [0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]
    lines.append(f"- duration_s — {_fmt_q(s.quantiles['duration_s'], qkeys)}")
    lines.append(f"- char_len (>0) — {_fmt_q(s.quantiles['char_len'], qkeys)}")
    lines.append(f"- word_len (>0) — {_fmt_q(s.quantiles['word_len'], qkeys)}")
    for m in RATIO_METRICS:
        lines.append(f"- {m['name']} — {_fmt_q(s.quantiles[m['name']], qkeys)}")
    lines.append("")

    lines.append("## Outlier counts & ranges (per ratio metric)\n")
    for m in RATIO_METRICS:
        lines.append(f"### {m['name']}  _({m['unit']})_\n")
        lines.extend(_md_outlier_table(s.outliers[m["name"]]))
        lines.append("")

    lines.append("## Charts\n")
    chart_order = ["dur_hist", "char_hist", "box_dist", "box_ratio",
                   "cps_long"] + [f"ratio_hist::{m['name']}" for m in RATIO_METRICS]
    for k in chart_order:
        p = chart_paths[k]
        try:
            rel_path = p.relative_to(WORKSPACE_ROOT)
        except ValueError:
            rel_path = p
        lines.append(f"![{p.name}]({rel_path.as_posix()})")
    lines.append("")

    high, fast = _top_outliers(
        s.df, s.text_col, top_n=top_n_outliers,
        long_text_min_chars=long_text_min_chars,
    )
    lines.append(f"## Top {top_n_outliers} — audio long, text short\n")
    for _, row in high.iterrows():
        lines.append(
            f"- `{row['audio_name']}` · "
            f"duration_s={float(row['duration_s']):.3f} · "
            f"char_len={int(row['__char_len'])} · "
            f"s/char={float(row['__ratio_sec_per_char']):.3f}"
        )
        lines.append(f"  > {row[s.text_col] or '_(empty)_'}")
    lines.append("")

    lines.append(f"## Top {top_n_outliers} — text long, audio short (char_len ≥ {long_text_min_chars})\n")
    for _, row in fast.iterrows():
        lines.append(
            f"- `{row['audio_name']}` · "
            f"duration_s={float(row['duration_s']):.3f} · "
            f"char_len={int(row['__char_len'])} · "
            f"chars/s={float(row['__chars_per_sec']):.2f}"
        )
        lines.append(f"  > {row[s.text_col] or '_(empty)_'}")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


# ── PDF: shared building blocks ──────────────────────────────────────────


def _xml(s: str) -> str:
    return _xml_escape(str(s), {'"': "&quot;", "'": "&#39;"})


def _make_pdf_styles(text_blob: pd.Series):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        HRFlowable, Image, KeepTogether, PageBreak,
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    cjk = "Helvetica"
    bold = "Helvetica-Bold"
    cjk_count = int(
        text_blob.str.contains(r"[\u4e00-\u9fff\u3040-\u30ff]", regex=True).sum()
    )
    if cjk_count / max(len(text_blob), 1) > 0.01:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            cjk = "STSong-Light"
            bold = cjk
        except Exception:
            pass

    palette = {
        "C_NAVY": colors.HexColor("#1E3A5F"),
        "C_BLUE": colors.HexColor("#2563EB"),
        "C_LBLUE": colors.HexColor("#DBEAFE"),
        "C_GRAYF": colors.HexColor("#F8FAFC"),
        "C_GRAY2": colors.HexColor("#E5E7EB"),
        "C_GRAY4": colors.HexColor("#6B7280"),
        "C_TEXT": colors.HexColor("#1F2937"),
        "C_WHITE": colors.white,
        "C_AMBER": colors.HexColor("#FEF3C7"),
        "C_AMBRD": colors.HexColor("#92400E"),
        "C_RED": colors.HexColor("#DC2626"),
    }
    base = getSampleStyleSheet()["BodyText"]

    def S(name: str, **kw: Any) -> ParagraphStyle:
        kw.setdefault("fontName", cjk)
        return ParagraphStyle(name, parent=base, **kw)

    styles = {
        "Title":   S("Ti",  fontSize=26, leading=36, textColor=palette["C_WHITE"],
                     fontName=bold, alignment=TA_LEFT),
        "Sub":     S("Su",  fontSize=13, leading=20, textColor=colors.HexColor("#93C5FD")),
        "Meta":    S("Me",  fontSize=10, leading=16, textColor=colors.HexColor("#CBD5E1")),
        "H2":      S("H2",  fontSize=15, leading=21, textColor=palette["C_NAVY"],
                     fontName=bold, spaceBefore=20, spaceAfter=6),
        "H3":      S("H3",  fontSize=12, leading=17, textColor=palette["C_NAVY"],
                     fontName=bold, spaceBefore=12, spaceAfter=4),
        "H4":      S("H4",  fontSize=11, leading=16, textColor=palette["C_NAVY"],
                     fontName=bold, spaceBefore=8, spaceAfter=2),
        "Body":    S("Bo",  fontSize=11, leading=17, textColor=palette["C_TEXT"]),
        "Small":   S("Sm",  fontSize=10, leading=15, textColor=palette["C_GRAY4"]),
        "MetricN": S("MN",  fontSize=22, leading=30, textColor=palette["C_NAVY"],
                     fontName=bold, alignment=TA_CENTER),
        "MetricL": S("ML",  fontSize=10, leading=15, textColor=palette["C_GRAY4"],
                     alignment=TA_CENTER),
        "TagBlue": S("TB",  fontSize=9.5, leading=14, textColor=palette["C_NAVY"],
                     fontName=bold),
        "TagAmber": S("TA", fontSize=9.5, leading=14, textColor=palette["C_AMBRD"],
                      fontName=bold),
        "TblLbl":  S("TL",  fontSize=10, leading=15, textColor=palette["C_TEXT"],
                     fontName=bold),
        "TblVal":  S("TV",  fontSize=10, leading=15, textColor=palette["C_TEXT"]),
    }

    return {
        "modules": {
            "colors": colors, "TA_CENTER": TA_CENTER, "TA_LEFT": TA_LEFT,
            "A4": A4, "cm": cm, "HRFlowable": HRFlowable, "Image": Image,
            "KeepTogether": KeepTogether, "PageBreak": PageBreak,
            "Paragraph": Paragraph, "SimpleDocTemplate": SimpleDocTemplate,
            "Spacer": Spacer, "Table": Table, "TableStyle": TableStyle,
        },
        "cjk": cjk, "bold": bold,
        "palette": palette, "styles": styles,
    }


def _hr(palette, HRFlowable):
    return HRFlowable(width="100%", thickness=0.5,
                      color=palette["C_GRAY2"], spaceBefore=4, spaceAfter=12)


def _section(title_str, styles, palette, mods):
    return [mods["Spacer"](1, 8),
            mods["Paragraph"](title_str, styles["H2"]),
            _hr(palette, mods["HRFlowable"])]


def _tbl(data, col_widths, style_cmds, *, cjk, mods, palette):
    t = mods["Table"](data, colWidths=col_widths)
    base_cmds = [
        ("FONT", (0, 0), (-1, -1), cjk, 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]
    t.setStyle(mods["TableStyle"](base_cmds + style_cmds))
    return t


def _add_chart(story, p: Path, page_w: float, mods):
    if not p.exists():
        return
    im = mods["Image"](str(p))
    scale = page_w / im.imageWidth
    im.drawWidth = page_w
    im.drawHeight = im.imageHeight * scale
    story.append(im)
    story.append(mods["Spacer"](1, 12))


def _outlier_stats_table(
    stats: OutlierStats, page_w: float, *, cjk, bold, mods, palette, styles,
):
    P = mods["Paragraph"]
    rows = [["rule", "side", "threshold", "count", "%", "actual range"]]
    if stats.n == 0:
        rows.append([P("(no data)", styles["TblVal"]), "—", "—", "—", "—", "—"])
    else:
        for r in stats.rules:
            rows.append([
                P(r.name, styles["TblLbl"]),
                r.side,
                _fmt_v(r.threshold),
                f"{r.count:,}",
                f"{r.pct:.3f}",
                _fmt_range(r.val_min, r.val_max),
            ])
    cw = [page_w * w for w in (0.20, 0.10, 0.18, 0.14, 0.12, 0.26)]
    return _tbl(rows, cw, [
        ("BACKGROUND", (0, 0), (-1, 0), palette["C_NAVY"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), palette["C_WHITE"]),
        ("FONT", (0, 0), (-1, 0), bold, 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [palette["C_WHITE"], palette["C_GRAYF"]]),
        ("GRID", (0, 0), (-1, -1), 0.25, palette["C_GRAY2"]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
    ], cjk=cjk, mods=mods, palette=palette)


def _outlier_summary_text(stats: OutlierStats) -> str:
    return (
        f"n={stats.n:,} · "
        f"p1={_fmt_v(stats.p1)} · "
        f"p99={_fmt_v(stats.p99)} · "
        f"p99.9={_fmt_v(stats.p999)} · "
        f"Tukey low={_fmt_v(stats.tukey_low)} · "
        f"Tukey high={_fmt_v(stats.tukey_high)}"
    )


def _outlier_card(
    row: pd.Series, *, kind: str, text_col: str, page_w: float,
    cjk, mods, palette, styles,
):
    P = mods["Paragraph"]
    if kind == "high":
        bg = palette["C_LBLUE"]
        tag = "AUDIO LONG · TEXT SHORT"
        metric = (f"duration_s={float(row['duration_s']):.3f} · "
                  f"char_len={int(row['__char_len'])} · "
                  f"s/char={float(row['__ratio_sec_per_char']):.3f}")
        tag_style = styles["TagBlue"]
    else:
        bg = palette["C_AMBER"]
        tag = "TEXT LONG · AUDIO SHORT"
        metric = (f"duration_s={float(row['duration_s']):.3f} · "
                  f"char_len={int(row['__char_len'])} · "
                  f"chars/s={float(row['__chars_per_sec']):.2f}")
        tag_style = styles["TagAmber"]
    transcript = row[text_col] or "(empty)"
    cell_rows = [
        [P(tag, tag_style)],
        [P(f"<b>{_xml(row['audio_name'])}</b>", styles["Body"])],
        [P(metric, styles["Small"])],
        [P(_xml(transcript), styles["Body"])],
    ]
    t = mods["Table"](cell_rows, colWidths=[page_w])
    t.setStyle(mods["TableStyle"]([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, palette["C_GRAY2"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return mods["KeepTogether"]([t, mods["Spacer"](1, 6)])


# ── PDF: overview report ─────────────────────────────────────────────────


def render_overview_pdf(
    sources: List[SourceData], chart_paths: Dict[str, Path],
    out_pdf: Path, *, top_n_outliers: int, long_text_min_chars: int,
) -> None:
    text_blob = pd.concat(
        [s.df[s.text_col].astype(str) for s in sources if s.text_col in s.df.columns],
        ignore_index=True,
    )
    bundle = _make_pdf_styles(text_blob)
    mods = bundle["modules"]
    palette = bundle["palette"]
    styles = bundle["styles"]
    cjk, bold = bundle["cjk"], bundle["bold"]

    A4 = mods["A4"]
    cm = mods["cm"]
    W, H = A4
    MARGIN = 2 * cm
    page_w = W - 2 * MARGIN

    P = mods["Paragraph"]
    Spacer = mods["Spacer"]
    PageBreak = mods["PageBreak"]
    Table = mods["Table"]
    TableStyle = mods["TableStyle"]

    footer_label = f"filtered_csv_comparison · {len(sources)} sources"

    def _on_first_page(canvas, doc):
        pass

    def _on_later_pages(canvas, doc):
        canvas.saveState()
        canvas.setFont(cjk, 7.5)
        canvas.setFillColor(palette["C_GRAY4"])
        canvas.drawString(MARGIN, H - 1.1 * cm, footer_label)
        canvas.drawRightString(W - MARGIN, H - 1.1 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(palette["C_GRAY2"])
        canvas.setLineWidth(0.35)
        canvas.line(MARGIN, H - 1.3 * cm, W - MARGIN, H - 1.3 * cm)
        canvas.restoreState()

    doc = mods["SimpleDocTemplate"](
        str(out_pdf), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
    )
    story: List[Any] = []

    # Cover ──────────────────────────────────────────────────────────────
    hero_rows = [
        [P("Filtered CSV Comparison Report", styles["Title"])],
        [P(f"{len(sources)} sources · {datetime.date.today().isoformat()}", styles["Sub"])],
        [P("workspace: " + _xml(WORKSPACE_ROOT.name), styles["Meta"])],
    ]
    hero = Table(hero_rows, colWidths=[page_w])
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), palette["C_NAVY"]),
        ("TOPPADDING", (0, 0), (-1, 0), 30),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 26),
        ("LEFTPADDING", (0, 0), (-1, -1), 24),
        ("RIGHTPADDING", (0, 0), (-1, -1), 24),
        ("TOPPADDING", (0, 1), (-1, -2), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 6),
    ]))
    story.append(hero)
    story.append(Spacer(1, 24))

    total_clips = sum(s.n_rows for s in sources)
    total_hours = sum(s.total_hours for s in sources)
    all_dur = pd.concat([s.df["duration_s"] for s in sources], ignore_index=True)
    mean_dur = float(pd.to_numeric(all_dur, errors="coerce").mean())

    metric_cells = [[
        [P(str(len(sources)), styles["MetricN"]),
         P("Sources", styles["MetricL"])],
        [P(f"{total_clips:,}", styles["MetricN"]),
         P("Total Clips", styles["MetricL"])],
        [P(f"{total_hours:,.1f} h", styles["MetricN"]),
         P("Total Audio", styles["MetricL"])],
        [P(f"{mean_dur:.2f} s", styles["MetricN"]),
         P("Mean Clip Duration", styles["MetricL"])],
    ]]
    cw = page_w / 4
    metric_tbl = Table(metric_cells, colWidths=[cw, cw, cw, cw])
    metric_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), palette["C_GRAYF"]),
        ("BOX", (0, 0), (-1, -1), 0.5, palette["C_GRAY2"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, palette["C_GRAY2"]),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(metric_tbl)
    story.append(PageBreak())

    # Section 1 — Source roster ──────────────────────────────────────────
    story.extend(_section("1. Source roster", styles, palette, mods))
    rows = [["source", "rows", "unique", "hours", "mean s", "empty %",
             "text col", "csv mtime"]]
    for s in sources:
        empty_pct = 100.0 * s.n_empty_text / max(s.n_rows, 1)
        rows.append([
            P(_xml(s.name), styles["TblVal"]),
            f"{s.n_rows:,}", f"{s.n_unique_clips:,}",
            f"{s.total_hours:.2f}", f"{s.mean_duration:.2f}",
            f"{empty_pct:.2f}",
            P(_xml(s.text_col), styles["TblVal"]),
            P(_xml(s.csv_mtime.strftime("%Y-%m-%d %H:%M")), styles["TblVal"]),
        ])
    col_w = [page_w * w for w in (0.27, 0.10, 0.10, 0.08, 0.08, 0.09, 0.13, 0.15)]
    story.append(_tbl(rows, col_w, [
        ("BACKGROUND", (0, 0), (-1, 0), palette["C_NAVY"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), palette["C_WHITE"]),
        ("FONT", (0, 0), (-1, 0), bold, 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [palette["C_WHITE"], palette["C_GRAYF"]]),
        ("GRID", (0, 0), (-1, -1), 0.25, palette["C_GRAY2"]),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
    ], cjk=cjk, mods=mods, palette=palette))

    # Section 2 — Cross-source quantiles ─────────────────────────────────
    story.extend(_section("2. Cross-source quantiles", styles, palette, mods))
    qcols = _qkeys_short()
    metric_groups = [
        ("duration_s", "duration_s"),
        ("char_len (>0)", "char_len"),
        ("word_len (>0)", "word_len"),
    ] + [(m["name"], m["name"]) for m in RATIO_METRICS]
    for label, key in metric_groups:
        story.append(P(label, styles["H3"]))
        rows = [["source"] + [f"p{int(q*100):02d}" for q in qcols]]
        for s in sources:
            q = s.quantiles[key]
            row: List[Any] = [P(_xml(s.name), styles["TblVal"])]
            for k in qcols:
                v = q.get(k, float("nan"))
                row.append("—" if not math.isfinite(v) else f"{v:.3g}")
            rows.append(row)
        cw = [page_w * 0.36] + [page_w * 0.128] * 5
        story.append(_tbl(rows, cw, [
            ("BACKGROUND", (0, 0), (-1, 0), palette["C_NAVY"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), palette["C_WHITE"]),
            ("FONT", (0, 0), (-1, 0), bold, 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [palette["C_WHITE"], palette["C_GRAYF"]]),
            ("GRID", (0, 0), (-1, -1), 0.25, palette["C_GRAY2"]),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ], cjk=cjk, mods=mods, palette=palette))

    # Section 3 — Outlier counts & ranges (per ratio metric) ─────────────
    story.append(PageBreak())
    story.extend(_section(
        "3. Outlier counts & ranges (per ratio metric)",
        styles, palette, mods,
    ))
    story.append(P(
        "Per-source thresholds (p99 / p99.9 / Tukey high / p1 / Tukey low), "
        "the row count that satisfies each rule, and the actual min..max of "
        "the matched values.",
        styles["Body"],
    ))
    story.append(Spacer(1, 6))
    for m in RATIO_METRICS:
        story.append(P(f"{m['name']}  ({m['unit']})", styles["H3"]))
        for s in sources:
            stats = s.outliers[m["name"]]
            story.append(P(s.name, styles["H4"]))
            if stats.n:
                story.append(P(_outlier_summary_text(stats),
                               styles["Small"]))
                story.append(Spacer(1, 4))
            story.append(_outlier_stats_table(
                stats, page_w,
                cjk=cjk, bold=bold, mods=mods, palette=palette, styles=styles,
            ))
            story.append(Spacer(1, 8))

    # Section 4 — Charts ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(_section("4. Charts", styles, palette, mods))
    chart_keys = ["clip_counts", "total_hours", "dur_box", "char_box",
                  "dur_overlay"] + [f"ratio_box::{m['name']}" for m in RATIO_METRICS]
    for k in chart_keys:
        _add_chart(story, chart_paths[k], page_w, mods)

    # Section 5 — Per-source highlights ──────────────────────────────────
    for s in sources:
        story.append(PageBreak())
        story.extend(_section(f"5. {s.name}", styles, palette, mods))
        empty_pct = 100.0 * s.n_empty_text / max(s.n_rows, 1)
        summary = (
            f"<b>{s.n_rows:,}</b> rows · <b>{s.total_hours:.2f} h</b> total · "
            f"mean <b>{s.mean_duration:.2f} s</b> · "
            f"empty transcripts <b>{s.n_empty_text:,} ({empty_pct:.2f}%)</b>"
        )
        story.append(P(summary, styles["Body"]))
        story.append(Spacer(1, 6))

        high, fast = _top_outliers(
            s.df, s.text_col,
            top_n=top_n_outliers,
            long_text_min_chars=long_text_min_chars,
        )
        if not high.empty:
            story.append(P(
                f"Audio long, text short — top {min(top_n_outliers, len(high))}",
                styles["H3"],
            ))
            for _, r in high.iterrows():
                story.append(_outlier_card(
                    r, kind="high", text_col=s.text_col, page_w=page_w,
                    cjk=cjk, mods=mods, palette=palette, styles=styles,
                ))
        if not fast.empty:
            story.append(P(
                f"Text long, audio short (char_len ≥ {long_text_min_chars}) — "
                f"top {min(top_n_outliers, len(fast))}",
                styles["H3"],
            ))
            for _, r in fast.iterrows():
                story.append(_outlier_card(
                    r, kind="fast", text_col=s.text_col, page_w=page_w,
                    cjk=cjk, mods=mods, palette=palette, styles=styles,
                ))

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)


# ── PDF: per-source report ────────────────────────────────────────────────


def render_per_source_pdf(
    s: SourceData, chart_paths: Dict[str, Path], out_pdf: Path,
    *, top_n_outliers: int, long_text_min_chars: int,
) -> None:
    bundle = _make_pdf_styles(s.df[s.text_col].astype(str))
    mods = bundle["modules"]
    palette = bundle["palette"]
    styles = bundle["styles"]
    cjk, bold = bundle["cjk"], bundle["bold"]

    A4 = mods["A4"]
    cm = mods["cm"]
    W, H = A4
    MARGIN = 2 * cm
    page_w = W - 2 * MARGIN

    P = mods["Paragraph"]
    Spacer = mods["Spacer"]
    PageBreak = mods["PageBreak"]
    Table = mods["Table"]
    TableStyle = mods["TableStyle"]

    footer_label = f"{s.name} · filtered report"

    def _on_first_page(canvas, doc):
        pass

    def _on_later_pages(canvas, doc):
        canvas.saveState()
        canvas.setFont(cjk, 7.5)
        canvas.setFillColor(palette["C_GRAY4"])
        canvas.drawString(MARGIN, H - 1.1 * cm, footer_label)
        canvas.drawRightString(W - MARGIN, H - 1.1 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(palette["C_GRAY2"])
        canvas.setLineWidth(0.35)
        canvas.line(MARGIN, H - 1.3 * cm, W - MARGIN, H - 1.3 * cm)
        canvas.restoreState()

    doc = mods["SimpleDocTemplate"](
        str(out_pdf), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
    )
    story: List[Any] = []

    # Cover ──────────────────────────────────────────────────────────────
    hero_rows = [
        [P("Filtered CSV Report", styles["Title"])],
        [P(_xml(s.name), styles["Sub"])],
        [P(f"csv: {_xml(s.csv_path.name)} · "
           f"generated {datetime.date.today().isoformat()}",
           styles["Meta"])],
    ]
    hero = Table(hero_rows, colWidths=[page_w])
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), palette["C_NAVY"]),
        ("TOPPADDING", (0, 0), (-1, 0), 30),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 26),
        ("LEFTPADDING", (0, 0), (-1, -1), 24),
        ("RIGHTPADDING", (0, 0), (-1, -1), 24),
        ("TOPPADDING", (0, 1), (-1, -2), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 6),
    ]))
    story.append(hero)
    story.append(Spacer(1, 24))

    empty_pct = 100.0 * s.n_empty_text / max(s.n_rows, 1)
    metric_cells = [[
        [P(f"{s.n_rows:,}", styles["MetricN"]),
         P("Rows", styles["MetricL"])],
        [P(f"{s.total_hours:,.1f} h", styles["MetricN"]),
         P("Total Audio", styles["MetricL"])],
        [P(f"{s.mean_duration:.2f} s", styles["MetricN"]),
         P("Mean Duration", styles["MetricL"])],
        [P(f"{empty_pct:.2f}%", styles["MetricN"]),
         P("Empty Transcripts", styles["MetricL"])],
    ]]
    cw = page_w / 4
    metric_tbl = Table(metric_cells, colWidths=[cw, cw, cw, cw])
    metric_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), palette["C_GRAYF"]),
        ("BOX", (0, 0), (-1, -1), 0.5, palette["C_GRAY2"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, palette["C_GRAY2"]),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(metric_tbl)
    story.append(PageBreak())

    # Section 1 — Overview ──────────────────────────────────────────────
    story.extend(_section("1. Overview", styles, palette, mods))
    csv_disp = (s.csv_path.relative_to(WORKSPACE_ROOT).as_posix()
                if s.csv_path.is_absolute() else s.csv_path.as_posix())
    info_rows = [
        ["csv path", csv_disp],
        ["csv mtime", s.csv_mtime.strftime("%Y-%m-%d %H:%M:%S")],
        ["transcript col", s.text_col],
        ["rows / unique clips", f"{s.n_rows:,} / {s.n_unique_clips:,}"],
        ["total audio", _fmt_h(s.total_hours)],
        ["mean clip duration", f"{s.mean_duration:.2f} s"],
        ["empty transcripts", f"{s.n_empty_text:,} ({empty_pct:.2f}%)"],
    ]
    rows = []
    for k, v in info_rows:
        rows.append([P(k, styles["TblLbl"]), P(_xml(v), styles["TblVal"])])
    cw = [page_w * 0.32, page_w * 0.68]
    story.append(_tbl(rows, cw, [
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [palette["C_WHITE"], palette["C_GRAYF"]]),
        ("GRID", (0, 0), (-1, -1), 0.25, palette["C_GRAY2"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ], cjk=cjk, mods=mods, palette=palette))

    # Section 2 — Quantiles ─────────────────────────────────────────────
    story.extend(_section("2. Distribution quantiles", styles, palette, mods))
    qkeys = [0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]
    rows = [["metric"] + [f"p{int(q*100):02d}" for q in qkeys]]
    metric_pairs = [
        ("duration_s", "duration_s"),
        ("char_len (>0)", "char_len"),
        ("word_len (>0)", "word_len"),
    ] + [(m["name"], m["name"]) for m in RATIO_METRICS]
    for label, key in metric_pairs:
        q = s.quantiles[key]
        row: List[Any] = [P(label, styles["TblLbl"])]
        for k in qkeys:
            v = q.get(k, float("nan"))
            row.append("—" if not math.isfinite(v) else f"{v:.3g}")
        rows.append(row)
    cw = [page_w * 0.30] + [page_w * 0.10] * 7
    story.append(_tbl(rows, cw, [
        ("BACKGROUND", (0, 0), (-1, 0), palette["C_NAVY"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), palette["C_WHITE"]),
        ("FONT", (0, 0), (-1, 0), bold, 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [palette["C_WHITE"], palette["C_GRAYF"]]),
        ("GRID", (0, 0), (-1, -1), 0.25, palette["C_GRAY2"]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
    ], cjk=cjk, mods=mods, palette=palette))

    # Section 3 — Outlier counts & ranges (per ratio metric) ────────────
    story.append(PageBreak())
    story.extend(_section(
        "3. Outlier counts & ranges (per ratio metric)",
        styles, palette, mods,
    ))
    for m in RATIO_METRICS:
        stats = s.outliers[m["name"]]
        story.append(P(f"{m['name']}  ({m['unit']})", styles["H3"]))
        if stats.n:
            story.append(P(_outlier_summary_text(stats),
                           styles["Small"]))
            story.append(Spacer(1, 4))
        story.append(_outlier_stats_table(
            stats, page_w,
            cjk=cjk, bold=bold, mods=mods, palette=palette, styles=styles,
        ))
        story.append(Spacer(1, 8))

    # Section 4 — Charts ────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(_section("4. Charts", styles, palette, mods))
    chart_order = ["dur_hist", "char_hist", "box_dist", "box_ratio",
                   "cps_long"] + [f"ratio_hist::{m['name']}" for m in RATIO_METRICS]
    for k in chart_order:
        _add_chart(story, chart_paths[k], page_w, mods)

    # Section 5 — Outlier samples ───────────────────────────────────────
    high, fast = _top_outliers(
        s.df, s.text_col,
        top_n=top_n_outliers,
        long_text_min_chars=long_text_min_chars,
    )
    story.append(PageBreak())
    story.extend(_section(
        f"5. Outlier samples — top {top_n_outliers}", styles, palette, mods,
    ))
    if not high.empty:
        story.append(P("Audio long, text short", styles["H3"]))
        for _, r in high.iterrows():
            story.append(_outlier_card(
                r, kind="high", text_col=s.text_col, page_w=page_w,
                cjk=cjk, mods=mods, palette=palette, styles=styles,
            ))
    if not fast.empty:
        story.append(P(
            f"Text long, audio short (char_len ≥ {long_text_min_chars})",
            styles["H3"],
        ))
        for _, r in fast.iterrows():
            story.append(_outlier_card(
                r, kind="fast", text_col=s.text_col, page_w=page_w,
                cjk=cjk, mods=mods, palette=palette, styles=styles,
            ))

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)


# ── CLI ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--text-col", default=None,
                        help="Force a transcript column name across all sources.")
    parser.add_argument("--top-n-outliers", type=int, default=5)
    parser.add_argument("--long-text-min-chars", type=int, default=30)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--no-overview", action="store_true",
                        help="Skip the overview report.")
    parser.add_argument("--no-per-source", action="store_true",
                        help="Skip per-source reports.")
    args = parser.parse_args()

    only = set(args.only) if args.only else None
    exclude = set(args.exclude) if args.exclude else None

    sources = load_sources(
        args.csv_dir,
        text_col_override=args.text_col,
        only=only,
        exclude=exclude,
    )
    print(f"Loaded {len(sources)} sources from {args.csv_dir}:")
    for s in sources:
        print(f"  - {s.name}: rows={s.n_rows:,}, hours={s.total_hours:.2f}, "
              f"text_col={s.text_col!r}, csv={s.csv_path.name}")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []

    if not args.no_overview:
        print("\n[overview] rendering ...")
        assets_dir = out_dir / "assets"
        chart_paths = render_overview_charts(sources, assets_dir)
        out_md = out_dir / "filtered_csv_comparison.md"
        out_pdf = out_dir / "filtered_csv_comparison.pdf"
        render_overview_markdown(
            sources, chart_paths, out_md,
            top_n_outliers=args.top_n_outliers,
            long_text_min_chars=args.long_text_min_chars,
        )
        render_overview_pdf(
            sources, chart_paths, out_pdf,
            top_n_outliers=args.top_n_outliers,
            long_text_min_chars=args.long_text_min_chars,
        )
        written += [out_md, out_pdf, *chart_paths.values()]

    if not args.no_per_source:
        for s in sources:
            print(f"\n[{s.name}] rendering ...")
            sub_dir = out_dir / s.name
            assets_dir = sub_dir / "assets"
            chart_paths = render_per_source_charts(
                s, assets_dir, args.long_text_min_chars,
            )
            out_md = sub_dir / f"{s.name}_filtered_report.md"
            out_pdf = sub_dir / f"{s.name}_filtered_report.pdf"
            render_per_source_markdown(
                s, chart_paths, out_md,
                top_n_outliers=args.top_n_outliers,
                long_text_min_chars=args.long_text_min_chars,
            )
            render_per_source_pdf(
                s, chart_paths, out_pdf,
                top_n_outliers=args.top_n_outliers,
                long_text_min_chars=args.long_text_min_chars,
            )
            written += [out_md, out_pdf, *chart_paths.values()]

    print("\nWrote:")
    for p in written:
        try:
            print(f"  {p.relative_to(WORKSPACE_ROOT)}")
        except ValueError:
            print(f"  {p}")


if __name__ == "__main__":
    main()
