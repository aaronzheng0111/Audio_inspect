"""In-memory, thread-safe per-session state for the wizard flow.

The app is single-machine and stateful only for the duration of a working
session, so a process-local store keyed by a random session id is enough. Each
session holds the working :class:`pandas.DataFrame` plus the user's mapping and
metric selections as they progress through the 5-step wizard.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class Session:
    """All state accumulated for one dataset working session."""

    session_id: str
    csv_path: str
    dataframe: pd.DataFrame
    #: original column name -> canonical required name (audio_name_id/text/audio_path)
    column_mapping: Dict[str, str] = field(default_factory=dict)
    #: metric keys the user chose to compute
    selected_metrics: List[str] = field(default_factory=list)
    #: metric keys that have actually been computed into the dataframe
    computed_metrics: List[str] = field(default_factory=list)

    def canonical_to_column(self, canonical: str) -> Optional[str]:
        """Return the dataframe column to use for a canonical name.

        After mapping, canonical names (``text``, ``audio_path``, …) are the
        actual column labels. ``column_mapping`` stores canonical -> original
        source column from the user's selection.
        """
        if canonical in self.dataframe.columns:
            return canonical
        source = self.column_mapping.get(canonical)
        if source and source in self.dataframe.columns:
            return source
        return None


class SessionStore:
    """Thread-safe registry of active sessions.

    A module-level singleton (:data:`session_store`) is shared by all views so
    that successive wizard requests operate on the same in-memory dataframe.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()

    def create(self, csv_path: str, dataframe: pd.DataFrame) -> Session:
        session_id = uuid.uuid4().hex
        session = Session(
            session_id=session_id,
            csv_path=csv_path,
            dataframe=dataframe,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session_id: {session_id!r}")
        return session

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


#: Process-wide singleton used by the API views.
session_store = SessionStore()
