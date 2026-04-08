"""
src/dialogue/intent_router.py

Intent Router — Layer 2 of the dialogue pipeline.

Sends the user's (already PII-scrubbed) input + dialogue context to an LLM
and parses back a structured LLMResponse.

Priority:
  1. Groq (llama-3.3-70b-versatile) — fast, free tier
  2. Anthropic claude-haiku — fallback if Groq fails
  3. Rule-based offline mode — used in tests / when both APIs are unavailable

The LLM callable is injected via the constructor so tests can pass a mock.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable, Optional

from .states import (
    DialogueContext,
    LLMResponse,
    VALID_INTENTS,
    VALID_TOPICS,
    TOPIC_LABELS,
)

logger = logging.getLogger(__name__)

# ─── System prompt template ───────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an intent-extraction engine for a voice-based advisor appointment scheduler.

Your ONLY job is to classify the user's intent and extract slot values. You must NEVER give investment advice.

VALID INTENTS:
- book_new            : user wants to book a new appointment
- reschedule          : user wants to reschedule an existing booking
- cancel              : user wants to cancel an existing booking
- what_to_prepare     : user asks what to bring / prepare for a meeting
- check_availability  : user asks about available time slots
- refuse_advice       : user is asking for investment advice or market predictions (must be refused)
- refuse_pii          : user has shared personal information (phone/email/ID/account number/DOB/SSN)
- timezone_query      : user asks what IST maps to in their local timezone or timezone conversion
- out_of_scope        : anything else not related to scheduling
- end_call            : user wants to stop, leave, not proceed, or end the conversation

VALID TOPICS (only for book_new, reschedule, what_to_prepare):
- kyc_onboarding      : KYC, onboarding, account opening, identity verification, fund transfer setup
- sip_mandates        : SIP, auto-debit, mandate, systematic investment plan
- statements_tax      : statement, tax document, capital gains, Form 26AS, ELSS, visa letter
- withdrawals         : withdraw, redeem, payout, exit, close account, pension, money out
- account_changes     : nominee, bank change, address update, joint account, beneficiary, moving abroad

SLOTS to extract (include only when present):
- topic              : one of the valid topics above
- day_preference     : e.g. "Monday", "tomorrow", "next week", "this week",
                       "6th", "10th April", "April 10", "6/4/2026", "weekend"
- time_preference    : e.g. "morning", "afternoon", "3pm", "10:30am", "14:00",
                       "2 PM", "any time", "anytime", "flexible"
- existing_booking_code : alphanumeric code from user (for reschedule/cancel)

Respond ONLY with valid JSON in this exact format:
{
  "intent": "<intent>",
  "slots": {
    "topic": "<topic or omit>",
    "day_preference": "<day or omit>",
    "time_preference": "<time or omit>",
    "existing_booking_code": "<code or omit>"
  },
  "speech": "<one short sentence acknowledgement, NO advice>",
  "compliance_flag": null
}

If intent is refuse_advice, set compliance_flag to "refuse_advice".
If intent is refuse_pii, set compliance_flag to "refuse_pii".
If intent is out_of_scope, set compliance_flag to "out_of_scope".
Otherwise compliance_flag must be null.
"""


def _build_user_message(user_input: str, ctx: DialogueContext) -> str:
    """Build the user message including current context summary."""
    filled = ctx.slots_filled()
    context_lines = [f"Current state: {ctx.current_state.name}"]
    if filled:
        context_lines.append(f"Slots already filled: {json.dumps(filled)}")
    if ctx.intent:
        context_lines.append(f"Current intent: {ctx.intent}")
    context_summary = "\n".join(context_lines)
    return f"[Context]\n{context_summary}\n\n[User said]\n{user_input}"


# ─── Rule-based offline fallback ─────────────────────────────────────────────

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "kyc_onboarding":  ["kyc", "onboard", "know your customer", "verification",
                        "transfer fund", "fund transfer", "open account", "new account"],
    "sip_mandates":    ["sip", "mandate", "systematic", "monthly investment",
                        "auto-debit", "auto debit"],
    "statements_tax":  ["statement", "tax", "document", "form", "download",
                        "capital gain", "26as", "elss", "80c", "visa letter",
                        "investment summary"],
    "withdrawals":     ["withdraw", "redemption", "redeem", "payout", "money out",
                        "pension", "close account", "close my account", "exit"],
    "account_changes": ["nominee", "account change", "update", "address", "bank",
                        "joint account", "beneficiary", "abroad", "mobile update",
                        "bank mandate", "moving to another state"],
}

_WEEKDAY_NAMES = [
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
]

_MONTH_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# Pre-compiled regex for date extraction (reused across calls)
_DATE_REGEX = re.compile(
    rf"({_MONTH_PATTERN}\s*\d{{1,2}}(?:st|nd|rd|th)?|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s*{_MONTH_PATTERN}|"
    rf"\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?)",
    re.IGNORECASE,
)
_ORDINAL_REGEX = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_SPECIFIC_TIME_REGEX = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b"
    r"|\b([01]?\d|2[0-3]):([0-5]\d)\b",
    re.IGNORECASE,
)


