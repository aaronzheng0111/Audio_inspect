"""Resolve the filesystem root for relative audio paths in a dataset CSV.

Many datasets store paths like ``kaggle/archive/foo.wav`` relative to the
dataset root, while the CSV itself lives in a ``CSV/`` subfolder. Joining
against ``dirname(csv_path)`` alone then fails. This module tries several
candidate roots and picks the one that resolves the most sample paths to real
files on disk.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


def candidate_roots(csv_path: str, max_levels: int = 5) -> List[str]:
    """Return directories to try as audio root, starting at the CSV folder."""
    roots: List[str] = []
    current = Path(csv_path).expanduser().resolve().parent
    for _ in range(max_levels):
        roots.append(str(current))
        parent = current.parent
        if parent == current:
            break
        current = parent
    return roots


def resolve_audio_root(
    csv_path: str,
    sample_paths: Sequence[object],
    max_samples: int = 25,
) -> Tuple[str, int, int]:
    """Pick the best audio root for ``sample_paths``.

    Returns ``(root, files_found, files_checked)``. For absolute paths in the
    sample, existence is checked directly (root is still the best-effort default).
    """
    csv_parent = str(Path(csv_path).expanduser().resolve().parent)
    samples = [
        str(p).strip()
        for p in sample_paths
        if p is not None and str(p).strip() and str(p).lower() not in ("nan", "none")
    ][:max_samples]

    if not samples:
        return csv_parent, 0, 0

    best_root = csv_parent
    best_found = -1

    for root in candidate_roots(csv_path):
        found = sum(1 for rel in samples if _path_exists(rel, root))
        if found > best_found:
            best_found = found
            best_root = root

    return best_root, max(best_found, 0), len(samples)


def resolve_audio_file(audio_path: object, csv_path: str, audio_root: Optional[str] = None) -> str:
    """Return the absolute path to an audio file, or the best-effort guess."""
    raw = str(audio_path).strip()
    if not raw:
        return ""
    if os.path.isabs(raw):
        return os.path.expanduser(raw)
    root = audio_root or str(Path(csv_path).expanduser().resolve().parent)
    return os.path.normpath(os.path.join(root, raw))


def _path_exists(audio_path: str, root: str) -> bool:
    resolved = resolve_audio_file(audio_path, csv_path="", audio_root=root)
    return os.path.isfile(resolved)
