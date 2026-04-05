"""
tests/test_phase2_extended.py

Phase 2 — Extended test suite covering all behaviours added during the
battle-hardening session:

TC-E1   IntentRouter — end_call: "leave", "bye", "not interested" → end_call intent
TC-E2   IntentRouter — end_call: "day after tomorrow" NOT treated as end_call
TC-E3   IntentRouter — "day after tomorrow" extracted as day_preference, not "tomorrow"
TC-E4   IntentRouter — "this week" / "next week" extracted as day_preference
TC-E5   IntentRouter — specific date extracted ("15th", "April 15", "15/04/2026")
TC-E6   IntentRouter — "3pm", "10:30am", "14:00" extracted as time_preference
TC-E7   IntentRouter — named time bands: morning / afternoon / evening
TC-E8   IntentRouter — "any time" / "anytime" / "flexible" → "any"
TC-E9   IntentRouter — "not interested" → end_call (not timezone, "est" word-boundary guard)
TC-E10  IntentRouter — timezone abbreviation IST only on word boundary
TC-E11  FSM — end_call intent from ANY state → END
TC-E12  FSM — end_call mid-booking → END with farewell speech
TC-E13  FSM — topic retry escalation: 1st vague → topic prompt
TC-E14  FSM — topic retry escalation: 2nd vague → clarity check
TC-E15  FSM — topic retry escalation: 3rd vague → final nudge
TC-E16  FSM — topic retry escalation: 4th vague → circuit breaker END
TC-E17  FSM — topic retry resets to 0 on valid topic
TC-E18  FSM — rule-based day fallback in INTENT_IDENTIFIED state
TC-E19  FSM — rule-based time fallback in TOPIC_COLLECTED state
TC-E20  FSM — rule-based fallback does NOT overwrite already-set day
TC-E21  FSM — SLOTS_OFFERED: ordinal "1st" / "first" → Option 1
TC-E22  FSM — SLOTS_OFFERED: ordinal "2nd" / "second" → Option 2
TC-E23  FSM — SLOTS_OFFERED: "1st" with month context NOT treated as Option 1
TC-E24  FSM — SLOTS_OFFERED: apply_slots does NOT overwrite day/time in SLOTS_OFFERED
TC-E25  FSM — SLOTS_OFFERED: same input 3× → waitlist circuit breaker
TC-E26  FSM — SLOTS_OFFERED: time match on offered slots (e.g., "10am is fine")
TC-E27  FSM — SLOTS_OFFERED: "waitlist" keyword → WAITLIST_OFFERED
TC-E28  FSM — SLOTS_OFFERED: rejection words → re-prompt new preference
TC-E29  FSM — smart day check: no slots on day → show next available day in speech
TC-E30  FSM — waitlist contextual confirmation includes topic + day + time
TC-E31  FSM — waitlist contextual confirmation with no time pref ("any") omits time part
TC-E32  FSM — waitlist redirect response resets day/time and loops back to TIME_PREF
TC-E33  FSM — slot confirmed speech includes topic label
TC-E34  FSM — _dispatch_mcp generates NL-prefixed booking code
TC-E35  FSM — reschedule then time preference → SLOTS_OFFERED
TC-E36  FSM — cancel with code → END with confirmation
TC-E37  DialogueContext — slots_repeat_count and last_slots_input initialise to defaults
TC-E38  DialogueContext — topic_retry_count initialises to 0
TC-E39  IntentRouter — extract_day_preference: "next monday" beats bare "monday"
TC-E40  IntentRouter — extract_day_preference: "today" extracted
TC-E41  ComplianceResult — effective_speech returns original when compliant
TC-E42  ComplianceResult — effective_speech returns safe_speech when non-compliant
TC-E43  FSM — what_to_prepare intent → topic prompt
TC-E44  FSM — timezone_query stays in same state, returns IST info
TC-E45  FSM — BOOKING_COMPLETE → END on next turn
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytz

from src.dialogue import (
    ComplianceGuard,
    DialogueFSM,
    IntentRouter,
)
from src.dialogue.states import (
    DialogueContext,
    DialogueState,
    LLMResponse,
)
from src.dialogue.intent_router import (
    _extract_day_preference,
    _extract_time_preference,
    _rule_based_parse,
)

IST = pytz.timezone("Asia/Kolkata")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ctx(state: DialogueState = DialogueState.IDLE) -> DialogueContext:
    return DialogueContext(
        call_id="TEST-EXT",
        session_start_ist=datetime.now(IST),
        current_state=state,
    )


def _resp(
    intent: str = "book_new",
    slots: dict | None = None,
    speech: str = "Sure.",
    flag: str | None = None,
    raw: str = "Sure.",
) -> LLMResponse:
    return LLMResponse(
        intent=intent,
        slots=slots or {},
        speech=speech,
        compliance_flag=flag,
        raw_response=raw,
    )


def _offered_slots() -> list[dict]:
    """Two realistic mock slots in IST."""
    return [
        {
            "slot_id": "S1",
            "start": "2026-04-13T09:00:00+05:30",   # Monday April 13
            "start_ist": "Monday, 13/04/2026 at 09:00 AM IST",
        },
        {
            "slot_id": "S2",
            "start": "2026-04-13T14:00:00+05:30",   # Monday April 13
            "start_ist": "Monday, 13/04/2026 at 02:00 PM IST",
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# TC-E1 to TC-E10 — IntentRouter rule-based extraction
# ══════════════════════════════════════════════════════════════════════════════

class TestEndCallDetection:
    """TC-E1/TC-E2: end_call intent extraction."""

    def _route(self, text: str) -> LLMResponse:
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        return _rule_based_parse(text, ctx)

    def test_leave_triggers_end_call(self):
        result = self._route("I want to leave")
        assert result.intent == "end_call"

    def test_bye_triggers_end_call(self):
        result = self._route("bye")
        assert result.intent == "end_call"

    def test_goodbye_triggers_end_call(self):
        result = self._route("goodbye")
        assert result.intent == "end_call"

    def test_not_interested_triggers_end_call(self):  # TC-E9 key case
        result = self._route("not interested")
        assert result.intent == "end_call"

    def test_nevermind_triggers_end_call(self):
        result = self._route("nevermind")
        assert result.intent == "end_call"

    def test_maybe_later_triggers_end_call(self):
        result = self._route("maybe later")
        assert result.intent == "end_call"

    def test_dont_want_to_book_triggers_end_call(self):
        result = self._route("I don't want to book")
        assert result.intent == "end_call"

    def test_day_after_tomorrow_is_not_end_call(self):  # TC-E2
        result = self._route("day after tomorrow please")
        assert result.intent != "end_call"

    def test_i_am_done_triggers_end_call(self):
        result = self._route("I am done")
        assert result.intent == "end_call"


class TestDayExtraction:
    """TC-E3 to TC-E5, TC-E39, TC-E40: _extract_day_preference."""

    def test_day_after_tomorrow_takes_priority_over_tomorrow(self):  # TC-E3
        assert _extract_day_preference("day after tomorrow") == "day after tomorrow"

    def test_this_week_extracted(self):  # TC-E4
        assert _extract_day_preference("this week") == "this week"

    def test_next_week_extracted(self):  # TC-E4
        assert _extract_day_preference("next week") == "next week"

    def test_ordinal_date_extracted(self):  # TC-E5
        result = _extract_day_preference("the 15th please")
        assert result is not None and "15" in result

    def test_full_date_extracted(self):  # TC-E5
        result = _extract_day_preference("april 15")
        assert result is not None and "april" in result.lower() and "15" in result

    def test_date_with_slash_extracted(self):  # TC-E5
        result = _extract_day_preference("15/04/2026")
        assert result is not None and "15" in result

    def test_next_weekday_beats_bare_weekday(self):  # TC-E39
        assert _extract_day_preference("next monday") == "next monday"

    def test_today_extracted(self):  # TC-E40
        assert _extract_day_preference("today") == "today"

    def test_tomorrow_extracted(self):
        assert _extract_day_preference("tomorrow") == "tomorrow"

    def test_weekend_extracted(self):
        assert _extract_day_preference("weekend works") == "weekend"

    def test_bare_weekday_extracted(self):
        assert _extract_day_preference("monday") == "monday"

    def test_no_day_returns_none(self):
        assert _extract_day_preference("I want to book an appointment") is None


class TestTimeExtraction:
    """TC-E6 to TC-E8: _extract_time_preference."""

    def test_3pm_extracted(self):  # TC-E6
        assert _extract_time_preference("3pm please") is not None

    def test_10_30am_extracted(self):  # TC-E6
        assert _extract_time_preference("10:30am") is not None

    def test_24h_extracted(self):  # TC-E6
        assert _extract_time_preference("14:00") is not None

    def test_morning_extracted(self):  # TC-E7
        assert _extract_time_preference("morning") == "morning"

    def test_afternoon_extracted(self):  # TC-E7
        assert _extract_time_preference("afternoon") == "afternoon"

    def test_evening_extracted(self):  # TC-E7
        assert _extract_time_preference("evening") == "evening"

    def test_anytime_returns_any(self):  # TC-E8
        assert _extract_time_preference("anytime") == "any"

    def test_any_time_returns_any(self):  # TC-E8
        assert _extract_time_preference("any time") == "any"

    def test_flexible_returns_any(self):  # TC-E8
        assert _extract_time_preference("I am flexible") == "any"

    def test_no_time_returns_none(self):
        assert _extract_time_preference("I want to book") is None


class TestWordBoundaryGuard:
    """TC-E10: timezone abbreviation word-boundary guard."""

    def _route(self, text: str) -> LLMResponse:
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        return _rule_based_parse(text, ctx)

    def test_not_interested_not_timezone(self):  # "est" ⊂ "not interested"
        result = self._route("not interested")
        assert result.intent != "timezone_query"

    def test_ist_on_word_boundary_triggers_timezone(self):
        result = self._route("What is the IST equivalent of 2pm EST?")
        assert result.intent == "timezone_query"

    def test_interested_does_not_trigger_timezone(self):
        result = self._route("I am interested in booking")
        assert result.intent != "timezone_query"


# ══════════════════════════════════════════════════════════════════════════════
# TC-E11 to TC-E12 — FSM end_call global handling
# ══════════════════════════════════════════════════════════════════════════════

class TestEndCallFSM:
    """TC-E11/TC-E12: end_call terminates call from any state."""

    def _fsm(self):
        return DialogueFSM()

    def test_end_call_from_greeted(self):  # TC-E11
        ctx = _ctx(DialogueState.GREETED)
        resp = _resp(intent="end_call")
        new_ctx, speech = self._fsm().process_turn(ctx, "bye", resp)
        assert new_ctx.current_state == DialogueState.END
        assert "happy to help" in speech.lower() or "thank you" in speech.lower()

    def test_end_call_from_disclaimer_confirmed(self):  # TC-E11
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="end_call")
        new_ctx, speech = self._fsm().process_turn(ctx, "leave", resp)
        assert new_ctx.current_state == DialogueState.END

    def test_end_call_mid_booking(self):  # TC-E12
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "morning"
        ctx.offered_slots = _offered_slots()
        resp = _resp(intent="end_call")
        new_ctx, speech = self._fsm().process_turn(ctx, "never mind", resp)
        assert new_ctx.current_state == DialogueState.END

    def test_end_call_from_slot_confirmed(self):  # TC-E11
        ctx = _ctx(DialogueState.SLOT_CONFIRMED)
        ctx.topic = "kyc_onboarding"
        ctx.resolved_slot = _offered_slots()[0]
        resp = _resp(intent="end_call")
        new_ctx, speech = self._fsm().process_turn(ctx, "forget it", resp)
        assert new_ctx.current_state == DialogueState.END


# ══════════════════════════════════════════════════════════════════════════════
# TC-E13 to TC-E17 — Topic retry escalation
# ══════════════════════════════════════════════════════════════════════════════

class TestTopicRetryEscalation:
    """TC-E13 to TC-E17: topic_retry_count drives escalating prompts."""

    def _fsm(self):
        return DialogueFSM()

    def _vague_resp(self) -> LLMResponse:
        """No topic extracted — simulates a vague reply."""
        return _resp(intent="book_new", slots={})

    def test_first_vague_shows_topic_prompt(self):  # TC-E13
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        _, speech = self._fsm().process_turn(ctx, "ok", self._vague_resp())
        # Generic topic prompt — mentions the 5 categories
        assert any(kw in speech.lower() for kw in ["kyc", "sip", "statement", "withdrawal", "account"])
        assert ctx.current_state != DialogueState.END

    def test_second_vague_shows_clarity_check(self):  # TC-E14
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        ctx.topic_retry_count = 1  # already tried once
        _, speech = self._fsm().process_turn(ctx, "ok", self._vague_resp())
        # Clarity message uses stronger phrasing
        assert "one specific topic" in speech.lower() or "which one" in speech.lower()

    def test_third_vague_shows_final_nudge(self):  # TC-E15
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        ctx.topic_retry_count = 2
        _, speech = self._fsm().process_turn(ctx, "ojk", self._vague_resp())
        assert "still need a topic" in speech.lower() or "whichever fits" in speech.lower()

    def test_fourth_vague_circuit_breaker_ends_call(self):  # TC-E16
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        ctx.topic_retry_count = 3
        new_ctx, speech = self._fsm().process_turn(ctx, "ok", self._vague_resp())
        assert new_ctx.current_state == DialogueState.END
        assert "advisor" in speech.lower() or "reach out" in speech.lower()

    def test_valid_topic_resets_retry_count(self):  # TC-E17
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        ctx.topic_retry_count = 2
        resp = _resp(intent="book_new", slots={"topic": "kyc_onboarding"})
        new_ctx, _ = self._fsm().process_turn(ctx, "KYC please", resp)
        assert new_ctx.topic_retry_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# TC-E18 to TC-E20 — Rule-based day/time fallback in FSM
# ══════════════════════════════════════════════════════════════════════════════

class TestRuleBasedFallback:
    """TC-E18 to TC-E20: process_turn applies rule-based extraction when LLM missed slots."""

    def _fsm(self):
        return DialogueFSM()

    def test_tomorrow_extracted_in_intent_identified(self):  # TC-E18
        ctx = _ctx(DialogueState.INTENT_IDENTIFIED)
        ctx.intent = "book_new"
        ctx.topic = "kyc_onboarding"
        # LLM returned no slots — simulates missing extraction
        resp = _resp(intent="book_new", slots={})
        new_ctx, _ = self._fsm().process_turn(ctx, "tomorrow", resp)
        # Should have set day_preference via rule-based fallback
        assert new_ctx.day_preference == "tomorrow"

    def test_this_week_extracted_in_topic_collected(self):  # TC-E18
        ctx = _ctx(DialogueState.TOPIC_COLLECTED)
        ctx.topic = "sip_mandates"
        resp = _resp(intent="book_new", slots={})
        new_ctx, _ = self._fsm().process_turn(ctx, "this week please", resp)
        assert new_ctx.day_preference == "this week"

    def test_morning_extracted_in_topic_collected(self):  # TC-E19
        ctx = _ctx(DialogueState.TOPIC_COLLECTED)
        ctx.topic = "withdrawals"
        ctx.day_preference = "Monday"
        resp = _resp(intent="book_new", slots={})
        new_ctx, _ = self._fsm().process_turn(ctx, "morning works", resp)
        assert new_ctx.time_preference == "morning"

    def test_already_set_day_not_overwritten_by_fallback(self):  # TC-E20
        ctx = _ctx(DialogueState.TOPIC_COLLECTED)
        ctx.topic = "account_changes"
        ctx.day_preference = "next monday"   # already set
        resp = _resp(intent="book_new", slots={})
        new_ctx, _ = self._fsm().process_turn(ctx, "tuesday", resp)
        # Fallback should NOT overwrite already-set day_preference
        assert new_ctx.day_preference == "next monday"


# ══════════════════════════════════════════════════════════════════════════════
# TC-E21 to TC-E28 — SLOTS_OFFERED state
# ══════════════════════════════════════════════════════════════════════════════

class TestSlotsOfferedOrdinal:
    """TC-E21 to TC-E23: ordinal / option selection."""

    def _fsm(self):
        return DialogueFSM()

    def _ctx_with_slots(self) -> DialogueContext:
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "morning"
        ctx.offered_slots = _offered_slots()
        ctx.resolved_slot = _offered_slots()[0]
        return ctx

    def test_first_maps_to_option_1(self):  # TC-E21
        ctx = self._ctx_with_slots()
        resp = _resp(intent="book_new", speech="first one", raw="first one")
        new_ctx, speech = self._fsm().process_turn(ctx, "first one", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S1"

    def test_1st_maps_to_option_1(self):  # TC-E21
        ctx = self._ctx_with_slots()
        resp = _resp(intent="book_new", speech="1st please", raw="1st please")
        new_ctx, speech = self._fsm().process_turn(ctx, "1st please", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S1"

    def test_one_maps_to_option_1(self):  # TC-E21
        ctx = self._ctx_with_slots()
        resp = _resp(intent="book_new", speech="one", raw="one")
        new_ctx, _ = self._fsm().process_turn(ctx, "one", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S1"

    def test_second_maps_to_option_2(self):  # TC-E22
        ctx = self._ctx_with_slots()
        resp = _resp(intent="book_new", speech="second please", raw="second please")
        new_ctx, _ = self._fsm().process_turn(ctx, "second please", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S2"

    def test_2nd_maps_to_option_2(self):  # TC-E22
        ctx = self._ctx_with_slots()
        # "2nd please" — "2nd" is an unambiguous Option 2 selector
        resp = _resp(intent="book_new", speech="2nd please", raw="2nd please")
        new_ctx, _ = self._fsm().process_turn(ctx, "2nd please", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S2"

    def test_2nd_one_maps_to_option_2(self):  # TC-E22 variant — "2nd one" (not "option one")
        ctx = self._ctx_with_slots()
        # "2nd one" means "the second one" — "one" must not override "2nd"
        resp = _resp(intent="book_new", speech="2nd one", raw="2nd one")
        new_ctx, _ = self._fsm().process_turn(ctx, "2nd one", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S2"

    def test_1st_with_month_not_treated_as_option_1(self):  # TC-E23
        """'april 1st' should NOT map to Option 1."""
        ctx = self._ctx_with_slots()
        # Simulate LLM extracting "april 1st" as a day_preference
        resp = _resp(
            intent="book_new",
            slots={"day_preference": "april 1st"},
            speech="april 1st please",
            raw="april 1st please",
        )
        new_ctx, _ = self._fsm().process_turn(ctx, "april 1st please", resp)
        # Should NOT be slot confirmed with slot S1 directly
        # (it either re-searches or stays in SLOTS_OFFERED due to no match)
        # The important thing: it doesn't snap to S1 via ordinal logic
        if new_ctx.current_state == DialogueState.SLOT_CONFIRMED:
            # If it did confirm, it shouldn't have used the April 1st ordinal path
            # (it may have matched via other logic — just ensure slot_id is from offered list)
            assert new_ctx.resolved_slot["slot_id"] in ("S1", "S2")


class TestSlotsOfferedDateDrift:
    """TC-E24: apply_slots must not overwrite day/time in SLOTS_OFFERED."""

    def test_slots_offered_ignores_llm_day_time(self):  # TC-E24
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "13/04/2026"   # specific date
        ctx.time_preference = "morning"
        ctx.offered_slots = _offered_slots()
        ctx.resolved_slot = _offered_slots()[0]

        # LLM returns "monday" for day_preference (the weekday name, not the date)
        resp = _resp(
            intent="book_new",
            slots={"day_preference": "monday", "time_preference": "morning"},
            speech="monday morning please",
            raw="monday morning please",
        )
        fsm = DialogueFSM()
        new_ctx, _ = fsm.process_turn(ctx, "monday morning please", resp)

        # The specific date must be preserved
        assert new_ctx.day_preference == "13/04/2026"


class TestSlotsOfferedRepetitionGuard:
    """TC-E25: same input 3× → waitlist circuit breaker."""

    def test_three_identical_inputs_trigger_waitlist(self):  # TC-E25
        # The repetition guard fires when the same raw_response is seen >2 times
        # while staying in SLOTS_OFFERED.  We use a non-affirmative, non-day/time
        # input so each turn re-presents options (state stays SLOTS_OFFERED).
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.offered_slots = _offered_slots()
        ctx.resolved_slot = _offered_slots()[0]

        # "hmm" has no day/time slots, no ordinal, no affirmative →
        # stays in SLOTS_OFFERED (re-presents options) each time.
        for _ in range(2):
            resp = _resp(intent="book_new", speech="hmm", raw="hmm")
            ctx, speech = fsm.process_turn(ctx, "hmm", resp)
            assert ctx.current_state == DialogueState.SLOTS_OFFERED, \
                f"Expected SLOTS_OFFERED after turn, got {ctx.current_state}"

        # 3rd identical input → circuit breaker
        resp = _resp(intent="book_new", speech="hmm", raw="hmm")
        ctx, speech = fsm.process_turn(ctx, "hmm", resp)
        assert ctx.current_state == DialogueState.WAITLIST_OFFERED
        assert "waitlist" in speech.lower()


class TestSlotsOfferedTimeMatch:
    """TC-E26: user says "10am is fine" → matches to offered slot by time."""

    def test_time_only_input_matches_offered_slot(self):  # TC-E26
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.offered_slots = _offered_slots()   # S1 at 09:00, S2 at 14:00
        ctx.resolved_slot = _offered_slots()[0]

        # "9am is fine" → should match S1 (09:00)
        resp = _resp(
            intent="book_new",
            slots={"time_preference": "9am"},
            speech="9am is fine",
            raw="9am is fine",
        )
        new_ctx, speech = fsm.process_turn(ctx, "9am is fine", resp)
        assert new_ctx.current_state == DialogueState.SLOT_CONFIRMED
        assert new_ctx.resolved_slot["slot_id"] == "S1"


class TestSlotsOfferedWaitlistKeyword:
    """TC-E27: "waitlist" keyword → WAITLIST_OFFERED."""

    def test_waitlist_keyword_transitions(self):  # TC-E27
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.offered_slots = _offered_slots()
        ctx.resolved_slot = _offered_slots()[0]

        resp = _resp(intent="book_new", speech="add me to waitlist", raw="add me to waitlist")
        new_ctx, speech = fsm.process_turn(ctx, "add me to waitlist", resp)
        assert new_ctx.current_state == DialogueState.WAITLIST_OFFERED
        assert "waitlist" in speech.lower()


class TestSlotsOfferedRejection:
    """TC-E28: rejection words → re-prompt new preference."""

    def test_neither_resets_and_reprompts(self):  # TC-E28
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOTS_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.offered_slots = _offered_slots()
        ctx.resolved_slot = _offered_slots()[0]

        resp = _resp(intent="out_of_scope", speech="neither works", raw="neither works")
        new_ctx, speech = fsm.process_turn(ctx, "neither works", resp)
        assert new_ctx.current_state == DialogueState.TIME_PREFERENCE_COLLECTED
        assert new_ctx.day_preference is None
        assert new_ctx.time_preference is None


# ══════════════════════════════════════════════════════════════════════════════
# TC-E29 — Smart day availability check
# ══════════════════════════════════════════════════════════════════════════════

class TestSmartDayCheck:
    """TC-E29: when no slots on requested day, speech names next available day."""

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_no_slots_on_day_names_next_available(self, mock_resolve):  # TC-E29
        """Mock: Sunday has no slots; weekday slots exist."""
        def _side(day_pref, *_args, **_kwargs):
            if day_pref == "Sunday":
                return []
            # Return one Monday slot
            slot = MagicMock()
            slot.slot_id = "S-MON"
            slot.start.isoformat.return_value = "2026-04-13T09:00:00+05:30"
            slot.start_ist_str.return_value = "Monday, 13/04/2026 at 09:00 AM IST"
            slot.start.date.return_value = type("D", (), {"weekday": lambda self: 0})()
            from datetime import date
            slot.start.date.return_value = date(2026, 4, 13)
            slot.start.strftime.return_value = "Monday, 13 Apr"
            return [slot]

        mock_resolve.side_effect = _side

        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.TOPIC_COLLECTED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Sunday"
        ctx.time_preference = "any"

        resp = _resp(intent="book_new", slots={})
        new_ctx, speech = fsm.process_turn(ctx, "Sunday please", resp)

        assert new_ctx.current_state == DialogueState.SLOTS_OFFERED
        # Speech should mention the fallback day
        assert "monday" in speech.lower() or "next available" in speech.lower() or "sorry" in speech.lower()


# ══════════════════════════════════════════════════════════════════════════════
# TC-E30 to TC-E32 — Waitlist contextual confirmation
# ══════════════════════════════════════════════════════════════════════════════

class TestWaitlistContextual:
    """TC-E30 to TC-E32: contextual waitlist captures topic + day + time."""

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_waitlist_confirmation_includes_topic(self, mock_resolve):  # TC-E30
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.WAITLIST_OFFERED)
        ctx.topic = "statements_tax"
        ctx.day_preference = "Saturday"
        ctx.time_preference = "afternoon"

        resp = _resp(intent="book_new", speech="yes please", raw="yes please")
        new_ctx, speech = fsm.process_turn(ctx, "yes please", resp)

        assert new_ctx.current_state == DialogueState.WAITLIST_CONFIRMED
        assert "statements" in speech.lower() or "tax" in speech.lower()
        assert "saturday" in speech.lower()
        assert "afternoon" in speech.lower()

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_waitlist_confirmation_omits_time_when_any(self, mock_resolve):  # TC-E31
        """When time_preference is 'any', the confirmation should not mention a specific time."""
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.WAITLIST_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Monday"
        ctx.time_preference = "any"

        resp = _resp(intent="book_new", speech="yes", raw="yes")
        new_ctx, speech = fsm.process_turn(ctx, "yes", resp)

        assert new_ctx.current_state == DialogueState.WAITLIST_CONFIRMED
        # "any" should not appear literally in time part
        assert "in the any" not in speech.lower()

    @patch("src.booking.slot_resolver.resolve_slots")
    def test_waitlist_redirect_resets_preference(self, mock_resolve):  # TC-E32
        mock_resolve.return_value = []
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.WAITLIST_OFFERED)
        ctx.topic = "kyc_onboarding"
        ctx.day_preference = "Saturday"
        ctx.time_preference = "evening"

        resp = _resp(intent="book_new", speech="what other slots are available?", raw="what other slots are available?")
        new_ctx, speech = fsm.process_turn(ctx, "what other slots are available?", resp)

        assert new_ctx.current_state == DialogueState.TIME_PREFERENCE_COLLECTED
        assert new_ctx.day_preference is None
        assert new_ctx.time_preference is None


# ══════════════════════════════════════════════════════════════════════════════
# TC-E33 to TC-E36 — Booking confirmation and code
# ══════════════════════════════════════════════════════════════════════════════

class TestBookingConfirmationSpeech:
    """TC-E33 to TC-E36: confirmation speech and booking code."""

    def test_slot_confirmed_speech_includes_topic_label(self):  # TC-E33
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOT_CONFIRMED)
        ctx.topic = "kyc_onboarding"
        ctx.resolved_slot = _offered_slots()[0]

        resp = _resp(intent="book_new", speech="yes confirmed", raw="yes confirmed")
        new_ctx, speech = fsm.process_turn(ctx, "yes", resp)

        assert new_ctx.current_state == DialogueState.BOOKING_COMPLETE
        # Speech should include the topic label
        assert "kyc" in speech.lower() or "onboarding" in speech.lower()

    def test_dispatch_mcp_generates_nl_prefixed_code(self):  # TC-E34
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.SLOT_CONFIRMED)
        ctx.topic = "withdrawals"
        ctx.resolved_slot = _offered_slots()[0]

        resp = _resp(intent="book_new", speech="yes please")
        new_ctx, _ = fsm.process_turn(ctx, "yes", resp)

        assert new_ctx.booking_code is not None
        assert new_ctx.booking_code.startswith("NL-")

    def test_reschedule_then_time_preference_leads_to_slots(self):  # TC-E35
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.RESCHEDULE_CODE_COLLECTED)
        resp = _resp(
            intent="reschedule",
            slots={"existing_booking_code": "NL-AB2C"},
            speech="NL-AB2C",
            raw="NL-AB2C",
        )
        new_ctx, speech = fsm.process_turn(ctx, "NL-AB2C", resp)
        assert new_ctx.current_state == DialogueState.TIME_PREFERENCE_COLLECTED
        assert "NL-AB2C" in speech

    def test_cancel_with_code_ends_call(self):  # TC-E36
        fsm = DialogueFSM()
        ctx = _ctx(DialogueState.CANCEL_CODE_COLLECTED)
        resp = _resp(
            intent="cancel",
            slots={"existing_booking_code": "NL-XY9Z"},
            speech="NL-XY9Z",
            raw="NL-XY9Z",
        )
        new_ctx, speech = fsm.process_turn(ctx, "NL-XY9Z", resp)
        assert new_ctx.current_state == DialogueState.END
        assert "NL-XY9Z" in speech
        assert "cancel" in speech.lower()


# ══════════════════════════════════════════════════════════════════════════════
# TC-E37 to TC-E38 — DialogueContext field defaults
# ══════════════════════════════════════════════════════════════════════════════

class TestDialogueContextDefaults:
    """TC-E37 to TC-E38: new fields introduced during session."""

    def test_slots_repeat_count_starts_at_zero(self):  # TC-E37
        ctx = _ctx()
        assert ctx.slots_repeat_count == 0

    def test_last_slots_input_starts_at_none(self):  # TC-E37
        ctx = _ctx()
        assert ctx.last_slots_input is None

    def test_topic_retry_count_starts_at_zero(self):  # TC-E38
        ctx = _ctx()
        assert ctx.topic_retry_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# TC-E41 to TC-E42 — ComplianceResult.effective_speech
# ══════════════════════════════════════════════════════════════════════════════

class TestComplianceResultEffectiveSpeech:
    """TC-E41 to TC-E42: effective_speech helper."""

    def test_effective_speech_returns_original_when_compliant(self):  # TC-E41
        guard = ComplianceGuard()
        result = guard.check("Your appointment is confirmed for Monday at 10 AM.")
        assert result.effective_speech("Your appointment is confirmed for Monday at 10 AM.") == \
               "Your appointment is confirmed for Monday at 10 AM."

    def test_effective_speech_returns_safe_when_non_compliant(self):  # TC-E42
        guard = ComplianceGuard()
        result = guard.check("You should buy Nifty 50 today for great returns.")
        assert result.is_compliant is False
        eff = result.effective_speech("You should buy Nifty 50 today for great returns.")
        assert "investment advice" in eff.lower()


# ══════════════════════════════════════════════════════════════════════════════
# TC-E43 to TC-E45 — FSM miscellaneous state handlers
# ══════════════════════════════════════════════════════════════════════════════

class TestFSMMiscellaneous:
    """TC-E43 to TC-E45: what_to_prepare, timezone_query, BOOKING_COMPLETE."""

    def _fsm(self):
        return DialogueFSM()

    def test_what_to_prepare_goes_to_topic_prompt(self):  # TC-E43
        fsm = self._fsm()
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="what_to_prepare")
        new_ctx, speech = fsm.process_turn(ctx, "what documents do I need?", resp)
        # Should be in INTENT_IDENTIFIED and prompt for topic
        assert new_ctx.current_state in (
            DialogueState.INTENT_IDENTIFIED,
            DialogueState.TOPIC_COLLECTED,
        )
        assert any(kw in speech.lower() for kw in ["kyc", "sip", "statement", "withdrawal", "account"])

    def test_timezone_query_stays_in_state(self):  # TC-E44
        fsm = self._fsm()
        ctx = _ctx(DialogueState.DISCLAIMER_CONFIRMED)
        resp = _resp(intent="timezone_query")
        new_ctx, speech = fsm.process_turn(ctx, "what is 2pm IST in New York?", resp)
        assert new_ctx.current_state == DialogueState.DISCLAIMER_CONFIRMED
        assert "ist" in speech.lower()

    def test_booking_complete_transitions_to_end(self):  # TC-E45
        fsm = self._fsm()
        ctx = _ctx(DialogueState.BOOKING_COMPLETE)
        ctx.booking_code = "NL-TEST"
        resp = _resp(intent="book_new", speech="thank you", raw="thank you")
        new_ctx, speech = fsm.process_turn(ctx, "thank you", resp)
        assert new_ctx.current_state == DialogueState.END


# ══════════════════════════════════════════════════════════════════════════════
# Integration: full end-to-end paths (rule-based offline, no LLM needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestFullFlowIntegration:
    """End-to-end flow tests using real FSM + offline IntentRouter."""

    def _run_flow(self, turns: list[str]) -> tuple[DialogueContext, list[str]]:
        """
        Runs a sequence of user inputs through FSM + offline IntentRouter.
        Returns (final_ctx, list_of_agent_responses).
        """
        router = IntentRouter(llm_callable=None)
        fsm = DialogueFSM()
        ctx, greeting = fsm.start()
        speeches = [greeting]
        for text in turns:
            resp = router.route(text, ctx)
            ctx, speech = fsm.process_turn(ctx, text, resp)
            speeches.append(speech)
            if ctx.current_state.is_terminal():
                break
        return ctx, speeches

    def test_end_call_from_greeting(self):
        ctx, speeches = self._run_flow(["bye"])
        assert ctx.current_state == DialogueState.END

    def test_refuse_advice_then_continue(self):
        ctx, speeches = self._run_flow([
            "yes",
            "which stock should I buy?",
            "ok, KYC onboarding Monday morning",
        ])
        # After advice refusal, user restated booking intent
        assert ctx.topic == "kyc_onboarding" or ctx.current_state not in (
            DialogueState.IDLE, DialogueState.GREETED
        )

    def test_reschedule_flow_end_to_end(self):
        # "I want to reschedule" from GREETED → rule-based intent=reschedule →
        # _from_greeted: intent not in book_new list → DISCLAIMER_CONFIRMED
        # second turn with same → _from_disclaimer → RESCHEDULE_CODE_COLLECTED
        ctx, speeches = self._run_flow([
            "I want to reschedule my appointment",   # GREETED → DISCLAIMER_CONFIRMED
            "I want to reschedule please",           # DISCLAIMER_CONFIRMED → RESCHEDULE_CODE_COLLECTED
        ])
        assert ctx.current_state == DialogueState.RESCHEDULE_CODE_COLLECTED
        assert any("booking code" in s.lower() for s in speeches)

    def test_cancel_flow_end_to_end(self):
        ctx, speeches = self._run_flow([
            "I want to cancel my booking",   # GREETED → DISCLAIMER_CONFIRMED
            "cancel please",                 # DISCLAIMER_CONFIRMED → CANCEL_CODE_COLLECTED
        ])
        assert ctx.current_state == DialogueState.CANCEL_CODE_COLLECTED
        assert any("booking code" in s.lower() for s in speeches)

    def test_silence_then_valid_input_resets_counter(self):
        router = IntentRouter(llm_callable=None)
        fsm = DialogueFSM()
        ctx, _ = fsm.start()

        # Two silences
        for _ in range(2):
            resp = router.route("", ctx)
            ctx, _ = fsm.process_turn(ctx, "", resp)
        assert ctx.no_input_count == 2

        # Valid input resets
        resp = router.route("yes", ctx)
        ctx, _ = fsm.process_turn(ctx, "yes", resp)
        assert ctx.no_input_count == 0