def _extract_day_preference(low: str) -> str | None:
    """
    Extract a day/date preference from lowercased user input.

    Priority:
        1. Multi-word relative phrases ("this week", "next week", "weekend")
        2. "today" / "tomorrow"
        3. "next <weekday>" (e.g. "next monday")
        4. Month+day or day+month (e.g. "april 10th", "10 april", "6/4")
        5. Ordinal alone (e.g. "6th", "10th")
        6. Bare weekday name (e.g. "monday")
    """
    # 1. Multi-word relative phrases (order matters: "next week" before bare "week")
    for phrase in ("next week", "this week", "next month", "weekend"):
        if phrase in low:
            return phrase

    # 2. today / tomorrow / day after tomorrow
    if "today" in low:
        return "today"
    if "day after tomorrow" in low or "overmorrow" in low:
        return "day after tomorrow"
    if "tomorrow" in low:
        return "tomorrow"

    # 3. "next <weekday>"
    for day in _WEEKDAY_NAMES:
        if f"next {day}" in low:
            return f"next {day}"

    # 4. Month+day patterns ("april 10th", "10 april", "6/4/2026")
    m = _DATE_REGEX.search(low)
    if m:
        return m.group(0).strip()

    # 5. Ordinal alone ("6th", "10th")
    m = _ORDINAL_REGEX.search(low)
    if m:
        return m.group(0)

    # 6. Bare weekday name
    for day in _WEEKDAY_NAMES:
        if re.search(rf"\b{day}\b", low):
            return day

    return None


def _extract_time_preference(low: str) -> str | None:
    """
    Extract a time preference from lowercased user input.

    Priority:
        1. "any time" / "anytime" / "flexible"
        2. Specific time with am/pm ("3pm", "10:30am")
        3. 24-hour time ("14:00", "09:30")
        4. Named band ("morning", "afternoon", "evening")
    """
    # 1. Open / flexible
    if any(w in low for w in ("any time", "anytime", "any slot", "flexible", "any")):
        return "any"

    # 2 & 3. Specific numeric time
    m = _SPECIFIC_TIME_REGEX.search(low)
    if m:
        return m.group(0).strip()

    # 4. Named bands (longest match first to avoid "noon" ⊂ "afternoon")
    for band in ("late afternoon", "early morning", "afternoon", "morning", "evening", "noon", "midday"):
        if band in low:
            return band

    return None


def _rule_based_parse(user_input: str, ctx: DialogueContext) -> LLMResponse:
    """
    Minimal rule-based parser used when LLM is unavailable.
    Errs on the side of booking intent and returns a plausible response.
    """
    low = user_input.lower()

    # Compliance flags first
    advice_words = ["invest", "stock", "return", "nifty", "sensex", "mutual fund",
                    "portfolio", "buy", "sell", "recommend", "crypto", "real estate",
                    "market crash", "market prediction", "gold", "apple stock"]
    if any(w in low for w in advice_words):
        return LLMResponse(
            intent="refuse_advice",
            compliance_flag="refuse_advice",
            speech="I can't provide investment advice.",
            raw_response=user_input,
        )

    # End-call detection — before timezone (avoids "est" ⊂ "interested" false positive)
    end_words = [
        "leave", "bye", "goodbye", "don't want to book", "dont want to book",
        "don't want to go ahead", "dont want to go ahead", "not interested",
        "no thanks", "no thank you", "forget it", "never mind", "nevermind",
        "i'm done", "i am done", "that's all", "thats all",
        "i'll pass", "ill pass", "not now", "maybe later",
        "don't want to proceed", "dont want to proceed",
        "don't want to continue", "dont want to continue",
    ]
    if any(w in low for w in end_words):
        return LLMResponse(
            intent="end_call",
            slots={},
            speech="Thank you for calling. We'll be happy to help whenever you're ready!",
            raw_response=user_input,
        )

    # Timezone query — use word boundaries for short abbreviations to avoid false positives
    timezone_words_plain = ["timezone", "time zone", "convert", "new york", "london",
                            "california", "dubai", "sydney", "japan", "berlin",
                            "what time is", "local time"]
    timezone_abbrevs = ["ist", "gmt", "est", "pst", "bst"]  # checked with word boundary
    if (any(w in low for w in timezone_words_plain) or
            any(re.search(rf"\b{abbr}\b", low) for abbr in timezone_abbrevs)):
        return LLMResponse(
            intent="timezone_query",
            slots={},
            speech="All our slots are in IST (India Standard Time, UTC+5:30). Please use a timezone converter for your local equivalent.",
            raw_response=user_input,
        )

    # Intent detection
    intent = "book_new"  # default
    if any(w in low for w in ["reschedule", "change my appointment", "move my booking", "shift", "move nl-"]):
        intent = "reschedule"
    elif any(w in low for w in ["cancel", "delete my booking", "abort", "drop my", "i won't be able"]):
        intent = "cancel"
    elif any(w in low for w in ["what to bring", "what to prepare", "what do i need", "documents", "do i need"]):
        intent = "what_to_prepare"
    elif any(w in low for w in ["available", "availability", "when can i", "free slot"]):
        intent = "check_availability"

    # Slot extraction
    slots: dict = {}

    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(k in low for k in keywords):
            slots["topic"] = topic
            break

    day = _extract_day_preference(low)
    if day:
        slots["day_preference"] = day

    time_pref = _extract_time_preference(low)
    if time_pref:
        slots["time_preference"] = time_pref

    # Booking code
    code_match = re.search(r"\bNL-[A-Z0-9]{4}\b", user_input.upper())
    if code_match:
        slots["existing_booking_code"] = code_match.group(0)

    speech = "Got it, let me help you with that."
    return LLMResponse(
        intent=intent,
        slots=slots,
        speech=speech,
        compliance_flag=None,
        raw_response=user_input,
    )


