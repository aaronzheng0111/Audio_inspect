"""Listening-list helper.

For one ratio metric (default ``words_per_sec``) and the five standard
outlier rules (``> p99``, ``> p99.9``, ``> Tukey high``, ``< p1``,
``< Tukey low``), pick the most extreme N rows per source × rule and
write a flat .txt file with absolute paths + transcripts so you can
listen through them.

Pairs with ``generate_filtered_csv_report.py`` (re-uses its
``RATIO_METRICS`` definition and ``load_sources`` so the metric
calculations stay identical).

Run from workspace root:
    python "Skill/filtered-csv-report/scripts/list_outlier_audios.py" \
        --metric words_per_sec --top-n 10 --exclusive-buckets \
        --out "report/outlier_words_per_sec_listen.txt"
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from generate_filtered_csv_report import (  # noqa: E402
    DEFAULT_CSV_DIR,
    RATIO_METRICS,
    WORKSPACE_ROOT,
    load_sources,
)


# Five rules in display order.  ``ascending`` decides how we sort the
# matched rows when picking the top-N: low-side rules keep the smallest
# values (most extreme), high-side rules keep the largest.
_RULE_DEFS = [
    ("> p99",        "high", False),
    ("> p99.9",      "high", False),
    ("> Tukey high", "high", False),
    ("< p1",         "low",  True),
    ("< Tukey low",  "low",  True),
]


def _fmt_v(v: float) -> str:
    return "—" if not math.isfinite(v) else f"{v:.4g}"


def _absolute(rel_path: str) -> str:
    p = Path(rel_path)
    if p.is_absolute():
        return str(p)
    return str((WORKSPACE_ROOT / p).resolve())


def _rule_masks(values: np.ndarray, stats, exclusive: bool) -> dict[str, np.ndarray]:
    if not exclusive:
        return {
            "> p99": values > stats.p99,
            "> p99.9": values > stats.p999,
            "> Tukey high": values > stats.tukey_high,
            "< p1": values < stats.p1,
            "< Tukey low": values < stats.tukey_low,
        }

    # Exclusive buckets (disjoint):
    # - > p99.9 keeps the far tail
    # - > p99 keeps the slice between p99 and p99.9
    # - > Tukey high keeps what is above Tukey high but not already
    #   captured by p99 / p99.9 buckets
    high_p999 = values > stats.p999
    high_p99 = (values > stats.p99) & (~high_p999)
    high_tukey = (values > stats.tukey_high) & (~high_p99) & (~high_p999)

    # Low side mirrors the same disjoint design.
    low_p1 = values < stats.p1
    low_tukey = (values < stats.tukey_low) & (~low_p1)

    return {
        "> p99": high_p99,
        "> p99.9": high_p999,
        "> Tukey high": high_tukey,
        "< p1": low_p1,
        "< Tukey low": low_tukey,
    }


def _pick_topn(df: pd.DataFrame, attr: str, n: int, ascending: bool) -> pd.DataFrame:
    df = df[df[attr].notna()]
    if df.empty:
        return df
    if ascending:
        return df.nsmallest(n, attr)
    return df.nlargest(n, attr)


def _rule_note(rule_name: str, stats, exclusive: bool) -> str:
    if not exclusive:
        return ""
    if rule_name == "> p99":
        return f"bucket=({_fmt_v(stats.p99)}, {_fmt_v(stats.p999)}]"
    if rule_name == "> p99.9":
        return f"bucket=({_fmt_v(stats.p999)}, +inf)"
    if rule_name == "> Tukey high":
        return f"bucket=({_fmt_v(stats.tukey_high)}, +inf) minus (>p99)"
    if rule_name == "< p1":
        return f"bucket=(-inf, {_fmt_v(stats.p1)})"
    if rule_name == "< Tukey low":
        return f"bucket=(-inf, {_fmt_v(stats.tukey_low)}) minus (<p1)"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument(
        "--metric",
        default="words_per_sec",
        choices=[m["name"] for m in RATIO_METRICS],
        help="Ratio metric to investigate (default: words_per_sec)",
    )
    parser.add_argument(
        "--top-n", type=int, default=10,
        help="Rows to keep per (source × rule). Default 10.",
    )
    parser.add_argument(
        "--out", type=Path, required=True,
        help="Output .txt path",
    )
    parser.add_argument("--text-col", default=None,
                        help="Force a transcript column name across sources.")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument(
        "--include-paths-only",
        action="store_true",
        help=("Also write a sibling ``*.paths.txt`` with one absolute path "
              "per line (handy for piping into afplay or a player)."),
    )
    parser.add_argument(
        "--exclusive-buckets",
        action="store_true",
        help=(
            "Make rule groups mutually exclusive so clips do not repeat across "
            "overlapping rules (especially >p99 / >p99.9 / >Tukey high)."
        ),
    )
    args = parser.parse_args()

    only = set(args.only) if args.only else None
    exclude = set(args.exclude) if args.exclude else None

    sources = load_sources(
        args.csv_dir,
        text_col_override=args.text_col,
        only=only,
        exclude=exclude,
    )
    metric = next(m for m in RATIO_METRICS if m["name"] == args.metric)
    attr = metric["attr"]

    print(
        f"Listing top {args.top_n} outliers per (source × rule) for "
        f"metric={args.metric} ... mode="
        f"{'exclusive' if args.exclusive_buckets else 'inclusive'}"
    )

    lines: List[str] = []
    paths_only: List[str] = []
    lines.append(f"# Outlier listening list  ·  metric: {args.metric}  "
                 f"({metric['unit']})")
    lines.append(f"# Sources: {', '.join(s.name for s in sources)}")
    lines.append(f"# Top-N per rule: {args.top_n}")
    lines.append(
        "# Rule mode: "
        + ("exclusive (disjoint buckets)" if args.exclusive_buckets else "inclusive (overlap allowed)")
    )
    lines.append(f"# Generated by list_outlier_audios.py")
    lines.append("")

    for s in sources:
        stats = s.outliers[args.metric]
        lines.append("=" * 80)
        lines.append(f"[{s.name}]  metric={args.metric}")
        if stats.n:
            lines.append(
                f"  n={stats.n:,}  ·  p1={_fmt_v(stats.p1)}  ·  "
                f"p99={_fmt_v(stats.p99)}  ·  p99.9={_fmt_v(stats.p999)}  ·  "
                f"Tukey low={_fmt_v(stats.tukey_low)}  ·  "
                f"Tukey high={_fmt_v(stats.tukey_high)}"
            )
        else:
            lines.append("  (no data)")
        lines.append("=" * 80)
        lines.append("")

        v_full = s.df[attr].to_numpy(dtype=float)
        rule_lookup = {r.name: r for r in stats.rules}
        masks = _rule_masks(v_full, stats, exclusive=args.exclusive_buckets)

        for rule_name, side, ascending in _RULE_DEFS:
            r = rule_lookup.get(rule_name)
            thr = r.threshold if r else float("nan")
            mask = masks[rule_name]
            count = int(mask.sum())
            pct = (count / stats.n * 100.0) if stats.n else 0.0
            note = _rule_note(rule_name, stats, args.exclusive_buckets)
            header = (
                f"----- {rule_name:<14}  threshold={_fmt_v(thr)}  "
                f"matched={count:,} ({pct:.3f}%)"
                + (f"  ·  {note}" if note else "")
                + "  -----"
            )
            lines.append(header)

            if count == 0 or stats.n == 0:
                lines.append("  (no rows)")
                lines.append("")
                continue

            sub = s.df.loc[mask].copy()
            sub = _pick_topn(sub, attr, args.top_n, ascending)

            for i, (_, row) in enumerate(sub.iterrows(), 1):
                abs_path = _absolute(str(row.get("path", "")))
                transcript = str(row.get(s.text_col, "")).strip() or "(empty)"
                duration = float(row.get("duration_s", float("nan")))
                char_len = int(row.get("__char_len", 0))
                word_len = int(row.get("__word_len", 0))
                value = float(row.get(attr, float("nan")))

                lines.append(
                    f"  [{i:>2}] {args.metric}={value:.4g}  "
                    f"duration_s={duration:.3f}  "
                    f"word_len={word_len}  char_len={char_len}"
                )
                lines.append(f"       {abs_path}")
                lines.append(f"       > {transcript}")
                lines.append("")
                paths_only.append(abs_path)

        lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")

    if args.include_paths_only:
        paths_path = args.out.with_suffix(".paths.txt")
        paths_path.write_text("\n".join(paths_only) + "\n", encoding="utf-8")

    print(f"\nWrote: {args.out.relative_to(WORKSPACE_ROOT) if args.out.is_absolute() else args.out}")
    if args.include_paths_only:
        rel = paths_path.relative_to(WORKSPACE_ROOT) if paths_path.is_absolute() else paths_path
        print(f"      {rel}  (one absolute path per line)")


if __name__ == "__main__":
    main()
