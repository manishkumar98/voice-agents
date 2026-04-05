"""
src/booking/waitlist_handler.py

Creates waitlist entries when no calendar slots are available for the user's
requested time. Waitlist codes use NL-WXXX format to distinguish from booking codes.

No external APIs or database — entries are returned as WaitlistEntry dataclasses.
Persistence to Google Sheets happens in Phase 4 (MCP layer).
"""

from dataclasses import dataclass, field
from datetime import datetime

import pytz

from .booking_code_generator import generate_waitlist_code

IST = pytz.timezone("Asia/Kolkata")

VALID_STATUSES = {"ACTIVE", "FULFILLED", "EXPIRED", "CANCELLED"}


@dataclass
class WaitlistEntry:
    waitlist_code: str
    topic: str
    day_preference: str
    time_preference: str
    created_at: datetime        # IST-aware datetime
    status: str = "ACTIVE"     # ACTIVE | FULFILLED | EXPIRED | CANCELLED

    def to_dict(self) -> dict:
        return {
            "waitlist_code": self.waitlist_code,
            "topic": self.topic,
            "day_preference": self.day_preference,
            "time_preference": self.time_preference,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }

    def summary(self) -> str:
        """Human-readable one-liner for logging / TTS."""
        return (
            f"Waitlist entry {self.waitlist_code}: {self.topic} — "
            f"{self.day_preference} {self.time_preference} (status: {self.status})"
        )


def create_waitlist_entry(
    topic: str,
    day_preference: str,
    time_preference: str,
    existing_codes: set[str] | None = None,
    reference_time: datetime | None = None,
) -> WaitlistEntry:
    """
    Create a new waitlist entry with a unique NL-WXXX code.

    Args:
        topic:           Canonical topic key (e.g. "kyc_onboarding").
        day_preference:  Natural language day the user wanted (e.g. "Monday").
        time_preference: Natural language time the user wanted (e.g. "2 PM").
        existing_codes:  Set of codes already issued (to avoid collision).
        reference_time:  Override for "now" in tests.

    Returns:
        A WaitlistEntry dataclass instance.
    """
    if not topic or not topic.strip():
        raise ValueError("topic must be a non-empty string")
    if not day_preference or not day_preference.strip():
        raise ValueError("day_preference must be a non-empty string")
    if not time_preference or not time_preference.strip():
        raise ValueError("time_preference must be a non-empty string")

    code = generate_waitlist_code(existing_codes or set())

    if reference_time is None:
        reference_time = datetime.now(IST)
    elif reference_time.tzinfo is None:
        reference_time = IST.localize(reference_time)

    return WaitlistEntry(
        waitlist_code=code,
        topic=topic,
        day_preference=day_preference,
        time_preference=time_preference,
        created_at=reference_time,
        status="ACTIVE",
    )


def cancel_waitlist_entry(entry: WaitlistEntry) -> WaitlistEntry:
    """Return a copy of the entry with status set to CANCELLED."""
    return WaitlistEntry(
        waitlist_code=entry.waitlist_code,
        topic=entry.topic,
        day_preference=entry.day_preference,
        time_preference=entry.time_preference,
        created_at=entry.created_at,
        status="CANCELLED",
    )
