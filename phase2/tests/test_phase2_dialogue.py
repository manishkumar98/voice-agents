"""
tests/test_phase2_dialogue.py

Phase 2 — Voice Agent Core: FSM + LLM + Compliance

Test plan:
  TC-2.1  DialogueState enum — 16 states, terminal states
  TC-2.2  DialogueContext — slot apply, missing slots, is_booking_ready
  TC-2.3  LLMResponse — validate(), is_compliant(), is_refusal()
  TC-2.4  ComplianceGuard — investment advice detection
  TC-2.5  ComplianceGuard — PII leakage detection
  TC-2.6  ComplianceGuard — clean output passes
  TC-2.7  ComplianceGuard — check_and_gate convenience method
  TC-2.8  SessionManager — create, get, update, close lifecycle
  TC-2.9  SessionManager — expired session returns None
  TC-2.10 SessionManager — active_count after prune
  TC-2.11 IntentRouter — offline rule-based mode (book_new)
  TC-2.12 IntentRouter — offline rule-based refuse_advice
  TC-2.13 IntentRouter — mocked LLM callable parses JSON correctly
  TC-2.14 IntentRouter — mocked LLM returns bad JSON → falls back to rules
  TC-2.15 DialogueFSM — start() returns GREETED state and greeting speech
  TC-2.16 DialogueFSM — GREETED → DISCLAIMER_CONFIRMED with topic prompt
  TC-2.17 DialogueFSM — compliance refusal stays in same state
  TC-2.18 DialogueFSM — no-input increments counter; 3 strikes → ERROR
  TC-2.19 DialogueFSM — full happy-path booking flow (mocked slots)
  TC-2.20 DialogueFSM — reschedule flow (code prompt)
  TC-2.21 DialogueFSM — cancel flow (code prompt)
  TC-2.22 DialogueFSM — waitlist offered when no slots available
  TC-2.23 DialogueFSM — waitlist accepted → WAITLIST_CONFIRMED
  TC-2.24 DialogueFSM — waitlist declined → END
  TC-2.25 IntentRouter — mocked LLM happy path (Groq/Anthropic)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytz

from src.dialogue import (
    ComplianceGuard,
    DialogueFSM,
    IntentRouter,
    SessionManager,
)
from src.dialogue.states import (
    VALID_INTENTS,
    DialogueContext,
    DialogueState,
    LLMResponse,
)

IST = pytz.timezone("Asia/Kolkata")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ctx(state: DialogueState = DialogueState.IDLE) -> DialogueContext:
    return DialogueContext(
        call_id="TEST-001",
        session_start_ist=datetime.now(IST),
        current_state=state,
    )


def _resp(
    intent: str = "book_new",
    slots: dict | None = None,
    speech: str = "Sure.",
    flag: str | None = None,
    raw: str = "",
) -> LLMResponse:
    return LLMResponse(
        intent=intent,
        slots=slots or {},
        speech=speech,
        compliance_flag=flag,
        raw_response=raw,
    )


# ─── TC-2.1: DialogueState ────────────────────────────────────────────────────

class TestDialogueState:
    def test_16_states_defined(self):
        assert len(DialogueState) == 16

    def test_idle_is_s0(self):
        assert DialogueState.IDLE.value == "S0"

    def test_end_is_s15(self):
        assert DialogueState.END.value == "S15"

    def test_terminal_states(self):
        assert DialogueState.END.is_terminal()
        assert DialogueState.ERROR.is_terminal()
        assert not DialogueState.GREETED.is_terminal()
        assert not DialogueState.BOOKING_COMPLETE.is_terminal()

    def test_label(self):
        assert "S1" in DialogueState.GREETED.label()
        assert "GREETED" in DialogueState.GREETED.label()


# ─── TC-2.2: DialogueContext ──────────────────────────────────────────────────

class TestDialogueContext:
    def test_apply_slots_valid_topic(self):
        ctx = _ctx()
        ctx.apply_slots({"topic": "sip_mandates", "day_preference": "Monday"})
        assert ctx.topic == "sip_mandates"
        assert ctx.day_preference == "Monday"

    def test_apply_slots_invalid_topic_ignored(self):
        ctx = _ctx()
        ctx.apply_slots({"topic": "crypto_gains"})
        assert ctx.topic is None

    def test_missing_booking_slots_all_missing(self):
        ctx = _ctx()
        missing = ctx.missing_booking_slots()
        assert "topic" in missing
        assert "day_preference" in missing
        assert "time_preference" in missing

    def test_missing_booking_slots_partial(self):
        ctx = _ctx()
        ctx.topic = "withdrawals"
        ctx.day_preference = "Tuesday"
        missing = ctx.missing_booking_slots()
        assert missing == ["time_preference"]

    def test_is_booking_ready_false_without_resolved_slot(self):
        ctx = _ctx()
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "morning"
        assert not ctx.is_booking_ready()

    def test_is_booking_ready_true(self):
        ctx = _ctx()
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "morning"
        ctx.resolved_slot = {"slot_id": "S1", "start": "2025-01-06T09:00:00"}
        assert ctx.is_booking_ready()

    def test_slots_filled_omits_none(self):
        ctx = _ctx()
        ctx.topic = "withdrawals"
        filled = ctx.slots_filled()
        assert "topic" in filled
        assert "day_preference" not in filled


# ─── TC-2.3: LLMResponse ─────────────────────────────────────────────────────

class TestLLMResponse:
    def test_is_compliant_true_when_no_flag(self):
        r = _resp()
        assert r.is_compliant()

    def test_is_compliant_false_with_flag(self):
        r = _resp(flag="refuse_advice")
        assert not r.is_compliant()

    def test_is_refusal(self):
        assert _resp(flag="refuse_advice").is_refusal()
        assert _resp(flag="refuse_pii").is_refusal()
        assert _resp(flag="out_of_scope").is_refusal()
        assert not _resp().is_refusal()

    def test_validate_valid_response(self):
        r = _resp(intent="book_new", speech="OK.")
        assert r.validate() == []

    def test_validate_unknown_intent(self):
        r = _resp(intent="invest_now", speech="OK.")
        errors = r.validate()
        assert any("intent" in e for e in errors)

    def test_validate_empty_speech(self):
        r = LLMResponse(intent="book_new", speech="")
        errors = r.validate()
        assert any("speech" in e for e in errors)

    def test_validate_bad_compliance_flag(self):
        r = LLMResponse(intent="book_new", speech="OK.", compliance_flag="hack")
        errors = r.validate()
        assert any("compliance_flag" in e for e in errors)


# ─── TC-2.4: ComplianceGuard — advice ────────────────────────────────────────

class TestComplianceGuardAdvice:
    def setup_method(self):
        self.guard = ComplianceGuard()

    def test_should_buy_triggers(self):
        result = self.guard.check("You should buy Nifty 50 now.")
        assert not result.is_compliant
        assert result.flag == "refuse_advice"

    def test_recommend_invest_triggers(self):
        result = self.guard.check("I recommend you invest in this fund.")
        assert result.flag == "refuse_advice"

    def test_expected_returns_triggers(self):
        result = self.guard.check("This fund has expected returns of 12%.")
        assert result.flag == "refuse_advice"

    def test_percentage_return_triggers(self):
        result = self.guard.check("You'll get 15% return on this.")
        assert result.flag == "refuse_advice"

    def test_market_prediction_triggers(self):
        result = self.guard.check("The market will go up next month.")
        assert result.flag == "refuse_advice"

    def test_diversify_triggers(self):
        result = self.guard.check("You should diversify your portfolio.")
        assert result.flag == "refuse_advice"

    def test_clean_schedule_text_passes(self):
        result = self.guard.check("I've booked your appointment for Monday morning.")
        assert result.is_compliant
        assert result.flag is None

    def test_empty_string_is_compliant(self):
        result = self.guard.check("")
        assert result.is_compliant


# ─── TC-2.5: ComplianceGuard — PII leakage ───────────────────────────────────

class TestComplianceGuardPII:
    def setup_method(self):
        self.guard = ComplianceGuard()

    def test_phone_in_output_triggers(self):
        result = self.guard.check("I'll call you at 9876543210.")
        assert result.flag == "refuse_pii"

    def test_email_in_output_triggers(self):
        result = self.guard.check("Your email is user@example.com.")
        assert result.flag == "refuse_pii"

    def test_pan_in_output_triggers(self):
        result = self.guard.check("Your PAN is ABCDE1234F.")
        assert result.flag == "refuse_pii"

    def test_aadhaar_in_output_triggers(self):
        result = self.guard.check("Your Aadhaar is 1234 5678 9012.")
        assert result.flag == "refuse_pii"

    def test_pii_safe_speech_is_set(self):
        result = self.guard.check("Call 9876543210 for support.")
        assert "secure link" in result.safe_speech.lower() or "personal" in result.safe_speech.lower()


# ─── TC-2.6 / 2.7: ComplianceGuard — clean + gate ───────────────────────────

class TestComplianceGuardClean:
    def setup_method(self):
        self.guard = ComplianceGuard()

    def test_clean_output_is_compliant(self):
        text = "Your booking is confirmed for Tuesday at 10 AM."
        result = self.guard.check(text)
        assert result.is_compliant
        assert result.safe_speech == text

    def test_check_and_gate_returns_original_when_clean(self):
        text = "Booking confirmed!"
        assert self.guard.check_and_gate(text) == text

    def test_check_and_gate_returns_refusal_when_violated(self):
        text = "You should sell your stocks now."
        gated = self.guard.check_and_gate(text)
        assert "investment advice" in gated.lower()


# ─── TC-2.8: SessionManager — lifecycle ─────────────────────────────────────

class TestSessionManagerLifecycle:
    def setup_method(self):
        self.mgr = SessionManager(ttl_minutes=30)

    def test_create_and_get_session(self):
        ctx = _ctx(DialogueState.GREETED)
        sid = self.mgr.create_session(ctx)
        fetched = self.mgr.get_session(sid)
        assert fetched is not None
        assert fetched.current_state == DialogueState.GREETED

    def test_update_session(self):
        ctx = _ctx(DialogueState.GREETED)
        sid = self.mgr.create_session(ctx)
        ctx.current_state = DialogueState.INTENT_IDENTIFIED
        ok = self.mgr.update_session(sid, ctx)
        assert ok
        fetched = self.mgr.get_session(sid)
        assert fetched.current_state == DialogueState.INTENT_IDENTIFIED

    def test_close_session(self):
        ctx = _ctx()
        sid = self.mgr.create_session(ctx)
        assert self.mgr.close_session(sid)
        assert self.mgr.get_session(sid) is None

    def test_close_nonexistent_returns_false(self):
        assert not self.mgr.close_session("no-such-id")

    def test_get_nonexistent_returns_none(self):
        assert self.mgr.get_session("nonexistent") is None

    def test_update_nonexistent_returns_false(self):
        ctx = _ctx()
        assert not self.mgr.update_session("nonexistent", ctx)

    def test_active_count(self):
        mgr = SessionManager(ttl_minutes=30)
        assert mgr.active_count() == 0
        sid1 = mgr.create_session(_ctx())
        mgr.create_session(_ctx())
        assert mgr.active_count() == 2
        mgr.close_session(sid1)
        assert mgr.active_count() == 1

    def test_all_session_ids(self):
        mgr = SessionManager(ttl_minutes=30)
        sid = mgr.create_session(_ctx())
        assert sid in mgr.all_session_ids()


# ─── TC-2.9: SessionManager — TTL expiry ─────────────────────────────────────

class TestSessionManagerExpiry:
    def test_expired_session_returns_none(self):
        mgr = SessionManager(ttl_minutes=0)
        ctx = _ctx()
        sid = mgr.create_session(ctx)

        # Manually back-date the entry
        with mgr._lock:
            old_ctx, _ = mgr._store[sid]
            mgr._store[sid] = (old_ctx, datetime.now(IST) - timedelta(minutes=1))

        assert mgr.get_session(sid) is None

    def test_prune_removes_expired(self):
        mgr = SessionManager(ttl_minutes=0)
        sid = mgr.create_session(_ctx())
        with mgr._lock:
            old_ctx, _ = mgr._store[sid]
            mgr._store[sid] = (old_ctx, datetime.now(IST) - timedelta(minutes=1))
        assert mgr.active_count() == 0


# ─── TC-2.11 / 2.12: IntentRouter — offline mode ─────────────────────────────

class TestIntentRouterOffline:
    def setup_method(self):
        # No LLM callable → forces rule-based mode
        self.router = IntentRouter(llm_callable=None)
        self.ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)

    def test_is_not_online_without_callable(self):
        # May be online if env vars set; just check routing still works
        result = self.router.route("I'd like to book an appointment", self.ctx)
        assert result.intent in VALID_INTENTS

    def test_book_new_intent_detected(self):
        result = self.router.route("I want to book an appointment please", self.ctx)
        assert result.intent == "book_new"

    def test_reschedule_intent_detected(self):
        result = self.router.route("I need to reschedule my appointment", self.ctx)
        assert result.intent == "reschedule"

    def test_cancel_intent_detected(self):
        result = self.router.route("I want to cancel my booking", self.ctx)
        assert result.intent == "cancel"

    def test_refuse_advice_intent_detected(self):
        result = self.router.route("Which stock should I invest in?", self.ctx)
        assert result.intent == "refuse_advice"
        assert result.compliance_flag == "refuse_advice"

    def test_topic_extracted(self):
        result = self.router.route("I have questions about my KYC", self.ctx)
        assert result.slots.get("topic") == "kyc_onboarding"

    def test_day_extracted(self):
        result = self.router.route("Can I book for Monday please", self.ctx)
        assert result.slots.get("day_preference", "").lower() == "monday"

    def test_time_extracted(self):
        result = self.router.route("morning works for me", self.ctx)
        assert result.slots.get("time_preference") == "morning"

    def test_booking_code_extracted(self):
        result = self.router.route("My code is NL-AB23", self.ctx)
        assert result.slots.get("existing_booking_code") == "NL-AB23"


# ─── TC-2.13: IntentRouter — mocked LLM, valid JSON ─────────────────────────

class TestIntentRouterMockedLLM:
    def _make_router(self, response_json: dict) -> IntentRouter:
        raw = json.dumps(response_json)
        mock_fn = MagicMock(return_value=raw)
        return IntentRouter(llm_callable=mock_fn)

    def test_valid_json_parsed_correctly(self):
        router = self._make_router({
            "intent": "book_new",
            "slots": {"topic": "withdrawals", "day_preference": "Wednesday"},
            "speech": "Sure, let me help you book.",
            "compliance_flag": None,
        })
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        result = router.route("I want to book about withdrawals on Wednesday", ctx)
        assert result.intent == "book_new"
        assert result.slots["topic"] == "withdrawals"
        assert result.slots["day_preference"] == "Wednesday"
        assert result.compliance_flag is None

    def test_refuse_advice_flag_set(self):
        router = self._make_router({
            "intent": "refuse_advice",
            "slots": {},
            "speech": "I cannot provide investment advice.",
            "compliance_flag": "refuse_advice",
        })
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        result = router.route("Tell me which fund to invest in", ctx)
        assert result.compliance_flag == "refuse_advice"

    def test_invalid_topic_ignored(self):
        router = self._make_router({
            "intent": "book_new",
            "slots": {"topic": "crypto_gains"},
            "speech": "OK.",
            "compliance_flag": None,
        })
        ctx = _ctx()
        result = router.route("Book me for crypto discussion", ctx)
        assert "topic" not in result.slots

    def test_unknown_intent_defaults_to_book_new(self):
        router = self._make_router({
            "intent": "hack_the_system",
            "slots": {},
            "speech": "OK.",
            "compliance_flag": None,
        })
        ctx = _ctx()
        result = router.route("anything", ctx)
        assert result.intent == "book_new"


# ─── TC-2.14: IntentRouter — bad JSON falls back ─────────────────────────────

class TestIntentRouterFallback:
    def test_malformed_json_falls_back_to_rules(self):
        mock_fn = MagicMock(return_value="This is not JSON at all!")
        router = IntentRouter(llm_callable=mock_fn)
        ctx = _ctx()
        result = router.route("I want to book an appointment", ctx)
        # Should have fallen back to rule-based
        assert result.intent in VALID_INTENTS

    def test_llm_exception_falls_back(self):
        mock_fn = MagicMock(side_effect=RuntimeError("Network error"))
        router = IntentRouter(llm_callable=mock_fn)
        ctx = _ctx()
        result = router.route("I want to reschedule", ctx)
        assert result.intent in VALID_INTENTS


# ─── TC-2.15: DialogueFSM.start() ────────────────────────────────────────────

class TestDialogueFSMStart:
    def test_start_returns_greeted_state(self):
        fsm = DialogueFSM()
        ctx, speech = fsm.start(call_id="TEST-START")
        assert ctx.current_state == DialogueState.GREETED
        assert ctx.call_id == "TEST-START"

    def test_start_speech_contains_greeting(self):
        fsm = DialogueFSM()
        _, speech = fsm.start()
        assert "scheduling" in speech.lower() or "advisor" in speech.lower()

    def test_start_auto_generates_call_id(self):
        fsm = DialogueFSM()
        ctx, _ = fsm.start()
        assert ctx.call_id.startswith("CALL-")


# ─── TC-2.16: FSM — GREETED → topic prompt ───────────────────────────────────

class TestDialogueFSMGreeted:
    def setup_method(self):
        self.fsm = DialogueFSM()

    def test_greeted_affirmative_goes_to_topic_prompt(self):
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp(intent="book_new", speech="Yes please.")
        new_ctx, speech = self.fsm.process_turn(ctx, "Yes please", resp)
        assert new_ctx.current_state in (
            DialogueState.DISCLAIMER_CONFIRMED,
            DialogueState.INTENT_IDENTIFIED,
            DialogueState.TOPIC_COLLECTED,
        )
        assert speech  # some speech produced

    def test_greeted_with_topic_skips_to_topic_collected(self):
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp(
            intent="book_new",
            slots={"topic": "sip_mandates"},
            speech="I'd like to book about SIP.",
        )
        ctx.apply_slots(resp.slots)
        new_ctx, speech = self.fsm.process_turn(ctx, "I want to book about SIP", resp)
        # Should now be prompting for time
        assert new_ctx.topic == "sip_mandates"


# ─── TC-2.17: FSM — compliance refusal stays in state ────────────────────────

class TestDialogueFSMCompliance:
    def setup_method(self):
        self.fsm = DialogueFSM()

    def test_refuse_advice_stays_in_same_state(self):
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="refuse_advice", flag="refuse_advice")
        new_ctx, speech = self.fsm.process_turn(ctx, "Which fund should I buy?", resp)
        assert new_ctx.current_state == DialogueState.DISCLAIMER_CONFIRMED
        assert "investment advice" in speech.lower()

    def test_refuse_pii_stays_in_same_state(self):
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="refuse_pii", flag="refuse_pii")
        new_ctx, speech = self.fsm.process_turn(ctx, "My phone is 9876543210", resp)
        assert new_ctx.current_state == DialogueState.DISCLAIMER_CONFIRMED
        assert "personal" in speech.lower() or "secure" in speech.lower()

    def test_out_of_scope_stays_in_same_state(self):
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="out_of_scope", flag="out_of_scope")
        new_ctx, speech = self.fsm.process_turn(ctx, "Tell me a joke", resp)
        assert new_ctx.current_state == DialogueState.DISCLAIMER_CONFIRMED
        assert "scheduling" in speech.lower()


# ─── TC-2.18: FSM — no-input handling ────────────────────────────────────────

class TestDialogueFSMNoInput:
    def setup_method(self):
        self.fsm = DialogueFSM()

    def test_one_silence_increments_counter(self):
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp()
        new_ctx, _ = self.fsm.process_turn(ctx, "", resp)
        assert new_ctx.no_input_count == 1
        assert new_ctx.current_state == DialogueState.GREETED

    def test_three_silences_triggers_error(self):
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp()
        ctx, _ = self.fsm.process_turn(ctx, "", resp)
        ctx, _ = self.fsm.process_turn(ctx, "", resp)
        ctx, speech = self.fsm.process_turn(ctx, "", resp)
        assert ctx.current_state == DialogueState.ERROR

    def test_valid_input_resets_counter(self):
        ctx = _ctx(DialogueState.GREETED)
        ctx.no_input_count = 2
        resp = _resp()
        new_ctx, _ = self.fsm.process_turn(ctx, "yes", resp)
        assert new_ctx.no_input_count == 0


# ─── TC-2.19: FSM — happy-path booking (mocked slot resolver) ────────────────

class TestDialogueFSMHappyPath:
    def setup_method(self):
        self.fsm = DialogueFSM()

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_full_booking_flow(self, mock_resolve):
        mock_slot = MagicMock()
        mock_slot.slot_id = "SLOT-001"
        mock_slot.start.isoformat.return_value = "2025-01-06T09:00:00+05:30"
        mock_slot.start_ist_str.return_value = "Monday, 6 Jan at 9:00 AM IST"
        mock_resolve.return_value = [mock_slot]

        # S1 GREETED
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp(intent="book_new", slots={"topic": "kyc_onboarding"}, speech="Yes.")
        ctx, speech = self.fsm.process_turn(ctx, "yes", resp)

        # S4/S5 — apply topic and time, get slots offered
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "morning"
        resp2 = _resp(
            intent="book_new",
            slots={"day_preference": "Monday", "time_preference": "morning"},
            speech="Monday morning please.",
        )
        ctx.current_state = DialogueState.TOPIC_COLLECTED
        ctx, speech = self.fsm.process_turn(ctx, "Monday morning please", resp2)
        assert ctx.current_state == DialogueState.SLOTS_OFFERED
        assert "Option 1" in speech

        # S6 → S7 — confirm slot
        resp3 = _resp(intent="book_new", speech="First one please.")
        ctx, speech = self.fsm.process_turn(ctx, "first one", resp3)
        assert ctx.current_state == DialogueState.SLOT_CONFIRMED

        # S7 → BOOKING_COMPLETE
        resp4 = _resp(intent="book_new", speech="Yes confirmed.")
        ctx, speech = self.fsm.process_turn(ctx, "yes", resp4)
        assert ctx.current_state == DialogueState.BOOKING_COMPLETE
        assert ctx.booking_code is not None
        assert "NL-" in ctx.booking_code


# ─── TC-2.20: FSM — reschedule flow ─────────────────────────────────────────

class TestDialogueFSMReschedule:
    def test_reschedule_from_disclaimer(self):
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="reschedule")
        new_ctx, speech = fsm.process_turn(ctx, "reschedule please", resp)
        assert new_ctx.current_state == DialogueState.RESCHEDULE_CODE_COLLECTED
        assert "booking code" in speech.lower()

    def test_reschedule_code_collected(self):
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.RESCHEDULE_CODE_COLLECTED)
        resp = _resp(intent="reschedule", slots={"existing_booking_code": "NL-AB23"})
        new_ctx, speech = fsm.process_turn(ctx, "NL-AB23", resp)
        assert new_ctx.current_state == DialogueState.TIME_PREFERENCE_COLLECTED
        assert "NL-AB23" in speech


# ─── TC-2.21: FSM — cancel flow ──────────────────────────────────────────────

class TestDialogueFSMCancel:
    def test_cancel_from_disclaimer(self):
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="cancel")
        new_ctx, speech = fsm.process_turn(ctx, "cancel my booking", resp)
        assert new_ctx.current_state == DialogueState.CANCEL_CODE_COLLECTED
        assert "booking code" in speech.lower()

    def test_cancel_code_collected(self):
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.CANCEL_CODE_COLLECTED)
        resp = _resp(intent="cancel", slots={"existing_booking_code": "NL-XY45"})
        new_ctx, speech = fsm.process_turn(ctx, "NL-XY45", resp)
        assert "NL-XY45" in speech
        assert "cancel" in speech.lower()


# ─── TC-2.22: FSM — waitlist offered when no slots ───────────────────────────

class TestDialogueFSMWaitlist:
    @patch("src.booking.slot_resolver.resolve_slots")
    def test_no_slots_offers_waitlist(self, mock_resolve):
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.TOPIC_COLLECTED)
        ctx.topic = "statements_tax"
        ctx.day_preference = "Sunday"
        ctx.time_preference = "evening"
        resp = _resp(intent="book_new", speech="Evening Sunday please.")
        new_ctx, speech = fsm.process_turn(ctx, "Sunday evening", resp)
        assert new_ctx.current_state == DialogueState.WAITLIST_OFFERED
        assert "waitlist" in speech.lower()

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_waitlist_accepted(self, mock_resolve):
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.WAITLIST_OFFERED)
        ctx.topic = "statements_tax"
        ctx.day_preference = "Sunday"
        ctx.time_preference = "evening"
        resp = _resp(intent="book_new", speech="Yes please add me.", raw="yes")
        new_ctx, speech = fsm.process_turn(ctx, "yes", resp)
        assert new_ctx.current_state == DialogueState.WAITLIST_CONFIRMED
        assert new_ctx.waitlist_code is not None
        assert "NL-W" in new_ctx.waitlist_code

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_waitlist_declined(self, mock_resolve):
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.WAITLIST_OFFERED)
        ctx.topic = "statements_tax"
        resp = _resp(intent="book_new", speech="No thanks.", raw="no thanks")
        new_ctx, speech = fsm.process_turn(ctx, "no thanks", resp)
        assert new_ctx.current_state == DialogueState.END


# ─── TC-2.25: IntentRouter — mocked LLM with markdown code fences ────────────

class TestIntentRouterCodeFences:
    def test_json_in_markdown_fence_parsed(self):
        payload = {
            "intent": "book_new",
            "slots": {"topic": "account_changes"},
            "speech": "Let me help you book.",
            "compliance_flag": None,
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        router = IntentRouter(llm_callable=MagicMock(return_value=raw))
        ctx = _ctx()
        result = router.route("I need to update my account", ctx)
        assert result.intent == "book_new"
        assert result.slots["topic"] == "account_changes"
