"""Generate per-source filtered CSVs of audio clips.

Per the current filtering stage the audio files themselves are NOT removed —
this script only produces a manifest CSV per data source so the user can later
listen / convert them.

Output layout:
    CSV/<source>_<YYYYmmdd-HHMMSS>.csv

Columns (in order):
    audio_name, source, path, duration_s, <all original metadata columns>

Filters applied (per user request 2026-04-21):
    - For sps-corpus-3.0-2026-03-09-de: drop rows where the transcription is
      empty / whitespace only.
    - All sources: keep rows with 0 <= duration_s <= 20.0 (i.e. drop > 20 s or
      missing / non-positive durations).

Run from workspace root:
    python "code/step 2 Filter/generate_filtered_csvs.py"
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = WORKSPACE_ROOT / "CSV"

DURATION_MIN_S = 0.0
DURATION_MAX_S = 20.0


@dataclass
class SourceResult:
    source: str
    out_path: Optional[Path]
    total_rows: int
    kept_rows: int
    dropped_empty_text: int
    dropped_duration: int
    missing_audio_files: int


def _audio_name(path: str) -> str:
    return Path(str(path)).name


def _ensure_out_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _finalize_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Return df with leading unified columns, then the original metadata."""
    leading = ["audio_name", "source", "path", "duration_s"]
    df = df.copy()
    df["source"] = source
    original_cols = [c for c in df.columns if c not in leading]
    return df[leading + original_cols]


def _load_cv(
    meta_path: Path,
    durations_path: Path,
    clips_dir: Path,
    *,
    enforce_transcription: bool,
    check_files: bool,
    source: str,
) -> SourceResult:
    if not meta_path.exists():
        return SourceResult(source, None, 0, 0, 0, 0, 0)

    df = pd.read_csv(meta_path, sep="\t", dtype=str, keep_default_na=False)
    total = len(df)

    dur = pd.read_csv(durations_path, sep="\t", dtype=str, keep_default_na=False)
    dur = dur.rename(columns={"clip": "path", "duration[ms]": "duration_ms"})
    dur["duration_ms"] = pd.to_numeric(dur["duration_ms"], errors="coerce")
    df = df.merge(dur[["path", "duration_ms"]], on="path", how="left")
    df["duration_s"] = df["duration_ms"] / 1000.0

    dropped_empty = 0
    if enforce_transcription:
        text_col = "sentence"
        mask_non_empty = df[text_col].astype(str).str.strip().ne("")
        dropped_empty = int((~mask_non_empty).sum())
        df = df[mask_non_empty]

    mask_dur = df["duration_s"].between(DURATION_MIN_S, DURATION_MAX_S, inclusive="both")
    dropped_duration = int((~mask_dur).sum())
    df = df[mask_dur]

    df["audio_name"] = df["path"].map(_audio_name)
    rel_clips = clips_dir.relative_to(WORKSPACE_ROOT)
    df["path"] = df["path"].map(lambda p: str(rel_clips / str(p)))

    missing = 0
    if check_files:
        missing = int((~df["path"].map(lambda p: (WORKSPACE_ROOT / p).exists())).sum())

    df = _finalize_columns(df, source)

    out_path = DEFAULT_OUT_DIR / f"{source}_{_timestamp()}.csv"
    df.to_csv(out_path, index=False)
    return SourceResult(source, out_path, total, len(df), dropped_empty, dropped_duration, missing)


def _load_sps(
    meta_path: Path,
    audios_dir: Path,
    *,
    check_files: bool,
    source: str,
) -> SourceResult:
    if not meta_path.exists():
        return SourceResult(source, None, 0, 0, 0, 0, 0)

    df = pd.read_csv(meta_path, sep="\t", dtype=str, keep_default_na=False)
    total = len(df)

    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")
    df["duration_s"] = df["duration_ms"] / 1000.0

    mask_non_empty = df["transcription"].astype(str).str.strip().ne("")
    dropped_empty = int((~mask_non_empty).sum())
    df = df[mask_non_empty]

    mask_dur = df["duration_s"].between(DURATION_MIN_S, DURATION_MAX_S, inclusive="both")
    dropped_duration = int((~mask_dur).sum())
    df = df[mask_dur]

    df["audio_name"] = df["audio_file"]
    rel_audios = audios_dir.relative_to(WORKSPACE_ROOT)
    df["path"] = df["audio_file"].map(lambda p: str(rel_audios / str(p)))

    missing = 0
    if check_files:
        missing = int((~df["path"].map(lambda p: (WORKSPACE_ROOT / p).exists())).sum())

    df = _finalize_columns(df, source)

    out_path = DEFAULT_OUT_DIR / f"{source}_{_timestamp()}.csv"
    df.to_csv(out_path, index=False)
    return SourceResult(source, out_path, total, len(df), dropped_empty, dropped_duration, missing)


