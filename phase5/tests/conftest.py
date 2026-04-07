"""
Phase 5 test configuration.

Sets up sys.path so all phase modules are importable, loads .env,
and provides shared fixtures for E2E conversation testing.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_tests_dir  = Path(__file__).resolve().parent
_phase5_dir = _tests_dir.parent
_root_dir   = _phase5_dir.parent   # voice-agents/

for _entry in [
    str(_root_dir / "phase0"),
    str(_root_dir / "phase1"),
    str(_root_dir / "phase2"),
    str(_root_dir / "phase3"),
    str(_root_dir / "phase4"),
]:
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(str(_root_dir / ".env"))
except ImportError:
    pass

# Point mock calendar at phase1 fixture (force-set — not setdefault — to override any stale value)
os.environ["MOCK_CALENDAR_PATH"] = str(_root_dir / "phase1" / "data" / "mock_calendar.json")

# ---------------------------------------------------------------------------
# MCP stub fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mcp_results():
    """Fake MCPResults — all tools succeed, no real API calls."""
    from src.mcp.models import MCPResults, ToolResult
    return MCPResults(
        calendar=ToolResult(
            success=True,
            data={"event_id": "evt_test_001", "html_link": "https://cal.test/evt001"},
            duration_ms=120.0,
        ),
        sheets=ToolResult(
            success=True,
            data={"row_index": 5, "spreadsheet_id": "sheet_test_001"},
            duration_ms=80.0,
        ),
        email=ToolResult(
            success=True,
            data={"draft_id": "draft_test_001", "thread_id": "thread_test_001"},
            duration_ms=95.0,
        ),
        total_duration_ms=300.0,
    )


@pytest.fixture
def mock_mcp_partial_failure():
    """Fake MCPResults — calendar OK, sheets/email fail."""
    from src.mcp.models import MCPResults, ToolResult
    return MCPResults(
        calendar=ToolResult(
            success=True,
            data={"event_id": "evt_test_002"},
            duration_ms=130.0,
        ),
        sheets=ToolResult(
            success=False,
            error="Sheets API quota exceeded",
            duration_ms=50.0,
        ),
        email=ToolResult(
            success=False,
            error="SMTP connection timeout",
            duration_ms=45.0,
        ),
        total_duration_ms=250.0,
    )


@pytest.fixture
def mock_mcp_full_failure():
    """Fake MCPResults — all tools fail."""
    from src.mcp.models import MCPResults, ToolResult
    return MCPResults(
        calendar=ToolResult(
            success=False,
            error="Calendar API 503",
            duration_ms=30.0,
        ),
        sheets=ToolResult(
            success=False,
            error="Sheets API 503",
            duration_ms=30.0,
        ),
        email=ToolResult(
            success=False,
            error="Email API 503",
            duration_ms=30.0,
        ),
        total_duration_ms=95.0,
    )


# ---------------------------------------------------------------------------
# FSM fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_fsm():
    """A new DialogueFSM instance with no state."""
    from src.dialogue.fsm import DialogueFSM
    return DialogueFSM()


@pytest.fixture
def fresh_session_manager():
    """A fresh SessionManager (in-memory)."""
    from src.dialogue.session_manager import SessionManager
    return SessionManager()


# ---------------------------------------------------------------------------
# Intent router stubs
# ---------------------------------------------------------------------------

def _make_llm_response(intent="book_new", topic="kyc_onboarding",
                        day="Monday", time_pref="morning",
                        compliance_flag=None, speech="OK, let me check."):
    from src.dialogue.states import LLMResponse
    return LLMResponse(
        intent=intent,
        slots={"topic": topic, "day_preference": day, "time_preference": time_pref},
        speech=speech,
        compliance_flag=compliance_flag,
    )


@pytest.fixture
def mock_intent_router_book():
    """IntentRouter that always returns book_new / kyc_onboarding."""
    with patch("src.dialogue.intent_router.IntentRouter.route") as m:
        m.return_value = _make_llm_response()
        yield m


@pytest.fixture
def mock_intent_router_refuse_advice():
    """IntentRouter that flags refuse_advice compliance block."""
    with patch("src.dialogue.intent_router.IntentRouter.route") as m:
        m.return_value = _make_llm_response(
            intent="refuse_advice",
            compliance_flag="refuse_advice",
            speech="I cannot provide investment advice.",
        )
        yield m


@pytest.fixture
def mock_intent_router_out_of_scope():
    """IntentRouter that flags out_of_scope."""
    with patch("src.dialogue.intent_router.IntentRouter.route") as m:
        m.return_value = _make_llm_response(
            intent="out_of_scope",
            compliance_flag="out_of_scope",
            speech="I can only help with scheduling today.",
        )
        yield m


@pytest.fixture
def mock_intent_router_end_call():
    """IntentRouter that signals end_call intent."""
    with patch("src.dialogue.intent_router.IntentRouter.route") as m:
        m.return_value = _make_llm_response(
            intent="end_call",
            compliance_flag=None,
            speech="Thank you for calling. Goodbye!",
        )
        yield m


# ---------------------------------------------------------------------------
# Slot resolver stub
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_slot_resolver():
    """Patches SlotResolver to return a deterministic slot."""
    with patch("src.dialogue.fsm.SlotResolver") as MockCls:
        instance = MockCls.return_value
        instance.resolve.return_value = [
            {
                "slot_id": "slot_001",
                "start": "2026-04-13T09:00:00+05:30",
                "start_ist": "Monday, 13/04/2026 at 09:00 AM IST",
            }
        ]
        yield instance
