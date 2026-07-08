from __future__ import annotations

import argparse
import datetime
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Matplotlib style constants ─────────────────────────────────────────────

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


def _add_median_vline(ax: Any, data: np.ndarray) -> None:
    if data.size < 2:
        return
    med = float(np.median(data))
    ax.axvline(med, color="#DC2626", linewidth=1.5, linestyle="--", alpha=0.85,
               label=f"Median: {med:.3g}")
    ax.legend(fontsize=9, framealpha=0.75, edgecolor="#CBD5E1")


def _plot_hist(
    data: np.ndarray,
    title: str,
    xlabel: str,
    out_path: Path,
    bins: int = 80,
    xlim: Optional[Tuple[float, float]] = None,
    color: str = "#3B82F6",
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    mpl.rcParams.update(_MPL_STYLE)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    x = data[np.isfinite(data)]
    if x.size == 0:
        return
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    ax.hist(x, bins=bins, color=color, alpha=0.85, edgecolor="white", linewidth=0.4)
    _add_median_vline(ax, x)
    _chart_style(ax, title, xlabel, "Count")
    if xlim is not None:
        ax.set_xlim(*xlim)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_logx_hist(
    x: np.ndarray,
    title: str,
    xlabel: str,
    out_path: Path,
    bins: int = 72,
    color: str = "#8B5CF6",
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    mpl.rcParams.update(_MPL_STYLE)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    v = x[np.isfinite(x)]
    v = v[v > 0]
    if v.size == 0:
        return
    lo = max(float(np.nanpercentile(v, 0.5)), 1e-6)
    hi = float(np.nanpercentile(v, 99.99))
    hi = max(hi, lo * 1.0001)
    edges = np.logspace(math.log10(lo), math.log10(hi), bins + 1)
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    ax.hist(v, bins=edges, color=color, alpha=0.88, edgecolor="white", linewidth=0.3)
    ax.set_xscale("log")
    ax.xaxis.grid(True, which="both", alpha=0.15, color="#E5E7EB", linewidth=0.7)
    _add_median_vline(ax, v)
    _chart_style(ax, title, xlabel, "Count")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Boxplot grid ──────────────────────────────────────────────────────────

def _plot_boxplot_grid(
    panels: List[Tuple[str, np.ndarray]],
    title: str,
    out_path: Path,
    log_scales: Optional[List[bool]] = None,
    colors: Optional[List[str]] = None,
) -> None:
    """One figure with N vertical boxplot panels, each showing one metric.

    panels      : list of (panel_title, 1-D data array)
    log_scales  : per-panel flag; True → log y-axis
    colors      : per-panel fill colours; cycles if shorter than panels
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    mpl.rcParams.update(_MPL_STYLE)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(panels)
    if n == 0:
        return

    _colors = colors or ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#06B6D4", "#EC4899"]
    _log = log_scales or [False] * n

    ncols = min(n, 4)
    nrows = math.ceil(n / ncols)
    fig, raw_axes = plt.subplots(
        nrows, ncols,
        figsize=(3.5 * ncols, 5.0 * nrows),   # 3.5 in/panel keeps the full grid visible in PDF
        dpi=150,
        squeeze=False,
    )
    axes_flat: List[Any] = [ax for row in raw_axes for ax in row]

    for idx, ax in enumerate(axes_flat):
        if idx >= n:
            ax.set_visible(False)
            continue

        panel_title, data = panels[idx]
        v = data[np.isfinite(data)]
        use_log = _log[idx]
        if use_log:
            v = v[v > 0]
        if v.size == 0:
            ax.set_visible(False)
            continue

        color = _colors[idx % len(_colors)]

        # Always hide built-in fliers; we draw a sampled scatter manually so
        # that outlier points are visible even for million-row datasets.
        _MAX_FLIER_DOTS = 400
        q1_pre  = float(np.percentile(v, 25))
        q3_pre  = float(np.percentile(v, 75))
        iqr_pre = q3_pre - q1_pre
        _outliers = v[(v < q1_pre - 1.5 * iqr_pre) | (v > q3_pre + 1.5 * iqr_pre)]
        if _outliers.size > _MAX_FLIER_DOTS:
            rng = np.random.default_rng(42)
            _outliers = rng.choice(_outliers, size=_MAX_FLIER_DOTS, replace=False)

        bp = ax.boxplot(
            v,
            patch_artist=True,
            notch=False,
            showfliers=False,
            medianprops=dict(color="#DC2626", linewidth=2.5),
            boxprops=dict(facecolor=color, alpha=0.55, linewidth=1.2),
            whiskerprops=dict(color="#6B7280", linewidth=1, linestyle="--"),
            capprops=dict(color="#6B7280", linewidth=1.5),
            widths=0.55,
        )
        if _outliers.size > 0:
            _jitter = np.random.default_rng(0).uniform(-0.08, 0.08, size=_outliers.size)
            ax.scatter(
                1 + _jitter, _outliers,
                s=6, color="#9CA3AF", alpha=0.45, zorder=3, linewidths=0,
            )

        mean_v   = float(np.mean(v))
        median_v = float(np.median(v))
        q1_v     = float(np.percentile(v, 25))
        q3_v     = float(np.percentile(v, 75))
        iqr_v    = q3_v - q1_v

        # Mean diamond
        ax.plot(1, mean_v, "D", color="#F59E0B", markersize=7, zorder=6,
                label=f"Mean   {mean_v:.3g}")
        # Stats legend (invisible handles for Q info)
        ax.plot([], [], " ", label=f"Median {median_v:.3g}")
        ax.plot([], [], " ", label=f"IQR    {q1_v:.3g} – {q3_v:.3g}")
        ax.legend(fontsize=8, framealpha=0.85, edgecolor="#E5E7EB",
                  handlelength=0, handletextpad=0, loc="upper right")

        if use_log:
            ax.set_yscale("log")
            ax.yaxis.grid(True, which="both", alpha=0.2, color="#E5E7EB", linewidth=0.6)
        else:
            # y-axis: show full whisker + sampled outlier dots.
            # Top = max(whisker endpoint, p99.5 of sampled outliers) + padding.
            tukey_hi = q3_v + 1.5 * iqr_v
            tukey_lo = q1_v - 1.5 * iqr_v
            whisker_top = float(v[v <= tukey_hi].max()) if (v <= tukey_hi).any() else tukey_hi
            whisker_bot = float(v[v >= tukey_lo].min()) if (v >= tukey_lo).any() else tukey_lo
            if _outliers.size > 0:
                whisker_top = max(whisker_top, float(np.percentile(_outliers, 99.5)))
                whisker_bot = min(whisker_bot, float(np.percentile(_outliers,  0.5)))
            span = whisker_top - whisker_bot if whisker_top > whisker_bot else 1.0
            pad  = span * 0.15
            ax.set_ylim(
                bottom=whisker_bot - pad,
                top=whisker_top   + pad,
            )

        _chart_style(ax, panel_title, "", panel_title)
        ax.set_xticks([])
        ax.set_xlabel("")

    fig.suptitle(title, fontsize=13, fontweight="bold", color="#1E3A5F", y=1.01)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Core stats helpers ─────────────────────────────────────────────────────

def _quantiles(series: pd.Series, qs: Iterable[float]) -> Dict[float, float]:
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return {q: float("nan") for q in qs}
    return {q: float(s.quantile(q)) for q in qs}


def _compute_ratio_anomaly_rates(ratio_sec_per_char: pd.Series) -> Dict[str, Any]:
    rc = pd.to_numeric(ratio_sec_per_char, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    out: Dict[str, Any] = {"n": int(len(rc))}
    if rc.empty:
        return out
    p99  = float(rc.quantile(0.99))
    p999 = float(rc.quantile(0.999))
    p1   = float(rc.quantile(0.01))
    p01  = float(rc.quantile(0.001))
    q1, q3 = float(rc.quantile(0.25)), float(rc.quantile(0.75))
    iqr = q3 - q1
    tukey_upper = q3 + 1.5 * iqr
    tukey_lower = q1 - 1.5 * iqr
    out.update({
        "threshold_p99":          p99,
        "count_gt_p99":           int((rc > p99).sum()),
        "pct_gt_p99":             float((rc > p99).mean() * 100),
        "threshold_p999":         p999,
        "count_gt_p999":          int((rc > p999).sum()),
        "pct_gt_p999":            float((rc > p999).mean() * 100),
        "threshold_p1":           p1,
        "count_lt_p1":            int((rc < p1).sum()),
        "pct_lt_p1":              float((rc < p1).mean() * 100),
        "threshold_p01":          p01,
        "count_lt_p01":           int((rc < p01).sum()),
        "pct_lt_p01":             float((rc < p01).mean() * 100),
        "tukey_upper":            tukey_upper,
        "count_gt_tukey_upper":   int((rc > tukey_upper).sum()),
        "pct_gt_tukey_upper":     float((rc > tukey_upper).mean() * 100),
        "tukey_lower":            tukey_lower,
        "count_lt_tukey_lower":   int((rc < tukey_lower).sum()),
        "pct_lt_tukey_lower":     float((rc < tukey_lower).mean() * 100),
    })
    return out


# ── File helpers ───────────────────────────────────────────────────────────

@dataclass
class ReportArtifacts:
    out_dir: Path
    assets_dir: Path
    exports_dir: Path
    md_path: Path
    pdf_path: Path


def _artifacts(out_dir: Path) -> ReportArtifacts:
    stem = out_dir.name  # e.g. "sps-corpus-3.0-2026-03-09-de"
    return ReportArtifacts(
        out_dir=out_dir,
        assets_dir=out_dir / "assets",
        exports_dir=out_dir / "exports",
        md_path=out_dir / f"{stem}_initial_analysis.md",
        pdf_path=out_dir / f"{stem}_initial_analysis.pdf",
    )


def _read_meta(meta_path: Path, sep: str) -> pd.DataFrame:
    return pd.read_csv(meta_path, sep=sep, dtype="string", na_filter=False)


def _read_durations(path: Path, sep: str, clip_col: str, dur_col: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=sep, usecols=[clip_col, dur_col],
                     dtype={clip_col: "string"}, na_filter=False)
    df = df.rename(columns={clip_col: "path", dur_col: "duration_ms"})
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")
    return df.drop_duplicates(subset=["path"], keep="last")


def _escape_xml(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CYRILLIC_RE = r"[\u0400-\u04FF\u0500-\u052F]"
_CJK_RE = r"[\u4e00-\u9fff\u3040-\u30ff]"

_UNICODE_FONT_PAIRS: List[Tuple[str, str, str, str]] = [
    (
        "ReportUnicode",
        "ReportUnicode-Bold",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
    (
        "ReportUnicode",
        "ReportUnicode-Bold",
        "/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ),
    (
        "ReportUnicode",
        "ReportUnicode-Bold",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "ReportUnicode",
        "ReportUnicode-Bold",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ),
]


def _text_series(df: pd.DataFrame) -> pd.Series:
    if "sentence" not in df.columns:
        return pd.Series(dtype="string")
    return df["sentence"].astype(str)


def _resolve_pdf_fonts(df: pd.DataFrame) -> Tuple[str, str]:
    """Pick a PDF font that can render the corpus transcript script."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    text = _text_series(df)
    n = max(len(text), 1)
    cjk_count = int(text.str.contains(_CJK_RE, regex=True).sum())
    cyr_count = int(text.str.contains(_CYRILLIC_RE, regex=True).sum())

    if cjk_count / n > 0.01:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            return "STSong-Light", "STSong-Light"
        except Exception:
            pass

    if cyr_count / n > 0.01:
        for regular_name, bold_name, regular_path, bold_path in _UNICODE_FONT_PAIRS:
            reg = Path(regular_path)
            bol = Path(bold_path)
            if not reg.is_file():
                continue
            try:
                pdfmetrics.registerFont(TTFont(regular_name, str(reg)))
                if bol.is_file():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bol)))
                    return regular_name, bold_name
                return regular_name, regular_name
            except Exception:
                continue

    return "Helvetica", "Helvetica-Bold"


