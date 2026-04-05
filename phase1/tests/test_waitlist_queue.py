"""
tests/test_waitlist_queue.py

Tests for the WaitlistQueue FIFO promotion engine.

TC-WQ-1   add() returns correct 1-based position
TC-WQ-2   FIFO order — first in, first promoted
TC-WQ-3   Topic filtering — wrong topic not promoted
TC-WQ-4   Topic filtering — any-topic slot promotes anyone
TC-WQ-5   Time band matching — morning entry not promoted for evening slot
TC-WQ-6   Time band matching — afternoon entry promoted for afternoon slot
TC-WQ-7   position() returns correct rank, None for unknown
TC-WQ-8   cancel_entry() removes from active queue
TC-WQ-9   on_cancellation() returns None when queue empty
TC-WQ-10  on_cancellation() returns None when no match
TC-WQ-11  Multiple cancellations promote in order
TC-WQ-12  FULFILLED entry is skipped for next promotion
TC-WQ-13  snapshot() shows queue_position only for ACTIVE entries
TC-WQ-14  active_count() correct after adds and cancels
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytz
import pytest

from src.booking.waitlist_queue import WaitlistQueue, PromotionResult, _topic_matches_slot, _time_pref_matches_slot
from src.booking.waitlist_handler import create_waitlist_entry
from src.booking.slot_resolver import CalendarSlot

IST = pytz.timezone("Asia/Kolkata")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _entry(topic="kyc_onboarding", day="Monday", time="morning", offset_seconds=0):
    ref = datetime(2026, 4, 6, 9, 0, 0, tzinfo=IST) + timedelta(seconds=offset_seconds)
    return create_waitlist_entry(topic=topic, day_preference=day, time_preference=time, reference_time=ref)


def _slot(hour=10, topic_affinity=None):
    start = datetime(2026, 4, 6, hour, 0, 0, tzinfo=IST)
    end   = datetime(2026, 4, 6, hour + 1, 0, 0, tzinfo=IST)
    return CalendarSlot(
        slot_id=f"SLOT-{hour}",
        start=start,
        end=end,
        status="AVAILABLE",
        topic_affinity=topic_affinity or [],
    )


# ── TC-WQ-1: position on add ───────────────────────────────────────────────────

def test_add_returns_position_1_for_first_entry():
    q = WaitlistQueue()
    e = _entry()
    assert q.add(e) == 1


def test_add_returns_incrementing_positions():
    q = WaitlistQueue()
    assert q.add(_entry(offset_seconds=0)) == 1
    assert q.add(_entry(offset_seconds=1)) == 2
    assert q.add(_entry(offset_seconds=2)) == 3


# ── TC-WQ-2: FIFO promotion ────────────────────────────────────────────────────

def test_fifo_first_entry_promoted():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1)
    q.add(e2)
    slot = _slot(hour=10)  # morning — matches "morning" preference
    result = q.on_cancellation(slot)
    assert result is not None
    assert result.promoted_entry.waitlist_code == e1.waitlist_code
    assert result.position_was == 1


def test_fifo_second_promoted_after_first_fulfilled():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1)
    q.add(e2)
    slot = _slot(hour=10)
    q.on_cancellation(slot)   # promotes e1
    result = q.on_cancellation(slot)  # should promote e2
    assert result is not None
    assert result.promoted_entry.waitlist_code == e2.waitlist_code


# ── TC-WQ-3: Topic filtering — wrong topic ─────────────────────────────────────

def test_topic_mismatch_not_promoted():
    q = WaitlistQueue()
    e = _entry(topic="kyc_onboarding")
    q.add(e)
    slot = _slot(hour=10, topic_affinity=["sip_mandates"])  # slot only for SIP
    result = q.on_cancellation(slot)
    assert result is None


# ── TC-WQ-4: Topic filtering — any-topic slot ─────────────────────────────────

def test_any_topic_slot_promotes_any_entry():
    q = WaitlistQueue()
    e = _entry(topic="withdrawals")
    q.add(e)
    slot = _slot(hour=10, topic_affinity=[])  # no restriction
    result = q.on_cancellation(slot)
    assert result is not None
    assert result.promoted_entry.topic == "withdrawals"


# ── TC-WQ-5: Time band — morning entry vs evening slot ────────────────────────

def test_morning_preference_not_promoted_for_evening_slot():
    q = WaitlistQueue()
    e = _entry(time="morning")
    q.add(e)
    slot = _slot(hour=18)  # 6pm — evening
    result = q.on_cancellation(slot)
    assert result is None


# ── TC-WQ-6: Time band — afternoon match ──────────────────────────────────────

def test_afternoon_preference_promoted_for_afternoon_slot():
    q = WaitlistQueue()
    e = _entry(time="afternoon")
    q.add(e)
    slot = _slot(hour=14)  # 2pm — afternoon (12-17)
    result = q.on_cancellation(slot)
    assert result is not None


# ── TC-WQ-7: position() ────────────────────────────────────────────────────────

def test_position_correct():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    e3 = _entry(offset_seconds=2)
    q.add(e1); q.add(e2); q.add(e3)
    assert q.position(e1.waitlist_code) == 1
    assert q.position(e2.waitlist_code) == 2
    assert q.position(e3.waitlist_code) == 3


def test_position_none_for_unknown_code():
    q = WaitlistQueue()
    assert q.position("NL-WXYZ") is None


def test_position_none_after_fulfillment():
    q = WaitlistQueue()
    e = _entry()
    q.add(e)
    q.on_cancellation(_slot(hour=10))  # fulfils e
    assert q.position(e.waitlist_code) is None


# ── TC-WQ-8: cancel_entry() ───────────────────────────────────────────────────

def test_cancel_entry_removes_from_active():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1); q.add(e2)
    assert q.cancel_entry(e1.waitlist_code)
    assert q.position(e1.waitlist_code) is None
    assert q.position(e2.waitlist_code) == 1  # e2 moves to position 1


def test_cancel_entry_false_for_unknown():
    q = WaitlistQueue()
    assert not q.cancel_entry("NL-WXYZ")


def test_cancelled_entry_skipped_on_promotion():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1); q.add(e2)
    q.cancel_entry(e1.waitlist_code)
    result = q.on_cancellation(_slot(hour=10))
    assert result is not None
    assert result.promoted_entry.waitlist_code == e2.waitlist_code
    assert result.position_was == 1  # e2 was position 1 after e1 cancelled


# ── TC-WQ-9: empty queue ──────────────────────────────────────────────────────

def test_on_cancellation_empty_queue_returns_none():
    q = WaitlistQueue()
    assert q.on_cancellation(_slot(hour=10)) is None


# ── TC-WQ-10: no match ────────────────────────────────────────────────────────

def test_on_cancellation_no_match_returns_none():
    q = WaitlistQueue()
    e = _entry(topic="kyc_onboarding", time="morning")
    q.add(e)
    slot = _slot(hour=18, topic_affinity=["sip_mandates"])  # wrong topic + wrong time
    assert q.on_cancellation(slot) is None


# ── TC-WQ-11: multiple promotions in order ────────────────────────────────────

def test_multiple_cancellations_promote_in_order():
    q = WaitlistQueue()
    entries = [_entry(offset_seconds=i) for i in range(4)]
    for e in entries:
        q.add(e)

    slot = _slot(hour=10)
    codes_promoted = []
    for _ in range(4):
        r = q.on_cancellation(slot)
        if r:
            codes_promoted.append(r.promoted_entry.waitlist_code)

    # Should be promoted in exact FIFO order
    assert codes_promoted == [e.waitlist_code for e in entries]


# ── TC-WQ-12: FULFILLED entry skipped ────────────────────────────────────────

def test_fulfilled_entry_skipped():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1); q.add(e2)
    slot = _slot(hour=10)
    q.on_cancellation(slot)  # fulfils e1
    assert e1.status == "FULFILLED"
    result = q.on_cancellation(slot)
    assert result.promoted_entry.waitlist_code == e2.waitlist_code


# ── TC-WQ-13: snapshot ────────────────────────────────────────────────────────

def test_snapshot_shows_position_for_active_only():
    q = WaitlistQueue()
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1); q.add(e2)
    q.cancel_entry(e1.waitlist_code)
    snap = q.snapshot()
    # e1 cancelled — no position
    e1_snap = next(s for s in snap if s["waitlist_code"] == e1.waitlist_code)
    e2_snap = next(s for s in snap if s["waitlist_code"] == e2.waitlist_code)
    assert e1_snap["queue_position"] is None
    assert e2_snap["queue_position"] == 1


# ── TC-WQ-14: active_count ────────────────────────────────────────────────────

def test_active_count():
    q = WaitlistQueue()
    assert q.active_count() == 0
    e1 = _entry(offset_seconds=0)
    e2 = _entry(offset_seconds=1)
    q.add(e1); q.add(e2)
    assert q.active_count() == 2
    q.cancel_entry(e1.waitlist_code)
    assert q.active_count() == 1
    q.on_cancellation(_slot(hour=10))  # fulfils e2
    assert q.active_count() == 0
