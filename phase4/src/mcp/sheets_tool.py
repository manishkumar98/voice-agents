"""
Phase 4 — Google Sheets tool.
Appends one booking-notes row to the Advisor Pre-Bookings worksheet.
"""
from __future__ import annotations

import asyncio
import re
import time

import gspread
from google.oauth2 import service_account

from .config import config
from .models import MCPPayload, ToolResult

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "booking_code", "topic_key", "topic_label",
    "slot_start_ist", "slot_end_ist", "advisor_id",
    "status", "calendar_event_id", "email_draft_id",
    "created_at_ist", "call_id",
]


def _build_client() -> gspread.Client:
    creds = service_account.Credentials.from_service_account_info(
        config.service_account, scopes=_SCOPES
    )
    return gspread.authorize(creds)


def _ensure_headers(worksheet: gspread.Worksheet) -> None:
    """Insert header row if the sheet is empty or has wrong headers."""
    existing = worksheet.row_values(1)
    if not existing or existing[0] != "booking_code":
        worksheet.insert_row(SHEET_HEADERS, index=1)


def _append_row_sync(payload: MCPPayload, event_id: str | None) -> dict:
    client = _build_client()
    spreadsheet = client.open_by_key(config.sheet_id)

    try:
        ws = spreadsheet.worksheet(config.sheet_tab)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=config.sheet_tab, rows=1000, cols=20)

    _ensure_headers(ws)

    row = [
        payload.booking_code,
        payload.topic_key,
        payload.topic_label,
        payload.slot_start_ist,
        "",                      # slot_end_ist — filled by calendar separately
        payload.advisor_id,
        "tentative",
        event_id or "",
        "",                      # email_draft_id — filled after email tool
        payload.created_at_ist,
        payload.call_id,
    ]

    result = ws.append_row(row, value_input_option="USER_ENTERED")

    updated_range = result.get("updates", {}).get("updatedRange", "")
    row_index: int | None = None
    if updated_range:
        m = re.search(r"(\d+)$", updated_range)
        if m:
            row_index = int(m.group(1))

    return {"row_index": row_index, "updated_range": updated_range}


async def append_booking_notes(payload: MCPPayload, event_id: str | None = None) -> ToolResult:
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _append_row_sync, payload, event_id
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        err_msg = str(exc) or repr(exc)
        return ToolResult(success=False, error=err_msg, duration_ms=(time.monotonic() - t0) * 1000)
