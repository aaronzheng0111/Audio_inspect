#!/usr/bin/env python3
"""Build a reproducible tar.zst of audio + CSV metadata from filtered CSVs.

Features
--------
- Stratified reservoir sampling per source (default: cv=3, kaggle=3, openslr=3, sps=1).
- Optional CSV embedding: subset rows, full filtered CSVs, both, or none.
- Sorted manifest (-T) for stable archive member order.
- On macOS, passes COPYFILE_DISABLE / COPY_EXTENDED_ATTRIBUTES_DISABLE into tar so
  AppleDouble sidecars (._*) are far less likely to appear inside the archive when
  unpacking on Linux.

Examples
--------
  python3 build_audio_pack.py --dry-run
  python3 build_audio_pack.py --out audio_sample10.tar.zst --write-checksum
  python3 build_audio_pack.py --pack-mode full --sources sps-corpus-3.0-2026-03-09-de \\
      --out german_audio_sps_filtered.tar.zst \\
      --manifest german_audio_sps_filtered.manifest.txt \\
      --include-csv full --write-checksum
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def _default_project_root() -> Path:
    # .../German Audio Dataset/Skill/audio-pack-rsync/scripts/build_audio_pack.py
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class SourceSpec:
    key: str
    csv_name: str  # basename under filtered_csvs/


def default_sources() -> list[SourceSpec]:
    return [
        SourceSpec("cv-corpus-25.0-2026-03-09-de", "cv-corpus-25.0-2026-03-09-de_20260430-115818.csv"),
        SourceSpec("kaggle-archive-de", "kaggle-archive-de_20260430-115818.csv"),
        SourceSpec("openslr-thorsten-de", "openslr-thorsten-de_20260430-115818.csv"),
        SourceSpec("sps-corpus-3.0-2026-03-09-de", "sps-corpus-3.0-2026-03-09-de_20260430-115818.csv"),
    ]


def pack_stem_from_out(out: str) -> str:
    name = Path(out).name
    if name.endswith(".tar.zst"):
        return name[: -len(".tar.zst")]
    return Path(out).stem


def sample_rows(csv_path: Path, n: int, seed: int) -> tuple[list[dict], list[str]]:
    rng = random.Random(seed)
    reservoir: list[dict] = []
    fieldnames: list[str] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames:
            fieldnames = [c for c in reader.fieldnames if c is not None]
        for i, row in enumerate(reader):
            if i < n:
                reservoir.append(row)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = row
    return reservoir, fieldnames


def read_all_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    """Load every data row from a filtered CSV (fine for small/medium files)."""
    rows: list[dict] = []
    fieldnames: list[str] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames:
            fieldnames = [c for c in reader.fieldnames if c is not None]
        for row in reader:
            rows.append(row)
    return rows, fieldnames


def write_subset_csv(dest: Path, rows: list[dict], fieldnames: list[str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def tar_subprocess_env() -> dict[str, str]:
    """Environment for tar: suppress macOS AppleDouble / xattr copy into archives."""
    env = dict(os.environ)
    if sys.platform == "darwin":
        # Prevents tar from synthesizing or copying ._ companion files / resource forks.
        env["COPYFILE_DISABLE"] = "1"
        env["COPY_EXTENDED_ATTRIBUTES_DISABLE"] = "1"
    return env


def run_tar_create(
    *,
    project_root: Path,
    manifest: Path,
    out: Path,
    zstd_level: int,
) -> int:
    cmd = [
        "tar",
        "-I",
        f"zstd -{zstd_level} -T0",
        "-cf",
        str(out),
        "-C",
        str(project_root),
        "-T",
        str(manifest),
    ]
    print("\n[tar] " + " ".join(repr(c) for c in cmd))
    if sys.platform == "darwin":
        print("      (darwin: COPYFILE_DISABLE=1 COPY_EXTENDED_ATTRIBUTES_DISABLE=1)")
    proc = subprocess.run(cmd, env=tar_subprocess_env(), check=False)
    return proc.returncode


def write_sha256(archive: Path, checksum_path: Path | None) -> Path:
    import hashlib

    h = hashlib.sha256()
    with archive.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    line = f"{h.hexdigest()}  {archive.name}\n"
    dest = checksum_path or archive.with_name(archive.name + ".sha256")
    dest.write_text(line, encoding="utf-8")
    print(f"\n[checksum] wrote {dest}")
    return dest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Dataset root (contains Mozilla/, kaggle/, openslr/, report/). "
        "Default: parent of Skill/ from this script.",
    )
    p.add_argument(
        "--filtered-csv-dir",
        type=Path,
        default=None,
        help="Directory with the four filtered *_20260430-115818.csv files. "
        "Default: <project-root>/report/20260430-115818/filtered_csvs",
    )
    p.add_argument(
        "--pack-mode",
        choices=("sample", "full"),
        default="sample",
        help="sample: reservoir sample per source (--cv/--kaggle/...). "
        "full: every row in each selected source's filtered CSV.",
    )
    p.add_argument(
        "--sources",
        default=None,
        metavar="KEYS",
        help="Comma-separated source keys to include (default: all four). "
        "Keys: cv-corpus-25.0-2026-03-09-de, kaggle-archive-de, "
        "openslr-thorsten-de, sps-corpus-3.0-2026-03-09-de",
    )
    p.add_argument("--out", default="audio_sample10.tar.zst", help="Output .tar.zst under project root.")
    p.add_argument("--manifest", default="audio_sample10.manifest.txt", help="Manifest path under project root.")
    p.add_argument("--cv", type=int, default=3)
    p.add_argument("--kaggle", type=int, default=3)
    p.add_argument("--openslr", type=int, default=3)
    p.add_argument("--sps", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--zstd-level", type=int, default=3)
    p.add_argument(
        "--include-csv",
        choices=("none", "subset", "full", "both"),
        default="subset",
        help="subset=rows under csv_exports/<stem>/; full=each selected source's report CSV; both; none.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print plan only; no files written.")
    p.add_argument(
        "--write-checksum",
        action="store_true",
        help="After tar, write <out>.sha256 (same format as shasum -a 256).",
    )
    p.add_argument(
        "--checksum-out",
        type=Path,
        default=None,
        help="Checksum file path (default: next to --out with .sha256 suffix).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    project_root = (args.project_root or _default_project_root()).expanduser().resolve()
    if not project_root.is_dir():
        print(f"[error] project root not a directory: {project_root}", file=sys.stderr)
        return 2

    filtered_dir = args.filtered_csv_dir
    if filtered_dir is None:
        filtered_dir = project_root / "report/20260430-115818/filtered_csvs"
    else:
        filtered_dir = filtered_dir.expanduser().resolve()

    sources = default_sources()
    csv_by_key: dict[str, Path] = {}
    for spec in sources:
        p = filtered_dir / spec.csv_name
        if not p.is_file():
            print(f"[error] missing filtered CSV: {p}", file=sys.stderr)
            return 2
        csv_by_key[spec.key] = p

    if args.sources:
        want = {s.strip() for s in args.sources.split(",") if s.strip()}
        active_specs = [s for s in sources if s.key in want]
        known = {s.key for s in sources}
        unknown = want - known
        if unknown:
            print(f"[error] unknown --sources keys: {sorted(unknown)}", file=sys.stderr)
            return 2
        if not active_specs:
            print("[error] --sources matched no configured sources", file=sys.stderr)
            return 2
    else:
        active_specs = list(sources)

    counts = {
        "cv-corpus-25.0-2026-03-09-de": args.cv,
        "kaggle-archive-de": args.kaggle,
        "openslr-thorsten-de": args.openslr,
        "sps-corpus-3.0-2026-03-09-de": args.sps,
    }

    stem = pack_stem_from_out(args.out)
    csv_export_rel = f"csv_exports/{stem}"

    audio_rels: list[str] = []
    subset_csv_rels: list[str] = []

    print(f"[root] {project_root}")
    print(f"[filtered_csv_dir] {filtered_dir}")
    print(f"[pack-mode] {args.pack_mode}  [sources] {', '.join(s.key for s in active_specs)}")
    print("[scan]")
    for spec in active_specs:
        csv_path = csv_by_key[spec.key]
        if args.pack_mode == "full":
            rows, fieldnames = read_all_rows(csv_path)
            print(f"  {spec.key}: full read, {len(rows)} rows")
        else:
            n = counts[spec.key]
            rows, fieldnames = sample_rows(csv_path, n, args.seed)
            print(f"  {spec.key}: sample, {len(rows)} rows")
        for row in rows:
            rel = row["path"].strip()
            full = project_root / rel
            ok = full.is_file()
            size = full.stat().st_size if ok else 0
            tag = "OK" if ok else "MISSING"
            print(f"    [{tag:7}] {rel}  ({size:,} bytes)")
            if ok:
                audio_rels.append(rel)

        if args.include_csv in ("subset", "both") and rows and fieldnames:
            dest = project_root / csv_export_rel / csv_path.name
            if not args.dry_run:
                write_subset_csv(dest, rows, fieldnames)
            subset_csv_rels.append(str(dest.relative_to(project_root)))
            print(f"    [csv subset -> {subset_csv_rels[-1]}]")

    if not audio_rels:
        print("[error] no resolvable audio paths", file=sys.stderr)
        return 2

    full_csv_rels: list[str] = []
    if args.include_csv in ("full", "both"):
        full_csv_rels = [
            str(csv_by_key[spec.key].relative_to(project_root)) for spec in active_specs
        ]
        print(f"\n[csv full] +{len(full_csv_rels)} filtered CSV(s) bundled")

    audio_rels = sorted(set(audio_rels))
    all_members = sorted(set(audio_rels) | set(subset_csv_rels) | set(full_csv_rels))

    manifest_path = (project_root / args.manifest).resolve()
    out_path = (project_root / args.out).resolve()

    print(
        f"\n[manifest] {len(all_members)} paths "
        f"(audio={len(audio_rels)}, subset_csv={len(subset_csv_rels)}, full_csv={len(full_csv_rels)})"
    )
    print(f"  -> {manifest_path}")

    if args.dry_run:
        print("[dry-run] no manifest/tar/checksum written.")
        return 0

    manifest_path.write_text("\n".join(all_members) + "\n", encoding="utf-8")

    rc = run_tar_create(
        project_root=project_root,
        manifest=manifest_path,
        out=out_path,
        zstd_level=args.zstd_level,
    )
    if rc != 0:
        print(f"[error] tar exit {rc}", file=sys.stderr)
        return rc

    raw_audio = sum((project_root / p).stat().st_size for p in audio_rels)
    raw_extra = sum((project_root / p).stat().st_size for p in all_members if p not in audio_rels)
    raw_total = raw_audio + raw_extra
    arch_sz = out_path.stat().st_size
    ratio = arch_sz / raw_total if raw_total else 0.0
    print(
        f"\n[done] {out_path.name}\n"
        f"  archive : {arch_sz:,} B ({arch_sz/1e6:.2f} MB)\n"
        f"  audio   : {raw_audio:,} B\n"
        f"  +csv    : {raw_extra:,} B\n"
        f"  ratio   : {ratio:.2%}"
    )

    chk_written: Path | None = None
    if args.write_checksum:
        chk: Path | None = None
        if args.checksum_out is not None:
            co = args.checksum_out.expanduser()
            chk = co.resolve() if co.is_absolute() else (project_root / co).resolve()
        chk_written = write_sha256(out_path, chk)

    sha_hint = ""
    if chk_written is not None:
        try:
            sha_hint = " " + chk_written.relative_to(project_root).as_posix()
        except ValueError:
            sha_hint = " " + str(chk_written)

    print(
        "\n[upload hint]\n"
        f"  cd {project_root}\n"
        f"  rsync -avh --partial --inplace --progress \\\n"
        f"    {out_path.name} {manifest_path.name}{sha_hint} \\\n"
        f"    user@host:/path/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
