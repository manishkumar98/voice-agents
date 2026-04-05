"""
Phase 4 — Gmail draft tool.
Saves a pre-booking approval email to the Gmail Drafts folder via IMAP APPEND.
The advisor receives it in Drafts; they review and click Send manually.
"""
from __future__ import annotations

import asyncio
import imaplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import config
from .models import MCPPayload, ToolResult

_IMAP_HOST = "imap.gmail.com"


def _html_body(payload: MCPPayload, event_id: str | None) -> str:
    cal_row = (
        f"<tr><td style='padding:8px;border:1px solid #ddd'><b>Calendar Event</b></td>"
        f"<td style='padding:8px;border:1px solid #ddd'>{event_id}</td></tr>"
        if event_id else ""
    )
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:640px">
<h2 style="color:#1a73e8">📅 Pre-Booking Request — {payload.topic_label}</h2>
<p>Dear {config.advisor_name},</p>
<p>A new advisor pre-booking has been created via the Voice Scheduling Agent.
Please review and confirm or reschedule as needed.</p>
<table style="border-collapse:collapse;width:100%">
  <tr style="background:#f1f3f4">
    <td style="padding:8px;border:1px solid #ddd"><b>Booking Code</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.booking_code}</td>
  </tr>
  <tr>
    <td style="padding:8px;border:1px solid #ddd"><b>Topic</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.topic_label}</td>
  </tr>
  <tr style="background:#f1f3f4">
    <td style="padding:8px;border:1px solid #ddd"><b>Slot (IST)</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.slot_start_ist}</td>
  </tr>
  <tr>
    <td style="padding:8px;border:1px solid #ddd"><b>Advisor ID</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.advisor_id}</td>
  </tr>
  <tr style="background:#f1f3f4">
    <td style="padding:8px;border:1px solid #ddd"><b>Status</b></td>
    <td style="padding:8px;border:1px solid #ddd"><span style="color:#f5a623;font-weight:bold">TENTATIVE</span></td>
  </tr>
  {cal_row}
  <tr>
    <td style="padding:8px;border:1px solid #ddd"><b>Call ID</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.call_id}</td>
  </tr>
  <tr style="background:#f1f3f4">
    <td style="padding:8px;border:1px solid #ddd"><b>Created At</b></td>
    <td style="padding:8px;border:1px solid #ddd">{payload.created_at_ist}</td>
  </tr>
</table>
<br>
<p style="color:#888;font-size:12px">
  Automated pre-booking notification. No PII was shared on the voice call.
  The client will receive a secure link to complete their details.
</p>
</body></html>"""


def _create_draft_sync(payload: MCPPayload, event_id: str | None) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"]    = config.gmail_address
    msg["To"]      = config.advisor_email
    msg["Subject"] = (
        f"[Pre-Booking] {payload.topic_label} — "
        f"{payload.booking_code} — {payload.slot_start_ist}"
    )
    msg["X-BookingCode"] = payload.booking_code
    msg["X-CallID"]      = payload.call_id

    plain = (
        f"Pre-Booking: {payload.topic_label}\n"
        f"Booking Code: {payload.booking_code}\n"
        f"Slot:         {payload.slot_start_ist}\n"
        f"Advisor:      {payload.advisor_id}\n"
        f"Call ID:      {payload.call_id}\n"
        f"Created:      {payload.created_at_ist}\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_html_body(payload, event_id), "html"))

    with imaplib.IMAP4_SSL(_IMAP_HOST) as imap:
        imap.login(config.gmail_address, config.gmail_app_password)
        # Gmail drafts folder name
        status, data = imap.append(
            '"[Gmail]/Drafts"',
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )
        if status != "OK":
            raise RuntimeError(f"IMAP APPEND failed: {status} — {data}")

        draft_uid = data[0].decode("utf-8") if data and data[0] else "unknown"

    return {"draft_id": draft_uid, "to": config.advisor_email}


async def draft_approval_email(payload: MCPPayload, event_id: str | None = None) -> ToolResult:
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _create_draft_sync, payload, event_id
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)
