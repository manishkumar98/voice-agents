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
        "summary": f"[TENTATIVE] {payload.topic_label} — {payload.booking_code}",
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
