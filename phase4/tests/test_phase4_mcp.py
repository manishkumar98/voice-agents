"""
tests/test_phase4_mcp.py

Phase 4 — MCP Integration: Google Calendar, Sheets, Gmail

TC-4.1  config — calendar_id decoded from base64
TC-4.2  config — service account file loads
TC-4.3  config — gmail_app_password strips spaces
TC-4.4  models — MCPPayload fields accessible
TC-4.5  models — ToolResult defaults
TC-4.6  models — MCPResults convenience properties
TC-4.7  models — MCPResults.all_succeeded / partial_success
TC-4.8  models — MCPResults.summary() string
TC-4.9  build_payload — builds correct MCPPayload from DialogueContext
TC-4.10 build_payload — handles missing resolved_slot gracefully
TC-4.11 calendar_tool — create_calendar_hold returns ToolResult on API error
TC-4.12 calendar_tool — create_calendar_hold succeeds with mocked service
TC-4.13 sheets_tool — append_booking_notes returns ToolResult on error
TC-4.14 sheets_tool — append_booking_notes succeeds with mocked gspread
TC-4.15 email_tool — draft_approval_email returns ToolResult on IMAP error
TC-4.16 email_tool — _html_body contains booking code and topic
TC-4.17 mcp_orchestrator — dispatch_mcp: calendar failure still runs sheets+email
TC-4.18 mcp_orchestrator — dispatch_mcp: all succeed → MCPResults.all_succeeded
TC-4.19 mcp_orchestrator — dispatch_mcp: exception in gather wrapped as ToolResult
TC-4.20 mcp_orchestrator — dispatch_mcp_sync callable from sync context
TC-4.21 mcp_logger — log() writes valid JSONL to temp file
TC-4.22 mcp_logger — log() creates parent dirs if missing
TC-4.23 fsm._dispatch_mcp — booking code generated and BOOKING_COMPLETE reached
TC-4.24 fsm._dispatch_mcp — MCP import failure does not block booking
TC-4.25 INTEGRATION: full dispatch_mcp hits real Google Calendar API (marked integration)
TC-4.26 INTEGRATION: full dispatch_mcp appends row to real Google Sheet (marked integration)
TC-4.27 INTEGRATION: full dispatch_mcp creates real Gmail draft (marked integration)
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_payload(**overrides):
    from src.mcp.models import MCPPayload
    defaults = dict(
        booking_code   = "NL-TEST",
        call_id        = "CALL-TEST",
        topic_key      = "kyc_onboarding",
        topic_label    = "KYC and Onboarding",
        slot_start_iso = "2026-04-13T09:00:00+05:30",
        slot_start_ist = "Monday, 13/04/2026 at 09:00 AM IST",
        slot_end_iso   = "2026-04-13T09:30:00+05:30",
        advisor_id     = "ADV-001",
        created_at_ist = "2026-04-05 14:00:00 IST",
    )
    defaults.update(overrides)
    return MCPPayload(**defaults)


def _make_ctx(booking_code="NL-TEST"):
    from src.dialogue.states import DialogueContext, DialogueState
    ctx = DialogueContext(
        call_id="CALL-TEST",
        session_start_ist=datetime.now(IST),
        current_state=DialogueState.SLOT_CONFIRMED,
    )
    ctx.booking_code  = booking_code
    ctx.topic         = "kyc_onboarding"
    ctx.day_preference  = "Monday"
    ctx.time_preference = "morning"
    ctx.resolved_slot = {
        "slot_id":   "S1",
        "start":     "2026-04-13T09:00:00+05:30",
        "start_ist": "Monday, 13/04/2026 at 09:00 AM IST",
    }
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.1 to TC-4.3 — Config
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPConfig:
    def test_calendar_id_decoded_from_base64(self):  # TC-4.1
        from src.mcp.config import _decode_if_base64
        raw = "Y2FkMDYzNjM2MzUyMzAwYTgzODQxOWVmYTI2YTQ2MjUzOTE3NzU3YmZlNzNiZDc3ZDBiMjY5ZWY5NDRlOGVhMEBncm91cC5jYWxlbmRhci5nb29nbGUuY29t"
        decoded = _decode_if_base64(raw)
        assert "@group.calendar.google.com" in decoded
        assert "cad" in decoded

    def test_raw_calendar_id_returned_unchanged(self):  # TC-4.1 variant
        from src.mcp.config import _decode_if_base64
        raw = "primary"
        assert _decode_if_base64(raw) == "primary"

    def test_service_account_loads(self):  # TC-4.2
        from src.mcp.config import get_service_account_info
        info = get_service_account_info()
        assert info["type"] == "service_account"
        assert "client_email" in info

    def test_gmail_app_password_strips_spaces(self):  # TC-4.3
        from src.mcp.config import MCPConfig
        cfg = MCPConfig()
        # The actual value has spaces: "thqi zgxl edlt kxrv"
        pwd = cfg.gmail_app_password
        assert " " not in pwd
        assert len(pwd) > 0


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.4 to TC-4.8 — Models
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPModels:
    def test_payload_fields(self):  # TC-4.4
        p = _make_payload()
        assert p.booking_code == "NL-TEST"
        assert p.topic_label  == "KYC and Onboarding"
        assert "09:00" in p.slot_start_ist

    def test_tool_result_defaults(self):  # TC-4.5
        from src.mcp.models import ToolResult
        r = ToolResult(success=True)
        assert r.data  == {}
        assert r.error is None
        assert r.duration_ms == 0.0

    def test_mcp_results_convenience_properties(self):  # TC-4.6
        from src.mcp.models import MCPResults, ToolResult
        results = MCPResults(
            calendar=ToolResult(success=True,  data={"event_id": "EVT-123"}),
            sheets  =ToolResult(success=True,  data={"row_index": 5}),
            email   =ToolResult(success=True,  data={"draft_id": "DFT-456"}),
        )
        assert results.calendar_event_id == "EVT-123"
        assert results.sheet_row_index   == 5
        assert results.email_draft_id    == "DFT-456"

    def test_all_succeeded(self):  # TC-4.7
        from src.mcp.models import MCPResults, ToolResult
        all_ok = MCPResults(
            calendar=ToolResult(success=True),
            sheets  =ToolResult(success=True),
            email   =ToolResult(success=True),
        )
        assert all_ok.all_succeeded
        assert all_ok.partial_success

        partial = MCPResults(
            calendar=ToolResult(success=True),
            sheets  =ToolResult(success=False, error="timeout"),
            email   =ToolResult(success=False, error="auth"),
        )
        assert not partial.all_succeeded
        assert partial.partial_success

    def test_summary_string(self):  # TC-4.8
        from src.mcp.models import MCPResults, ToolResult
        r = MCPResults(
            calendar=ToolResult(success=True),
            sheets  =ToolResult(success=False, error="err"),
            email   =ToolResult(success=True),
        )
        s = r.summary()
        assert "calendar" in s
        assert "sheets"   in s
        assert "email"    in s


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.9 to TC-4.10 — build_payload
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildPayload:
    def test_builds_from_context(self):  # TC-4.9
        from src.mcp.mcp_orchestrator import build_payload
        ctx     = _make_ctx()
        payload = build_payload(ctx)
        assert payload.booking_code   == "NL-TEST"
        assert payload.topic_key      == "kyc_onboarding"
        assert payload.topic_label    == "KYC and Onboarding"
        assert "09:00" in payload.slot_start_iso
        assert "09:30" in payload.slot_end_iso     # start + 30 min
        assert payload.advisor_id     == os.environ.get("ADVISOR_ID", "ADV-001")

    def test_handles_missing_resolved_slot(self):  # TC-4.10
        from src.mcp.mcp_orchestrator import build_payload
        ctx = _make_ctx()
        ctx.resolved_slot = None
        payload = build_payload(ctx)
        assert payload.slot_start_iso == ""
        assert payload.slot_end_iso   == ""
        assert payload.slot_start_ist == "TBD"


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.11 to TC-4.12 — calendar_tool
# ══════════════════════════════════════════════════════════════════════════════

class TestCalendarTool:
    @patch("src.mcp.calendar_tool._build_service")
    def test_http_error_returns_tool_result(self, mock_build):  # TC-4.11
        from googleapiclient.errors import HttpError
        from src.mcp.calendar_tool import create_calendar_hold
        svc = MagicMock()
        svc.events.return_value.insert.return_value.execute.side_effect = (
            HttpError(resp=MagicMock(status=403), content=b"Forbidden")
        )
        mock_build.return_value = svc
        result = asyncio.run(create_calendar_hold(_make_payload()))
        assert not result.success
        assert result.error is not None

    @patch("src.mcp.calendar_tool._build_service")
    def test_success_returns_event_id(self, mock_build):  # TC-4.12
        from src.mcp.calendar_tool import create_calendar_hold
        svc = MagicMock()
        svc.events.return_value.insert.return_value.execute.return_value = {
            "id": "EVT-XYZ",
            "htmlLink": "https://cal.google.com/event/EVT-XYZ",
            "status": "tentative",
        }
        mock_build.return_value = svc
        result = asyncio.run(create_calendar_hold(_make_payload()))
        assert result.success
        assert result.data["event_id"] == "EVT-XYZ"


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.13 to TC-4.14 — sheets_tool
# ══════════════════════════════════════════════════════════════════════════════

class TestSheetsTool:
    @patch("src.mcp.sheets_tool._build_client")
    def test_exception_returns_tool_result(self, mock_build):  # TC-4.13
        from src.mcp.sheets_tool import append_booking_notes
        mock_build.side_effect = Exception("auth failed")
        result = asyncio.run(append_booking_notes(_make_payload()))
        assert not result.success
        assert "auth failed" in result.error

    @patch("src.mcp.sheets_tool._build_client")
    def test_success_returns_row_index(self, mock_build):  # TC-4.14
        from src.mcp.sheets_tool import append_booking_notes
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["booking_code"]
        mock_ws.append_row.return_value = {
            "updates": {"updatedRange": "'Advisor Pre-Bookings'!A5:K5"}
        }
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        mock_build.return_value.open_by_key.return_value = mock_spreadsheet

        result = asyncio.run(append_booking_notes(_make_payload(), event_id="EVT-123"))
        assert result.success
        assert result.data["row_index"] == 5


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.15 to TC-4.16 — email_tool
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailTool:
    @patch("src.mcp.email_tool.imaplib.IMAP4_SSL")
    def test_imap_error_returns_tool_result(self, mock_imap):  # TC-4.15
        from src.mcp.email_tool import draft_approval_email
        mock_imap.side_effect = Exception("Connection refused")
        result = asyncio.run(draft_approval_email(_make_payload()))
        assert not result.success
        assert result.error is not None

    def test_html_body_contains_booking_info(self):  # TC-4.16
        from src.mcp.email_tool import _html_body
        html = _html_body(_make_payload(), event_id="EVT-999")
        assert "NL-TEST" in html
        assert "KYC and Onboarding" in html
        assert "EVT-999" in html
        assert "TENTATIVE" in html

    @patch("src.mcp.email_tool.imaplib.IMAP4_SSL")
    def test_success_returns_draft_id(self, mock_imap_cls):  # TC-4.16 variant
        from src.mcp.email_tool import draft_approval_email
        mock_imap = MagicMock()
        mock_imap.__enter__ = lambda s: mock_imap
        mock_imap.__exit__  = MagicMock(return_value=False)
        mock_imap.login     = MagicMock()
        mock_imap.append    = MagicMock(return_value=("OK", [b"[APPENDUID 12345 67890]"]))
        mock_imap_cls.return_value = mock_imap

        result = asyncio.run(draft_approval_email(_make_payload(), event_id="EVT-123"))
        assert result.success
        assert "draft_id" in result.data


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.17 to TC-4.20 — mcp_orchestrator
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPOrchestrator:
    @patch("src.mcp.mcp_orchestrator.create_calendar_hold")
    @patch("src.mcp.mcp_orchestrator.append_booking_notes")
    @patch("src.mcp.mcp_orchestrator.draft_approval_email")
    @patch("src.mcp.mcp_orchestrator._logger")
    def test_calendar_failure_still_runs_sheets_email(
        self, mock_logger, mock_email, mock_sheets, mock_cal
    ):  # TC-4.17
        from src.mcp.models import ToolResult
        from src.mcp.mcp_orchestrator import dispatch_mcp

        mock_cal.return_value    = ToolResult(success=False, error="quota exceeded")
        mock_sheets.return_value = ToolResult(success=True, data={"row_index": 3})
        mock_email.return_value  = ToolResult(success=True, data={"draft_id": "D1"})

        # Make them awaitable
        mock_cal    = AsyncMock(return_value=ToolResult(success=False, error="quota exceeded"))
        mock_sheets = AsyncMock(return_value=ToolResult(success=True, data={"row_index": 3}))
        mock_email  = AsyncMock(return_value=ToolResult(success=True, data={"draft_id": "D1"}))

        with patch("src.mcp.mcp_orchestrator.create_calendar_hold", mock_cal), \
             patch("src.mcp.mcp_orchestrator.append_booking_notes", mock_sheets), \
             patch("src.mcp.mcp_orchestrator.draft_approval_email", mock_email), \
             patch("src.mcp.mcp_orchestrator._logger"):
            results = asyncio.run(dispatch_mcp(_make_payload()))

        assert not results.calendar_success
        assert results.sheets_success
        assert results.email_success

    @patch("src.mcp.mcp_orchestrator._logger")
    def test_all_succeed(self, _mock_logger):  # TC-4.18
        from src.mcp.models import ToolResult
        from src.mcp.mcp_orchestrator import dispatch_mcp

        cal_ok    = AsyncMock(return_value=ToolResult(success=True, data={"event_id": "E1"}))
        sheets_ok = AsyncMock(return_value=ToolResult(success=True, data={"row_index": 2}))
        email_ok  = AsyncMock(return_value=ToolResult(success=True, data={"draft_id": "D2"}))

        with patch("src.mcp.mcp_orchestrator.create_calendar_hold", cal_ok), \
             patch("src.mcp.mcp_orchestrator.append_booking_notes", sheets_ok), \
             patch("src.mcp.mcp_orchestrator.draft_approval_email", email_ok):
            results = asyncio.run(dispatch_mcp(_make_payload()))

        assert results.all_succeeded
        assert results.calendar_event_id == "E1"

    @patch("src.mcp.mcp_orchestrator._logger")
    def test_exception_in_gather_wrapped_as_tool_result(self, _mock_logger):  # TC-4.19
        from src.mcp.models import ToolResult
        from src.mcp.mcp_orchestrator import dispatch_mcp

        cal_ok       = AsyncMock(return_value=ToolResult(success=True, data={"event_id": "E1"}))
        sheets_raise = AsyncMock(side_effect=RuntimeError("sheets exploded"))
        email_ok     = AsyncMock(return_value=ToolResult(success=True, data={"draft_id": "D3"}))

        with patch("src.mcp.mcp_orchestrator.create_calendar_hold", cal_ok), \
             patch("src.mcp.mcp_orchestrator.append_booking_notes", sheets_raise), \
             patch("src.mcp.mcp_orchestrator.draft_approval_email", email_ok):
            results = asyncio.run(dispatch_mcp(_make_payload()))

        assert not results.sheets_success
        assert results.email_success

    @patch("src.mcp.mcp_orchestrator._logger")
    def test_dispatch_mcp_sync_callable_from_sync(self, _mock_logger):  # TC-4.20
        from src.mcp.models import ToolResult
        from src.mcp.mcp_orchestrator import dispatch_mcp_sync

        cal_ok    = AsyncMock(return_value=ToolResult(success=True, data={"event_id": "E1"}))
        sheets_ok = AsyncMock(return_value=ToolResult(success=True, data={"row_index": 2}))
        email_ok  = AsyncMock(return_value=ToolResult(success=True, data={"draft_id": "D2"}))

        with patch("src.mcp.mcp_orchestrator.create_calendar_hold", cal_ok), \
             patch("src.mcp.mcp_orchestrator.append_booking_notes", sheets_ok), \
             patch("src.mcp.mcp_orchestrator.draft_approval_email", email_ok):
            results = dispatch_mcp_sync(_make_payload())

        assert results.all_succeeded


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.21 to TC-4.22 — mcp_logger
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPLogger:
    def test_log_writes_valid_jsonl(self, tmp_path):  # TC-4.21
        from src.mcp.models import MCPResults, ToolResult
        from src.mcp.mcp_logger import MCPLogger

        log_file = tmp_path / "mcp_ops_log.jsonl"
        with patch.dict(os.environ, {"MCP_OPS_LOG_PATH": str(log_file)}):
            logger = MCPLogger()
            results = MCPResults(
                calendar=ToolResult(success=True, data={"event_id": "EVT-1"}, duration_ms=120.5),
                sheets  =ToolResult(success=True, data={"row_index": 3},     duration_ms=80.2),
                email   =ToolResult(success=True, data={"draft_id": "DFT-1"}, duration_ms=200.0),
                total_duration_ms=400.7,
            )
            logger.log(_make_payload(), results)

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["booking_code"] == "NL-TEST"
        assert entry["calendar"]["ok"]   is True
        assert entry["calendar"]["event_id"] == "EVT-1"
        assert entry["sheets"]["row_index"]  == 3

    def test_log_creates_parent_dirs(self, tmp_path):  # TC-4.22
        from src.mcp.models import MCPResults, ToolResult
        from src.mcp.mcp_logger import MCPLogger

        nested = tmp_path / "deep" / "nested" / "mcp.jsonl"
        with patch.dict(os.environ, {"MCP_OPS_LOG_PATH": str(nested)}):
            logger = MCPLogger()
            results = MCPResults(
                calendar=ToolResult(success=False, error="x"),
                sheets  =ToolResult(success=False, error="x"),
                email   =ToolResult(success=False, error="x"),
            )
            logger.log(_make_payload(), results)

        assert nested.exists()


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.23 to TC-4.24 — FSM _dispatch_mcp integration
# ══════════════════════════════════════════════════════════════════════════════

class TestFSMDispatchMCP:
    def test_booking_complete_reached(self):  # TC-4.23
        from src.dialogue.fsm import DialogueFSM
        from src.dialogue.states import DialogueState

        fsm = DialogueFSM()
        ctx = _make_ctx()
        ctx.current_state = DialogueState.SLOT_CONFIRMED

        # Simulate MCP unavailable by making dispatch_mcp_sync raise an ImportError;
        # the FSM's except-clause falls back to mock flags and still issues booking code.
        with patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", side_effect=ImportError("mcp unavailable")), \
             patch("src.mcp.mcp_orchestrator.build_payload", return_value=_make_payload()):
            new_ctx, speech = fsm._dispatch_mcp(ctx)

        assert new_ctx.current_state == DialogueState.BOOKING_COMPLETE
        assert new_ctx.booking_code.startswith("NL-")

    @patch("src.mcp.mcp_orchestrator._logger")
    def test_mcp_failure_does_not_block_booking(self, _mock_logger):  # TC-4.24
        from src.dialogue.fsm import DialogueFSM
        from src.dialogue.states import DialogueState
        from src.mcp.models import MCPResults, ToolResult

        failed_results = MCPResults(
            calendar=ToolResult(success=False, error="403 Forbidden"),
            sheets  =ToolResult(success=False, error="quota"),
            email   =ToolResult(success=False, error="auth"),
        )

        with patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=failed_results), \
             patch("src.mcp.mcp_orchestrator.build_payload", return_value=_make_payload()):
            fsm = DialogueFSM()
            ctx = _make_ctx()
            ctx.current_state = DialogueState.SLOT_CONFIRMED
            new_ctx, speech = fsm._dispatch_mcp(ctx)

        assert new_ctx.current_state == DialogueState.BOOKING_COMPLETE
        assert new_ctx.booking_code.startswith("NL-")
        # MCP failures recorded in context flags
        assert not new_ctx.calendar_hold_created
        assert not new_ctx.notes_appended
        assert not new_ctx.email_drafted


# ══════════════════════════════════════════════════════════════════════════════
# TC-4.25 to TC-4.27 — INTEGRATION tests (real APIs, skipped by default)
# ══════════════════════════════════════════════════════════════════════════════

_RUN_INTEGRATION = os.environ.get("RUN_INTEGRATION", "false").lower() == "true"


@pytest.mark.integration
@pytest.mark.skipif(not _RUN_INTEGRATION, reason="RUN_INTEGRATION not set")
class TestMCPIntegration:
    """
    These tests hit real Google APIs.
    Run with: RUN_INTEGRATION=true pytest tests/ -m integration -v
    They create/clean up real calendar events and sheet rows.
    """

    def test_create_real_calendar_hold(self):  # TC-4.25
        from src.mcp.calendar_tool import create_calendar_hold
        result = asyncio.run(create_calendar_hold(_make_payload(booking_code="NL-INT-TEST")))
        assert result.success, f"Calendar error: {result.error}"
        assert result.data.get("event_id"), "No event_id in result"
        print(f"\n✅ Calendar event created: {result.data['event_id']}")

    def test_append_real_sheet_row(self):  # TC-4.26
        from src.mcp.sheets_tool import append_booking_notes
        result = asyncio.run(append_booking_notes(_make_payload(booking_code="NL-INT-TEST")))
        assert result.success, f"Sheets error: {result.error}"
        assert result.data.get("row_index"), "No row_index in result"
        print(f"\n✅ Sheet row appended at index: {result.data['row_index']}")

    def test_create_real_gmail_draft(self):  # TC-4.27
        from src.mcp.email_tool import draft_approval_email
        result = asyncio.run(draft_approval_email(_make_payload(booking_code="NL-INT-TEST"), event_id="INT-TEST"))
        assert result.success, f"Email error: {result.error}"
        assert result.data.get("draft_id"), "No draft_id in result"
        print(f"\n✅ Gmail draft created: {result.data['draft_id']}")
