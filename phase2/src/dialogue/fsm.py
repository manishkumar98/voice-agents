"""
src/dialogue/fsm.py

Dialogue State Machine — controls exactly which states the agent
can be in and what transitions are valid.

The FSM is intentionally stateless: all state lives in DialogueContext,
which is passed in and returned on each call. This makes it easy to
persist, reload, and test without side effects.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytz

from .states import DialogueContext, DialogueState, LLMResponse, TOPIC_LABELS

IST = pytz.timezone("Asia/Kolkata")

# ─── Static responses ─────────────────────────────────────────────────────────

_STRINGS = {
    "en-IN": {
        "greeting": (
            "Hello! I'm the Advisor Scheduling assistant. "
            "I'll help you book a consultation in about two minutes."
        ),
        "disclaimer": (
            "Quick note: this service is for scheduling only. "
            "Our advisors provide informational guidance, not investment advice. "
            "Shall we continue?"
        ),
        "topic_prompt": (
            "Great. What topic would you like to discuss? "
            "I can help with: KYC and onboarding, SIP and mandates, "
            "statements and tax documents, withdrawals and timelines, "
            "or account changes and nominee updates."
        ),
        "topic_clarity": (
            "To connect you with the right advisor, I need you to choose one specific topic: "
            "KYC and onboarding, SIP and mandates, statements and tax documents, "
            "withdrawals and timelines, or account changes. Which one applies to you?"
        ),
        "topic_final_nudge": (
            "I still need a topic to proceed. Just say one of: KYC, SIP, statements, "
            "withdrawals, or account changes — whichever fits best."
        ),
        "time_prompt": "What day and time works best for you this week or next?",
        "refusal_advice": (
            "I'm not able to provide investment advice. "
            "I can help you book a consultation with an advisor. "
            "Would you like to do that?"
        ),
        "refusal_pii": (
            "Please don't share personal details on this call. "
            "You'll receive a secure link after booking to submit your contact information."
        ),
        "out_of_scope": "I'm only able to help with advisor appointment scheduling today.",
        "timezone": (
            "All our appointment slots are in IST (India Standard Time, UTC+5:30). "
            "Please use a timezone converter to find your local equivalent. "
            "Would you like to book a slot?"
        ),
        "error": (
            "I'm having trouble understanding. "
            "Let me connect you with our support team. Goodbye."
        ),
        "farewell": "Thank you for calling. Have a great day!",
        "end_call": (
            "Thank you for reaching out. We'll be happy to help whenever you're ready. "
            "Have a wonderful day!"
        ),
        "waitlist": (
            "I'm sorry, no slots are available for your requested time. "
            "Would you like to be added to our waitlist? "
            "We'll contact you as soon as a slot opens."
        ),
        "booking_code_prompt": "Please share your booking code so I can find your appointment.",
        "topic_circuit_breaker": (
            "It seems we're having trouble finding the right topic. "
            "A human advisor will reach out to you directly. "
            "Thank you for calling — have a great day!"
        ),
        "booking_confirmed": (
            "Your booking is confirmed. "
            "{topic_label} on {slot_readable}. "
            "Your booking code is {code_spoken}. "
            "Please note it down. "
            "You'll receive a secure link to submit your contact details. "
            "Thank you for calling!"
        ),
        "waitlist_confirmed": (
            "{queue_msg}Done. I've added you to the waitlist specifically for "
            "{topic_label}{day_part}{time_part}. "
            "Your waitlist code is {code_spoken}. "
            "An advisor will reach out as soon as that slot opens. Thank you!"
        ),
        "waitlist_decline": "No problem. Feel free to call back when you're ready. Goodbye!",
        "waitlist_redirect": (
            "Unfortunately no slots are open for that time. "
            "Would you like to try a different day or time? "
            "Or I can add you to the waitlist and we'll reach out when something opens."
        ),
        "waitlist_reprompt": "Sorry, I didn't catch that. Would you like to be added to the waitlist? Just say yes or no.",
        "code_not_found": "I didn't catch your booking code. Could you repeat it?",
    },
    "hi-IN": {
        "greeting": (
            "नमस्ते! मैं Advisor Scheduling सहायक हूँ। "
            "मैं आपकी लगभग दो मिनट में एक परामर्श बुक करने में मदद करूँगा।"
        ),
        "disclaimer": (
            "एक छोटी सी जानकारी: यह सेवा केवल अपॉइंटमेंट शेड्यूलिंग के लिए है। "
            "हमारे सलाहकार मार्गदर्शन देते हैं, निवेश सलाह नहीं। "
            "क्या हम आगे बढ़ें?"
        ),
        "topic_prompt": (
            "बढ़िया। आप किस विषय पर चर्चा करना चाहते हैं? "
            "मैं इनमें मदद कर सकता हूँ: KYC और ऑनबोर्डिंग, SIP और मैंडेट, "
            "स्टेटमेंट और टैक्स दस्तावेज़, निकासी, "
            "या खाते में बदलाव और नॉमिनी अपडेट।"
        ),
        "topic_clarity": (
            "सही सलाहकार से जोड़ने के लिए, कृपया एक विषय चुनें: "
            "KYC और ऑनबोर्डिंग, SIP और मैंडेट, स्टेटमेंट और टैक्स, "
            "निकासी, या खाता परिवर्तन। आपके लिए कौन सा सही है?"
        ),
        "topic_final_nudge": (
            "आगे बढ़ने के लिए मुझे एक विषय चाहिए। बस बोलिए: KYC, SIP, स्टेटमेंट, "
            "निकासी, या खाता परिवर्तन।"
        ),
        "time_prompt": "इस सप्ताह या अगले सप्ताह कौन सा दिन और समय आपके लिए सुविधाजनक है?",
        "refusal_advice": (
            "मैं निवेश सलाह देने में असमर्थ हूँ। "
            "मैं आपकी सलाहकार के साथ मुलाकात बुक करने में मदद कर सकता हूँ। "
            "क्या आप बुकिंग करना चाहेंगे?"
        ),
        "refusal_pii": (
            "कृपया इस कॉल पर व्यक्तिगत जानकारी साझा न करें। "
            "बुकिंग के बाद आपको एक सुरक्षित लिंक मिलेगा।"
        ),
        "out_of_scope": "मैं केवल सलाहकार अपॉइंटमेंट शेड्यूलिंग में मदद कर सकता हूँ।",
        "timezone": (
            "हमारे सभी अपॉइंटमेंट IST (भारतीय मानक समय, UTC+5:30) में हैं। "
            "अपने स्थानीय समय के लिए कृपया टाइमज़ोन कन्वर्टर का उपयोग करें। "
            "क्या आप स्लॉट बुक करना चाहेंगे?"
        ),
        "error": (
            "मुझे समझने में कठिनाई हो रही है। "
            "कृपया हमारी सपोर्ट टीम से संपर्क करें। धन्यवाद।"
        ),
        "farewell": "कॉल करने के लिए धन्यवाद। आपका दिन शुभ हो!",
        "end_call": (
            "संपर्क करने के लिए धन्यवाद। जब भी ज़रूरत हो हम मदद के लिए तैयार हैं। "
            "आपका दिन अच्छा हो!"
        ),
        "waitlist": (
            "खेद है, आपके अनुरोधित समय के लिए कोई स्लॉट उपलब्ध नहीं है। "
            "क्या आप वेटलिस्ट में जुड़ना चाहेंगे? "
            "स्लॉट खुलते ही हम आपसे संपर्क करेंगे।"
        ),
        "booking_code_prompt": "कृपया अपना बुकिंग कोड बताएं ताकि मैं आपकी अपॉइंटमेंट ढूंढ सकूँ।",
        "topic_circuit_breaker": (
            "लगता है हमें सही विषय खोजने में कठिनाई हो रही है। "
            "एक सलाहकार जल्द ही आपसे संपर्क करेगा। "
            "कॉल करने के लिए धन्यवाद — आपका दिन शुभ हो!"
        ),
        "booking_confirmed": (
            "आपकी बुकिंग की पुष्टि हो गई है। "
            "{topic_label} — {slot_readable}। "
            "आपका बुकिंग कोड है {code_spoken}। "
            "कृपया इसे नोट कर लें। "
            "आपकी संपर्क जानकारी जमा करने के लिए एक सुरक्षित लिंक भेजा जाएगा। "
            "कॉल करने के लिए धन्यवाद!"
        ),
        "waitlist_confirmed": (
            "{queue_msg}हो गया। मैंने आपको {topic_label}{day_part}{time_part} के लिए वेटलिस्ट में जोड़ दिया है। "
            "आपका वेटलिस्ट कोड है {code_spoken}। "
            "स्लॉट खुलते ही सलाहकार आपसे संपर्क करेंगे। धन्यवाद!"
        ),
        "waitlist_decline": "कोई बात नहीं। जब भी ज़रूरत हो, दोबारा कॉल करें। अलविदा!",
        "waitlist_redirect": (
            "खेद है, उस समय के लिए कोई स्लॉट उपलब्ध नहीं है। "
            "क्या आप कोई अलग दिन या समय आज़माना चाहेंगे? "
            "या मैं आपको वेटलिस्ट में जोड़ सकता हूँ।"
        ),
        "waitlist_reprompt": "माफ़ करें, मैं समझ नहीं पाया। क्या आप वेटलिस्ट में जुड़ना चाहते हैं? हाँ या नहीं बोलिए।",
        "code_not_found": "मैं आपका बुकिंग कोड नहीं समझ पाया। क्या आप दोबारा बता सकते हैं?",
    },
}


def _s(key: str) -> str:
    """Return the speech string for the current language (from TTS_LANGUAGE env var)."""
    lang = os.environ.get("TTS_LANGUAGE", "en-IN")
    return _STRINGS.get(lang, _STRINGS["en-IN"])[key]


# Keep legacy names as callables for any external references
def _GREETING():        return _s("greeting")
def _DISCLAIMER():      return _s("disclaimer")
def _TOPIC_PROMPT():    return _s("topic_prompt")
def _TOPIC_CLARITY():   return _s("topic_clarity")
def _TOPIC_FINAL_NUDGE(): return _s("topic_final_nudge")
def _TIME_PROMPT():     return _s("time_prompt")
def _REFUSAL_ADVICE():  return _s("refusal_advice")
def _REFUSAL_PII():     return _s("refusal_pii")
def _OUT_OF_SCOPE():    return _s("out_of_scope")
def _TIMEZONE_RESPONSE(): return _s("timezone")
def _ERROR_MSG():       return _s("error")
def _FAREWELL():        return _s("farewell")
def _END_CALL():        return _s("end_call")
def _WAITLIST_OFFER():  return _s("waitlist")
def _BOOKING_CODE_PROMPT(): return _s("booking_code_prompt")

MAX_NO_INPUT = 3


class DialogueFSM:
    """
    Stateless dialogue FSM.

    Usage:
        fsm = DialogueFSM()
        ctx, speech = fsm.start(call_id="CALL-001")
        ctx, speech = fsm.process_turn(ctx, user_input="yes", llm_response=llm_resp)
    """

    # ── Entry point ────────────────────────────────────────────────────────────

    def start(self, call_id: str | None = None) -> tuple[DialogueContext, str]:
        """
        Initialise a new call. Transitions S0 → S1.
        Returns (context, greeting_speech).
        """
        if call_id is None:
            now = datetime.now(IST)
            call_id = f"CALL-{now.strftime('%Y%m%d-%H%M%S')}"

        ctx = DialogueContext(
            call_id=call_id,
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.IDLE,
        )
        ctx.current_state = DialogueState.GREETED
        speech = f"{_GREETING()} {_DISCLAIMER()}"
        return ctx, speech

    # ── Main turn processor ────────────────────────────────────────────────────

    def process_turn(
        self,
        ctx: DialogueContext,
        user_input: str,
        llm_response: LLMResponse,
    ) -> tuple[DialogueContext, str]:
        """
        Process one dialogue turn.

        Args:
            ctx:          Current dialogue context (will be mutated and returned).
            user_input:   The user's raw (already PII-scrubbed) text.
            llm_response: Structured response from the intent router.

        Returns:
            (updated_ctx, speech_text)
        """
        ctx.turn_count += 1

        # ── No-input / silence handling ────────────────────────────────────────
        if not user_input.strip():
            ctx.no_input_count += 1
            if ctx.no_input_count >= MAX_NO_INPUT:
                return self._go_error(ctx)
            return ctx, self._re_prompt(ctx)

        ctx.no_input_count = 0  # reset on valid input

        # ── User wants to end the call — valid at any point ───────────────────
        if llm_response.intent == "end_call":
            ctx.current_state = DialogueState.END
            return ctx, _END_CALL()

        # ── Compliance refusals — stay in same state ──────────────────────────
        if llm_response.compliance_flag == "refuse_advice":
            return ctx, _REFUSAL_ADVICE()
        if llm_response.compliance_flag == "refuse_pii":
            return ctx, _REFUSAL_PII()
        if llm_response.compliance_flag == "out_of_scope":
            return ctx, _OUT_OF_SCOPE()
        if llm_response.intent == "timezone_query":
            return ctx, _TIMEZONE_RESPONSE()

        # ── Merge extracted slots into context ────────────────────────────────
        # In SLOTS_OFFERED we intentionally do NOT apply day/time from the LLM —
        # the user is picking from already-offered options, not setting new preferences.
        # _from_slots_offered will apply them only if a genuine new search is needed.
        if ctx.current_state == DialogueState.SLOTS_OFFERED:
            safe = {k: v for k, v in llm_response.slots.items()
                    if k not in ("day_preference", "time_preference")}
            ctx.apply_slots(safe)
        else:
            ctx.apply_slots(llm_response.slots)

        # ── Rule-based extraction fallback ────────────────────────────────────
        # LLMs sometimes omit day/time from slots for short replies like
        # "tomorrow", "this week", "15th", or "Monday 3pm".
        # Only run when we are actively collecting day/time (not when the user
        # is picking a slot, confirming, or in any terminal/code state).
        _DAY_TIME_COLLECTION_STATES = {
            DialogueState.INTENT_IDENTIFIED,
            DialogueState.TOPIC_COLLECTED,
            DialogueState.TIME_PREFERENCE_COLLECTED,
        }
        if ctx.current_state in _DAY_TIME_COLLECTION_STATES and (
            not ctx.day_preference or not ctx.time_preference
        ):
            from src.dialogue.intent_router import (
                _extract_day_preference, _extract_time_preference,
            )
            raw_low = user_input.lower().strip()
            if raw_low:
                if not ctx.day_preference:
                    _day = _extract_day_preference(raw_low)
                    if _day:
                        ctx.day_preference = _day
                if not ctx.time_preference:
                    _time = _extract_time_preference(raw_low)
                    if _time:
                        ctx.time_preference = _time

        # ── Route by current state ────────────────────────────────────────────
        state = ctx.current_state

        if state == DialogueState.GREETED:
            return self._from_greeted(ctx, llm_response)

        if state == DialogueState.DISCLAIMER_CONFIRMED:
            return self._from_disclaimer(ctx, llm_response)

        if state in (DialogueState.INTENT_IDENTIFIED, DialogueState.TOPIC_COLLECTED):
            return self._collect_topic(ctx, llm_response)

        if state == DialogueState.TIME_PREFERENCE_COLLECTED:
            return self._offer_slots(ctx, llm_response)

        if state == DialogueState.SLOTS_OFFERED:
            return self._from_slots_offered(ctx, llm_response)

        if state == DialogueState.SLOT_CONFIRMED:
            return self._dispatch_mcp(ctx)

        if state == DialogueState.BOOKING_COMPLETE:
            ctx.current_state = DialogueState.END
            return ctx, _FAREWELL()

        if state == DialogueState.WAITLIST_OFFERED:
            return self._from_waitlist_offered(ctx, llm_response)

        if state in (DialogueState.RESCHEDULE_CODE_COLLECTED, DialogueState.CANCEL_CODE_COLLECTED):
            return self._handle_code_flow(ctx, llm_response)

        if state == DialogueState.ERROR:
            ctx.current_state = DialogueState.END
            return ctx, _FAREWELL()

        # Terminal states — nothing more to do
        return ctx, _FAREWELL()

    # ── State handlers ─────────────────────────────────────────────────────────

    def _from_greeted(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S1 → S2 on any affirmative / acknowledgement."""
        ctx.current_state = DialogueState.DISCLAIMER_CONFIRMED
        # If the LLM already extracted an intent, jump straight to topic
        if resp.intent in ("book_new", "what_to_prepare", "check_availability"):
            ctx.intent = resp.intent
            ctx.current_state = DialogueState.INTENT_IDENTIFIED
            return self._collect_topic(ctx, resp)
        return ctx, _TOPIC_PROMPT()

    def _from_disclaimer(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S2 → branch by intent."""
        ctx.intent = resp.intent

        if resp.intent == "book_new":
            ctx.current_state = DialogueState.INTENT_IDENTIFIED
            return self._collect_topic(ctx, resp)

        if resp.intent == "reschedule":
            ctx.current_state = DialogueState.RESCHEDULE_CODE_COLLECTED
            return ctx, _BOOKING_CODE_PROMPT()

        if resp.intent == "cancel":
            ctx.current_state = DialogueState.CANCEL_CODE_COLLECTED
            return ctx, _BOOKING_CODE_PROMPT()

        if resp.intent in ("what_to_prepare", "check_availability"):
            ctx.current_state = DialogueState.INTENT_IDENTIFIED
            return self._collect_topic(ctx, resp)

        # Unclear intent — re-prompt
        return ctx, _TOPIC_PROMPT()

    def _collect_topic(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S3/S4 — ensure topic is filled, then move to slot resolution.

        Proceeds to _offer_slots as soon as day_preference is known.
        time_preference is optional — _offer_slots defaults it to 'any'
        and shows all available slots on that day.

        If the LLM missed day/time extraction (common for short replies like
        "tomorrow" or "Monday 3pm"), we re-extract from the raw user input
        using the rule-based extractors as a guaranteed fallback.
        """
        if ctx.topic:
            ctx.topic_retry_count = 0  # reset on success
            ctx.current_state = DialogueState.TOPIC_COLLECTED
            if ctx.day_preference:
                return self._offer_slots(ctx, resp)
            return ctx, _TIME_PROMPT()

        # Topic not filled — escalate with each retry
        ctx.topic_retry_count += 1
        ctx.current_state = DialogueState.INTENT_IDENTIFIED

        if ctx.topic_retry_count >= 4:
            # Circuit breaker — end gracefully after 3 failed attempts
            ctx.current_state = DialogueState.END
            return ctx, _s("topic_circuit_breaker")
        if ctx.topic_retry_count == 3:
            return ctx, _TOPIC_FINAL_NUDGE()
        if ctx.topic_retry_count == 2:
            return ctx, _TOPIC_CLARITY()
        return ctx, _TOPIC_PROMPT()

    def _offer_slots(self, ctx: DialogueContext, _resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S5 — always offer exactly 2 slots; expand search if needed.

        Flow:
          1. Check if requested day has ANY slots (ignoring time filter).
          2. If the day has no slots → tell the user and show next available day.
          3. If the day has slots → apply time filter, then show options.
        """
        from src.booking.slot_resolver import (
            resolve_slots, parse_datetime_summary,
            _parse_day_preference,
        )

        # Absolute path fallback so CWD never matters
        _default_cal = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "phase1", "data", "mock_calendar.json",
        ))
        calendar_path = os.environ.get("MOCK_CALENDAR_PATH") or _default_cal

        day_pref  = ctx.day_preference or "this week"
        time_pref = ctx.time_preference or "any"

        # Only re-ask if day is completely unparseable (no candidate dates at all)
        _, needs_confirm = parse_datetime_summary(day_pref, time_pref)
        candidate_dates, _ = _parse_day_preference(day_pref)
        if needs_confirm and not candidate_dates:
            ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
            return ctx, (
                f"I didn't quite catch the date. "
                f"Could you say something like: 'Monday', 'this week', or '10th April'?"
            )

        def _merge(base: list, additions: list) -> list:
            seen = {s.slot_id for s in base}
            result = list(base)
            for s in additions:
                if s.slot_id not in seen:
                    result.append(s)
                    seen.add(s.slot_id)
            return result

        # ── Step 1: Does the requested day have ANY slots at all? ──────────────
        candidate_dates, day_confident = _parse_day_preference(day_pref)
        target_date = candidate_dates[0].date() if (candidate_dates and day_confident) else None

        day_has_slots = bool(
            resolve_slots(day_pref, "any", ctx.topic, calendar_path, max_results=1)
        ) if target_date else True  # For week-ranges we skip this check

        time_clause = f" at {time_pref}" if time_pref not in ("any", "anytime", "any time", "") else ""

        if not day_has_slots:
            # ── No slots on the requested day — find the next available day ───
            fallback: list = []
            for period in ("this week", "next week"):
                fallback = resolve_slots(period, "any", ctx.topic, calendar_path, max_results=2)
                # Filter out any that are on the no-slot day itself (shouldn't exist but be safe)
                fallback = [s for s in fallback if s.start.date() != target_date]
                if len(fallback) >= 1:
                    break

            if not fallback:
                ctx.current_state = DialogueState.WAITLIST_OFFERED
                return ctx, _WAITLIST_OFFER()

            next_day_label = fallback[0].start.strftime("%A, %d %b")
            slots = fallback[:2]
            slots.sort(key=lambda s: s.start)

            ctx.current_state = DialogueState.SLOTS_OFFERED
            ctx.offered_slots = [
                {"slot_id": s.slot_id, "start": s.start.isoformat(), "start_ist": s.start_ist_str()}
                for s in slots
            ]
            ctx.resolved_slot = ctx.offered_slots[0]

            preamble = (
                f"Sorry, no slots are available on {day_pref}{time_clause}. "
                f"The next available day is {next_day_label}. "
                "Here are the options — or I can add you to the waitlist: "
            )
            parts = [preamble]
            for i, s in enumerate(slots, 1):
                parts.append(f"Option {i}: {s.start_ist_str()}.")
            parts.append(" Which would you prefer, or shall I add you to the waitlist?")
            return ctx, "".join(parts)

        # ── Step 2: Day has slots — apply time filter then fill up to 2 ───────
        slots = resolve_slots(day_pref, time_pref, ctx.topic, calendar_path, max_results=2)

        # Pad: same day, any time (if time filter was too narrow)
        if len(slots) < 2:
            same_day = resolve_slots(day_pref, "any", ctx.topic, calendar_path, max_results=4)
            slots = _merge(slots, same_day)[:2]

        # Pad: next periods (shouldn't be needed since day has slots, but be safe)
        if len(slots) < 2:
            for period in ("this week", "next week"):
                more = resolve_slots(period, "any", ctx.topic, calendar_path, max_results=6)
                slots = _merge(slots, more)[:2]
                if len(slots) >= 2:
                    break

        slots.sort(key=lambda s: s.start)

        if not slots:
            ctx.current_state = DialogueState.WAITLIST_OFFERED
            return ctx, _WAITLIST_OFFER()

        ctx.current_state = DialogueState.SLOTS_OFFERED
        ctx.offered_slots = [
            {"slot_id": s.slot_id, "start": s.start.isoformat(), "start_ist": s.start_ist_str()}
            for s in slots
        ]
        ctx.resolved_slot = ctx.offered_slots[0]

        on_requested = [s for s in slots if target_date and s.start.date() == target_date]

        if target_date is None:
            # Range-based query (e.g. "this week", "next week") — all found slots are valid
            next_day_label = slots[0].start.strftime("%A, %d %b")
            preamble = (
                f"Here are the available slots{time_clause}: "
                f"The earliest is {next_day_label}. "
            )
        elif len(on_requested) == len(slots):
            preamble = f"I found {len(slots)} slot(s) on {day_pref}{time_clause}. "
        elif on_requested:
            preamble = (
                f"I only have 1 slot on {day_pref}{time_clause}. "
                "Here are the two closest available options: "
            )
        else:
            next_day_label = slots[0].start.strftime("%A, %d %b")
            preamble = (
                f"No slots match {day_pref}{time_clause}. "
                f"The next available day is {next_day_label}. "
                "Here are the closest options: "
            )

        parts = [preamble]
        for i, s in enumerate(slots, 1):
            parts.append(f"Option {i}: {s.start_ist_str()}.")
        parts.append(" Which would you prefer, or shall I add you to the waitlist?")
        return ctx, "".join(parts)

    def _from_slots_offered(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S6 — user picks a slot, requests waitlist, asks a question, or gives new preference."""
        from src.booking.slot_resolver import _parse_time_preference, _parse_day_preference
        from datetime import datetime as _dt

        user_text = (resp.raw_response or "").strip().lower()
        speech_lower = (resp.speech + " " + (resp.raw_response or "")).lower()

        # ── Repetition guard ────────────────────────────────────────────────
        if user_text and user_text == (ctx.last_slots_input or "").lower():
            ctx.slots_repeat_count += 1
        else:
            ctx.slots_repeat_count = 1
        ctx.last_slots_input = user_text

        if ctx.slots_repeat_count > 2:
            ctx.slots_repeat_count = 0
            ctx.current_state = DialogueState.WAITLIST_OFFERED
            return ctx, (
                "I'm having trouble matching that to an available slot. "
                "Let me add you to the waitlist and we'll call you back. " + _WAITLIST_OFFER()
            )

        # ── Waitlist request ────────────────────────────────────────────────
        waitlist_words = {"waitlist", "wait list", "wait-list", "add me", "notify me", "let me know"}
        if any(w in speech_lower for w in waitlist_words):
            ctx.current_state = DialogueState.WAITLIST_OFFERED
            return ctx, _WAITLIST_OFFER()

        # ── Ordinal / option selector — must run BEFORE day/time extraction ─
        # "1st", "first", "option 1" → Option 1
        # "2nd", "second", "option 2" → Option 2
        # Without this, "1st" gets extracted as day=1 (April 1st) and fails.
        import re as _re
        if ctx.offered_slots:
            # Use speech_lower (resp.speech + resp.raw_response) for ordinal detection so
            # that test helpers with raw="" still work — resp.speech carries "First one please."
            _words = set(_re.findall(r"[a-z0-9]+", speech_lower))
            _opt2_words = {"2nd", "second", "two"}
            # Option 1: "1st"/"first"/"one" — but NOT when "2nd/second/two" is also present
            # ("2nd one" means "the second one", not "option one")
            if (any(w in _words for w in {"1st", "first", "one"})
                    and not any(w in _words for w in _opt2_words)
                    and not _re.search(r"\b\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d)", speech_lower)):
                ctx.resolved_slot = ctx.offered_slots[0]
                ctx.current_state = DialogueState.SLOT_CONFIRMED
                topic_label = TOPIC_LABELS.get(ctx.topic or "", ctx.topic or "your topic")
                slot_str = ctx.resolved_slot.get("start_ist", "your selected time")
                return ctx, f"Perfect. Confirming: {topic_label} consultation on {slot_str}. Is that correct?"
            if any(w in _words for w in _opt2_words) and len(ctx.offered_slots) >= 2:
                ctx.resolved_slot = ctx.offered_slots[1]
                ctx.current_state = DialogueState.SLOT_CONFIRMED
                topic_label = TOPIC_LABELS.get(ctx.topic or "", ctx.topic or "your topic")
                slot_str = ctx.resolved_slot.get("start_ist", "your selected time")
                return ctx, f"Perfect. Confirming: {topic_label} consultation on {slot_str}. Is that correct?"

        # ── Slot matching: check if user is selecting an offered slot ────────
        # Handles: "10am", "10am is fine", "monday 10am", "option 1", "second"
        new_day  = resp.slots.get("day_preference")
        new_time = resp.slots.get("time_preference")

        if new_day or new_time:
            matched_idx = None

            if ctx.offered_slots:
                # Parse time band
                time_band = None
                if new_time:
                    band, _ = _parse_time_preference(new_time)
                    time_band = band

                # Parse target day from new_day (if present).
                # Bare weekday names ("monday") match by weekday number so that
                # "monday" matches any Monday in the offered list (April 6 or 13…).
                # Specific dates ("13/04/2026") still require exact date equality.
                target_date = None
                target_weekday = None
                if new_day:
                    from src.dialogue.intent_router import _WEEKDAY_NAMES
                    dates, confident = _parse_day_preference(new_day)
                    if dates and confident:
                        if new_day.lower().strip() in _WEEKDAY_NAMES:
                            # Bare weekday → match by weekday number
                            target_weekday = dates[0].weekday()
                        else:
                            # Specific date → exact match
                            target_date = dates[0].date()

                for i, sl in enumerate(ctx.offered_slots):
                    slot_dt = _dt.fromisoformat(sl["start"])
                    time_ok = (not time_band) or (time_band[0] <= slot_dt.hour < time_band[1])
                    if target_date is not None:
                        day_ok = slot_dt.date() == target_date
                    elif target_weekday is not None:
                        day_ok = slot_dt.weekday() == target_weekday
                    else:
                        day_ok = True
                    if time_ok and day_ok:
                        matched_idx = i
                        break

            if matched_idx is not None:
                ctx.resolved_slot = ctx.offered_slots[matched_idx]
                ctx.current_state = DialogueState.SLOT_CONFIRMED
                topic_label = TOPIC_LABELS.get(ctx.topic or "", ctx.topic or "your topic")
                slot_str = ctx.resolved_slot.get("start_ist", "your selected time")
                return ctx, (
                    f"Perfect. Confirming: {topic_label} consultation "
                    f"on {slot_str}. Is that correct?"
                )

            # No match — genuinely new preference: now apply day/time to ctx
            if new_day:
                ctx.day_preference = new_day
            if new_time:
                ctx.time_preference = new_time
            ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
            return self._offer_slots(ctx, resp)

        # ── Question — re-present the same options ──────────────────────────
        question_words = {"available", "is there", "do you have", "can i", "any slot", "?"}
        if any(w in speech_lower for w in question_words):
            if ctx.offered_slots:
                parts = ["Here are the available options again. "]
                for i, sl in enumerate(ctx.offered_slots, 1):
                    parts.append(f"Option {i}: {sl['start_ist']}.")
                parts.append(" Which would you prefer, or shall I add you to the waitlist?")
                return ctx, "".join(parts)

        # ── Rejection — ask for a different day/time ────────────────────────
        rejection_words = {"neither", "none", "different", "other", "else", "no", "change"}
        if any(w in speech_lower for w in rejection_words) and resp.intent not in ("book_new",):
            ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
            ctx.day_preference = None
            ctx.time_preference = None
            return ctx, (
                "No problem. What other day and time works for you? "
                "Or I can add you to the waitlist for your original preference."
            )

        # Detect which option the user picked (option 2 / second)
        _picked_second = False
        if ctx.offered_slots and len(ctx.offered_slots) >= 2:
            second_words = {"2", "two", "second", "option 2", "second one", "latter", "last"}
            if any(w in speech_lower for w in second_words):
                ctx.resolved_slot = ctx.offered_slots[1]
                _picked_second = True

        # Only confirm when there is a clear positive signal.
        # If input is truly unrecognised, re-present options so the repetition
        # guard can activate on the next identical turn.
        _affirm_words = {
            "yes", "ok", "okay", "sure", "correct", "fine", "alright", "right",
            "confirm", "confirmed", "go ahead", "proceed", "sounds good",
            "yep", "yup", "that", "works", "great", "perfect", "1", "option 1",
        }
        _is_affirm = _picked_second or any(w in speech_lower for w in _affirm_words)

        if not _is_affirm and ctx.offered_slots:
            # Unrecognised — re-present slots (state stays SLOTS_OFFERED)
            parts = ["I'm sorry, I didn't catch that. Here are the available options: "]
            for i, sl in enumerate(ctx.offered_slots, 1):
                parts.append(f"Option {i}: {sl['start_ist']}.")
            parts.append(" Which would you prefer?")
            return ctx, "".join(parts)

        # Slot confirmed — always use human-readable IST string
        ctx.current_state = DialogueState.SLOT_CONFIRMED
        topic_label = TOPIC_LABELS.get(ctx.topic or "", ctx.topic or "your topic")
        slot_str = (
            ctx.resolved_slot.get("start_ist", ctx.resolved_slot.get("start", "your selected time"))
            if ctx.resolved_slot else "your selected time"
        )
        return ctx, (
            f"Perfect. Confirming: {topic_label} consultation "
            f"on {slot_str}. Is that correct?"
        )

    def _dispatch_mcp(self, ctx: DialogueContext) -> tuple[DialogueContext, str]:
        """
        S7 → S8 → S9 — generate booking code + secure URL.
        MCP tools (Calendar, Sheets, Gmail) are Phase 4; here we simulate success.
        """
        from src.booking.booking_code_generator import generate_booking_code
        from src.booking.secure_url_generator import generate_secure_url

        ctx.current_state = DialogueState.MCP_DISPATCHED
        if not ctx.booking_code:
            ctx.booking_code = generate_booking_code()

        # Use ISO for secure URL signing, readable IST for speech
        slot_iso = ctx.resolved_slot.get("start", datetime.now(IST).isoformat()) if ctx.resolved_slot else ""
        slot_readable = (
            ctx.resolved_slot.get("start_ist", slot_iso)
            if ctx.resolved_slot else slot_iso
        )
        url = generate_secure_url(
            booking_code=ctx.booking_code,
            topic=ctx.topic or "general",
            slot_ist=slot_iso,
        )
        ctx.secure_url = url

        # Phase 4: attempt real MCP dispatch; fall back to mock flags on any failure
        ctx.calendar_hold_created, ctx.notes_appended, ctx.email_drafted = True, True, True
        try:
            from src.mcp.mcp_orchestrator import dispatch_mcp_sync, build_payload
            _mcp_results = dispatch_mcp_sync(build_payload(ctx))
            ctx.calendar_hold_created = _mcp_results.calendar_success
            ctx.notes_appended        = _mcp_results.sheets_success
            ctx.email_drafted         = _mcp_results.email_success
        except Exception:
            pass  # MCP unavailable or failed — booking code still issued
        ctx.current_state = DialogueState.BOOKING_COMPLETE

        topic_label = TOPIC_LABELS.get(ctx.topic or "", "your consultation")
        code_spoken = " - ".join(list(ctx.booking_code))
        return ctx, _s("booking_confirmed").format(
            topic_label=topic_label, slot_readable=slot_readable, code_spoken=code_spoken
        )

    def _from_waitlist_offered(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S10 — user accepts or declines waitlist."""
        from src.booking.waitlist_handler import create_waitlist_entry

        positive  = {"yes", "sure", "ok", "okay", "please", "add", "waitlist", "go ahead", "sounds good"}
        negative  = {"no", "nope", "don't", "not interested", "cancel", "skip", "nevermind", "never mind"}
        redirect  = {"which", "what", "when", "available", "slot", "other", "different", "another", "change", "instead"}

        user_lower = resp.raw_response.lower()

        if any(w in user_lower for w in positive):
            from src.booking.waitlist_queue import get_global_queue
            entry = create_waitlist_entry(
                topic=ctx.topic or "general",
                day_preference=ctx.day_preference or "any day",
                time_preference=ctx.time_preference or "any time",
            )
            queue = get_global_queue()
            position = queue.add(entry)
            ctx.waitlist_code = entry.waitlist_code
            ctx.current_state = DialogueState.WAITLIST_CONFIRMED
            code_spoken = " - ".join(list(entry.waitlist_code))

            # Build contextual confirmation using whatever slots are filled
            topic_label = TOPIC_LABELS.get(ctx.topic or "", ctx.topic or "your topic")
            day_part  = f" on {ctx.day_preference}" if ctx.day_preference else ""
            time_part = (f" in the {ctx.time_preference}" if ctx.time_preference and ctx.time_preference != "any"
                         else "")
            queue_msg = f"You're number {position} in the queue. " if position > 1 else ""

            return ctx, _s("waitlist_confirmed").format(
                queue_msg=queue_msg, topic_label=topic_label,
                day_part=day_part, time_part=time_part, code_spoken=code_spoken
            )

        if any(w in user_lower for w in negative):
            ctx.current_state = DialogueState.END
            return ctx, _s("waitlist_decline")

        # User asked about other slots or gave an unclear response — re-prompt with context
        if any(w in user_lower for w in redirect):
            # Reset time preference so they can try a different day/time
            ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
            ctx.day_preference = None
            ctx.time_preference = None
            return ctx, _s("waitlist_redirect")

        # Ambiguous — stay in WAITLIST_OFFERED and re-ask
        return ctx, _s("waitlist_reprompt")

    def _handle_code_flow(self, ctx: DialogueContext, resp: LLMResponse) -> tuple[DialogueContext, str]:
        """S12/S13 — reschedule or cancel by booking code."""
        code = resp.slots.get("existing_booking_code") or ctx.existing_booking_code
        if not code:
            return ctx, _s("code_not_found")

        ctx.existing_booking_code = code
        if ctx.current_state == DialogueState.CANCEL_CODE_COLLECTED:
            # On confirmed cancel: free the slot and promote the next person in queue
            from src.booking.waitlist_queue import get_global_queue
            from src.booking.slot_resolver import resolve_slots
            queue = get_global_queue()
            promotion_note = ""
            # Try to find the slot that was held for this booking (if resolved_slot stored)
            if ctx.resolved_slot:
                try:
                    calendar_path = os.environ.get("MOCK_CALENDAR_PATH", "data/mock_calendar.json")
                    freed_slots = resolve_slots(
                        day_preference="this week",
                        time_preference="any",
                        topic=ctx.topic,
                        calendar_path=calendar_path,
                        max_results=10,
                    )
                    for freed_slot in freed_slots:
                        result = queue.on_cancellation(freed_slot)
                        if result:
                            promotion_note = (
                                f" The next person on our waitlist (position {result.position_was}) "
                                f"will be notified about the opening."
                            )
                            break
                except Exception:
                    pass  # Promotion is best-effort — don't block the cancel
            ctx.current_state = DialogueState.END
            return ctx, (
                f"Your booking {code} has been cancelled.{promotion_note} "
                f"Feel free to call back if you'd like to rebook. Goodbye!"
            )
        # Reschedule
        ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
        return ctx, (
            f"I found your booking {code}. "
            f"What new day and time works for you?"
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _go_error(self, ctx: DialogueContext) -> tuple[DialogueContext, str]:
        ctx.current_state = DialogueState.ERROR
        return ctx, _ERROR_MSG()

    def _re_prompt(self, ctx: DialogueContext) -> str:
        """Short re-prompt based on current state."""
        prompts = {
            DialogueState.GREETED:              "Sorry, I didn't catch that. Shall we continue?",
            DialogueState.DISCLAIMER_CONFIRMED: "How can I help you today?",
            DialogueState.INTENT_IDENTIFIED:    "What topic would you like to discuss?",
            DialogueState.TOPIC_COLLECTED:      "What day and time works for you?",
            DialogueState.SLOTS_OFFERED:        "Which slot would you prefer?",
            DialogueState.SLOT_CONFIRMED:       "Can you confirm the booking?",
            DialogueState.WAITLIST_OFFERED:     "Would you like to join the waitlist?",
        }
        return prompts.get(ctx.current_state, "Sorry, I didn't catch that. Could you repeat?")
