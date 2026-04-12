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
        payload.status,
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


def _get_booking_row_sync(booking_code: str) -> tuple[int | None, str | None]:
    """
    Find the row index and calendar_event_id for a booking code.
    Returns (row_index, event_id) or (None, None) if not found.
    """
    details = _get_booking_details_sync(booking_code)
    if details is None:
        return None, None
    return details["row_index"], details.get("calendar_event_id") or None


def _get_booking_details_sync(booking_code: str) -> dict | None:
    """
    Return all stored fields for a booking code as a dict, or None if not found.
    Keys: row_index, booking_code, topic_key, topic_label, slot_start_ist,
          slot_end_ist, advisor_id, status, calendar_event_id, created_at_ist, call_id
    """
    client = _build_client()
    spreadsheet = client.open_by_key(config.sheet_id)
    try:
        ws = spreadsheet.worksheet(config.sheet_tab)
    except gspread.WorksheetNotFound:
        return None

    all_values = ws.get_all_values()
    if not all_values:
        return None

    headers = [h.lower().strip() for h in all_values[0]]
    try:
        code_col = headers.index("booking_code")
    except ValueError:
        return None

    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) > code_col and row[code_col].strip() == booking_code:
            record = {"row_index": row_idx}
            for col_idx, header in enumerate(headers):
                record[header] = row[col_idx] if col_idx < len(row) else ""
            return record

    return None


def _update_status_sync(booking_code: str, new_status: str) -> dict:
    """
    Find the row for booking_code and update its status column.
    Returns {"row_index": int, "booking_code": str, "status": str}.
    """
    client = _build_client()
    spreadsheet = client.open_by_key(config.sheet_id)
    try:
        ws = spreadsheet.worksheet(config.sheet_tab)
    except gspread.WorksheetNotFound:
        raise RuntimeError(f"Sheet tab '{config.sheet_tab}' not found")

    all_values = ws.get_all_values()
    if not all_values:
        raise RuntimeError("Sheet is empty")

    headers = [h.lower().strip() for h in all_values[0]]
    try:
        code_col   = headers.index("booking_code")
        status_col = headers.index("status")
    except ValueError as e:
        raise RuntimeError(f"Missing column: {e}")

    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) > code_col and row[code_col].strip() == booking_code:
            # status_col is 0-based in list → 1-based column letter in Sheets
            ws.update_cell(row_idx, status_col + 1, new_status)
            return {"row_index": row_idx, "booking_code": booking_code, "status": new_status}

    raise RuntimeError(f"Booking code {booking_code!r} not found in sheet")


def _reschedule_row_sync(booking_code: str, new_slot_start_ist: str,
                         new_slot_end_ist: str, new_event_id: str | None) -> dict:
    """
    Update an existing Sheets row in-place for a reschedule.
    Updates: slot_start_ist, slot_end_ist, calendar_event_id, status → 'rescheduled'.
    """
    client = _build_client()
    spreadsheet = client.open_by_key(config.sheet_id)
    try:
        ws = spreadsheet.worksheet(config.sheet_tab)
    except gspread.WorksheetNotFound:
        raise RuntimeError(f"Sheet tab '{config.sheet_tab}' not found")

    all_values = ws.get_all_values()
    if not all_values:
        raise RuntimeError("Sheet is empty")

    headers = [h.lower().strip() for h in all_values[0]]
    try:
        code_col      = headers.index("booking_code")
        start_col     = headers.index("slot_start_ist")
        end_col       = headers.index("slot_end_ist")
        status_col    = headers.index("status")
        event_col     = headers.index("calendar_event_id")
    except ValueError as e:
        raise RuntimeError(f"Missing column: {e}")

    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) > code_col and row[code_col].strip() == booking_code:
            ws.update_cell(row_idx, start_col  + 1, new_slot_start_ist)
            ws.update_cell(row_idx, end_col    + 1, new_slot_end_ist)
            ws.update_cell(row_idx, status_col + 1, "rescheduled")
            if new_event_id:
                ws.update_cell(row_idx, event_col + 1, new_event_id)
            return {"row_index": row_idx, "booking_code": booking_code, "status": "rescheduled"}

    raise RuntimeError(f"Booking code {booking_code!r} not found in sheet")


async def reschedule_booking_in_sheets(booking_code: str, new_slot_start_ist: str,
                                       new_slot_end_ist: str, new_event_id: str | None) -> ToolResult:
    """Update the existing row for a rescheduled booking."""
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _reschedule_row_sync, booking_code, new_slot_start_ist, new_slot_end_ist, new_event_id
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)


async def update_booking_status(booking_code: str, new_status: str) -> ToolResult:
    """Update the status column for a booking code row."""
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _update_status_sync, booking_code, new_status
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)


async def get_event_id_for_booking(booking_code: str) -> str | None:
    """Return the calendar_event_id stored for the booking, or None."""
    row_idx, event_id = await asyncio.get_event_loop().run_in_executor(
        None, _get_booking_row_sync, booking_code
    )
    return event_id


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
