"""
Phase 4 — Gmail email tools.

draft_approval_email   — saves advisor approval email to Gmail Drafts (IMAP APPEND)
send_user_confirmation — actually sends a confirmation email to the user via SMTP
"""
from __future__ import annotations

import asyncio
import imaplib
import smtplib
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


def _user_confirmation_html(name: str, booking_code: str, topic_label: str, slot_ist: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto">
<div style="background:linear-gradient(135deg,#8b5cf6,#6d28d9);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0">📅 Appointment Confirmed</h2>
  <p style="color:#ede9fe;margin:6px 0 0">Advisor Scheduling — Booking Details</p>
</div>
<div style="background:#ffffff;border:1px solid #ede9fe;border-radius:0 0 12px 12px;padding:28px 32px">
  <p>Dear <strong>{name}</strong>,</p>
  <p>Your advisor appointment has been tentatively confirmed. Here are your details:</p>
  <table style="border-collapse:collapse;width:100%;margin:16px 0">
    <tr style="background:#f5f3ff">
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Booking Code</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">
        <span style="background:#ede9fe;color:#6d28d9;padding:3px 10px;border-radius:6px;font-weight:700;font-size:1.05em">{booking_code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Topic</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">{topic_label}</td>
    </tr>
    <tr style="background:#f5f3ff">
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Date &amp; Time</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">{slot_ist} <span style="color:#7c3aed;font-size:0.88em">(IST)</span></td>
    </tr>
  </table>
  <p style="background:#fef9c3;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;font-size:0.92em">
    ⚠️ This is a <strong>tentative hold</strong>. An advisor will reach out to confirm.
    No investment advice will be provided — this is an informational consultation only.
  </p>
  <p style="color:#6b7280;font-size:0.85em;margin-top:20px">
    If you did not request this booking, please ignore this email.<br>
    To reschedule or cancel, call us and quote your booking code.
  </p>
</div>
</body></html>"""


def send_user_confirmation(
    to_name: str,
    to_email: str,
    booking_code: str,
    topic_label: str,
    slot_ist: str,
) -> dict:
    """
    Send an appointment confirmation email directly to the user via SMTP.
    Called after the user submits their contact details on the secure URL form.
    """
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = to_email
    msg["Subject"] = f"Appointment Confirmed — {booking_code} | {topic_label}"

    plain = (
        f"Dear {to_name},\n\n"
        f"Your advisor appointment is tentatively confirmed.\n\n"
        f"Booking Code : {booking_code}\n"
        f"Topic        : {topic_label}\n"
        f"Date & Time  : {slot_ist} (IST)\n\n"
        f"An advisor will reach out to confirm. This is an informational consultation only.\n\n"
        f"To reschedule or cancel, call us and quote your booking code.\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_user_confirmation_html(to_name, booking_code, topic_label, slot_ist), "html"))

    with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.gmail_address, config.gmail_app_password)
        smtp.sendmail(config.gmail_address, to_email, msg.as_bytes())

    return {"to": to_email, "booking_code": booking_code}


async def draft_approval_email(payload: MCPPayload, event_id: str | None = None) -> ToolResult:
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _create_draft_sync, payload, event_id
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)
