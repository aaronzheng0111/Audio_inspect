"""Take N sample rows from each CSV in ``CSV/`` and convert them with ffmpeg
to 16 kHz mono WAV, grouped by source under ``sample_audio/<source>/``.

The source-name is derived from the CSV filename (``<source>_<timestamp>.csv``)
and each output wav is named after the original ``audio_name`` column with the
extension swapped to ``.wav``.  A small ``_manifest.csv`` is written per source
so you can correlate the converted sample with its original row (``path``,
``duration_s``, transcription, etc.).

Run from the workspace root:

    python "code/step 2 Filter/convert_samples_ffmpeg.py"
    python "code/step 2 Filter/convert_samples_ffmpeg.py" --samples 20 --seed 7
    python "code/step 2 Filter/convert_samples_ffmpeg.py" --only sps-corpus-3.0-2026-03-09-de
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_DIR = WORKSPACE_ROOT / "CSV"
DEFAULT_OUT_DIR = WORKSPACE_ROOT / "sample_audio"

TARGET_SR = 16_000
TARGET_CHANNELS = 1

_TIMESTAMP_SUFFIX_RE = re.compile(r"_\d{8}-\d{6}$")


@dataclass
class ConvertResult:
    source: str
    out_dir: Path
    requested: int
    converted: int
    skipped: int
    failed: int


def _source_name_from_csv(csv_path: Path) -> str:
    stem = csv_path.stem
    return _TIMESTAMP_SUFFIX_RE.sub("", stem)


def _latest_csv_per_source(csv_dir: Path) -> dict[str, Path]:
    """If multiple timestamped CSVs exist per source, keep only the newest."""
    latest: dict[str, Path] = {}
    for p in sorted(csv_dir.glob("*.csv")):
        if p.name.startswith("_"):
            continue
        src = _source_name_from_csv(p)
        prev = latest.get(src)
        if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
            latest[src] = p
    return latest


def _sample_rows(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(df) <= n:
        return df.reset_index(drop=True)
    return df.sample(n=n, random_state=seed).sort_index().reset_index(drop=True)


def _convert_one(
    ffmpeg_bin: str,
    src_path: Path,
    dst_path: Path,
    overwrite: bool,
) -> str:
    """Return 'converted', 'skipped' or 'failed'."""
    if dst_path.exists() and not overwrite:
        return "skipped"
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(src_path),
        "-ac", str(TARGET_CHANNELS),
        "-ar", str(TARGET_SR),
        "-vn",
        str(dst_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        print(f"    ffmpeg binary not found: {ffmpeg_bin}")
        return "failed"
    if proc.returncode != 0:
        print(f"    FAILED {src_path.name}: {proc.stderr.strip()[:200]}")
        return "failed"
    return "converted"


def process_source(
    csv_path: Path,
    out_root: Path,
    *,
    samples: int,
    seed: int,
    ffmpeg_bin: str,
    overwrite: bool,
) -> ConvertResult:
    source = _source_name_from_csv(csv_path)
    out_dir = out_root / source
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    sampled = _sample_rows(df, samples, seed)

    converted = skipped = failed = 0
    rows_out = []
    print(f"[{source}] sampling {len(sampled)} / {len(df)} -> {out_dir.relative_to(WORKSPACE_ROOT)}")

    for _, row in sampled.iterrows():
        rel_src = row["path"]
        src_full = WORKSPACE_ROOT / rel_src
        audio_name = row.get("audio_name") or src_full.name
        dst_stem = Path(audio_name).stem
        dst_full = out_dir / f"{dst_stem}.wav"

        if not src_full.exists():
            print(f"    MISSING source file: {rel_src}")
            failed += 1
            continue

        status = _convert_one(ffmpeg_bin, src_full, dst_full, overwrite=overwrite)
        if status == "converted":
            converted += 1
        elif status == "skipped":
            skipped += 1
        else:
            failed += 1

        out_rel = dst_full.relative_to(WORKSPACE_ROOT)
        rows_out.append({
            "audio_name": dst_full.name,
            "source": source,
            "sample_path": str(out_rel),
            "original_path": rel_src,
            "duration_s": row.get("duration_s", ""),
            "transcription": row.get("transcription") or row.get("sentence") or "",
        })

    if rows_out:
        manifest = pd.DataFrame(rows_out)
        manifest_path = out_dir / "_manifest.csv"
        manifest.to_csv(manifest_path, index=False)

    return ConvertResult(
        source=source,
        out_dir=out_dir,
        requested=len(sampled),
        converted=converted,
        skipped=skipped,
        failed=failed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--samples", type=int, default=10, help="Samples per source (default 10).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing wav files.")
    parser.add_argument(
        "--only",
        nargs="*",
        help="Restrict to given source names, e.g. sps-corpus-3.0-2026-03-09-de.",
    )
    args = parser.parse_args()

    if not Path(args.ffmpeg).exists() and not shutil.which(args.ffmpeg):
        raise SystemExit(f"ffmpeg not found at {args.ffmpeg!r}. Install via 'brew install ffmpeg'.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    latest = _latest_csv_per_source(args.csv_dir)
    if args.only:
        keep = set(args.only)
        latest = {k: v for k, v in latest.items() if k in keep}
        missing = keep - set(latest)
        for m in sorted(missing):
            print(f"[warn] requested source not found in {args.csv_dir}: {m}")

    if not latest:
        raise SystemExit(f"No matching CSVs found in {args.csv_dir}")

    results: list[ConvertResult] = []
    for src, csv_path in sorted(latest.items()):
        results.append(
            process_source(
                csv_path,
                args.out_dir,
                samples=args.samples,
                seed=args.seed,
                ffmpeg_bin=args.ffmpeg,
                overwrite=args.overwrite,
            )
        )

    print("\n=== Summary ===")
    print(f"{'source':<35} {'req':>4} {'ok':>4} {'skip':>5} {'fail':>5}  out_dir")
    for r in results:
        print(
            f"{r.source:<35} {r.requested:>4d} {r.converted:>4d} "
            f"{r.skipped:>5d} {r.failed:>5d}  {r.out_dir.relative_to(WORKSPACE_ROOT)}"
        )


if __name__ == "__main__":
    main()
