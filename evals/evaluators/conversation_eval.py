"""
Conversation Flow Evaluator

Runs multi-turn dialogue scenarios through the FSM with mocked MCP calls.
Verifies that the FSM reaches the expected final state and the booking
code/topic/cancellation outcome is correct.
"""

from __future__ import annotations

import json
import sys
import unittest.mock as mock
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT / "phase4", _ROOT / "phase2"):
    sys.path.insert(0, str(_p))

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "conversation_flows.json"


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def _make_booking_modules() -> dict:
    """
    Build mock sys.modules entries for src.booking.* so the FSM can be tested
    without phase1 on sys.path (phase2 already owns the 'src' namespace).
    """
    import types
    from datetime import datetime, timezone, timedelta

    IST = timezone(timedelta(hours=5, minutes=30))
    _t1 = datetime(2026, 4, 21, 10, 0, tzinfo=IST)
    _t2 = datetime(2026, 4, 22, 14, 0, tzinfo=IST)

    class _MockSlot:
        _counter = 0
        def __init__(self, start_dt):
            _MockSlot._counter += 1
            self.slot_id   = f"SLOT-MOCK-{_MockSlot._counter}"
            self.start     = start_dt
            self.end       = start_dt + timedelta(minutes=30)
            self.status    = "free"
            self.topic_affinity = []
        def start_ist_str(self):
            return self.start.strftime("%A, %d/%m/%Y at %I:%M %p IST")

    _slots = [_MockSlot(_t1), _MockSlot(_t2)]

    # ── src.booking.slot_resolver ──────────────────────────────────────────────
    slot_mod = types.ModuleType("src.booking.slot_resolver")
    slot_mod.resolve_slots       = mock.MagicMock(return_value=_slots)
    slot_mod.parse_datetime_summary = mock.MagicMock(return_value=("Monday morning", False))
    slot_mod._parse_day_preference  = mock.MagicMock(return_value=([_t1], True))
    slot_mod._parse_time_preference = mock.MagicMock(return_value=None)
    slot_mod.CalendarSlot = _MockSlot

    # ── src.booking.booking_code_generator ────────────────────────────────────
    code_mod = types.ModuleType("src.booking.booking_code_generator")
    _cnt = [0]
    def _gen_code():
        _cnt[0] += 1
        return f"NL-EVAL{_cnt[0]:02d}"
    code_mod.generate_booking_code = _gen_code

    # ── src.booking.secure_url_generator ──────────────────────────────────────
    url_mod = types.ModuleType("src.booking.secure_url_generator")
    url_mod.generate_secure_url = mock.MagicMock(return_value="https://mock.url/booking/EVAL01")

    # ── src.booking.waitlist_handler ──────────────────────────────────────────
    wl_mod = types.ModuleType("src.booking.waitlist_handler")
    _wl_entry = mock.MagicMock()
    _wl_entry.waitlist_code = "WL-EVAL01"
    wl_mod.create_waitlist_entry = mock.MagicMock(return_value=_wl_entry)

    # ── src.booking.waitlist_queue ────────────────────────────────────────────
    wq_mod = types.ModuleType("src.booking.waitlist_queue")
    _queue = mock.MagicMock()
    _queue.size.return_value = 0
    wq_mod.get_global_queue = mock.MagicMock(return_value=_queue)

    # ── src.booking (package) ─────────────────────────────────────────────────
    pkg_mod = types.ModuleType("src.booking")

    return {
        "src.booking":                          pkg_mod,
        "src.booking.slot_resolver":            slot_mod,
        "src.booking.booking_code_generator":   code_mod,
        "src.booking.secure_url_generator":     url_mod,
        "src.booking.waitlist_handler":         wl_mod,
        "src.booking.waitlist_queue":           wq_mod,
    }


def _make_mock_mcp_results(success: bool = True):
    """Build a fake MCPResults object so FSM doesn't call real Google APIs."""
    try:
        from src.mcp.models import ToolResult, MCPResults
        tr = ToolResult(success=success, data={"event_id": "mock_evt_001", "row_index": 5})
        return MCPResults(
            calendar=tr,
            sheets=tr,
            email=tr,
            total_duration_ms=50.0,
        )
    except ImportError:
        # Phase 4 not available — return minimal mock
        result = mock.MagicMock()
        result.all_succeeded = success
        result.calendar.success = success
        result.sheets.success = success
        result.email.success = success
        result.calendar.data = {"event_id": "mock_evt_001"}
        result.sheets.data = {"row_index": 5}
        return result


