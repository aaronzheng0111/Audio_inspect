"""Generate a human-inspection Markdown list for outlier audio clips.

Reads the two outlier CSVs produced by the ``audio-metadata-report`` skill
(``outliers_high_ratio_sec_per_char_top.csv`` and
``outliers_long_text_short_duration_top.csv``) and emits a single Markdown
report listing the top-N clips per dataset and category, with:

- filename
- metric values (duration_s, char_len, ratio / chars_per_sec)
- absolute file path on disk  (✓ / ✗ MISSING existence check)
- full transcript text

Usage (repeat ``--dataset`` once per dataset):

    python generate_outlier_inspection_list.py \
        --dataset "Common Voice 25.0 (de)::report/cv-.../exports::Mozilla/cv-.../de/clips" \
        --dataset "OpenSLR Thorsten-de::report/openslr-thorsten-de/exports::openslr/thorsten-de/wavs::.wav" \
        --out report/outlier_inspection_list.md

``--dataset`` format:  ``name::export_dir::clips_dir[::path_suffix]``

- ``name``         — section heading in the markdown
- ``export_dir``   — folder containing the two ``outliers_*.csv`` files
- ``clips_dir``    — folder containing the audio files
- ``path_suffix``  — optional, appended to the CSV ``path`` column when the
                    CSV stores a bare stem (e.g. Thorsten clips are hashes
                    without the ``.wav`` extension)
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class DatasetSpec:
    name: str
    export_dir: Path
    clips_dir: Path
    path_suffix: str = ""

    @classmethod
    def parse(cls, spec: str) -> "DatasetSpec":
        parts = spec.split("::")
        if len(parts) not in (3, 4):
            raise ValueError(
                f"--dataset must be 'name::export_dir::clips_dir[::suffix]', got: {spec!r}"
            )
        name, export_dir, clips_dir = parts[0], Path(parts[1]), Path(parts[2])
        suffix = parts[3] if len(parts) == 4 else ""
        return cls(name=name, export_dir=export_dir, clips_dir=clips_dir, path_suffix=suffix)


CATEGORIES: List[Tuple[str, str, List[str]]] = [
    (
        "Audio Long / Text Short (high s/char)",
        "outliers_high_ratio_sec_per_char_top.csv",
        ["duration_s", "char_len", "ratio_sec_per_char"],
    ),
    (
        "Text Long / Audio Short (high chars/s)",
        "outliers_long_text_short_duration_top.csv",
        ["duration_s", "char_len", "chars_per_sec"],
    ),
]


def _fmt_metric(row: dict, key: str) -> str:
    if key not in row or row[key] == "":
        return f"{key}=n/a"
    try:
        return f"{key}={float(row[key]):.3f}"
    except ValueError:
        return f"{key}={row[key]}"


def _verify(p: Path) -> str:
    return "✓" if p.exists() else "✗ MISSING"


def _resolve_clip(clip: str, clips_dir: Path, suffix: str) -> Tuple[str, Path]:
    fname = clip + suffix if suffix and not clip.endswith(suffix) else clip
    return fname, (clips_dir / fname).resolve()


def build_markdown(datasets: List[DatasetSpec], top_n: int) -> str:
    lines: List[str] = [
        "# Outlier Audio Inspection List",
        "",
        f"For each dataset and anomaly category below, the top {top_n} outliers "
        "with an absolute file path and the full transcript text. Paste the "
        "path into a player (QuickTime / VLC / `afplay`) to listen.",
        "",
        "> macOS quick-play: `afplay \"<path>\"`",
        "",
    ]

    for ds in datasets:
        lines.append(f"## {ds.name}")
        lines.append("")
        lines.append(f"- Clips folder: `{ds.clips_dir.resolve()}`")
        lines.append("")

        for title, csv_name, metric_cols in CATEGORIES:
            csv_path = ds.export_dir / csv_name
            lines.append(f"### {title}")
            lines.append("")
            if not csv_path.exists():
                lines.append(f"_CSV not found: `{csv_path}`_")
                lines.append("")
                continue
            with open(csv_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))[:top_n]
            if not rows:
                lines.append("_No outliers in this category._")
                lines.append("")
                continue
            for i, r in enumerate(rows, 1):
                fname, full_path = _resolve_clip(r["path"], ds.clips_dir, ds.path_suffix)
                metrics = "  ".join(_fmt_metric(r, c) for c in metric_cols)
                sentence = (r.get("sentence") or "").strip() or "_(empty)_"
                lines.append(f"**{i}. `{fname}`**  {_verify(full_path)}")
                lines.append(f"- {metrics}")
                lines.append(f"- path: `{full_path}`")
                lines.append(f"- text: {sentence}")
                lines.append("")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a Markdown inspection list for audio outliers.",
    )
    ap.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Repeatable. Format: 'name::export_dir::clips_dir[::path_suffix]'",
    )
    ap.add_argument("--out", type=Path, required=True, help="Output .md path")
    ap.add_argument("--top-n", type=int, default=20, help="Max entries per category (default 20)")
    args = ap.parse_args()

    datasets = [DatasetSpec.parse(s) for s in args.dataset]
    md = build_markdown(datasets, top_n=args.top_n)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")

    missing = md.count("✗ MISSING")
    present = md.count("✓")
    print(f"Wrote {args.out}  ({len(md):,} chars)")
    print(f"Entries: ✓ verified={present}   ✗ missing={missing}")


if __name__ == "__main__":
    main()