def _speaker_col(df: pd.DataFrame) -> Optional[str]:
    for col in ("speaker", "client_id"):
        if col in df.columns:
            return col
    return None


def _outlier_export_cols(df: pd.DataFrame, base: List[str]) -> List[str]:
    spk = _speaker_col(df)
    cols = list(base)
    if spk and spk not in cols:
        insert_at = cols.index("path") + 1 if "path" in cols else 0
        cols.insert(insert_at, spk)
    return [c for c in cols if c in df.columns]


def _outlier_speaker_label(row: Any, df: pd.DataFrame) -> str:
    spk = _speaker_col(df)
    if not spk:
        return "—"
    val = getattr(row, spk, None)
    return str(val).strip() if val is not None and str(val).strip() else "—"


# ── PDF builder ────────────────────────────────────────────────────────────

def _build_pdf(
    art: ReportArtifacts,
    *,
    dataset_dir: Path,
    meta_file: str,
    df: pd.DataFrame,
    durations_joined: bool,
    char_q: Dict[float, float],
    word_q: Dict[float, float],
    dur_q: Dict[float, float],
    ratio_q: Dict[float, float],
    ratio_rates: Dict[str, Any],
    out_high: pd.DataFrame,
    out_fast: pd.DataFrame,
    pdf_fulltext_n: int,
    long_text_min_chars: int,
    qs: List[float],
    extra_stats: Dict[str, Any],
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Image, KeepTogether, PageBreak,
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    # ── Palette ──────────────────────────────────────────────────────────
    C_NAVY   = colors.HexColor("#1E3A5F")
    C_BLUE   = colors.HexColor("#2563EB")
    C_LBLUE  = colors.HexColor("#DBEAFE")
    C_GRAYF  = colors.HexColor("#F8FAFC")
    C_GRAY2  = colors.HexColor("#E5E7EB")
    C_GRAY4  = colors.HexColor("#6B7280")
    C_TEXT   = colors.HexColor("#1F2937")
    C_WHITE  = colors.white
    C_AMBER  = colors.HexColor("#FEF3C7")
    C_AMBR2  = colors.HexColor("#FDE68A")
    C_AMBRD  = colors.HexColor("#92400E")

    W, _H = A4
    MARGIN = 2 * cm
    page_w = W - 2 * MARGIN

    # ── Font ─────────────────────────────────────────────────────────────
    # Helvetica for Latin corpora; Arial/DejaVu TTF for Cyrillic (e.g. Russian);
    # STSong-Light only when CJK makes up > 1 % of transcripts.
    cjk, bold = _resolve_pdf_fonts(df)

    gen_date = datetime.date.today().isoformat()

    # ── Styles ───────────────────────────────────────────────────────────
    base = getSampleStyleSheet()["BodyText"]

    def S(name: str, **kw: Any) -> ParagraphStyle:
        kw.setdefault("fontName", cjk)
        return ParagraphStyle(name, parent=base, **kw)

    sTitle    = S("Ti",  fontSize=26, leading=36, textColor=C_WHITE,  fontName=bold, alignment=TA_LEFT)
    sSub      = S("Su",  fontSize=13, leading=20, textColor=colors.HexColor("#93C5FD"))
    sMeta     = S("Me",  fontSize=10, leading=16, textColor=colors.HexColor("#CBD5E1"))
    sH2       = S("H2",  fontSize=15, leading=21, textColor=C_NAVY,   fontName=bold, spaceBefore=20, spaceAfter=6)
    sH3       = S("H3",  fontSize=12, leading=17, textColor=C_NAVY,   fontName=bold, spaceBefore=12, spaceAfter=4)
    sBody     = S("Bo",  fontSize=11, leading=17, textColor=C_TEXT)
    sSmall    = S("Sm",  fontSize=10, leading=15, textColor=C_GRAY4)
    sMetricN  = S("MN",  fontSize=22, leading=30, textColor=C_NAVY,   fontName=bold, alignment=TA_CENTER)
    sMetricL  = S("ML",  fontSize=10, leading=15, textColor=C_GRAY4,  alignment=TA_CENTER)
    sTagBlue  = S("TB",  fontSize=9.5, leading=14, textColor=C_NAVY,  fontName=bold)
    sTagAmber = S("TA",  fontSize=9.5, leading=14, textColor=C_AMBRD, fontName=bold)
    # Table cell styles — Paragraph objects enable word-wrap inside cells
    sTblLbl   = S("TL",  fontSize=10,  leading=15, textColor=C_TEXT,  fontName=bold)
    sTblVal   = S("TV",  fontSize=10,  leading=15, textColor=C_TEXT)

    # ── Reusable builders ─────────────────────────────────────────────
    def _hr() -> HRFlowable:
        return HRFlowable(width="100%", thickness=0.5, color=C_GRAY2, spaceBefore=4, spaceAfter=12)

    def _section(title_str: str) -> List[Any]:
        return [Spacer(1, 8), Paragraph(title_str, sH2), _hr()]

    def _tbl(data: List[List[Any]], col_widths: List[float], style_cmds: List[Any]) -> Table:
        t = Table(data, colWidths=col_widths)
        base_cmds = [
            ("FONT",          (0, 0), (-1, -1), cjk, 10),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]
        t.setStyle(TableStyle(base_cmds + style_cmds))
        return t

    def _paragraph_breaks(text: str, style: Any) -> Paragraph:
        t = _escape_xml(text).replace("\r\n", "\n").replace("\n", "<br/>")
        return Paragraph(t, style)

    def _plbl(text: str) -> Paragraph:
        """Bold label cell — wraps and uses sTblLbl style."""
        return Paragraph(_escape_xml(str(text)), sTblLbl)

    def _pval(text: str) -> Paragraph:
        """Value cell — wraps and uses sTblVal style."""
        return Paragraph(_escape_xml(str(text)), sTblVal)

    def _fv(v: float, d: int = 2) -> str:
        return "—" if math.isnan(v) else f"{v:.{d}f}"

    def _fmt_dur(hours: float) -> str:
        if math.isnan(hours):
            return "N/A"
        mins = hours * 60
        if mins < 1:
            return f"{mins*60:.1f} sec"
        if mins < 60:
            return f"{mins:.1f} min"
        return f"{hours:.2f} hr"

    # ── Page header/footer callbacks ──────────────────────────────────
    footer_label = f"{dataset_dir.name}  ·  {meta_file}"

    def _on_first_page(canvas: Any, doc: Any) -> None:
        pass  # Cover page is self-contained

    def _on_later_pages(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(cjk, 7.5)
        canvas.setFillColor(C_GRAY4)
        canvas.drawString(MARGIN, _H - 1.1 * cm, footer_label)
        canvas.drawRightString(W - MARGIN, _H - 1.1 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(C_GRAY2)
        canvas.setLineWidth(0.35)
        canvas.line(MARGIN, _H - 1.3 * cm, W - MARGIN, _H - 1.3 * cm)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(art.pdf_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
    )
    story: List[Any] = []

    # ══════════════════════════════════════════════════════════════════
    # PAGE 1 · COVER
    # ══════════════════════════════════════════════════════════════════

    hero_rows = [
        [Paragraph("Audio Metadata Report", sTitle)],
        [Paragraph(_escape_xml(meta_file), sSub)],
        [Paragraph(_escape_xml(dataset_dir.as_posix()), sMeta)],
        [Paragraph(f"Generated: {gen_date}", sMeta)],
    ]
    hero = Table(hero_rows, colWidths=[page_w])
    hero.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, 0),  30),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 26),
        ("LEFTPADDING",   (0, 0), (-1, -1), 24),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 24),
        ("TOPPADDING",    (0, 1), (-1, -2), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 6),
    ]))
    story.append(hero)
    story.append(Spacer(1, 24))

    # Key metrics grid (3 columns)
    total_hours = extra_stats.get("total_hours", float("nan"))
    n_spk       = extra_stats.get("n_unique_speakers")
    pct_empty   = extra_stats.get("pct_empty_transcripts", float("nan"))
    n_empty     = extra_stats.get("n_empty_transcripts", 0)

    metrics: List[Tuple[str, str]] = [
        (str(len(df)),                                               "Total Clips"),
        (str(df["path"].nunique()),                                  "Unique Clips"),
        (str(n_spk) if n_spk is not None else "N/A",                "Unique Speakers"),
        (_fmt_dur(total_hours),                                      "Total Audio Duration"),
        (f"{pct_empty:.1f}%" if not math.isnan(pct_empty) else "N/A", "Empty Transcriptions"),
        (f"{dur_q.get(0.5, float('nan')):.1f}s"
         if not math.isnan(dur_q.get(0.5, float("nan"))) else "N/A", "Median Duration"),
    ]
    while len(metrics) % 3:
        metrics.append(("", ""))

    NCOLS = 3
    col_w = page_w / NCOLS
    for row_start in range(0, len(metrics), NCOLS):
        row_slice = metrics[row_start:row_start + NCOLS]
        cells = [
            Table(
                [[Paragraph(v, sMetricN)], [Paragraph(lbl, sMetricL)]],
                colWidths=[col_w - 0.2 * cm],
            )
            for v, lbl in row_slice
        ]
        metric_tbl = Table([cells], colWidths=[col_w] * NCOLS)
        metric_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_GRAYF),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY2),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, C_GRAY2),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ]))
        story.append(metric_tbl)
        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════
    # SECTION 1 · DATASET OVERVIEW
    # ══════════════════════════════════════════════════════════════════

    story.extend(_section("1 · Dataset Overview"))

    # Header row: plain strings so TableStyle TEXTCOLOR/FONT/BACKGROUND apply.
    # Data rows: Paragraph objects so long values (distributions) word-wrap.
    ov_rows: List[List[Any]] = [
        ["Field", "Value"],
        [_plbl("Dataset directory"), _pval(dataset_dir.as_posix())],
        [_plbl("Metadata file"),     _pval(meta_file)],
        [_plbl("Total rows"),        _pval(str(len(df)))],
        [_plbl("Unique clips"),      _pval(str(df["path"].nunique()))],
    ]
    if n_spk is not None:
        ov_rows.append([_plbl("Unique speakers"), _pval(str(n_spk))])
    if not math.isnan(total_hours):
        ov_rows.append([_plbl("Total audio"),
                        _pval(f"{total_hours:.3f} h  ({total_hours*60:.1f} min)")])
    ov_rows.append([_plbl("Duration source"),
                    _pval("clip_durations.tsv" if durations_joined
                          else "duration column in main metadata")])
    ov_rows.append([_plbl("Empty transcriptions"),
                    _pval(f"{n_empty}  ({pct_empty:.1f}%)")])

    spk_col = extra_stats.get("speaker_col")
    if spk_col:
        ov_rows.append([_plbl("Speaker column"), _pval(spk_col)])
    clips_mean = extra_stats.get("clips_per_speaker_mean")
    clips_min = extra_stats.get("clips_per_speaker_min")
    clips_max = extra_stats.get("clips_per_speaker_max")
    if clips_mean is not None:
        ov_rows.append([
            _plbl("Clips per speaker"),
            _pval(f"mean={clips_mean:.2f}, min={clips_min}, max={clips_max}"),
        ])
    if extra_stats.get("script_label"):
        ov_rows.append([_plbl("Transcript script"), _pval(extra_stats["script_label"])])

    speaker_top = extra_stats.get("speaker_top_by_hours")
    if speaker_top:
        val = ",  ".join(
            f"{spk}: {clips} clips, {hours:.2f} h"
            for spk, clips, hours in speaker_top
        )
        ov_rows.append([_plbl("Top speakers by total audio"), _pval(val)])

    for col_name, col_label in [
        ("split",   "Split distribution"),
        ("gender",  "Gender distribution"),
        ("age",     "Age distribution"),
        ("accents", "Accent distribution"),
    ]:
        dist = extra_stats.get(f"{col_name}_dist")
        if dist:
            val = ",  ".join(f"{k}: {v}" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
            ov_rows.append([_plbl(col_label), _pval(val)])

    ov_tbl = _tbl(ov_rows, [5 * cm, page_w - 5 * cm], [
        ("FONT",           (0, 0), (-1, 0),  bold, 9.5),
        ("BACKGROUND",     (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAYF]),
        ("GRID",           (0, 0), (-1, -1), 0.25, C_GRAY2),
        ("VALIGN",         (0, 1), (-1, -1), "TOP"),
    ])
    story.append(ov_tbl)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 2 · DISTRIBUTION STATISTICS
    # ══════════════════════════════════════════════════════════════════

    story.extend(_section("2 · Distribution Statistics"))

    q_head = ["Metric"] + [f"p{int(q*100):02d}" for q in qs]

    def _qrow(label: str, q: Dict[float, float]) -> List[str]:
        return [label] + [_fv(q.get(k, float("nan"))) for k in qs]

    q_rows = [
        q_head,
        _qrow("char_len (chars)", char_q),
        _qrow("word_len (words)", word_q),
        _qrow("duration_s (sec)", dur_q),
        _qrow("ratio  s/char",    ratio_q),
    ]
    ncq = len(q_head)
    c1w = 3.8 * cm
    cxw = (page_w - c1w) / (ncq - 1)
    q_tbl = _tbl(q_rows, [c1w] + [cxw] * (ncq - 1), [
        ("FONT",          (0, 0), (-1, 0),  bold, 8.5),
        ("FONT",          (0, 1), (0, -1),  bold, 8.5),
        ("BACKGROUND",    (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("BACKGROUND",    (0, 1), (0, -1),  C_LBLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAYF]),
        ("GRID",          (0, 0), (-1, -1), 0.25, C_GRAY2),
        ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
    ])
    story.append(q_tbl)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 3 · ANOMALY ANALYSIS
    # ══════════════════════════════════════════════════════════════════

    story.extend(_section("3 · Anomaly Analysis  (ratio_sec_per_char)"))
    story.append(Paragraph(
        "ratio_sec_per_char = duration_s / max(char_len, 1).  "
        "High → audio long but transcript short/empty.  "
        "Low → very dense transcription relative to audio.",
        sSmall,
    ))
    story.append(Spacer(1, 6))

    an_head = ["Condition", "Threshold (s/char)", "Count", "Rate"]
    an_rows: List[List[Any]] = [an_head]
    for condition, thr_key, cnt_key, pct_key in [
        ("ratio > p99  (long audio, short text)",
         "threshold_p99",  "count_gt_p99",  "pct_gt_p99"),
        ("ratio > p99.9",
         "threshold_p999", "count_gt_p999", "pct_gt_p999"),
        ("ratio > Tukey upper  (Q3 + 1.5 × IQR)",
         "tukey_upper", "count_gt_tukey_upper", "pct_gt_tukey_upper"),
        ("ratio < p1  (dense transcription, short audio)",
         "threshold_p1", "count_lt_p1", "pct_lt_p1"),
        ("ratio < Tukey lower  (Q1 − 1.5 × IQR)",
         "tukey_lower", "count_lt_tukey_lower", "pct_lt_tukey_lower"),
    ]:
        thr = ratio_rates.get(thr_key, float("nan"))
        cnt = ratio_rates.get(cnt_key, "—")
        pct = ratio_rates.get(pct_key, float("nan"))
        an_rows.append([
            _pval(condition),
            _pval(_fv(thr, 4) if not isinstance(thr, str) else thr),
            _pval(str(cnt)),
            _pval(f"{pct:.2f}%" if not math.isnan(float(pct)) else "—"),
        ])
    an_tbl = _tbl(an_rows, [8.2 * cm, 3.8 * cm, 2.0 * cm, 2.4 * cm], [
        ("FONT",          (0, 0), (-1, 0),  bold, 9),
        ("BACKGROUND",    (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAYF]),
        ("GRID",          (0, 0), (-1, -1), 0.25, C_GRAY2),
        ("ALIGN",         (1, 1), (-1, -1), "RIGHT"),
    ])
    story.append(an_tbl)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 4a · OUTLIERS: AUDIO LONG, TEXT SHORT
    # ══════════════════════════════════════════════════════════════════

    n_high = min(pdf_fulltext_n, len(out_high))
    if n_high:
        story.extend(_section(f"4a · Outliers: Audio Long, Text Short  (Top {n_high})"))
        story.append(Paragraph(
            "Sorted by ratio_sec_per_char descending. "
            "A high ratio typically means the transcription is missing or very short.",
            sSmall,
        ))
        story.append(Spacer(1, 6))

        for i, r in enumerate(out_high.head(n_high).itertuples(index=False), 1):
            dur_v = float(r.duration_s)
            spk_lbl = _outlier_speaker_label(r, df)
            tag_data = [[
                Paragraph(f"#{i}", sTagBlue),
                Paragraph(_escape_xml(spk_lbl), sTagBlue),
                Paragraph(f"dur={dur_v:.2f}s", sTagBlue),
                Paragraph(f"chars={int(r.char_len)}", sTagBlue),
                Paragraph(f"s/char={float(r.ratio_sec_per_char):.3f}", sTagBlue),
            ]]
            tag_tbl = Table(tag_data, colWidths=[0.6*cm, 5.2*cm, 2.2*cm, 2.0*cm, 2.8*cm])
            path_row = [[Paragraph(_escape_xml(str(r.path)), sTagBlue)]]
            path_tbl = Table(path_row, colWidths=[page_w])
            path_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_LBLUE),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ]))
            tag_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_LBLUE),
                ("TOPPADDING",    (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("GRID",          (0, 0), (-1, -1), 0.25, C_GRAY2),
            ]))
            sentence = str(r.sentence).strip()
            trans_p = (
                Paragraph("<i>(empty)</i>", sSmall)
                if not sentence
                else _paragraph_breaks(sentence, sBody)
            )
            trans_data = [[trans_p]]
            trans_tbl = Table(trans_data, colWidths=[page_w])
            trans_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_GRAYF),
                ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(KeepTogether([tag_tbl, path_tbl, trans_tbl, Spacer(1, 10)]))

    # ══════════════════════════════════════════════════════════════════
    # SECTION 4b · OUTLIERS: TEXT LONG, AUDIO SHORT
    # ══════════════════════════════════════════════════════════════════

    n_fast = min(pdf_fulltext_n, len(out_fast))
    if n_fast:
        story.extend(_section(f"4b · Outliers: Text Long, Audio Short  (Top {n_fast})"))
        story.append(Paragraph(
            f"Filter: char_len ≥ {long_text_min_chars}. "
            "Sorted by chars_per_sec descending. "
            "High values mean the transcription is surprisingly long for the clip's duration.",
            sSmall,
        ))
        story.append(Spacer(1, 6))

        for i, r in enumerate(out_fast.head(n_fast).itertuples(index=False), 1):
            dur_v = float(r.duration_s)
            spk_lbl = _outlier_speaker_label(r, df)
            tag_data = [[
                Paragraph(f"#{i}", sTagAmber),
                Paragraph(_escape_xml(spk_lbl), sTagAmber),
                Paragraph(f"dur={dur_v:.2f}s", sTagAmber),
                Paragraph(f"chars={int(r.char_len)}", sTagAmber),
                Paragraph(f"ch/s={float(r.chars_per_sec):.2f}", sTagAmber),
            ]]
            tag_tbl = Table(tag_data, colWidths=[0.6*cm, 5.2*cm, 2.2*cm, 2.0*cm, 2.8*cm])
            path_row = [[Paragraph(_escape_xml(str(r.path)), sTagAmber)]]
            path_tbl = Table(path_row, colWidths=[page_w])
            path_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_AMBER),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ]))
            tag_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_AMBER),
                ("TOPPADDING",    (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("GRID",          (0, 0), (-1, -1), 0.25, C_AMBR2),
            ]))
            trans_data = [[_paragraph_breaks(str(r.sentence).strip(), sBody)]]
            trans_tbl = Table(trans_data, colWidths=[page_w])
            trans_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                ("BOX",           (0, 0), (-1, -1), 0.5, C_AMBR2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(KeepTogether([tag_tbl, path_tbl, trans_tbl, Spacer(1, 10)]))

    # ══════════════════════════════════════════════════════════════════
    # SECTION 5 · CHARTS
    # ══════════════════════════════════════════════════════════════════

    story.append(PageBreak())
    story.extend(_section("5 · Charts"))

    chart_defs = [
        # ── Histograms ────────────────────────────────────────────────
        (art.assets_dir / "duration_seconds_hist.png",
         "Duration Distribution (seconds)"),
        (art.assets_dir / "sentence_length_chars_hist.png",
         "Transcription Length Distribution (characters)"),
        (art.assets_dir / "ratio_sec_per_char_hist_logx.png",
         "Ratio: duration_s / char_len  (log scale)  — high values = missing or very short transcription"),
        (art.assets_dir / "ratio_sec_per_word_hist_logx.png",
         "Ratio: duration_s / word_len  (log scale)"),
        (art.assets_dir / "long_text_chars_per_second_hist_logx.png",
         f"Long-text: Chars per Second  (char_len ≥ {long_text_min_chars}, log scale)"),
        (art.assets_dir / "long_text_words_per_second_hist_logx.png",
         f"Long-text: Words per Second  (char_len ≥ {long_text_min_chars}, log scale)"),
        # ── Boxplots ──────────────────────────────────────────────────
        (art.assets_dir / "boxplot_distributions.png",
         "Boxplots: Duration, Transcript Char Length, Transcript Word Length"),
        (art.assets_dir / "boxplot_ratios.png",
         "Boxplots: Ratio & Rate metrics  (log scale) — box = IQR, whiskers = 1.5 × IQR, ◆ = mean"),
    ]
    avail = [(p, lbl) for p, lbl in chart_defs if p.exists()]

    # Scale every chart to full page width while preserving its true aspect ratio.
    # ReportLab stores image dimensions in points (72 DPI basis); imageWidth and
    # imageHeight reflect the natural size.  We set drawWidth = page_w and
    # drawHeight = page_w * (natural_h / natural_w) so all panels of multi-panel
    # boxplots are fully visible without distortion.
    img_w = page_w
    for idx, (p, lbl) in enumerate(avail):
        story.append(Paragraph(lbl, sH3))
        story.append(Spacer(1, 4))
        im = Image(str(p))
        scale = img_w / im.imageWidth
        im.drawWidth  = img_w
        im.drawHeight = im.imageHeight * scale
        story.append(im)
        story.append(Spacer(1, 14))
        if idx < len(avail) - 1:
            story.append(_hr())

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)


