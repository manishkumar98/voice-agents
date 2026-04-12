"""
Phase 4 — Google Calendar tool.
Creates a TENTATIVE calendar hold for an advisor slot.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import config
from .models import MCPPayload, ToolResult

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_service():
    creds = service_account.Credentials.from_service_account_info(
        config.service_account, scopes=_SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def _create_hold_sync(payload: MCPPayload) -> dict:
    service = _build_service()

    start_dt = datetime.fromisoformat(payload.slot_start_iso)
    end_dt   = datetime.fromisoformat(payload.slot_end_iso)

    event_body = {
        "summary": f"Advisor Q&A — {payload.topic_label} — {payload.booking_code}",
        "description": (
            f"Pre-booking via Voice Agent\n"
            f"Booking Code : {payload.booking_code}\n"
            f"Topic        : {payload.topic_label}\n"
            f"Advisor ID   : {payload.advisor_id}\n"
            f"Call ID      : {payload.call_id}\n"
            f"Created      : {payload.created_at_ist}"
        ),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
        "status": "tentative",
        "colorId": "5",   # banana yellow — clearly tentative
        "reminders": {"useDefault": False},
    }

    created = (
        service.events()
        .insert(calendarId=config.calendar_id, body=event_body, sendUpdates="none")
        .execute()
    )

    return {
        "event_id":  created["id"],
        "html_link": created.get("htmlLink", ""),
        "status":    created.get("status", "tentative"),
    }


async def create_calendar_hold(payload: MCPPayload) -> ToolResult:
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _create_hold_sync, payload)
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except HttpError as exc:
        return ToolResult(
            success=False,
            error=f"Calendar API {exc.status_code}: {exc.reason}",
            duration_ms=(time.monotonic() - t0) * 1000,
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)


def _cancel_event_sync(event_id: str) -> dict:
    """
    Delete a Google Calendar event so it no longer appears on the calendar.
    """
    service = _build_service()
    try:
        service.events().delete(
            calendarId=config.calendar_id,
            eventId=event_id,
            sendUpdates="none",
        ).execute()
        return {"event_id": event_id, "action": "deleted"}
    except HttpError as exc:
        if exc.status_code == 410:  # already deleted
            return {"event_id": event_id, "action": "already_gone"}
        raise


def _find_event_by_booking_code_sync(booking_code: str) -> str | None:
    """
    Search the calendar for an event whose summary contains the booking code.
    Returns the event_id or None if not found.
    """
    service = _build_service()
    results = service.events().list(
        calendarId=config.calendar_id,
        q=booking_code,
        singleEvents=True,
        maxResults=5,
    ).execute()
    for event in results.get("items", []):
        if booking_code in event.get("summary", ""):
            return event["id"]
    return None


def _update_event_sync(event_id: str, new_start_iso: str, new_end_iso: str) -> dict:
    """PATCH an existing calendar event with new start/end times."""
    service = _build_service()
    start_dt = datetime.fromisoformat(new_start_iso)
    end_dt   = datetime.fromisoformat(new_end_iso)
    patch_body = {
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
    }
    updated = (
        service.events()
        .patch(calendarId=config.calendar_id, eventId=event_id,
               body=patch_body, sendUpdates="none")
        .execute()
    )
    return {"event_id": updated["id"], "status": updated.get("status", "confirmed")}


async def update_calendar_event(event_id: str, new_start_iso: str, new_end_iso: str) -> ToolResult:
    """Update an existing calendar event's time in-place."""
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _update_event_sync, event_id, new_start_iso, new_end_iso
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except HttpError as exc:
        return ToolResult(success=False, error=f"Calendar API {exc.status_code}: {exc.reason}",
                          duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)


async def cancel_calendar_event(event_id: str | None, booking_code: str | None = None) -> ToolResult:
    """
    Cancel a calendar event by event_id. If event_id is missing, searches by booking_code.
    """
    t0 = time.monotonic()
    try:
        _eid = event_id
        if not _eid and booking_code:
            _eid = await asyncio.get_event_loop().run_in_executor(
                None, _find_event_by_booking_code_sync, booking_code
            )
        if not _eid:
            return ToolResult(success=False, error="Event ID not found",
                              duration_ms=(time.monotonic() - t0) * 1000)
        data = await asyncio.get_event_loop().run_in_executor(None, _cancel_event_sync, _eid)
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except HttpError as exc:
        return ToolResult(success=False, error=f"Calendar API {exc.status_code}: {exc.reason}",
                          duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)