def _load_thorsten(
    meta_path: Path,
    durations_path: Path,
    wavs_dir: Path,
    *,
    check_files: bool,
    source: str,
) -> SourceResult:
    if not meta_path.exists():
        return SourceResult(source, None, 0, 0, 0, 0, 0)

    df = pd.read_csv(meta_path, sep="\t", dtype=str, keep_default_na=False)
    total = len(df)

    dur = pd.read_csv(durations_path, sep="\t", dtype=str, keep_default_na=False)
    dur = dur.rename(columns={"clip": "path", "duration[ms]": "duration_ms"})
    dur["duration_ms"] = pd.to_numeric(dur["duration_ms"], errors="coerce")
    df = df.merge(dur[["path", "duration_ms"]], on="path", how="left")
    df["duration_s"] = df["duration_ms"] / 1000.0

    mask_non_empty = df["sentence"].astype(str).str.strip().ne("")
    dropped_empty = int((~mask_non_empty).sum())
    df = df[mask_non_empty]

    mask_dur = df["duration_s"].between(DURATION_MIN_S, DURATION_MAX_S, inclusive="both")
    dropped_duration = int((~mask_dur).sum())
    df = df[mask_dur]

    df["audio_name"] = df["path"].map(lambda p: f"{p}.wav")
    rel_wavs = wavs_dir.relative_to(WORKSPACE_ROOT)
    df["path"] = df["path"].map(lambda p: str(rel_wavs / f"{p}.wav"))

    missing = 0
    if check_files:
        missing = int((~df["path"].map(lambda p: (WORKSPACE_ROOT / p).exists())).sum())

    df = _finalize_columns(df, source)

    out_path = DEFAULT_OUT_DIR / f"{source}_{_timestamp()}.csv"
    df.to_csv(out_path, index=False)
    return SourceResult(source, out_path, total, len(df), dropped_empty, dropped_duration, missing)


def _load_kaggle(
    transcript_path: Path,
    archive_dir: Path,
    *,
    check_files: bool,
    source: str,
) -> SourceResult:
    if not transcript_path.exists():
        return SourceResult(source, None, 0, 0, 0, 0, 0)

    cols = ["rel_path", "sentence", "sentence_normalized", "duration_s_raw"]
    df = pd.read_csv(
        transcript_path,
        sep="|",
        header=None,
        names=cols,
        dtype=str,
        keep_default_na=False,
        engine="python",
    )
    total = len(df)

    df["duration_s"] = pd.to_numeric(df["duration_s_raw"], errors="coerce")

    mask_non_empty = df["sentence"].astype(str).str.strip().ne("")
    dropped_empty = int((~mask_non_empty).sum())
    df = df[mask_non_empty]

    mask_dur = df["duration_s"].between(DURATION_MIN_S, DURATION_MAX_S, inclusive="both")
    dropped_duration = int((~mask_dur).sum())
    df = df[mask_dur]

    df["audio_name"] = df["rel_path"].map(_audio_name)
    rel_archive = archive_dir.relative_to(WORKSPACE_ROOT)
    df["path"] = df["rel_path"].map(lambda p: str(rel_archive / str(p)))
    df = df.drop(columns=["rel_path", "duration_s_raw"])

    missing = 0
    if check_files:
        missing = int((~df["path"].map(lambda p: (WORKSPACE_ROOT / p).exists())).sum())

    df = _finalize_columns(df, source)

    out_path = DEFAULT_OUT_DIR / f"{source}_{_timestamp()}.csv"
    df.to_csv(out_path, index=False)
    return SourceResult(source, out_path, total, len(df), dropped_empty, dropped_duration, missing)


