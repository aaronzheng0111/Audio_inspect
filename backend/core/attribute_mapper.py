"""Map non-standard CSV column names onto the canonical required names.

Different data sources name their columns differently (``file``, ``wav``,
``transcript`` ...). :class:`AttributeMapper` lets the user bind their actual
columns to the canonical names the pipeline relies on
(``audio_name_id`` / ``text`` / ``audio_path``) and applies the rename in place.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .csv_inspector import REQUIRED_CANONICAL_COLUMNS

#: Heuristic aliases used to pre-suggest a mapping in the UI.
ALIASES: Dict[str, List[str]] = {
    "audio_name_id": [
        "audio_name_id", "id", "name", "audio_name", "utt_id", "utterance_id", "filename",
    ],
    "text": ["text", "transcript", "transcription", "sentence", "label", "content"],
    "audio_path": [
        "audio_path", "path", "sample_path", "original_path", "full_path",
        "wav", "wav_path", "file", "filepath", "audio",
    ],
}


class AttributeMapper:
    """Validate and apply a mapping from real columns to canonical names."""

    def __init__(self, columns: List[str]) -> None:
        self.columns = [str(c) for c in columns]

    def suggest(self) -> Dict[str, str]:
        """Best-effort guess of canonical -> actual-column based on aliases."""
        lowered = {c.lower(): c for c in self.columns}
        suggestion: Dict[str, str] = {}
        for canonical, aliases in ALIASES.items():
            for alias in aliases:
                if alias in lowered:
                    suggestion[canonical] = lowered[alias]
                    break
        return suggestion

    def validate(self, mapping: Dict[str, str]) -> None:
        """Ensure every mapped source column actually exists.

        ``mapping`` is canonical-name -> actual-column. ``audio_path`` is
        mandatory because metric computation reads the audio files; the other
        canonical columns are recommended but not strictly required.

        Mapping is idempotent: if a prior submit already renamed ``sentence`` to
        ``text``, a repeat request with ``text -> sentence`` is accepted because
        ``text`` is already present in the dataframe.
        """
        for canonical, source in mapping.items():
            if not source:
                continue
            if source in self.columns:
                continue
            if canonical in self.columns:
                # Already renamed on a previous map (user went back and re-submitted).
                continue
            raise ValueError(
                f"Mapped column {source!r} for {canonical!r} does not exist. "
                f"Available columns: {', '.join(self.columns)}"
            )
        has_audio_path = (
            mapping.get("audio_path")
            or "audio_path" in self.columns
        )
        if not has_audio_path:
            raise ValueError(
                "A column must be mapped to 'audio_path' so audio files can be read."
            )

    @staticmethod
    def to_rename_dict(mapping: Dict[str, str]) -> Dict[str, str]:
        """Convert canonical->source mapping into a DataFrame.rename mapping.

        Returns ``{source_column: canonical_name}`` skipping entries where the
        source already equals the canonical name.
        """
        rename: Dict[str, str] = {}
        for canonical, source in mapping.items():
            if source and source != canonical and canonical in REQUIRED_CANONICAL_COLUMNS:
                rename[source] = canonical
        return rename

    def apply(self, dataframe: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Return a copy of ``dataframe`` with canonical columns renamed."""
        self.validate(mapping)
        rename = self.to_rename_dict(mapping)
        # Skip renames whose source column was already renamed in a prior submit.
        rename = {src: dst for src, dst in rename.items() if src in dataframe.columns}
        if not rename:
            return dataframe.copy()
        return dataframe.rename(columns=rename)
