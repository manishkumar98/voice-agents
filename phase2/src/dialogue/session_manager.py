"""
src/dialogue/session_manager.py

Thread-safe in-memory session store for active calls.

Each session maps a UUID session_id to a (DialogueContext, last_active_time) pair.
Sessions expire after TTL_MINUTES of inactivity and are cleaned up lazily.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Optional

import pytz

from .states import DialogueContext

IST = pytz.timezone("Asia/Kolkata")
TTL_MINUTES = 30


class SessionManager:
    """
    Thread-safe in-memory session store.

    Usage:
        mgr = SessionManager()
        session_id = mgr.create_session(ctx)
        ctx = mgr.get_session(session_id)      # None if expired/missing
        mgr.update_session(session_id, ctx)
        mgr.close_session(session_id)
        active = mgr.active_count()
    """

    def __init__(self, ttl_minutes: int = TTL_MINUTES) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._store: dict[str, tuple[DialogueContext, datetime]] = {}
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_session(self, ctx: DialogueContext) -> str:
        """Store a new session and return its UUID session_id."""
        session_id = str(uuid.uuid4())
        with self._lock:
            self._store[session_id] = (ctx, datetime.now(IST))
        return session_id

    def get_session(self, session_id: str) -> Optional[DialogueContext]:
        """
        Return the DialogueContext if session exists and is not expired.
        Returns None if missing or expired (and removes expired session).
        """
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            ctx, last_active = entry
            if self._is_expired(last_active):
                del self._store[session_id]
                return None
            return ctx

    def update_session(self, session_id: str, ctx: DialogueContext) -> bool:
        """
        Update context and refresh TTL.
        Returns False if session is missing or expired.
        """
        with self._lock:
            if session_id not in self._store:
                return False
            _, last_active = self._store[session_id]
            if self._is_expired(last_active):
                del self._store[session_id]
                return False
            self._store[session_id] = (ctx, datetime.now(IST))
            return True

    def close_session(self, session_id: str) -> bool:
        """Remove a session explicitly. Returns True if it existed."""
        with self._lock:
            return self._store.pop(session_id, None) is not None

    def active_count(self) -> int:
        """Return number of non-expired sessions (also prunes expired ones)."""
        self._prune()
        with self._lock:
            return len(self._store)

    def all_session_ids(self) -> list[str]:
        """Return list of non-expired session IDs (also prunes expired ones)."""
        self._prune()
        with self._lock:
            return list(self._store.keys())

    # ── Internals ──────────────────────────────────────────────────────────────

    def _is_expired(self, last_active: datetime) -> bool:
        return datetime.now(IST) - last_active > self._ttl

    def _prune(self) -> None:
        """Remove all expired sessions."""
        with self._lock:
            expired = [
                sid for sid, (_, last_active) in self._store.items()
                if self._is_expired(last_active)
            ]
            for sid in expired:
                del self._store[sid]
