"""
data/training_set.py

Runs all dialogue flows end-to-end and prints a formatted transcript.
Used for manual review, LLM fine-tuning data generation, and QA.

Flows are derived from:
  - Original 12 FSM flows (Phase 2 design)
  - LLM Training Data: Advisor Appointment Scenarios.xlsx (144 examples)

Usage:
    python3 phase2/data/training_set.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFERENCE TRANSCRIPT — Happy Path, Pick Option 2
This is the canonical baseline for agent tone, slot order, and phrasing.
All other flows must be consistent with this transcript.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Agent: Hello! I'm the Advisor Scheduling assistant. I'll help you book a
       consultation in about two minutes. Quick note: this service is for
       scheduling only. Our advisors provide informational guidance, not
       investment advice. Shall we continue?

User:  yes sure

Agent: Great. What topic would you like to discuss? I can help with: KYC and
       onboarding, SIP and mandates, statements and tax documents, withdrawals
       and timelines, or account changes and nominee updates.

User:  I want to book an appointment for KYC and onboarding

Agent: What day and time works best for you this week or next?

User:  Monday afternoon

Agent: I found 2 slots on Monday at afternoon.
       Option 1: Monday, 06/04/2026 at 02:00 PM IST.
       Option 2: Monday, 06/04/2026 at 03:30 PM IST.
       Which would you prefer, or shall I add you to the waitlist?

User:  Option 2 please

Agent: Perfect. Confirming: KYC and Onboarding consultation on
       Monday, 06/04/2026 at 03:30 PM IST. Is that correct?

User:  yes that is correct

Agent: Your booking is confirmed. KYC and Onboarding on
       Monday, 06/04/2026 at 03:30 PM IST. Your booking code is NL-U9YA.
       Please note it down. You'll receive a secure link to submit your
       contact details. Thank you for calling!

User:  thank you

Agent: Thank you for calling. Have a great day!

6 turns — disclaimer → topic → day/time → 2 slots offered →
user picks option 2 → confirm → booked → farewell.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys

# Resolve voice-agents/ root and add phase0, phase1, phase2 to sys.path
_phase2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # voice-agents/phase2/
_root = os.path.dirname(_phase2)                                         # voice-agents/
for _p in ["phase0", "phase1", "phase2"]:
    _path = os.path.join(_root, _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    os.path.join(_root, "phase1", "data", "mock_calendar.json"),
)

from src.dialogue.fsm import DialogueFSM
from src.dialogue.states import LLMResponse


def run_flow(title: str, steps: list[tuple[str, str, dict]]) -> None:
    print()
    print("=" * 70)
    print(f"  FLOW: {title}")
    print("=" * 70)
    fsm = DialogueFSM()
    ctx, greeting = fsm.start()
    print(f"Agent: {greeting}")
    print()
    for user_text, intent, slots in steps:
        compliance_flag = slots.pop("compliance_flag", None)
        print(f"User:  {user_text}")
        resp = LLMResponse(
            intent=intent,
            slots=slots,
            speech=user_text,
            raw_response=user_text,
            compliance_flag=compliance_flag,
        )
        ctx, speech = fsm.process_turn(ctx, user_text, resp)
        print(f"Agent: {speech}")
        print(f"       [{ctx.current_state.name}]")
        print()
        if ctx.current_state.is_terminal():
            break


# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — ORIGINAL FSM FLOWS (Core path coverage)
# ══════════════════════════════════════════════════════════════════════════════

# ── FLOW A1: Happy path — pick option 1 ───────────────────────────────────────
run_flow("A1. HAPPY PATH — Book new, pick option 1", [
    ("yes", "book_new", {}),
    ("SIP mandates", "book_new", {"topic": "sip_mandates"}),
    ("Monday morning", "book_new", {"day_preference": "Monday", "time_preference": "morning"}),
    ("first one", "book_new", {}),
    ("yes confirmed", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW A2: Requested time not available — fallback slots ────────────────────
run_flow("A2. REQUESTED TIME NOT AVAILABLE — Fallback slots offered, user picks one", [
    ("yes", "book_new", {}),
    ("withdrawals", "book_new", {"topic": "withdrawals"}),
    ("tomorrow 4pm", "book_new", {"day_preference": "tomorrow", "time_preference": "4pm"}),
    ("option 2", "book_new", {}),
    ("yes", "book_new", {}),
    ("bye", "book_new", {}),
])

# ── FLOW A3: User changes preference mid-way ─────────────────────────────────
run_flow("A3. USER CHANGES PREFERENCE — Says new day/time while slots are shown", [
    ("yes", "book_new", {}),
    ("KYC", "book_new", {"topic": "kyc_onboarding"}),
    ("Monday afternoon", "book_new", {"day_preference": "Monday", "time_preference": "afternoon"}),
    ("actually Tuesday morning", "book_new", {"day_preference": "Tuesday", "time_preference": "morning"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("ok", "book_new", {}),
])

# ── FLOW A4: User asks a question about availability ─────────────────────────
run_flow("A4. USER ASKS QUESTION — \"Is Thursday available?\" while slots are shown", [
    ("yes", "book_new", {}),
    ("statements and tax", "book_new", {"topic": "statements_tax"}),
    ("Wednesday 10am", "book_new", {"day_preference": "Wednesday", "time_preference": "10am"}),
    ("is Thursday available?", "book_new", {"day_preference": "Thursday", "time_preference": "any"}),
    ("second option", "book_new", {}),
    ("yes correct", "book_new", {}),
    ("thank you", "book_new", {}),
])

# ── FLOW A5: User joins waitlist ──────────────────────────────────────────────
run_flow("A5. WAITLIST PATH — No suitable slot, user joins waitlist", [
    ("yes", "book_new", {}),
    ("account changes", "book_new", {"topic": "account_changes"}),
    ("tomorrow 4pm", "book_new", {"day_preference": "tomorrow", "time_preference": "4pm"}),
    ("add me to waitlist", "book_new", {}),
    ("yes please add me", "book_new", {}),
])

# ── FLOW A6: User declines waitlist ──────────────────────────────────────────
run_flow("A6. DECLINE WAITLIST — User says no to waitlist and ends call", [
    ("yes", "book_new", {}),
    ("SIP", "book_new", {"topic": "sip_mandates"}),
    ("tomorrow 4pm", "book_new", {"day_preference": "tomorrow", "time_preference": "4pm"}),
    ("add me to waitlist", "book_new", {}),
    ("no thanks", "book_new", {}),
])

# ── FLOW A7: Reschedule ───────────────────────────────────────────────────────
run_flow("A7. RESCHEDULE — User wants to move an existing booking", [
    ("yes", "reschedule", {}),
    ("reschedule my appointment", "reschedule", {}),
    ("NL-AB2C", "reschedule", {"existing_booking_code": "NL-AB2C"}),
    ("Tuesday morning", "book_new", {"day_preference": "Tuesday", "time_preference": "morning"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW A8: Cancel ───────────────────────────────────────────────────────────
run_flow("A8. CANCEL — User cancels an existing booking", [
    ("yes", "cancel", {}),
    ("I want to cancel my booking", "cancel", {}),
    ("NL-XY9Z", "cancel", {"existing_booking_code": "NL-XY9Z"}),
])

# ── FLOW A9: Compliance — investment advice refused ───────────────────────────
run_flow("A9. COMPLIANCE REFUSAL — User asks for investment advice, then books", [
    ("yes", "book_new", {}),
    ("should I invest in mutual funds?", "book_new", {"compliance_flag": "refuse_advice"}),
    ("ok, I want to book KYC", "book_new", {"topic": "kyc_onboarding"}),
    ("Monday morning", "book_new", {"day_preference": "Monday", "time_preference": "morning"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW A10: Out-of-scope question ──────────────────────────────────────────
run_flow("A10. OUT OF SCOPE — User asks unrelated question, then books", [
    ("yes", "book_new", {}),
    ("what is the weather today?", "out_of_scope", {"compliance_flag": "out_of_scope"}),
    ("ok book KYC Monday morning", "book_new", {
        "topic": "kyc_onboarding", "day_preference": "Monday", "time_preference": "morning"
    }),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW A11: Silence / no-input — 3 silences triggers error ─────────────────
run_flow("A11. SILENCE / NO INPUT — 3 silences trigger error and farewell", [
    ("yes", "book_new", {}),
    ("", "book_new", {}),
    ("", "book_new", {}),
    ("", "book_new", {}),
    ("", "book_new", {}),
])

# ── FLOW A12: Happy path — pick option 2 ─────────────────────────────────────
# Executable version of the reference transcript in the module docstring above.

run_flow("A12. HAPPY PATH — Book new, pick option 2 (reference transcript)", [
    ("yes sure", "book_new", {}),
    ("I want to book an appointment for KYC and onboarding", "book_new", {"topic": "kyc_onboarding"}),
    ("Monday afternoon", "book_new", {"day_preference": "Monday", "time_preference": "afternoon"}),
    ("Option 2 please", "book_new", {}),
    ("yes that is correct", "book_new", {}),
    ("thank you", "book_new", {}),
])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — EXCEL TRAINING DATA FLOWS (from LLM Training Scenarios.xlsx)
# ══════════════════════════════════════════════════════════════════════════════

# ── FLOW B1: New Booking — all 5 topics ──────────────────────────────────────
run_flow("B1. NEW BOOKING — All 5 topic variants (Excel rows 1-5, 16-20)", [
    ("yes", "book_new", {}),
    ("I need help with my KYC verification.", "book_new", {"topic": "kyc_onboarding"}),
    ("Monday 10am", "book_new", {"day_preference": "Monday", "time_preference": "10am"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B2. NEW BOOKING — SIP mandates", [
    ("yes", "book_new", {}),
    ("How do I start a new SIP?", "book_new", {"topic": "sip_mandates"}),
    ("Wednesday 9am", "book_new", {"day_preference": "Wednesday", "time_preference": "9am"}),
    ("first option", "book_new", {}),
    ("yes", "book_new", {}),
    ("ok", "book_new", {}),
])

run_flow("B3. NEW BOOKING — Withdrawals", [
    ("yes", "book_new", {}),
    ("I want to withdraw my investment.", "book_new", {"topic": "withdrawals"}),
    ("Thursday 3pm", "book_new", {"day_preference": "Thursday", "time_preference": "3pm"}),
    ("option 2", "book_new", {}),
    ("yes that's correct", "book_new", {}),
    ("bye", "book_new", {}),
])

run_flow("B4. NEW BOOKING — Account changes", [
    ("yes", "book_new", {}),
    ("Can I add a nominee to my account?", "book_new", {"topic": "account_changes"}),
    ("Monday 1pm", "book_new", {"day_preference": "Monday", "time_preference": "1pm"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thank you", "book_new", {}),
])

run_flow("B5. NEW BOOKING — Tax statements", [
    ("yes", "book_new", {}),
    ("I need my tax statements for last year.", "book_new", {"topic": "statements_tax"}),
    ("Wednesday 10am", "book_new", {"day_preference": "Wednesday", "time_preference": "10am"}),
    ("second", "book_new", {}),
    ("yes correct", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW B6: PII Block — mid-flow, then continues ────────────────────────────
run_flow("B6. PII BLOCK — Email shared mid-flow, then booking continues (Excel row 6)", [
    ("yes", "book_new", {}),
    ("My email is rahul@gmail.com, book me.", "refuse_pii", {"compliance_flag": "refuse_pii"}),
    ("ok fine, I want to book KYC", "book_new", {"topic": "kyc_onboarding"}),
    ("Monday 10am", "book_new", {"day_preference": "Monday", "time_preference": "10am"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B7. PII BLOCK — Phone number shared, then booking continues (Excel row 7)", [
    ("yes", "book_new", {}),
    ("My phone number is 9876543210.", "refuse_pii", {"compliance_flag": "refuse_pii"}),
    ("ok I want to book about withdrawals", "book_new", {"topic": "withdrawals"}),
    ("Tuesday afternoon", "book_new", {"day_preference": "Tuesday", "time_preference": "afternoon"}),
    ("option 2", "book_new", {}),
    ("yes", "book_new", {}),
    ("bye", "book_new", {}),
])

run_flow("B8. PII BLOCK — Account number shared (Excel row 38)", [
    ("yes", "book_new", {}),
    ("Here is my account number: 123456789", "refuse_pii", {"compliance_flag": "refuse_pii"}),
    ("sorry, book KYC for me", "book_new", {"topic": "kyc_onboarding"}),
    ("Friday 11am", "book_new", {"day_preference": "Friday", "time_preference": "11am"}),
    ("first one", "book_new", {}),
    ("yes", "book_new", {}),
    ("ok thanks", "book_new", {}),
])

# ── FLOW B9: Compliance — investment advice refused, then books ───────────────
run_flow("B9. COMPLIANCE — Mutual fund advice refused (Excel row 8)", [
    ("yes", "book_new", {}),
    ("Which mutual fund should I buy?", "refuse_advice", {"compliance_flag": "refuse_advice"}),
    ("ok book me for KYC Monday morning", "book_new", {
        "topic": "kyc_onboarding", "day_preference": "Monday", "time_preference": "morning"
    }),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B10. COMPLIANCE — Market crash prediction refused (Excel row 9)", [
    ("yes", "book_new", {}),
    ("Is the market going to crash today?", "refuse_advice", {"compliance_flag": "refuse_advice"}),
    ("I'd like to book about withdrawals then", "book_new", {"topic": "withdrawals"}),
    ("Thursday 2pm", "book_new", {"day_preference": "Thursday", "time_preference": "2pm"}),
    ("second option", "book_new", {}),
    ("yes", "book_new", {}),
    ("bye", "book_new", {}),
])

run_flow("B11. COMPLIANCE — Crypto advice refused (Excel row 52)", [
    ("yes", "book_new", {}),
    ("Which crypto should I buy?", "refuse_advice", {"compliance_flag": "refuse_advice"}),
    ("fine, book SIP meeting", "book_new", {"topic": "sip_mandates"}),
    ("Wednesday 11am", "book_new", {"day_preference": "Wednesday", "time_preference": "11am"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

# ── FLOW B12: Reschedule — various booking codes ──────────────────────────────
run_flow("B12. RESCHEDULE — Move to Friday (Excel row 10)", [
    ("yes", "reschedule", {}),
    ("Change my booking NL-A742 to Friday.", "reschedule", {"existing_booking_code": "NL-A742"}),
    ("NL-A742", "reschedule", {"existing_booking_code": "NL-A742"}),
    ("Friday 11am", "book_new", {"day_preference": "Friday", "time_preference": "11am"}),
    ("option 1", "book_new", {}),
    ("yes confirmed", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B13. RESCHEDULE — Move to tomorrow (Excel row 21)", [
    ("yes", "reschedule", {}),
    ("Can I move my appointment NL-A123 to tomorrow?", "reschedule", {"existing_booking_code": "NL-A123"}),
    ("NL-A123", "reschedule", {"existing_booking_code": "NL-A123"}),
    ("tomorrow morning", "book_new", {"day_preference": "tomorrow", "time_preference": "morning"}),
    ("first one", "book_new", {}),
    ("yes", "book_new", {}),
    ("ok", "book_new", {}),
])

# ── FLOW B14: Cancel — various styles ────────────────────────────────────────
run_flow("B14. CANCEL — Direct cancel with code (Excel row 11)", [
    ("yes", "cancel", {}),
    ("Cancel my appointment NL-B921.", "cancel", {"existing_booking_code": "NL-B921"}),
    ("NL-B921", "cancel", {"existing_booking_code": "NL-B921"}),
])

run_flow("B15. CANCEL — Informal phrasing (Excel row 78)", [
    ("yes", "cancel", {}),
    ("I won't be able to make NL-L456.", "cancel", {"existing_booking_code": "NL-L456"}),
    ("NL-L456", "cancel", {"existing_booking_code": "NL-L456"}),
])

# ── FLOW B16: What to Prepare ─────────────────────────────────────────────────
run_flow("B16. WHAT TO PREPARE — KYC documents (Excel row 66)", [
    ("yes", "what_to_prepare", {}),
    ("What documents do I need for KYC?", "what_to_prepare", {"topic": "kyc_onboarding"}),
    ("ok book KYC Monday 10am", "book_new", {
        "topic": "kyc_onboarding", "day_preference": "Monday", "time_preference": "10am"
    }),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B17. WHAT TO PREPARE — Withdrawal docs (Excel row 67)", [
    ("yes", "what_to_prepare", {}),
    ("Do I need anything for the withdrawal call?", "what_to_prepare", {"topic": "withdrawals"}),
    ("book me a slot Tuesday afternoon", "book_new", {
        "topic": "withdrawals", "day_preference": "Tuesday", "time_preference": "afternoon"
    }),
    ("second", "book_new", {}),
    ("yes", "book_new", {}),
    ("bye", "book_new", {}),
])

# ── FLOW B18: Waitlist — outside business hours ───────────────────────────────
run_flow("B18. WAITLIST — Requested Sunday 8 PM (closed), added to waitlist (Excel row 13)", [
    ("yes", "book_new", {}),
    ("I need a meeting this Sunday at 8 PM.", "book_new", {
        "day_preference": "Sunday", "time_preference": "8pm"
    }),
    ("add me to waitlist", "book_new", {}),
    ("yes please", "book_new", {}),
])

run_flow("B19. WAITLIST — Saturday request (Excel row 56)", [
    ("yes", "book_new", {}),
    ("I need a meeting on Saturday.", "book_new", {
        "day_preference": "Saturday", "time_preference": "any"
    }),
    ("waitlist is fine", "book_new", {}),
    ("yes add me", "book_new", {}),
])

run_flow("B20. WAITLIST — Midnight request (Excel row 57)", [
    ("yes", "book_new", {}),
    ("Are you open at midnight?", "book_new", {
        "day_preference": "today", "time_preference": "midnight"
    }),
    ("add me to the waitlist", "book_new", {}),
    ("yes", "book_new", {}),
])

# ── FLOW B21: Timezone query — stays in current state ────────────────────────
run_flow("B21. TIMEZONE QUERY — User asks timezone, then books (Excel row 14)", [
    ("yes", "book_new", {}),
    ("What time is 2 PM IST in New York?", "timezone_query", {}),
    ("ok Monday 10am then", "book_new", {
        "topic": "kyc_onboarding", "day_preference": "Monday", "time_preference": "10am"
    }),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B22. TIMEZONE QUERY — Is the meeting in my local time? (Excel row 72)", [
    ("yes", "book_new", {}),
    ("Is the meeting in my local time?", "timezone_query", {}),
    ("sure book SIP Wednesday morning", "book_new", {
        "topic": "sip_mandates", "day_preference": "Wednesday", "time_preference": "morning"
    }),
    ("second slot", "book_new", {}),
    ("yes confirmed", "book_new", {}),
    ("bye", "book_new", {}),
])

# ── FLOW B23: Edge cases — ambiguous topic mapping ───────────────────────────
run_flow("B23. EDGE CASE — Pension maps to withdrawals (Excel row 15)", [
    ("yes", "book_new", {}),
    ("I want to talk about my pension.", "book_new", {"topic": "withdrawals"}),
    ("Monday afternoon", "book_new", {"day_preference": "Monday", "time_preference": "afternoon"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B24. EDGE CASE — Joint account maps to account changes (Excel row 46)", [
    ("yes", "book_new", {}),
    ("I want to open a joint account with my wife.", "book_new", {"topic": "account_changes"}),
    ("Tuesday 2pm", "book_new", {"day_preference": "Tuesday", "time_preference": "2pm"}),
    ("first", "book_new", {}),
    ("yes correct", "book_new", {}),
    ("ok bye", "book_new", {}),
])

run_flow("B25. EDGE CASE — Visa letter maps to statements/tax (Excel row 90)", [
    ("yes", "book_new", {}),
    ("I need a letter for my visa.", "book_new", {"topic": "statements_tax"}),
    ("Friday 11am", "book_new", {"day_preference": "Friday", "time_preference": "11am"}),
    ("option 2", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])

run_flow("B26. EDGE CASE — Fund transfer maps to KYC (Excel row 47)", [
    ("yes", "book_new", {}),
    ("How do I transfer funds from another bank?", "book_new", {"topic": "kyc_onboarding"}),
    ("Wednesday 10am", "book_new", {"day_preference": "Wednesday", "time_preference": "10am"}),
    ("first one", "book_new", {}),
    ("yes", "book_new", {}),
    ("bye", "book_new", {}),
])

run_flow("B27. EDGE CASE — Beneficiary maps to account changes (Excel row 108)", [
    ("yes", "book_new", {}),
    ("I want to add a beneficiary.", "book_new", {"topic": "account_changes"}),
    ("Thursday 3pm", "book_new", {"day_preference": "Thursday", "time_preference": "3pm"}),
    ("option 1", "book_new", {}),
    ("yes", "book_new", {}),
    ("thank you", "book_new", {}),
])

run_flow("B28. EDGE CASE — Moving abroad maps to account changes (Excel row 50)", [
    ("yes", "book_new", {}),
    ("What happens to my account if I move abroad?", "book_new", {"topic": "account_changes"}),
    ("Monday 1pm", "book_new", {"day_preference": "Monday", "time_preference": "1pm"}),
    ("second option", "book_new", {}),
    ("yes", "book_new", {}),
    ("thanks", "book_new", {}),
])
