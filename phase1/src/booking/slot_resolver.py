"""
src/booking/slot_resolver.py

Resolves natural language time preferences ("Monday at 2 PM") to available
calendar slots. Tries Google Calendar freeBusy API first; falls back to
mock_calendar.json if credentials are missing or the API call fails.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytz

IST = pytz.timezone("Asia/Kolkata")

# Day-of-week name → weekday number (Monday=0, Sunday=6)
_DAY_MAP: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Time-of-day keywords → (start_hour, end_hour) in 24h
_TIME_BAND_MAP: dict[str, tuple[int, int]] = {
    "morning": (9, 12),
    "afternoon": (12, 17),
    "evening": (17, 20),
    "night": (18, 21),
    "noon": (12, 14),
    "midday": (11, 14),
}


@dataclass
class CalendarSlot:
    slot_id: str
    start: datetime      # timezone-aware IST
    end: datetime        # timezone-aware IST
    status: str
    topic_affinity: list[str]

    def start_ist_str(self) -> str:
        return self.start.strftime("%A, %d/%m/%Y at %I:%M %p IST")


# Month name → month number
_MONTH_MAP: dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# Time-of-day band → implied am/pm and hour range
_BAND_AMPM: dict[str, str] = {
    "morning": "am", "noon": "pm", "midday": "pm",
    "afternoon": "pm", "evening": "pm", "night": "pm",
}
_BAND_DEFAULT_HOUR: dict[str, int] = {
    "morning": 10, "noon": 12, "midday": 12,
    "afternoon": 14, "evening": 18, "night": 20,
}


def _parse_day_preference(
    day_pref: str,
    reference_date: datetime | None = None,
) -> tuple[list[datetime], bool]:
    """
    Convert a day preference string to (candidate_dates, confident).

    confident=False means we couldn't extract a specific date and fell back
    to a range — caller should confirm with user.

    Handles:
        "today" / "tomorrow"
        "Monday" / "next Monday"
        "6th" / "6" → 6th of current month (next month if past)
        "6th April" / "April 6" / "6 April 2026"
        "this week" / "next week" → range fallback (confident=False)
    """
    if reference_date is None:
        reference_date = datetime.now(IST)

    pref = day_pref.lower().strip()
    today = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Relative keywords ──────────────────────────────────────────────────────
    if "today" in pref:
        return [today], True

    if "day after tomorrow" in pref or "overmorrow" in pref:
        return [today + timedelta(days=2)], True

    if "tomorrow" in pref:
        return [today + timedelta(days=1)], True

    force_next_week = pref.startswith("next") and not any(
        m in pref for m in _MONTH_MAP
    )

    # ── Ordinal / numeric day of month ─────────────────────────────────────────
    # Matches: "6th", "6", "6th april", "april 6", "6/4", "6-4"
    ordinal_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", pref)
    if ordinal_match:
        day_num = int(ordinal_match.group(1))
        if 1 <= day_num <= 31:
            # Check for explicit month
            target_month = reference_date.month
            target_year  = reference_date.year
            for month_name, month_num in _MONTH_MAP.items():
                if month_name in pref:
                    target_month = month_num
                    if month_num < reference_date.month:
                        target_year += 1  # next year
                    break

            # Check for explicit 4-digit year
            year_match = re.search(r"\b(202\d)\b", pref)
            if year_match:
                target_year = int(year_match.group(1))

            try:
                candidate = today.replace(year=target_year, month=target_month, day=day_num)
                # If the date is in the past (same month), roll to next month
                if candidate < today and target_month == reference_date.month and not year_match:
                    if target_month == 12:
                        candidate = candidate.replace(year=target_year + 1, month=1)
                    else:
                        candidate = candidate.replace(month=target_month + 1)
                return [candidate], True
            except ValueError:
                pass  # invalid day for that month — fall through

    # ── Weekday name ───────────────────────────────────────────────────────────
    for day_name, target_weekday in _DAY_MAP.items():
        if day_name in pref:
            current_weekday = reference_date.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0 and not force_next_week:
                candidate = today
            else:
                if force_next_week:
                    days_ahead = days_ahead if days_ahead > 0 else 7
                    days_ahead += 7 if days_ahead <= 7 and "next" in pref else 0
                candidate = today + timedelta(days=days_ahead or 7)
            return [candidate], True

    # ── Fallback: range (not confident) ────────────────────────────────────────
    days_offset = 8 if "next week" in pref else 1
    return [
        today + timedelta(days=i)
        for i in range(days_offset, days_offset + 7)
    ], False


def _parse_time_preference(time_pref: str) -> tuple[tuple[int, int] | None, bool]:
    """
    Convert a time preference string to ((start_hour, end_hour), confident).

    confident=False means only a broad band was matched — caller may want to confirm.

    Handles:
        "10am" / "10 am" / "10:30am"     → exact window, confident
        "2pm" / "2 pm"                   → exact window, confident
        "14:00"                           → exact window, confident
        "2 afternoon" / "afternoon 2"    → 14:xx, confident
        "10 morning" / "morning 10"      → 10:xx AM, confident
        "6 evening"                      → 18:xx, confident
        "morning" / "afternoon" / "evening" → band, not fully confident
        "any" / ""                        → None (no filter)
    """
    pref = time_pref.lower().strip()

    if not pref or pref in ("any", "anytime", "any time", "flexible"):
        return None, True  # No filter = confident we should show all

    # ── Detect time-of-day band in phrase (longest match first to avoid "noon" ⊂ "afternoon") ──
    detected_band: str | None = None
    for band_name in sorted(_BAND_AMPM, key=len, reverse=True):
        if band_name in pref:
            detected_band = band_name
            break

    # ── Try to extract an explicit numeric hour ────────────────────────────────
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", pref)
    if time_match:
        hour  = int(time_match.group(1))
        am_pm = time_match.group(3)

        # Resolve AM/PM from explicit marker first, then from band context
        if am_pm == "pm" and hour < 12:
            hour += 12
        elif am_pm == "am" and hour == 12:
            hour = 0
        elif am_pm is None and detected_band:
            # "2 afternoon" → 2 PM, "10 morning" → 10 AM
            implied = _BAND_AMPM[detected_band]
            if implied == "pm" and hour < 12:
                hour += 12
            elif implied == "am" and hour == 12:
                hour = 0
        elif am_pm is None and hour <= 6:
            # Bare "2" with no context → assume PM (people rarely book at 2 AM)
            hour += 12

        # 1-hour window centred on stated time (±1h to catch nearby slots)
        return (max(0, hour - 1), min(23, hour + 2)), True

    # ── Band-only match (morning / afternoon / evening) ───────────────────────
    # A clear time-of-day word is confident — user expressed an explicit preference
    if detected_band:
        return _TIME_BAND_MAP[detected_band], True

    return None, False  # Truly could not parse


def parse_datetime_summary(
    day_pref: str,
    time_pref: str,
    reference_date: datetime | None = None,
) -> tuple[str, bool]:
    """
    Return a human-readable summary of what was understood + a confidence flag.
    Used by FSM to echo back interpretation to the user.

    Returns:
        (summary_string, needs_confirmation)
    """
    if reference_date is None:
        reference_date = datetime.now(IST)

    dates, day_confident = _parse_day_preference(day_pref, reference_date)
    band, time_confident = _parse_time_preference(time_pref)

    # Date summary
    if dates and day_confident:
        date_str = dates[0].strftime("%A, %d/%m/%Y")
    elif dates:
        date_str = f"sometime in the coming days (from {dates[0].strftime('%d/%m/%Y')})"
    else:
        date_str = day_pref

    # Time summary
    if band and time_confident:
        # Show the window as a clock time
        start_h, end_h = band
        # Pick midpoint for display
        mid = (start_h + end_h) // 2
        ampm = "AM" if mid < 12 else "PM"
        disp = mid if mid <= 12 else mid - 12
        time_str = f"{disp}:00 {ampm} IST"
    elif band:
        # Named band
        for name, rng in _TIME_BAND_MAP.items():
            if rng == band:
                time_str = f"{name} IST"
                break
        else:
            time_str = time_pref
    else:
        time_str = time_pref

    # Only ask for confirmation if we genuinely couldn't parse the date or time
    needs_confirmation = not day_confident or (not time_confident and band is None)
    return f"{date_str} at {time_str}", needs_confirmation


def _resolve_slots_gcal(
    candidate_dates: list[datetime],
    time_band: tuple[int, int] | None,
    max_results: int = 2,
    slot_duration_minutes: int = 30,
    business_start_hour: int = 9,
    business_end_hour: int = 18,
) -> list[CalendarSlot]:
    """
    Query Google Calendar freeBusy API to find available advisor slots.

    Generates every `slot_duration_minutes`-min window during business hours
    for each candidate date, then subtracts busy intervals reported by the
    Calendar API.  Returns up to `max_results` free slots.
    """
    try:
        import sys
        from pathlib import Path

        # Locate phase4 on sys.path so we can reuse the credential loader
        _here = Path(__file__).resolve()
        for _p in _here.parents:
            _candidate = _p / "phase4"
            if _candidate.exists():
                _phase4_src = str(_candidate / "src")
                if _phase4_src not in sys.path:
                    sys.path.insert(0, _phase4_src)
                break

        from mcp.config import get_service_account_info, _decode_if_base64  # type: ignore
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        _SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        sa_info = get_service_account_info()
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
        service = build("calendar", "v3", credentials=creds)

        calendar_id = _decode_if_base64(os.environ.get("GOOGLE_CALENDAR_ID", ""))
        if not calendar_id:
            return []

        # Determine overall time window to query.
        # candidate_dates may be tz-aware (IST) or naive — normalise to IST-aware.
        def _to_ist(dt: datetime, hour: int) -> datetime:
            naive = dt.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=None)
            return IST.localize(naive)

        all_starts = [_to_ist(d, business_start_hour) for d in candidate_dates]
        all_ends   = [_to_ist(d, business_end_hour)   for d in candidate_dates]

        query_start = min(all_starts)
        query_end   = max(all_ends)

        # isoformat() on an IST-aware datetime already includes "+05:30"
        body = {
            "timeMin": query_start.isoformat(),
            "timeMax": query_end.isoformat(),
            "timeZone": "Asia/Kolkata",
            "items": [{"id": calendar_id}],
        }
        fb = service.freebusy().query(body=body).execute()
        busy_intervals = fb.get("calendars", {}).get(calendar_id, {}).get("busy", [])

        # Convert busy intervals to aware datetimes
        busy: list[tuple[datetime, datetime]] = []
        for interval in busy_intervals:
            b_start = datetime.fromisoformat(interval["start"].replace("Z", "+00:00")).astimezone(IST)
            b_end   = datetime.fromisoformat(interval["end"].replace("Z", "+00:00")).astimezone(IST)
            busy.append((b_start, b_end))

        slot_delta = timedelta(minutes=slot_duration_minutes)
        now = datetime.now(IST)
        results: list[CalendarSlot] = []

        for day in candidate_dates:
            cursor     = _to_ist(day, business_start_hour)
            day_end_dt = _to_ist(day, business_end_hour)

            # Narrow to time_band if given
            if time_band:
                band_start = max(cursor, _to_ist(day, time_band[0]))
                band_end   = min(day_end_dt, _to_ist(day, time_band[1]))
                if band_start < band_end:
                    cursor     = band_start
                    day_end_dt = band_end

            while cursor + slot_delta <= day_end_dt:
                slot_end = cursor + slot_delta
                # Skip slots in the past
                if slot_end <= now:
                    cursor = slot_end
                    continue
                # Check overlap with any busy interval
                is_busy = any(b_s < slot_end and b_e > cursor for b_s, b_e in busy)
                if not is_busy:
                    results.append(CalendarSlot(
                        slot_id=f"gcal-{cursor.strftime('%Y%m%dT%H%M')}",
                        start=cursor,
                        end=slot_end,
                        status="AVAILABLE",
                        topic_affinity=[],
                    ))
                    if len(results) >= max_results:
                        return results
                cursor = slot_end

        return results

    except Exception:
        return []


def _resolve_slots_mock(
    candidate_dates: list[datetime],
    time_band: tuple[int, int] | None,
    topic: str | None,
    calendar_path: str | None,
    max_results: int,
) -> list[CalendarSlot]:
    """Read available slots from mock_calendar.json."""
    if calendar_path is None:
        calendar_path = os.environ.get(
            "MOCK_CALENDAR_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "mock_calendar.json"),
        )

    with open(calendar_path, encoding="utf-8") as f:
        cal = json.load(f)

    all_slots: list[CalendarSlot] = []
    for raw in cal.get("slots", []):
        if raw.get("status") != "AVAILABLE":
            continue
        try:
            start_dt = datetime.fromisoformat(raw["start"])
            end_dt   = datetime.fromisoformat(raw["end"])
            if start_dt.tzinfo is None:
                start_dt = IST.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(IST)
            if end_dt.tzinfo is None:
                end_dt = IST.localize(end_dt)
            else:
                end_dt = end_dt.astimezone(IST)
            all_slots.append(CalendarSlot(
                slot_id=raw["slot_id"],
                start=start_dt,
                end=end_dt,
                status=raw["status"],
                topic_affinity=raw.get("topic_affinity", []),
            ))
        except (KeyError, ValueError):
            continue

    if topic:
        all_slots = [s for s in all_slots if not s.topic_affinity or topic in s.topic_affinity]

    matched: list[CalendarSlot] = []
    for slot in all_slots:
        slot_date = slot.start.date()
        for cand in candidate_dates:
            if slot_date == cand.date():
                matched.append(slot)
                break

    if time_band and matched:
        start_h, end_h = time_band
        time_matched = [s for s in matched if start_h <= s.start.hour < end_h]
        if time_matched:
            matched = time_matched

    matched.sort(key=lambda s: s.start)
    return matched[:max_results]


def resolve_slots(
    day_preference: str,
    time_preference: str,
    topic: str | None = None,
    calendar_path: str | None = None,
    max_results: int = 2,
    reference_date: datetime | None = None,
) -> list[CalendarSlot]:
    """
    Find available calendar slots matching the user's day/time preference.

    Tries Google Calendar freeBusy API first (when GOOGLE_CALENDAR_ID is set).
    Falls back to mock_calendar.json if credentials are missing or the API fails.

    Args:
        day_preference:  Natural language day, e.g. "Monday", "next Tuesday", "tomorrow".
        time_preference: Natural language time, e.g. "2 PM", "afternoon", "morning".
        topic:           Optional topic key for topic_affinity filtering.
        calendar_path:   Path to mock_calendar.json (used only for mock fallback).
        max_results:     Maximum number of slots to return (default 2).
        reference_date:  Override "today" for testing.

    Returns:
        List of up to `max_results` CalendarSlot objects with status=AVAILABLE.
        Empty list if no slots match.
    """
    candidate_dates, _ = _parse_day_preference(day_preference, reference_date)
    time_band, _       = _parse_time_preference(time_preference)

    # Try Google Calendar first (requires GOOGLE_CALENDAR_ID + service account)
    use_gcal = bool(os.environ.get("GOOGLE_CALENDAR_ID", "").strip())
    if use_gcal:
        gcal_slots = _resolve_slots_gcal(candidate_dates, time_band, max_results)
        if gcal_slots:
            return gcal_slots
        # GCal returned empty — fall through to mock (handles misconfiguration gracefully)

    # Fall back to mock calendar
    return _resolve_slots_mock(candidate_dates, time_band, topic, calendar_path, max_results)
