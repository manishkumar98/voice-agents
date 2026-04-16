"""
src/booking/waitlist_queue.py

In-memory FIFO waitlist queue with slot-promotion logic.

When a booking is cancelled, the queue finds the first ACTIVE entry
that matches the freed slot (by topic + time band) and promotes them.

Rules:
  - Queue is ordered strictly by created_at (FIFO — first in, first served)
  - Topic must match (or entry has no topic preference)
  - Time preference is matched approximately to the slot's hour via time bands
  - Only ACTIVE entries are eligible for promotion
  - Promoted entry status → FULFILLED; freed slot is offered back via the return value
  - This class is the single source of truth for Phase 2 (dev).
    Phase 4 will replace the in-memory store with a Google Sheets row-append + query.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz

from .slot_resolver import CalendarSlot
from .waitlist_handler import WaitlistEntry

logger = logging.getLogger(__name__)

_WAITLIST_JSON_PATH = os.environ.get(
    "WAITLIST_JSON_PATH",
    str(Path(__file__).resolve().parents[3] / "data" / "waitlist.json"),
)

IST = pytz.timezone("Asia/Kolkata")

# Time band mapping — same bands as slot_resolver
_TIME_BANDS: dict[str, tuple[int, int]] = {
    "morning":   (9, 12),
    "afternoon": (12, 17),
    "evening":   (17, 20),
    "night":     (18, 21),
    "noon":      (12, 14),
    "midday":    (11, 14),
    "any":       (0, 24),
}


@dataclass
class PromotionResult:
    """Returned when a cancellation triggers a queue promotion."""
    promoted_entry: WaitlistEntry       # Entry that gets the slot
    freed_slot: CalendarSlot            # The slot that became available
    position_was: int                   # 1-based queue position they held


def _time_pref_matches_slot(time_preference: str, slot: CalendarSlot) -> bool:
    """
    Return True if the slot's start hour falls within the entry's time preference band.
    If preference is unrecognised or 'any', always matches.
    """
    pref = time_preference.lower().strip()
    band = _TIME_BANDS.get(pref)
    if band is None:
        # Try partial match (e.g. "4 pm" → afternoon band)
        for band_name, band_range in _TIME_BANDS.items():
            if band_name in pref:
                band = band_range
                break
    if band is None:
        return True  # Can't parse → don't block on time
    start_h, end_h = band
    return start_h <= slot.start.hour < end_h


def _topic_matches_slot(topic: str, slot: CalendarSlot) -> bool:
    """
    Return True if the slot accepts this topic.
    Slot with empty topic_affinity accepts any topic.
    """
    if not slot.topic_affinity:
        return True
    return topic in slot.topic_affinity


class WaitlistQueue:
    """
    Thread-safe FIFO waitlist queue.

    Usage:
        queue = WaitlistQueue()
        queue.add(entry)
        result = queue.on_cancellation(freed_slot)   # → PromotionResult | None
        pos = queue.position(waitlist_code)           # → 1-based position | None
    """

    def __init__(self) -> None:
        self._entries: list[WaitlistEntry] = []   # ordered by created_at
        self._lock = threading.Lock()
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from JSON file on startup."""
        path = Path(_WAITLIST_JSON_PATH)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._entries = [WaitlistEntry.from_dict(d) for d in data.get("entries", [])]
        except Exception as exc:
            logger.warning("Waitlist JSON load failed: %s", exc)

    def _save(self) -> None:
        """Persist current entries to JSON file. Must be called with _lock held."""
        path = Path(_WAITLIST_JSON_PATH)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"entries": [e.to_dict() for e in self._entries]}, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Waitlist JSON save failed: %s", exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def add(self, entry: WaitlistEntry) -> int:
        """
        Add a waitlist entry to the queue.
        Returns the 1-based position the entry holds among ACTIVE entries.
        """
        with self._lock:
            self._entries.append(entry)
            self._entries.sort(key=lambda e: e.created_at)
            pos = self._active_position(entry.waitlist_code)
            self._save()
            return pos

    def update_email(self, waitlist_code: str, name: str, email: str) -> bool:
        """Store contact details on an existing entry. Returns True if found."""
        with self._lock:
            for entry in self._entries:
                if entry.waitlist_code == waitlist_code:
                    entry.name = name
                    entry.email = email
                    self._save()
                    return True
        return False

    def on_cancellation(self, freed_slot: CalendarSlot) -> Optional[PromotionResult]:
        """
        Called when a booking is cancelled and the slot is freed.

        Scans ACTIVE entries in FIFO order and promotes the first one
        whose topic + time preference matches the freed slot.

        Returns PromotionResult if someone was promoted, None if queue is empty
        or no entry matches.
        """
        with self._lock:
            active = [e for e in self._entries if e.status == "ACTIVE"]
            for i, entry in enumerate(active):
                topic_ok = _topic_matches_slot(entry.topic, freed_slot)
                time_ok  = _time_pref_matches_slot(entry.time_preference, freed_slot)
                if topic_ok and time_ok:
                    # Promote: mark as FULFILLED
                    entry.status = "FULFILLED"
                    entry.fulfilled_at = datetime.now(IST)  # type: ignore[attr-defined]
                    pos = i + 1  # 1-based position they held
                    self._save()
                    return PromotionResult(
                        promoted_entry=entry,
                        freed_slot=freed_slot,
                        position_was=pos,
                    )
        return None

    def position(self, waitlist_code: str) -> Optional[int]:
        """
        Return the 1-based ACTIVE queue position for this code.
        Returns None if the code doesn't exist or is no longer ACTIVE.
        """
        with self._lock:
            return self._active_position(waitlist_code)

    def cancel_entry(self, waitlist_code: str) -> bool:
        """Mark a specific waitlist entry as CANCELLED. Returns True if found."""
        with self._lock:
            for entry in self._entries:
                if entry.waitlist_code == waitlist_code and entry.status == "ACTIVE":
                    entry.status = "CANCELLED"
                    self._save()
                    return True
        return False

    def get_by_code(self, waitlist_code: str) -> Optional[WaitlistEntry]:
        """Return entry by code, or None."""
        with self._lock:
            for entry in self._entries:
                if entry.waitlist_code == waitlist_code:
                    return entry
        return None

    def active_entries(self) -> list[WaitlistEntry]:
        """Return a copy of all ACTIVE entries in FIFO order."""
        with self._lock:
            return [e for e in self._entries if e.status == "ACTIVE"]

    def all_entries(self) -> list[WaitlistEntry]:
        """Return all entries (any status) in created_at order."""
        with self._lock:
            return list(self._entries)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._entries if e.status == "ACTIVE")

    def snapshot(self) -> list[dict]:
        """Serialisable snapshot of all entries — for logging / dashboard."""
        with self._lock:
            result = []
            active_pos = 0
            for e in self._entries:
                if e.status == "ACTIVE":
                    active_pos += 1
                result.append({
                    **e.to_dict(),
                    "queue_position": active_pos if e.status == "ACTIVE" else None,
                })
            return result

    # ── Internal ───────────────────────────────────────────────────────────────

    def _active_position(self, waitlist_code: str) -> Optional[int]:
        """Must be called with _lock held."""
        pos = 0
        for entry in self._entries:
            if entry.status == "ACTIVE":
                pos += 1
                if entry.waitlist_code == waitlist_code:
                    return pos
        return None


# ── Module-level singleton (shared across the process in dev) ──────────────────
# Phase 4 will replace this with a Sheets-backed store.

_global_queue = WaitlistQueue()


def get_global_queue() -> WaitlistQueue:
    """Return the process-level singleton queue."""
    return _global_queue
