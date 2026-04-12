"""
Phase 4 — MCP Orchestrator.

Execution order:
  1. Calendar hold (sequential — email & sheets need the event_id)
  2. Sheet append + Email draft (parallel via asyncio.gather)

Any single tool failure does NOT block booking code issuance.
Partial failures are logged to mcp_ops_log.jsonl for async retry.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import time
from datetime import datetime, timedelta

import pytz

from .calendar_tool import cancel_calendar_event, create_calendar_hold, update_calendar_event
from .config import config
from .email_tool import draft_approval_email
from .mcp_logger import MCPLogger
from .models import MCPPayload, MCPResults, ToolResult
from .sheets_tool import (append_booking_notes, get_event_id_for_booking,
                           reschedule_booking_in_sheets, update_booking_status)

IST = pytz.timezone("Asia/Kolkata")
_logger = MCPLogger()


def build_payload(ctx) -> MCPPayload:
    """
    Build MCPPayload from a DialogueContext.
    Import is deferred to avoid circular dependency when called from fsm.py.
    """
    try:
        from src.dialogue.states import TOPIC_LABELS
    except ImportError:
        TOPIC_LABELS = {}

    topic_key   = ctx.topic or "general"
    topic_label = TOPIC_LABELS.get(topic_key, topic_key.replace("_", " ").title())

    slot_start_iso = ""
    slot_start_ist = "TBD"
    slot_end_iso   = ""

    if ctx.resolved_slot:
        slot_start_iso = ctx.resolved_slot.get("start", "")
        slot_start_ist = ctx.resolved_slot.get("start_ist", slot_start_iso)
        if slot_start_iso:
            start_dt   = datetime.fromisoformat(slot_start_iso)
            end_dt     = start_dt + timedelta(minutes=config.slot_duration_minutes)
            slot_end_iso = end_dt.isoformat()

    return MCPPayload(
        booking_code   = ctx.booking_code or "",
        call_id        = ctx.call_id,
        topic_key      = topic_key,
        topic_label    = topic_label,
        slot_start_iso = slot_start_iso,
        slot_start_ist = slot_start_ist,
        slot_end_iso   = slot_end_iso,
        advisor_id     = config.advisor_id,
        created_at_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
    )


async def dispatch_mcp(payload: MCPPayload) -> MCPResults:
    """
    Full async MCP dispatch:
      Step 1 — Calendar hold (sequential, provides event_id)
      Step 2 — Sheet row + Email draft (parallel)
    """
    t0 = time.monotonic()

    # Step 1: Calendar
    calendar_result = await create_calendar_hold(payload)
    event_id = calendar_result.data.get("event_id") if calendar_result.success else None

    # Step 2: Parallel
    raw_sheets, raw_email = await asyncio.gather(
        append_booking_notes(payload, event_id),
        draft_approval_email(payload, event_id),
        return_exceptions=True,
    )

    sheets_result: ToolResult = (
        raw_sheets if isinstance(raw_sheets, ToolResult)
        else ToolResult(success=False, error=str(raw_sheets))
    )
    email_result: ToolResult = (
        raw_email if isinstance(raw_email, ToolResult)
        else ToolResult(success=False, error=str(raw_email))
    )

    results = MCPResults(
        calendar          = calendar_result,
        sheets            = sheets_result,
        email             = email_result,
        total_duration_ms = (time.monotonic() - t0) * 1000,
    )

    _logger.log(payload, results)
    return results


def build_waitlist_payload(waitlist_entry, ctx) -> MCPPayload:
    """
    Build MCPPayload for a waitlist entry.
    No confirmed slot exists, so a next-business-day placeholder is used for the
    calendar hold; the title and notes make the waitlist nature explicit.
    """
    try:
        from src.dialogue.states import TOPIC_LABELS
    except ImportError:
        TOPIC_LABELS = {}

    topic_key   = ctx.topic or "general"
    topic_label = TOPIC_LABELS.get(topic_key, topic_key.replace("_", " ").title())

    # Placeholder time: next weekday at 10:00 AM IST
    now_ist    = datetime.now(IST)
    days_ahead = 1
    while True:
        candidate = now_ist + timedelta(days=days_ahead)
        if candidate.weekday() < 5:   # Mon–Fri
            break
        days_ahead += 1
    placeholder_start = candidate.replace(hour=10, minute=0, second=0, microsecond=0)
    placeholder_end   = placeholder_start + timedelta(minutes=config.slot_duration_minutes)

    preferred = f"{waitlist_entry.day_preference} {waitlist_entry.time_preference}".strip()

    return MCPPayload(
        booking_code   = waitlist_entry.waitlist_code,
        call_id        = ctx.call_id,
        topic_key      = topic_key,
        topic_label    = f"{topic_label} (Waitlist)",
        slot_start_iso = placeholder_start.isoformat(),
        slot_start_ist = f"Waitlist — preferred: {preferred}",
        slot_end_iso   = placeholder_end.isoformat(),
        advisor_id     = config.advisor_id,
        created_at_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        status         = "waitlisted",
    )


def dispatch_mcp_sync(payload: MCPPayload) -> MCPResults:
    """
    Synchronous wrapper around dispatch_mcp.
    Safe to call from the synchronous FSM regardless of whether an event loop
    is already running (e.g. inside Streamlit or Jupyter).
    """
    try:
        asyncio.get_running_loop()
        # Already inside a running loop — use a worker thread with its own loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, dispatch_mcp(payload))
            return future.result(timeout=15)
    except RuntimeError:
        # No running loop — safe to call asyncio.run directly
        return asyncio.run(dispatch_mcp(payload))


def record_waitlist_in_sheets_sync(waitlist_entry, ctx) -> None:
    """
    Write a 'waitlisted' row to Google Sheets for a new waitlist entry.
    Failures are silently ignored — waitlist still works without Sheets.
    """
    try:
        payload = build_waitlist_payload(waitlist_entry, ctx)
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, append_booking_notes(payload)).result(timeout=10)
        except RuntimeError:
            asyncio.run(append_booking_notes(payload))
    except Exception:
        pass


async def cancel_booking_mcp(booking_code: str) -> MCPResults:
    """
    Cancel a booking in both Google Calendar and Google Sheets.
      Step 1 — Get the calendar event_id from Sheets (or fall back to calendar search)
      Step 2 — Cancel the Calendar event (PATCH to 'cancelled', falls back to DELETE)
      Step 3 — Update the Sheets row status to 'CANCELLED'
    Partial failures are tolerated — all results are returned for inspection.
    """
    t0 = time.monotonic()

    # Step 1: Retrieve event_id from Sheets
    event_id = await get_event_id_for_booking(booking_code)

    # Step 2 & 3: Cancel Calendar + update Sheets in parallel
    cal_result, sheets_result = await asyncio.gather(
        cancel_calendar_event(event_id, booking_code),
        update_booking_status(booking_code, "cancelled"),
        return_exceptions=True,
    )

    if not isinstance(cal_result, ToolResult):
        cal_result = ToolResult(success=False, error=str(cal_result))
    if not isinstance(sheets_result, ToolResult):
        sheets_result = ToolResult(success=False, error=str(sheets_result))

    results = MCPResults(
        calendar          = cal_result,
        sheets            = sheets_result,
        email             = ToolResult(success=True, data={"skipped": "cancellation has no email step"}),
        total_duration_ms = (time.monotonic() - t0) * 1000,
    )
    # Re-use MCPLogger so cancel results appear in the same ops log
    from .models import MCPPayload as _MP
    from datetime import datetime as _dt
    _cancel_payload = _MP(
        booking_code=booking_code, call_id="cancel", topic_key="cancel",
        topic_label="Cancellation", slot_start_iso="", slot_start_ist="",
        slot_end_iso="", advisor_id=config.advisor_id,
        created_at_ist=_dt.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        status="cancelled",
    )
    _logger.log(_cancel_payload, results)
    return results


def cancel_booking_mcp_sync(booking_code: str) -> MCPResults:
    """
    Synchronous wrapper for cancel_booking_mcp.
    Safe to call from the synchronous FSM.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, cancel_booking_mcp(booking_code))
            return future.result(timeout=15)
    except RuntimeError:
        return asyncio.run(cancel_booking_mcp(booking_code))