def build_all(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    check_files: bool = False,
    only: Optional[set[str]] = None,
) -> list[SourceResult]:
    global DEFAULT_OUT_DIR
    DEFAULT_OUT_DIR = out_dir
    _ensure_out_dir(out_dir)

    jobs: list[tuple[str, Callable[[], SourceResult]]] = [
        (
            "cv-corpus-25.0-2026-03-09-de",
            lambda: _load_cv(
                meta_path=WORKSPACE_ROOT / "Mozilla/cv-corpus-25.0-2026-03-09/de/validate_final.tsv",
                durations_path=WORKSPACE_ROOT / "Mozilla/cv-corpus-25.0-2026-03-09/de/clip_durations.tsv",
                clips_dir=WORKSPACE_ROOT / "Mozilla/cv-corpus-25.0-2026-03-09/de/clips",
                enforce_transcription=False,
                check_files=check_files,
                source="cv-corpus-25.0-2026-03-09-de",
            ),
        ),
        (
            "sps-corpus-3.0-2026-03-09-de",
            lambda: _load_sps(
                meta_path=WORKSPACE_ROOT / "Mozilla/sps-corpus-3.0-2026-03-09-de/ss-corpus-de.tsv",
                audios_dir=WORKSPACE_ROOT / "Mozilla/sps-corpus-3.0-2026-03-09-de/audios",
                check_files=check_files,
                source="sps-corpus-3.0-2026-03-09-de",
            ),
        ),
        (
            "openslr-thorsten-de",
            lambda: _load_thorsten(
                meta_path=WORKSPACE_ROOT / "openslr/thorsten-de/metadata_with_header.tsv",
                durations_path=WORKSPACE_ROOT / "openslr/thorsten-de/clip_durations.tsv",
                wavs_dir=WORKSPACE_ROOT / "openslr/thorsten-de/wavs",
                check_files=check_files,
                source="openslr-thorsten-de",
            ),
        ),
        (
            "kaggle-archive-de",
            lambda: _load_kaggle(
                transcript_path=WORKSPACE_ROOT / "kaggle/archive/transcript.txt",
                archive_dir=WORKSPACE_ROOT / "kaggle/archive",
                check_files=check_files,
                source="kaggle-archive-de",
            ),
        ),
    ]

    results: list[SourceResult] = []
    for name, run in jobs:
        if only is not None and name not in only:
            continue
        print(f"[{name}] processing...", flush=True)
        try:
            r = run()
        except FileNotFoundError as exc:
            print(f"  skipped: {exc}")
            continue
        if r.out_path is None:
            print(f"  skipped: source metadata not found")
            continue
        results.append(r)
        print(
            f"  total={r.total_rows} kept={r.kept_rows} "
            f"dropped_empty_text={r.dropped_empty_text} dropped_duration={r.dropped_duration} "
            f"missing_audio_files={r.missing_audio_files}"
        )
        print(f"  -> {r.out_path.relative_to(WORKSPACE_ROOT)}")
    return results


def _print_summary(results: list[SourceResult]) -> None:
    print("\n=== Summary ===")
    print(f"{'source':<35} {'total':>8} {'kept':>8} {'empty_text':>11} {'dur_drop':>9} {'missing':>8}")
    for r in results:
        print(
            f"{r.source:<35} {r.total_rows:>8d} {r.kept_rows:>8d} "
            f"{r.dropped_empty_text:>11d} {r.dropped_duration:>9d} {r.missing_audio_files:>8d}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for CSVs")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Verify that every kept audio path actually exists on disk (slower).",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        choices=[
            "cv-corpus-25.0-2026-03-09-de",
            "sps-corpus-3.0-2026-03-09-de",
            "openslr-thorsten-de",
            "kaggle-archive-de",
        ],
        help="Only process the given source(s). Defaults to all.",
    )
    args = parser.parse_args()

    results = build_all(
        out_dir=args.out_dir,
        check_files=args.check_files,
        only=set(args.only) if args.only else None,
    )
    _print_summary(results)


if __name__ == "__main__":
    main()
