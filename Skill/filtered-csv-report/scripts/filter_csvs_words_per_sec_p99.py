"""Filter unified CSVs by per-source words_per_sec tails (p1 & p99) and text tags.

Goal:
  For each source's *latest* unified CSV in a given `--csv-dir`, compute
  `words_per_sec` exactly like `generate_filtered_csv_report.py`, then
  DROP rows whose `words_per_sec` is finite and either:

  - `> p99`  (fast tail)
  - `< p1`   (slow tail)

  Thresholds are computed per-source on that source's distribution.
  Write the filtered CSVs to `--out-csv-dir`.

Text-based filtering:
  Some datasets include bracketed tags in the transcript, e.g. ``[disfluency]``.
  Use ``--drop-text-regex`` to drop rows whose transcript matches a regex.

Why:
  When you listen to the `words_per_sec` tails, a chunk of
  clips can be genuinely "too fast" or "too slow". This script creates a new filtered
  CSV set so you can re-generate the PDF reports and outlier lists on the
  cleaned distribution.

Run (workspace root):
  python "Skill/filtered-csv-report/scripts/filter_csvs_words_per_sec_p99.py" \
      --csv-dir "CSV" \
      --out-csv-dir "report/20260430-1139/filtered_csvs"
"""

from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from generate_filtered_csv_report import (  # shared logic / constants
    DEFAULT_CSV_DIR,
    WORKSPACE_ROOT,
    _detect_text_col,
    _latest_csv_per_source,
)


def _words_per_sec_and_quantiles(
    df_raw: pd.DataFrame, *, text_col: str
) -> Tuple[np.ndarray, float, float]:
    """Compute words_per_sec array and its (p1, p99) for this DF."""
    df = df_raw.copy()
    df["duration_s"] = pd.to_numeric(df.get("duration_s", ""), errors="coerce")
    text = df[text_col].astype(str).fillna("")
    text_stripped = text.str.strip()
    wlen = text_stripped.str.split().map(len).astype(float).to_numpy()
    dur = df["duration_s"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        wps = np.where(dur > 0, wlen / dur, np.nan)
    v = wps[np.isfinite(wps)]
    if v.size:
        p1, p99 = np.quantile(v, [0.01, 0.99])
        return wps, float(p1), float(p99)
    return wps, float("nan"), float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    ap.add_argument("--out-csv-dir", type=Path, required=True)
    ap.add_argument("--text-col", default=None, help="Force transcript column name across sources.")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument(
        "--drop-text-regex",
        default=r"\[disfluency\]",
        help=(
            "Drop rows whose transcript matches this regex (case-insensitive). "
            "Default drops '[disfluency]'. Set to '' to disable."
        ),
    )
    ap.add_argument(
        "--keep-low-p1",
        action="store_true",
        help="Do NOT drop rows where words_per_sec < p1 (slow tail).",
    )
    ap.add_argument(
        "--keep-nonfinite",
        action="store_true",
        help="Keep rows where words_per_sec is NaN/inf (default keeps them).",
    )
    args = ap.parse_args()

    only = set(args.only) if args.only else None
    exclude = set(args.exclude) if args.exclude else None

    latest: Dict[str, Path] = _latest_csv_per_source(args.csv_dir)
    if only:
        latest = {k: v for k, v in latest.items() if k in only}
    if exclude:
        latest = {k: v for k, v in latest.items() if k not in exclude}
    if not latest:
        raise SystemExit(f"No CSVs found in {args.csv_dir} after applying --only/--exclude.")

    args.out_csv_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    drop_low_p1 = not args.keep_low_p1
    text_re = None
    if (args.drop_text_regex or "").strip():
        text_re = re.compile(args.drop_text_regex, flags=re.IGNORECASE)
    mode = "> p99" + (" and < p1" if drop_low_p1 else "")
    if text_re is not None:
        mode += f" and drop_text~/{args.drop_text_regex}/i"
    print(f"Filtering per-source words_per_sec {mode}")
    print(f"  in : {args.csv_dir.relative_to(WORKSPACE_ROOT) if args.csv_dir.is_absolute() else args.csv_dir}")
    print(f"  out: {args.out_csv_dir.relative_to(WORKSPACE_ROOT) if args.out_csv_dir.is_absolute() else args.out_csv_dir}")
    print("")

    for src, p in sorted(latest.items()):
        df_raw = pd.read_csv(p, dtype=str, keep_default_na=False)
        text_col = _detect_text_col(df_raw, args.text_col)

        wps, p1, p99 = _words_per_sec_and_quantiles(df_raw, text_col=text_col)
        finite = np.isfinite(wps)
        drop = np.zeros_like(finite, dtype=bool)
        if np.isfinite(p99):
            drop |= finite & (wps > p99)
        if drop_low_p1 and np.isfinite(p1):
            drop |= finite & (wps < p1)
        if text_re is not None:
            text = df_raw[text_col].astype(str).fillna("")
            drop |= text.str.contains(text_re, regex=True, na=False).to_numpy(dtype=bool)
        if args.keep_nonfinite:
            # explicitly keep nonfinite; default behaviour already keeps them.
            pass

        df_out = df_raw.loc[~drop].copy()
        out_path = args.out_csv_dir / f"{src}_{ts}.csv"
        df_out.to_csv(out_path, index=False)

        n_in = len(df_raw)
        n_drop = int(drop.sum())
        n_out = len(df_out)
        pct = (100.0 * n_drop / n_in) if n_in else 0.0
        out_abs = out_path.resolve()
        out_disp = out_abs.relative_to(WORKSPACE_ROOT).as_posix()
        print(
            f"- {src}: rows {n_in:,} -> {n_out:,}  (dropped {n_drop:,} = {pct:.3f}%)"
            f"  ·  p1={p1:.6g}  ·  p99={p99:.6g}  ·  text_col={text_col}"
        )
        print(f"  wrote: {out_disp}")


if __name__ == "__main__":
    main()