# ── Markdown builder ───────────────────────────────────────────────────────

def _build_markdown(
    art: ReportArtifacts,
    *,
    dataset_dir: Path,
    meta_file: str,
    df: pd.DataFrame,
    durations_joined: bool,
    char_q: Dict[float, float],
    word_q: Dict[float, float],
    dur_q: Dict[float, float],
    ratio_q: Dict[float, float],
    ratio_rates: Dict[str, Any],
    out_high: pd.DataFrame,
    out_fast: pd.DataFrame,
    md_fulltext_n: int,
    long_text_min_chars: int,
    qs: List[float],
    extra_stats: Dict[str, Any],
) -> None:
    def fmtq(q: Dict[float, float]) -> str:
        parts = []
        for k in qs:
            v = q.get(k, float("nan"))
            parts.append(f"p{int(k*100):02d}={'nan' if math.isnan(v) else f'{v:.4g}'}")
        return ", ".join(parts)

    def bq(s: str) -> str:
        if not s:
            return "> _（empty）_"
        return "\n".join("> " + (ln or " ") for ln in str(s).replace("\r\n", "\n").split("\n"))

    lines: List[str] = []
    lines += [
        f"# Audio Metadata Report — `{meta_file}`",
        "",
        "## Overview",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| dataset_dir | `{dataset_dir.as_posix()}` |",
        f"| meta_file | `{meta_file}` |",
        f"| total_rows | {len(df)} |",
        f"| unique_clips | {df['path'].nunique()} |",
    ]
    if extra_stats.get("n_unique_speakers") is not None:
        lines.append(f"| unique_speakers | {extra_stats['n_unique_speakers']} |")
    if extra_stats.get("speaker_col"):
        lines.append(f"| speaker_column | `{extra_stats['speaker_col']}` |")
    if extra_stats.get("clips_per_speaker_mean") is not None:
        lines.append(
            f"| clips_per_speaker | mean={extra_stats['clips_per_speaker_mean']:.2f}, "
            f"min={extra_stats['clips_per_speaker_min']}, "
            f"max={extra_stats['clips_per_speaker_max']} |"
        )
    if extra_stats.get("script_label"):
        lines.append(f"| transcript_script | {extra_stats['script_label']} |")
    h = extra_stats.get("total_hours", float("nan"))
    if not math.isnan(h):
        lines.append(f"| total_audio | {h:.3f} h ({h*60:.1f} min) |")
    ne = extra_stats.get("n_empty_transcripts", 0)
    pe = extra_stats.get("pct_empty_transcripts", float("nan"))
    lines.append(f"| empty_transcriptions | {ne} ({pe:.1f}%) |")
    lines.append(f"| durations_source | {'clip_durations.tsv' if durations_joined else 'main metadata'} |")

    speaker_top = extra_stats.get("speaker_top_by_hours")
    if speaker_top:
        val = ", ".join(
            f"{spk}: {clips} clips, {hours:.2f} h"
            for spk, clips, hours in speaker_top
        )
        lines.append(f"| top_speakers_by_audio | {val} |")

    for col_name, col_label in [
        ("split", "split_distribution"),
        ("gender", "gender_distribution"),
        ("age", "age_distribution"),
        ("accents", "accent_distribution"),
    ]:
        dist = extra_stats.get(f"{col_name}_dist")
        if dist:
            val = ", ".join(f"{k}: {v}" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
            lines.append(f"| {col_label} | {val} |")

    lines += [
        "",
        "## Key Quantiles",
        "",
        f"- **char_len**: {fmtq(char_q)}",
        f"- **word_len**: {fmtq(word_q)}",
        f"- **duration_s**: {fmtq(dur_q)}",
        f"- **ratio_sec_per_char**: {fmtq(ratio_q)}",
        "",
        "## Anomaly Rates (ratio_sec_per_char)",
        "",
        f"- n={ratio_rates.get('n', 0)}",
        f"- >p99  (≈{ratio_rates.get('threshold_p99', float('nan')):.4g}):"
        f"  {ratio_rates.get('count_gt_p99', '—')} clips  ({ratio_rates.get('pct_gt_p99', float('nan')):.3f}%)",
        f"- >p99.9 (≈{ratio_rates.get('threshold_p999', float('nan')):.4g}):"
        f"  {ratio_rates.get('count_gt_p999', '—')} clips  ({ratio_rates.get('pct_gt_p999', float('nan')):.3f}%)",
        f"- Tukey upper (≈{ratio_rates.get('tukey_upper', float('nan')):.4g}):"
        f"  {ratio_rates.get('count_gt_tukey_upper', '—')} clips  ({ratio_rates.get('pct_gt_tukey_upper', float('nan')):.3f}%)",
        f"- <p1  (≈{ratio_rates.get('threshold_p1', float('nan')):.4g}):"
        f"  {ratio_rates.get('count_lt_p1', '—')} clips  ({ratio_rates.get('pct_lt_p1', float('nan')):.3f}%)",
        "",
        "## Charts",
    ]
    for p in [
        art.assets_dir / "duration_seconds_hist.png",
        art.assets_dir / "sentence_length_chars_hist.png",
        art.assets_dir / "ratio_sec_per_char_hist_logx.png",
        art.assets_dir / "ratio_sec_per_word_hist_logx.png",
        art.assets_dir / "long_text_chars_per_second_hist_logx.png",
    ]:
        if p.exists():
            lines.append(f"![{p.name}]({p.as_posix()})")
    lines.append("")

    lines.append(f"## Outliers: Audio Long, Text Short (Top {md_fulltext_n})")
    for i, r in enumerate(out_high.head(md_fulltext_n).itertuples(index=False), 1):
        spk_lbl = _outlier_speaker_label(r, df)
        lines += [
            f"### {i}. `{r.path}`",
            f"- speaker={spk_lbl}  duration_s={float(r.duration_s):.3f}  char_len={int(r.char_len)}"
            f"  s/char={float(r.ratio_sec_per_char):.4f}",
            "",
            bq(r.sentence),
            "",
        ]

    lines.append(f"## Outliers: Text Long, Audio Short (char_len≥{long_text_min_chars}, Top {md_fulltext_n})")
    for i, r in enumerate(out_fast.head(md_fulltext_n).itertuples(index=False), 1):
        spk_lbl = _outlier_speaker_label(r, df)
        lines += [
            f"### {i}. `{r.path}`",
            f"- speaker={spk_lbl}  duration_s={float(r.duration_s):.3f}  char_len={int(r.char_len)}"
            f"  chars/s={float(r.chars_per_sec):.2f}",
            "",
            bq(r.sentence),
            "",
        ]

    art.md_path.write_text("\n".join(lines), encoding="utf-8")


# ── Main orchestration ─────────────────────────────────────────────────────

def build_report(
    dataset_dir: Path,
    meta_file: str,
    out_dir: Path,
    *,
    meta_sep: str = "\t",
    path_col: str = "path",
    text_col: str = "sentence",
    durations_file: Optional[str] = "clip_durations.tsv",
    durations_sep: str = "\t",
    durations_clip_col: str = "clip",
    durations_dur_col: str = "duration[ms]",
    outlier_csv_n: int = 50,
    pdf_fulltext_n: int = 10,
    md_fulltext_n: int = 20,
    long_text_min_chars: int = 30,
) -> None:
    art = _artifacts(out_dir)
    art.assets_dir.mkdir(parents=True, exist_ok=True)
    art.exports_dir.mkdir(parents=True, exist_ok=True)

    # ── Load metadata ─────────────────────────────────────────────────
    meta_path = dataset_dir / meta_file
    df = _read_meta(meta_path, sep=meta_sep)
    if path_col != "path":
        df = df.rename(columns={path_col: "path"})
    if text_col != "sentence":
        df = df.rename(columns={text_col: "sentence"})

    # ── Duration ──────────────────────────────────────────────────────
    durations = None
    if durations_file:
        dur_path = dataset_dir / durations_file
        if dur_path.exists():
            durations = _read_durations(
                dur_path, sep=durations_sep,
                clip_col=durations_clip_col, dur_col=durations_dur_col,
            )

    if durations is not None:
        df = df.merge(durations, on="path", how="left")
        df["duration_s"] = pd.to_numeric(df["duration_ms"], errors="coerce") / 1000.0
    elif "duration_s" in df.columns:
        df["duration_s"] = pd.to_numeric(df["duration_s"], errors="coerce")
    elif "duration_ms" in df.columns:
        df["duration_s"] = pd.to_numeric(df["duration_ms"], errors="coerce") / 1000.0
    else:
        df["duration_s"] = np.nan

    # ── Derived columns ───────────────────────────────────────────────
    df["char_len"] = df["sentence"].astype(str).str.len()
    df["word_len"] = df["sentence"].astype(str).str.split().str.len()
    df["ratio_sec_per_char"] = df["duration_s"] / df["char_len"].clip(lower=1)
    df["ratio_sec_per_word"] = df["duration_s"] / df["word_len"].clip(lower=1)
    df["chars_per_sec"] = df["char_len"] / df["duration_s"].replace(0, np.nan)
    df["words_per_sec"] = df["word_len"] / df["duration_s"].replace(0, np.nan)

    # ── Core stats ────────────────────────────────────────────────────
    qs = [0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]
    char_q    = _quantiles(df["char_len"], qs)
    word_q    = _quantiles(df["word_len"], qs)
    dur_q     = _quantiles(df["duration_s"], qs)
    ratio_q   = _quantiles(df["ratio_sec_per_char"], qs)
    ratio_rates = _compute_ratio_anomaly_rates(df["ratio_sec_per_char"])

    # ── Extra stats (speakers, empty transcriptions, distributions) ───
    extra_stats: Dict[str, Any] = {}

    n_empty = int((df["sentence"].str.strip() == "").sum())
    extra_stats["n_empty_transcripts"] = n_empty
    extra_stats["pct_empty_transcripts"] = (
        n_empty / len(df) * 100 if len(df) else float("nan")
    )
    spk_col = _speaker_col(df)
    if spk_col:
        extra_stats["speaker_col"] = spk_col
        extra_stats["n_unique_speakers"] = int(df[spk_col].nunique())
        clips_per_spk = df.groupby(spk_col).size()
        extra_stats["clips_per_speaker_mean"] = float(clips_per_spk.mean())
        extra_stats["clips_per_speaker_min"] = int(clips_per_spk.min())
        extra_stats["clips_per_speaker_max"] = int(clips_per_spk.max())
        spk_hours = (
            df.assign(_dur=pd.to_numeric(df["duration_s"], errors="coerce"))
            .groupby(spk_col)
            .agg(clips=(spk_col, "count"), hours=("_dur", "sum"))
            .assign(hours=lambda x: x["hours"] / 3600.0)
            .sort_values("hours", ascending=False)
            .head(10)
        )
        extra_stats["speaker_top_by_hours"] = [
            (str(idx), int(row.clips), float(row.hours))
            for idx, row in spk_hours.iterrows()
        ]

    text = _text_series(df)
    if len(text):
        cyr_share = float(text.str.contains(_CYRILLIC_RE, regex=True).mean())
        if cyr_share > 0.5:
            extra_stats["script_label"] = f"Russian / Cyrillic ({cyr_share * 100:.1f}% of rows)"

    dur_sum = pd.to_numeric(df["duration_s"], errors="coerce").sum()
    extra_stats["total_hours"] = (
        float(dur_sum) / 3600 if not math.isnan(float(dur_sum)) else float("nan")
    )

    for col_name in ("split", "gender", "age", "accents"):
        if col_name in df.columns:
            dist = (
                df[col_name].replace("", "unknown")
                .value_counts()
                .head(10)
                .to_dict()
            )
            extra_stats[f"{col_name}_dist"] = dist

    # ── Charts ────────────────────────────────────────────────────────
    d = pd.to_numeric(df["duration_s"], errors="coerce").dropna().to_numpy(dtype=float)
    if d.size:
        xlim = (0.0, float(np.nanpercentile(d, 99.5))) if d.size > 1000 else None
        _plot_hist(
            d, "Duration Distribution (seconds)", "duration_s",
            art.assets_dir / "duration_seconds_hist.png", bins=90, xlim=xlim,
        )
    _plot_hist(
        df["char_len"].to_numpy(dtype=float),
        "Transcription Length Distribution (characters)", "char_len",
        art.assets_dir / "sentence_length_chars_hist.png", bins=90, color="#10B981",
    )
    _plot_logx_hist(
        df["ratio_sec_per_char"].to_numpy(dtype=float),
        "Ratio: duration_s / char_len  (log scale)", "ratio_sec_per_char (s/char)",
        art.assets_dir / "ratio_sec_per_char_hist_logx.png",
    )
    _plot_logx_hist(
        df["ratio_sec_per_word"].to_numpy(dtype=float),
        "Ratio: duration_s / word_len  (log scale)", "ratio_sec_per_word (s/word)",
        art.assets_dir / "ratio_sec_per_word_hist_logx.png", color="#06B6D4",
    )

    sub_lt = df[df["char_len"] >= long_text_min_chars].dropna(subset=["chars_per_sec"])
    if len(sub_lt):
        _plot_logx_hist(
            sub_lt["chars_per_sec"].to_numpy(dtype=float),
            f"Long-text Chars per Second  (char_len ≥ {long_text_min_chars})",
            "chars_per_sec",
            art.assets_dir / "long_text_chars_per_second_hist_logx.png",
            color="#F59E0B",
        )

    sub_lt_wps = df[df["char_len"] >= long_text_min_chars].dropna(subset=["words_per_sec"])
    if len(sub_lt_wps):
        _plot_logx_hist(
            sub_lt_wps["words_per_sec"].to_numpy(dtype=float),
            f"Long-text Words per Second  (char_len ≥ {long_text_min_chars})",
            "words_per_sec",
            art.assets_dir / "long_text_words_per_second_hist_logx.png",
            color="#EC4899",
        )

    # ── Boxplots ──────────────────────────────────────────────────────
    # Exclude empty transcriptions (char_len == 0) from char/word panels so
    # the long lower-whisker to 0 does not compress the box visually.
    df_nz = df[df["char_len"] > 0]
    n_empty_excluded = len(df) - len(df_nz)
    excl_note = f"\n({n_empty_excluded:,} empty excluded)" if n_empty_excluded > 0 else ""
    _plot_boxplot_grid(
        panels=[
            ("Duration (s)",             pd.to_numeric(df["duration_s"], errors="coerce").dropna().to_numpy(dtype=float)),
            (f"Transcript\nLength (chars){excl_note}", df_nz["char_len"].to_numpy(dtype=float)),
            (f"Transcript\nLength (words){excl_note}", df_nz["word_len"].to_numpy(dtype=float)),
        ],
        title="Distribution Boxplots",
        out_path=art.assets_dir / "boxplot_distributions.png",
        colors=["#3B82F6", "#10B981", "#8B5CF6"],
    )

    ratio_panels: List[Tuple[str, np.ndarray]] = [
        ("ratio s/char",  df["ratio_sec_per_char"].to_numpy(dtype=float)),
        ("ratio s/word",  df["ratio_sec_per_word"].to_numpy(dtype=float)),
    ]
    if len(sub_lt):
        ratio_panels.append(("chars/sec\n(long-text)", sub_lt["chars_per_sec"].to_numpy(dtype=float)))
    if len(sub_lt_wps):
        ratio_panels.append(("words/sec\n(long-text)", sub_lt_wps["words_per_sec"].to_numpy(dtype=float)))
    _plot_boxplot_grid(
        panels=ratio_panels,
        title="Ratio & Rate Boxplots  (log scale)",
        out_path=art.assets_dir / "boxplot_ratios.png",
        log_scales=[True] * len(ratio_panels),
        colors=["#8B5CF6", "#06B6D4", "#F59E0B", "#EC4899"],
    )

    # ── Outlier exports ───────────────────────────────────────────────
    out_high = (
        df.dropna(subset=["duration_s", "ratio_sec_per_char"])
        .sort_values("ratio_sec_per_char", ascending=False)
        .head(outlier_csv_n)[
            _outlier_export_cols(df, [
                "path", "duration_s", "char_len", "word_len",
                "ratio_sec_per_char", "ratio_sec_per_word", "sentence",
            ])
        ]
    )
    out_high.to_csv(art.exports_dir / "outliers_high_ratio_sec_per_char_top.csv", index=False)

    out_fast = (
        sub_lt.dropna(subset=["duration_s", "chars_per_sec"])
        .sort_values("chars_per_sec", ascending=False)
        .head(outlier_csv_n)[
            _outlier_export_cols(df, [
                "path", "duration_s", "char_len", "word_len",
                "chars_per_sec", "ratio_sec_per_char", "sentence",
            ])
        ]
    )
    out_fast.to_csv(art.exports_dir / "outliers_long_text_short_duration_top.csv", index=False)

    # ── Write reports ─────────────────────────────────────────────────
    shared = dict(
        dataset_dir=dataset_dir, meta_file=meta_file, df=df,
        durations_joined=(durations is not None),
        char_q=char_q, word_q=word_q, dur_q=dur_q,
        ratio_q=ratio_q, ratio_rates=ratio_rates,
        out_high=out_high, out_fast=out_fast,
        long_text_min_chars=long_text_min_chars,
        qs=qs, extra_stats=extra_stats,
    )
    _build_markdown(art, md_fulltext_n=md_fulltext_n, **shared)
    _build_pdf(art, pdf_fulltext_n=pdf_fulltext_n, **shared)


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate an audio-metadata analysis report (Markdown + PDF + charts).",
    )
    ap.add_argument("--dataset-dir",      required=True,  type=Path)
    ap.add_argument("--meta-file",        required=True)
    ap.add_argument("--out-dir",          required=True,  type=Path)
    ap.add_argument("--meta-sep",         default="\\t")
    ap.add_argument("--path-col",         default="path")
    ap.add_argument("--text-col",         default="sentence")
    ap.add_argument("--durations-file",   default="clip_durations.tsv",
                    help="Durations filename ('' to disable)")
    ap.add_argument("--durations-sep",    default="\\t")
    ap.add_argument("--durations-clip-col", default="clip")
    ap.add_argument("--durations-dur-col",  default="duration[ms]")
    ap.add_argument("--outlier-csv-n",    type=int, default=50)
    ap.add_argument("--pdf-fulltext-n",   type=int, default=10)
    ap.add_argument("--md-fulltext-n",    type=int, default=20)
    ap.add_argument("--long-text-min-chars", type=int, default=30)

    args = ap.parse_args()

    def _unescape(s: str) -> str:
        return s.encode("utf-8").decode("unicode_escape")

    build_report(
        dataset_dir=args.dataset_dir,
        meta_file=args.meta_file,
        out_dir=args.out_dir,
        meta_sep=_unescape(args.meta_sep),
        path_col=args.path_col,
        text_col=args.text_col,
        durations_file=args.durations_file.strip() or None,
        durations_sep=_unescape(args.durations_sep),
        durations_clip_col=args.durations_clip_col,
        durations_dur_col=args.durations_dur_col,
        outlier_csv_n=args.outlier_csv_n,
        pdf_fulltext_n=args.pdf_fulltext_n,
        md_fulltext_n=args.md_fulltext_n,
        long_text_min_chars=args.long_text_min_chars,
    )


if __name__ == "__main__":
    main()