async def reschedule_booking_mcp(
    booking_code: str,
    new_slot_start_iso: str,
    new_slot_end_iso: str,
    new_slot_start_ist: str,
) -> MCPResults:
    """
    Reschedule an existing booking in-place:
      Step 1 — Fetch calendar_event_id from Sheets
      Step 2 — PATCH the Calendar event with new times
      Step 3 — Update the Sheets row: new slot times + status='rescheduled'
    The booking code, topic, and advisor are all preserved.
    """
    t0 = time.monotonic()

    # Step 1: get existing event_id
    event_id = await get_event_id_for_booking(booking_code)

    # Step 2: update Calendar event (or skip if no event_id found)
    if event_id:
        cal_result = await update_calendar_event(event_id, new_slot_start_iso, new_slot_end_iso)
    else:
        cal_result = ToolResult(
            success=False,
            error=f"No calendar event found for {booking_code}",
            duration_ms=0,
        )

    # Step 3: update Sheets row in-place
    new_slot_end_ist = ""
    if new_slot_end_iso:
        try:
            end_dt = datetime.fromisoformat(new_slot_end_iso)
            new_slot_end_ist = end_dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")
        except Exception:
            pass

    sheets_result = await reschedule_booking_in_sheets(
        booking_code,
        new_slot_start_ist,
        new_slot_end_ist,
        event_id,
    )

    results = MCPResults(
        calendar=cal_result,
        sheets=sheets_result,
        email=ToolResult(success=True, data={"skipped": "reschedule has no new email step"}),
        total_duration_ms=(time.monotonic() - t0) * 1000,
    )

    from .models import MCPPayload as _MP
    from datetime import datetime as _dt
    _reschedule_payload = _MP(
        booking_code=booking_code, call_id="reschedule", topic_key="reschedule",
        topic_label="Reschedule", slot_start_iso=new_slot_start_iso,
        slot_start_ist=new_slot_start_ist, slot_end_iso=new_slot_end_iso,
        advisor_id=config.advisor_id,
        created_at_ist=_dt.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        status="rescheduled",
    )
    _logger.log(_reschedule_payload, results)
    return results


def reschedule_booking_mcp_sync(
    booking_code: str,
    new_slot_start_iso: str,
    new_slot_end_iso: str,
    new_slot_start_ist: str,
) -> MCPResults:
    """Synchronous wrapper for reschedule_booking_mcp. Safe to call from the FSM."""
    coro = reschedule_booking_mcp(booking_code, new_slot_start_iso, new_slot_end_iso, new_slot_start_ist)
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=15)
    except RuntimeError:
        return asyncio.run(coro)
