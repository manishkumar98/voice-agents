# Phase 1 — Booking Brain ✅ Done

**Goal:** Pure business logic — no LLM, no voice, no external APIs. All offline and unit-testable.

## What's in this folder

```
phase1/
├── src/booking/
│   ├── slot_resolver.py           # Natural language → CalendarSlot objects
│   ├── booking_code_generator.py  # NL-XXXX code generation
│   ├── waitlist_handler.py        # WaitlistEntry dataclass + factory
│   ├── waitlist_queue.py          # Thread-safe FIFO queue + slot promotion
│   ├── pii_scrubber.py            # Two-pass regex PII scrubber
│   └── secure_url_generator.py    # HMAC-signed booking URLs (itsdangerous)
├── data/
│   └── mock_calendar.json         # Advisor availability fixture
└── tests/
    ├── test_phase1_booking.py
    └── test_waitlist_queue.py
```

## What was built

| Component | Status |
|---|---|
| `resolve_slots(day, time, topic)` — NL → `CalendarSlot` | ✅ |
| 4-step slot expansion (exact → same day → this week → next week) | ✅ |
| `generate_booking_code()` — NL-XXXX format | ✅ |
| `generate_waitlist_code()` — NL-WXXX format | ✅ |
| `WaitlistQueue` — FIFO + slot-promotion on cancellation | ✅ |
| `scrub_pii()` — phone, email, PAN, Aadhaar, 16-digit account | ✅ |
| `generate_secure_url()` — HMAC-SHA256, 24h TTL | ✅ |

## How to import (from any entry point)

```python
from src.booking.slot_resolver import resolve_slots, CalendarSlot
from src.booking.booking_code_generator import generate_booking_code
from src.booking.waitlist_handler import create_waitlist_entry
from src.booking.pii_scrubber import scrub_pii
from src.booking.secure_url_generator import generate_secure_url
```

> **Note:** `path_setup.py` (in `phase0/`) must be run before these imports so that `phase1/` is on `sys.path`.

## How to run tests

```bash
cd voice-agents/phase0
pytest ../phase1/tests/
```