# ─── LLM response parser ─────────────────────────────────────────────────────

def _parse_llm_json(raw: str, user_input: str) -> LLMResponse:
    """Extract JSON from LLM output and build LLMResponse."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", raw).strip()
    # Find first JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in LLM output")

    data = json.loads(m.group(0))
    intent = data.get("intent", "book_new")
    if intent not in VALID_INTENTS:
        intent = "book_new"

    raw_slots = data.get("slots", {})
    slots: dict = {}
    if raw_slots.get("topic") in VALID_TOPICS:
        slots["topic"] = raw_slots["topic"]
    for key in ("day_preference", "time_preference", "existing_booking_code"):
        if raw_slots.get(key):
            slots[key] = raw_slots[key]

    flag = data.get("compliance_flag")
    if flag not in (None, "refuse_advice", "refuse_pii", "out_of_scope"):
        flag = None

    speech = data.get("speech", "Got it.")
    if not speech:
        speech = "Got it."

    return LLMResponse(
        intent=intent,
        slots=slots,
        speech=speech,
        compliance_flag=flag,
        raw_response=raw,
    )


# ─── IntentRouter ─────────────────────────────────────────────────────────────

LLMCallable = Callable[[str, str], str]  # (system_prompt, user_message) -> raw_text


def _make_groq_callable() -> Optional[LLMCallable]:
    """Return a Groq callable if the API key is set, else None."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=api_key)

        def _call(system: str, user: str) -> str:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=512,
            )
            return resp.choices[0].message.content or ""

        return _call
    except Exception as exc:
        logger.warning("Groq setup failed: %s", exc)
        return None


def _make_anthropic_callable() -> Optional[LLMCallable]:
    """Return an Anthropic callable if the API key is set, else None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=api_key)

        def _call(system: str, user: str) -> str:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text if msg.content else ""

        return _call
    except Exception as exc:
        logger.warning("Anthropic setup failed: %s", exc)
        return None


class IntentRouter:
    """
    Routes PII-scrubbed user input to an LLM and returns a structured LLMResponse.

    Usage:
        router = IntentRouter()                     # auto-detect APIs
        router = IntentRouter(llm_callable=mock_fn) # inject for testing
        response = router.route(user_input, ctx)
    """

    def __init__(self, llm_callable: Optional[LLMCallable] = None) -> None:
        if llm_callable is not None:
            self._llm: Optional[LLMCallable] = llm_callable
        else:
            # Try Groq first, then Anthropic
            self._llm = _make_groq_callable() or _make_anthropic_callable()
            if self._llm is None:
                logger.warning(
                    "No LLM API keys found (GROQ_API_KEY / ANTHROPIC_API_KEY). "
                    "Using rule-based offline mode."
                )

    @property
    def is_online(self) -> bool:
        return self._llm is not None

    def route(self, user_input: str, ctx: DialogueContext) -> LLMResponse:
        """
        Classify intent and extract slots for the given user input.

        Falls back to rule-based parsing if LLM is unavailable or fails.
        """
        if not self._llm:
            return _rule_based_parse(user_input, ctx)

        system_prompt = _SYSTEM_PROMPT
        # If Hindi is selected, instruct LLM to reply in Hindi
        lang = os.environ.get("TTS_LANGUAGE", "en-IN")
        if lang == "hi-IN":
            system_prompt = system_prompt + (
                "\n\nIMPORTANT: The user is speaking Hindi. "
                "The \"speech\" field in your JSON response MUST be in Hindi (Devanagari script). "
                "All acknowledgements, questions, and responses must be in Hindi."
            )
        user_message = _build_user_message(user_input, ctx)

        try:
            raw = self._llm(system_prompt, user_message)
            result = _parse_llm_json(raw, user_input)
            return result
        except Exception as exc:
            logger.error("LLM call failed, using rule-based fallback: %s", exc)
            return _rule_based_parse(user_input, ctx)