def _run_flow(flow: dict) -> dict[str, Any]:
    """
    Simulate a multi-turn dialogue for one flow.
    Uses IntentRouter + FSM.process_turn() per turn.
    """
    from src.dialogue.fsm import DialogueFSM
    from src.dialogue.intent_router import IntentRouter
    from src.dialogue.states import LLMResponse

    fsm = DialogueFSM()
    router = IntentRouter()
    ctx, _greeting = fsm.start()

    mock_results = _make_mock_mcp_results(success=True)
    mock_cancel_results = _make_mock_mcp_results(success=True)

    sheets_patch = mock.patch(
        "src.mcp.sheets_tool._get_booking_details_sync",
        return_value={"topic_key": "kyc_onboarding", "slot_start_ist": "Mon 09:00 AM"}
    )

    turn_results = []
    final_state = ctx.current_state.name

    with mock.patch.dict(sys.modules, _make_booking_modules()), \
         mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_results), \
         mock.patch("src.mcp.mcp_orchestrator.reschedule_booking_mcp_sync", return_value=mock_results), \
         mock.patch("src.mcp.mcp_orchestrator.cancel_booking_mcp_sync", return_value=mock_cancel_results), \
         sheets_patch:

        for turn in flow["turns"]:
            user_input = turn["user"]
            expected_state = turn.get("expected_state")

            # Empty input → no-input LLMResponse (FSM handles the empty string branch)
            if not user_input:
                llm_resp = LLMResponse(intent="out_of_scope")
            else:
                llm_resp = router.route(user_input, ctx)

            ctx, response_text = fsm.process_turn(ctx, user_input, llm_resp)

            actual_state = ctx.current_state.name
            state_match = (expected_state is None) or (actual_state == expected_state)

            turn_results.append({
                "user": user_input,
                "expected_state": expected_state,
                "actual_state": actual_state,
                "state_match": state_match,
                "response_preview": (response_text or "")[:120],
            })

            final_state = actual_state

    # Check final state
    expected_final = flow.get("expected_final_state")
    final_state_match = (expected_final is None) or (final_state == expected_final)

    # Check booking code was generated (not None/empty)
    booking_code_ok = True
    if flow.get("expected_booking_code_generated"):
        booking_code_ok = bool(ctx.booking_code)

    # Check old code preserved for reschedule
    keeps_old_code_ok = True
    if flow.get("expected_keeps_old_code"):
        keeps_old_code_ok = bool(ctx.booking_code)  # booking_code should be set to old one

    # Check topic
    topic_ok = True
    if "expected_topic" in flow:
        topic_ok = ctx.topic == flow["expected_topic"]

    all_passed = (
        final_state_match
        and booking_code_ok
        and keeps_old_code_ok
        and topic_ok
        and all(t["state_match"] for t in turn_results)
    )

    return {
        "id": flow["id"],
        "description": flow["description"],
        "turns": turn_results,
        "expected_final_state": expected_final,
        "actual_final_state": final_state,
        "final_state_match": final_state_match,
        "booking_code": ctx.booking_code,
        "topic": ctx.topic,
        "booking_code_ok": booking_code_ok,
        "topic_ok": topic_ok,
        "passed": all_passed,
    }


def run_conversation_eval(**_kwargs) -> dict[str, Any]:
    """Run all conversation flow evals."""
    dataset = load_dataset()
    results = []
    passed = 0

    for flow in dataset:
        try:
            result = _run_flow(flow)
        except Exception as exc:
            result = {
                "id": flow["id"],
                "description": flow["description"],
                "passed": False,
                "error": str(exc),
                "turns": [],
            }

        results.append(result)
        if result.get("passed"):
            passed += 1

    failures = [r for r in results if not r.get("passed")]

    return {
        "eval": "conversation_flows",
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "failures": failures,
        "results": results,
    }
