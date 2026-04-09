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

from .calendar_tool import create_calendar_hold
from .config import config
from .email_tool import draft_approval_email
from .mcp_logger import MCPLogger
from .models import MCPPayload, MCPResults, ToolResult
from .sheets_tool import append_booking_notes

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
