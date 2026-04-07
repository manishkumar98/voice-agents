"""
Voice Audit Logger — append-only JSONL compliance log.

Every agent turn, compliance block, MCP trigger, and session lifecycle
event is written as a single JSON line to the audit file.

Design constraints
------------------
- PII scrubber (Phase 1) is applied to ALL user transcripts before logging.
  Raw transcripts are NEVER written to disk.
- Log entries are immutable once written (append-only file).
- Path is resolved at write-time so tests can monkeypatch the env var.
- Import of Phase-1 scrubber is lazy and gracefully falls back to a
  built-in minimal scrubber if Phase 1 is not on sys.path.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

EVENT_TURN             = "TURN"
EVENT_COMPLIANCE_BLOCK = "COMPLIANCE_BLOCK"
EVENT_MCP_TRIGGER      = "MCP_TRIGGER"
EVENT_SESSION_START    = "SESSION_START"
EVENT_SESSION_END      = "SESSION_END"

VALID_EVENTS = {
    EVENT_TURN, EVENT_COMPLIANCE_BLOCK,
    EVENT_MCP_TRIGGER, EVENT_SESSION_START, EVENT_SESSION_END,
}

# ---------------------------------------------------------------------------
# Log entry dataclass
# ---------------------------------------------------------------------------

@dataclass
class VoiceLogEntry:
    """One line in the JSONL audit log."""

    call_id: str
    event_type: str                          # see VALID_EVENTS
    timestamp_ist: str                       # ISO 8601 with +05:30
    turn_index: int = 0
    user_transcript_sanitised: str = ""      # raw PII already scrubbed
    detected_intent: str | None = None
    slots_filled: dict = field(default_factory=dict)
    agent_speech: str = ""
    pii_blocked: bool = False
    pii_categories: list[str] = field(default_factory=list)
    current_state: str = ""
    booking_code: str | None = None
    compliance_flag: str | None = None       # None | "refuse_advice" | "refuse_pii"
    mcp_summary: str = ""                    # e.g. "calendar:✅ sheets:✅ email:✅"
    extra: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.call_id:
            errors.append("call_id must not be empty")
        if self.event_type not in VALID_EVENTS:
            errors.append(f"unknown event_type {self.event_type!r}")
        return errors

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Minimal built-in scrubber (fallback when Phase 1 not importable)
# ---------------------------------------------------------------------------

_BUILTIN_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone",   re.compile(r"(?<!\d)(?:\+91[\s\-]?|91[\s\-]?|0)?[6-9]\d{8,9}(?!\d)")),
    ("email",   re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("pan",     re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("aadhaar", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("account", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
]
_REDACT = "[REDACTED]"


def _builtin_scrub(text: str) -> tuple[str, bool, list[str]]:
    """
    Minimal PII scrubber — returns (cleaned_text, pii_found, categories).
    Used only when phase1.src.booking.pii_scrubber is not importable.
    """
    cleaned = text
    found_categories: list[str] = []
    for category, pattern in _BUILTIN_PII_PATTERNS:
        new, count = pattern.subn(_REDACT, cleaned)
        if count:
            cleaned = new
            found_categories.append(category)
    return cleaned, bool(found_categories), found_categories


def _scrub(text: str) -> tuple[str, bool, list[str]]:
    """
    Attempt to use Phase-1 PII scrubber; fall back to built-in.
    Returns (sanitised_text, pii_detected, categories).
    """
    try:
        from src.booking.pii_scrubber import scrub_pii  # type: ignore[import]
        result = scrub_pii(text)
        # Phase-1 scrubber returns ScrubResult with .text, .pii_detected, .categories
        return result.text, result.pii_detected, list(getattr(result, "categories", []))
    except Exception:
        pass
    try:
        # Alternate Phase-1 import path
        from phase1.src.booking.pii_scrubber import scrub_pii  # type: ignore[import]
        result = scrub_pii(text)
        return result.text, result.pii_detected, list(getattr(result, "categories", []))
    except Exception:
        pass
    return _builtin_scrub(text)


# ---------------------------------------------------------------------------
# Log path resolver
# ---------------------------------------------------------------------------

def _resolve_log_path(raw: str) -> str:
    if os.path.isabs(raw):
        return raw
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / raw
        if candidate.parent.exists() or parent.name in ("phase3", "voice-agent"):
            return str(candidate)
    return raw


# ---------------------------------------------------------------------------
# VoiceLogger
# ---------------------------------------------------------------------------

class VoiceLogger:
    """
    Append-only JSONL voice audit logger.

    Usage::

        log = VoiceLogger()
        log.log_turn(call_id="C-001", turn_index=1,
                     user_transcript_raw="my phone is 9876543210",
                     detected_intent="book_new", ...)

    Log path is controlled by the VOICE_AUDIT_LOG_PATH env var.
    Pass an explicit ``log_path`` to override (useful in tests).
    """

    def __init__(self, log_path: str | None = None) -> None:
        self._explicit_path = log_path

    # ------------------------------------------------------------------
    def _get_path(self) -> str:
        if self._explicit_path:
            return self._explicit_path
        raw = os.environ.get("VOICE_AUDIT_LOG_PATH", "data/logs/voice_audit_log.jsonl")
        return _resolve_log_path(raw)

    def _write(self, entry: VoiceLogEntry) -> None:
        path = self._get_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(entry.to_json() + "\n")
        except OSError as exc:
            logger.error("VoiceLogger write failed: %s", exc)

    # ------------------------------------------------------------------
    def _now_ist(self) -> str:
        return datetime.now(IST).isoformat()

    # ------------------------------------------------------------------
    def log_session_start(self, call_id: str, extra: dict | None = None) -> None:
        entry = VoiceLogEntry(
            call_id=call_id,
            event_type=EVENT_SESSION_START,
            timestamp_ist=self._now_ist(),
            extra=extra or {},
        )
        self._write(entry)

    def log_session_end(self, call_id: str, turn_count: int = 0) -> None:
        entry = VoiceLogEntry(
            call_id=call_id,
            event_type=EVENT_SESSION_END,
            timestamp_ist=self._now_ist(),
            turn_index=turn_count,
        )
        self._write(entry)

    def log_turn(
        self,
        call_id: str,
        turn_index: int,
        user_transcript_raw: str,
        detected_intent: str | None = None,
        slots_filled: dict | None = None,
        agent_speech: str = "",
        current_state: str = "",
        booking_code: str | None = None,
    ) -> VoiceLogEntry:
        """
        Log a single dialogue turn.  PII is scrubbed from ``user_transcript_raw``
        before writing — the raw transcript is never stored.
        """
        sanitised, pii_blocked, pii_cats = _scrub(user_transcript_raw)

        entry = VoiceLogEntry(
            call_id=call_id,
            event_type=EVENT_TURN,
            timestamp_ist=self._now_ist(),
            turn_index=turn_index,
            user_transcript_sanitised=sanitised,
            detected_intent=detected_intent,
            slots_filled=slots_filled or {},
            agent_speech=agent_speech,
            pii_blocked=pii_blocked,
            pii_categories=pii_cats,
            current_state=current_state,
            booking_code=booking_code,
        )
        self._write(entry)
        return entry

    def log_compliance_block(
        self,
        call_id: str,
        turn_index: int,
        flag: str,
        blocked_speech: str,
        safe_speech: str,
    ) -> VoiceLogEntry:
        """Log when ComplianceGuard blocks LLM output."""
        entry = VoiceLogEntry(
            call_id=call_id,
            event_type=EVENT_COMPLIANCE_BLOCK,
            timestamp_ist=self._now_ist(),
            turn_index=turn_index,
            compliance_flag=flag,
            extra={"blocked_speech_hash": _short_hash(blocked_speech),
                   "safe_speech": safe_speech},
        )
        self._write(entry)
        return entry

    def log_mcp_trigger(
        self,
        call_id: str,
        turn_index: int,
        booking_code: str,
        mcp_summary: str,
    ) -> VoiceLogEntry:
        """Log the MCP dispatch event (after slot confirmation)."""
        entry = VoiceLogEntry(
            call_id=call_id,
            event_type=EVENT_MCP_TRIGGER,
            timestamp_ist=self._now_ist(),
            turn_index=turn_index,
            booking_code=booking_code,
            mcp_summary=mcp_summary,
        )
        self._write(entry)
        return entry

    # ------------------------------------------------------------------
    def read_entries(self, call_id: str | None = None) -> list[VoiceLogEntry]:
        """
        Read all log entries (optionally filtered by call_id).
        Primarily used in tests and the internal dashboard.
        """
        path = self._get_path()
        if not Path(path).is_file():
            return []

        entries: list[VoiceLogEntry] = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = VoiceLogEntry(**{
                            k: v for k, v in data.items()
                            if k in VoiceLogEntry.__dataclass_fields__
                        })
                        if call_id is None or entry.call_id == call_id:
                            entries.append(entry)
                    except Exception:
                        pass
        except OSError:
            pass
        return entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _short_hash(text: str, length: int = 8) -> str:
    """Return a short hash of text for audit logging (not PII-safe for storage)."""
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:length]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_logger: VoiceLogger | None = None


def get_default_logger() -> VoiceLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = VoiceLogger()
    return _default_logger
