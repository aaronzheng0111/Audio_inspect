#!/usr/bin/env python3
"""Build a unified metadata TSV for VoxForge Russian corpus."""

from __future__ import annotations

import argparse
import wave
from pathlib import Path


def _wav_duration_ms(wav_path: Path) -> int | None:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return None
            return int(round(frames * 1000 / rate))
    except (wave.Error, OSError):
        return None


def build_metadata(dataset_dir: Path, out_path: Path) -> None:
    rows: list[str] = []
    header = "path\tsentence\tspeaker\tduration_ms"
    rows.append(header)

    speaker_dirs = sorted(
        p for p in dataset_dir.iterdir()
        if p.is_dir() and (p / "etc" / "PROMPTS").is_file()
    )

    missing_wav = 0
    bad_duration = 0

    for speaker_dir in speaker_dirs:
        prompts_path = speaker_dir / "etc" / "PROMPTS"
        speaker = speaker_dir.name
        for line in prompts_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            rel_audio = parts[0]
            sentence = parts[1]
            clip_id = Path(rel_audio).name
            wav_path = speaker_dir / "wav" / f"{clip_id}.wav"
            if not wav_path.is_file():
                missing_wav += 1
                continue
            duration_ms = _wav_duration_ms(wav_path)
            if duration_ms is None or duration_ms <= 0:
                bad_duration += 1
                continue
            rel_path = f"{speaker}/wav/{clip_id}.wav"
            sentence = sentence.replace("\t", " ").replace("\n", " ")
            rows.append(f"{rel_path}\t{sentence}\t{speaker}\t{duration_ms}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    clip_count = len(rows) - 1
    print(f"Wrote {clip_count} rows to {out_path}")
    print(f"missing_wav={missing_wav} bad_duration={bad_duration} speakers={len(speaker_dirs)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build VoxForge metadata TSV")
    ap.add_argument("--dataset-dir", type=Path, required=True)
    ap.add_argument("--out-file", type=Path, required=True)
    args = ap.parse_args()
    build_metadata(args.dataset_dir, args.out_file)


if __name__ == "__main__":
    main()
