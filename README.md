# Voice Agent — Advisor Appointment Scheduler

A production-grade, compliance-first voice agent that books tentative advisor consultation slots.
Callers speak naturally; the agent collects topic + time preference, offers two real calendar slots,
confirms the booking, generates a booking code, and triggers Google Calendar / Sheets / Gmail via MCP.

---

## Live Demo

**Streamlit App:** [https://voice-agents-production-3f40.up.railway.app](https://voice-agents-production-3f40.up.railway.app)

**Bookings Sheet:** [Advisor Pre-Bookings (Google Sheet)](https://docs.google.com/spreadsheets/d/1rIGbbWXwfEJW7Y77iFGqpjbN5UK_Ef1gJMM6O6asJiI/edit)

Supports **Voice mode** (microphone → Whisper STT → Sarvam TTS) and **Text mode**.
Available in **English (en-IN)** and **हिंदी (hi-IN)**.

---

## What Was Built

### Intents (5)

| Intent | Description |
|--------|-------------|
| `book_new` | Start a fresh appointment booking |
| `reschedule` | Change an existing booking (by code) |
| `cancel` | Cancel an existing booking (by code) |
| `what_to_prepare` | Advice on what to bring / prepare for topic |
| `check_availability` | Ask about open slots without committing |

### Full Conversation Flow

```
IDLE
 └─► GREETED          — "Hello, I'm the Advisor Scheduling assistant…"
      └─► DISCLAIMER_CONFIRMED  — compliance disclaimer + user consent
           └─► INTENT_IDENTIFIED — book_new / reschedule / cancel / …
                └─► TOPIC_COLLECTED  — KYC / SIP / Statements / Withdrawals / Account Changes
                     └─► TIME_PREFERENCE_COLLECTED — day + time parsed (IST-aware)
                          ├─► SLOTS_OFFERED         — 2 slots always shown (4-level expansion)
                          │    └─► SLOT_CONFIRMED   — user picks a slot; agent confirms date/time IST
                          │         └─► MCP_DISPATCHED ─────────────────────────────────────────┐
                          │              └─► BOOKING_COMPLETE                                   │
                          │                   └─► END                                           │
                          │                                                                     │
                          └─► WAITLIST_OFFERED      — when no slots match                      │
                               └─► WAITLIST_CONFIRMED ──► MCP_DISPATCHED (waitlist hold) ──────┘
                                    └─► END
```

### On Booking Confirmed — MCP Actions (all three in parallel after calendar)

1. **Google Calendar** — `Advisor Q&A — {Topic} — {Code}` TENTATIVE hold (banana yellow)
2. **Google Sheets** — Row appended to "Advisor Pre-Bookings" tab (booking code, topic, slot IST, advisor ID, call ID)
3. **Gmail Draft** — HTML email pre-composed in advisor's Drafts folder; advisor clicks Send manually (approval-gated)

### Booking Code

Format: `NL-XXXX` (4 alphanumeric chars, excludes O/I/0/1 for clarity). Example: `NL-A742`

Spoken character-by-character: *"N - L - A - 7 - 4 - 2"*

### Secure URL

After booking, a HMAC-SHA256 signed link is read out:
`https://{domain}/book/{token}` — 24-hour TTL, carries booking code + topic + slot.
Caller uses this to submit contact details outside the call (no PII on voice).

---

## Key Constraints

### No PII on Call
- Two-pass PII scrubber blocks phone numbers, email addresses, PAN, Aadhaar, 16-digit account numbers
- If user shares PII: *"Please don't share personal details on this call. You'll receive a secure link after booking."*

### IST Timezone
- All times are in **IST (Asia/Kolkata, UTC+5:30)**
- Confirmation repeats full date + time: *"Monday, 13th April at 2:00 PM IST"*

### Investment Advice Refusal + Educational Links
- If user asks for investment advice: agent refuses and provides:
  - **SEBI Investor Education:** https://investor.sebi.gov.in
  - **AMFI Investor Corner:** https://www.amfiindia.com/investor-corner
- Response: *"I'm not able to provide investment advice on this call. For investor education, you can visit SEBI's portal at investor.sebi.gov.in…"*

### No-Slots → Waitlist Hold + Draft Email
- When no calendar slots match requested time:
  - User is offered the waitlist
  - On acceptance: waitlist code issued (`NL-WXXX`), **calendar hold created** ("Advisor Q&A — Topic (Waitlist) — Code"), **Gmail draft** sent to advisor
  - Advisor contacts user when a slot opens

---

## Mock Calendar JSON

Located at [`phase1/data/mock_calendar.json`](phase1/data/mock_calendar.json).

```json
{
  "advisor_id": "ADV-001",
  "timezone": "Asia/Kolkata",
  "slots": [
    { "slot_id": "SLOT-20260406-1000", "start": "2026-04-06T10:00:00", "end": "2026-04-06T10:30:00", "status": "AVAILABLE", "topic_affinity": [] },
    { "slot_id": "SLOT-20260407-1400", "start": "2026-04-07T14:00:00", "end": "2026-04-07T14:30:00", "status": "AVAILABLE", "topic_affinity": [] },
    ...19 slots total across Apr 6–16, 2026...
  ]
}
```

**Slot fields:**
- `slot_id` — unique identifier
- `start` / `end` — ISO 8601 local IST (no tz suffix in file; treated as IST)
- `status` — `AVAILABLE` | `TENTATIVE` | `BOOKED`
- `topic_affinity` — optional list of preferred topic keys (e.g. `["kyc_onboarding"]`)

**How slots are resolved (4-level expansion):**
1. Exact match on requested day + time
2. Same day, any time
3. Same week, any day/time
4. Next week, any day/time → always returns exactly 2 slots

If Google Calendar credentials are configured (`GOOGLE_CALENDAR_ID` env var), the agent queries **real Google Calendar freeBusy API** and subtracts busy intervals to find true availability. Falls back to mock JSON if credentials absent.

---

## Reschedule Flow

1. User says *"I want to reschedule"* → FSM enters `RESCHEDULE_CODE_COLLECTED` state
2. Agent asks for booking code
3. User provides code (e.g. `NL-A742`)
4. Agent re-enters `TIME_PREFERENCE_COLLECTED` → offers 2 new slots
5. On confirm: new calendar hold created, old hold description updated, Sheets row status changed to `RESCHEDULED`

---

## Cancel Flow

1. User says *"I want to cancel"* → FSM enters `CANCEL_CODE_COLLECTED` state
2. Agent asks for booking code
3. User provides code
4. Booking removed; if a waitlist entry exists for that topic/time, it is auto-promoted from the queue
5. Confirmation: *"Your booking NL-A742 has been cancelled."*

---

## Project Structure

```
voice-agents/
├── phase0/               # Project scaffold, .env config, service account setup
├── phase1/               # Booking brain (offline)
│   ├── src/booking/
│   │   ├── slot_resolver.py         # Mock + real GCal freeBusy slot resolution
│   │   ├── booking_code_generator.py # NL-XXXX / NL-WXXX code generation
│   │   ├── pii_scrubber.py          # Two-pass PII detection + redaction
│   │   ├── secure_url_generator.py  # HMAC-signed booking URL (24h TTL)
│   │   ├── waitlist_handler.py      # WaitlistEntry dataclass + queue management
│   │   └── waitlist_queue.py        # In-memory queue with promotion logic
│   └── data/
│       └── mock_calendar.json       # 19 mock slots, Apr 6–16 2026
├── phase2/               # FSM + LLM dialogue core
│   └── src/dialogue/
│       ├── fsm.py                   # 16-state machine, bilingual strings, all flows
│       ├── states.py                # DialogueState enum, DialogueContext, LLMResponse
│       ├── llm_router.py            # Groq (primary) → Claude (fallback) → rules
│       ├── compliance_guard.py      # PII blocking, advice refusal, scope guard
│       └── intent_router.py         # 9-intent classifier
├── phase3/               # Voice I/O
│   └── data/tts_cache/              # 30+ pre-synthesized WAV files
├── phase4/               # Google Workspace MCP
│   └── src/mcp/
│       ├── calendar_tool.py         # Google Calendar — create TENTATIVE hold
│       ├── sheets_tool.py           # Google Sheets — append booking row
│       ├── email_tool.py            # Gmail — save to Drafts via IMAP APPEND
│       ├── mcp_orchestrator.py      # Sequential + parallel dispatch; waitlist support
│       └── models.py                # MCPPayload, ToolResult, MCPResults
├── phase5/               # Streamlit UI + deployment
│   ├── ui/app.py                    # Full production UI (voice + text, bilingual)
│   └── docker/Dockerfile
├── evals/                # AI Evals suite
│   ├── datasets/              # Golden datasets (JSON)
│   ├── evaluators/            # Intent, slot, compliance, flow, LLM-judge evaluators
│   ├── results/               # JSON results from each eval run
│   └── run_evals.py           # Main runner (offline + LLM mode)
├── railway.toml                     # Railway deployment config
├── requirements.txt
├── utterance_script.md              # Demo phrases for all 10 flows
└── README.md                        # This file
```

---

## AI Evals

The project includes a purpose-built eval suite at [`evals/`](evals/) that measures quality across four dimensions.

### Run the evals

```bash
# Offline mode — rule-based fallback, no API keys needed (~3 seconds)
python3 evals/run_evals.py --offline --no-judge

# Full LLM mode — uses Groq + Claude
python3 evals/run_evals.py

# Run a single suite
python3 evals/run_evals.py --only intent    # intent classification
python3 evals/run_evals.py --only slots     # slot extraction
python3 evals/run_evals.py --only compliance# safety / compliance
python3 evals/run_evals.py --only flows     # multi-turn conversation flows
python3 evals/run_evals.py --only judge     # LLM-as-judge response quality
```

### What is evaluated

| Suite | Dataset | Metric | Offline Baseline |
|-------|---------|--------|-----------------|
| **Intent Classification** | 45 cases — 10 intent types, EN + Hindi | Accuracy per category | 68.9% |
| **Slot Extraction** | 20 cases — topic, day, time, booking code | Precision / Recall / F1 per slot | 85.0% full-match |
| **Compliance / Safety** | 20 cases — advice refusal, PII blocking, scope | Safety recall (FN = 0 target) | 83.3% advice recall |
| **Conversation Flows** | 10 multi-turn flows (new booking, reschedule, cancel, what-to-prepare, no-input) | Pass rate (state + outcome) | 90.0% |
| **LLM-as-Judge** | 8 sample agent responses | Tone / Clarity / Helpfulness / Compliance (Claude scores 1–5) | Requires API |

### Why these evals exist

- **Intent** — The LLM chain (Groq → Claude → rule-based) must classify 10 intents correctly across accents, languages, and phrasing variants.
- **Slots** — Booking code extraction must be robust to Whisper transcription noise (e.g., "N L A B 2 3" → `NL-AB23`).
- **Compliance** — A false negative on `refuse_advice` or `refuse_pii` is a regulatory violation. Safety recall is tracked separately.
- **Flows** — Integration test that the FSM + router + mocked MCP complete end-to-end without getting stuck in a state.
- **LLM Judge** — Catches degraded tone or unhelpful responses that unit tests miss.

Results are saved as JSON to [`evals/results/`](evals/results/).

---

## Skills Demonstrated

| Week | Skill | How |
|------|-------|-----|
| W9 | Voice Agents: ASR/TTS | Groq Whisper STT, Sarvam AI TTS, audio autoplay + auto-mic |
| W5 | Multi-Agent & MCP | Calendar + Sheets + Email dispatch with human-in-the-loop approval |
| W4 | AI Agents & Protocols | 16-state FSM slot-filling; reschedule/cancel/waitlist flows |
| W2 | LLMs & Prompting | Safe disclaimers, refusals, bilingual prompts, TTS-optimised phrasing |
| W7 | Designing for AI Products | Booking-code UX, secure URL, compliance microcopy, ZAY-G UI |

---

## Prompts Used

### 1. LLM System Prompt — Intent Router

Used in [`phase2/src/dialogue/intent_router.py`](phase2/src/dialogue/intent_router.py) to classify every user utterance.
Primary model: **Groq llama-3.3-70b-versatile** → fallback: **Anthropic claude-haiku-4-5**.

```
You are an intent-extraction engine for a voice-based advisor appointment scheduler.

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
- day_preference     : e.g. "Monday", "tomorrow", "next week", "this week", "10th April"
- time_preference    : e.g. "morning", "afternoon", "3pm", "10:30am", "any time", "flexible"
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
```

**Hindi addendum** (appended when language is `hi-IN`):
```
IMPORTANT: The user is speaking Hindi.
The "speech" field in your JSON response MUST be in Hindi (Devanagari script).
All acknowledgements, questions, and responses must be in Hindi.
```

**User message template** (context injected with every turn):
```
[Context]
Current state: {state_name}
Slots already filled: {filled_slots_json}
Current intent: {intent}

[User said]
{user_input}
```

---

### 2. FSM Dialogue Strings — English (en-IN)

Hardcoded in [`phase2/src/dialogue/fsm.py`](phase2/src/dialogue/fsm.py). No LLM used — deterministic, compliance-safe.

| Key | Agent Says |
|-----|------------|
| `greeting` | "Hello! I'm the Advisor Scheduling assistant. I can help you book, reschedule, or cancel advisor consultations for topics like KYC, SIP, tax documents, withdrawals, or account changes. I can also check available slots or tell you what to prepare." |
| `disclaimer` | "Quick note: our advisors provide informational guidance only, not investment advice under SEBI regulations. No personal details are collected on this call. Shall we continue?" |
| `topic_prompt` | "Great. What topic would you like to discuss? I can help with: KYC and onboarding, SIP and mandates, statements and tax documents, withdrawals and timelines, or account changes and nominee updates." |
| `topic_clarity` | "To connect you with the right advisor, I need you to choose one specific topic: KYC and onboarding, SIP and mandates, statements and tax documents, withdrawals and timelines, or account changes. Which one applies to you?" |
| `time_prompt` | "What day and time works best for you this week or next?" |
| `refusal_advice` | "I'm not able to provide investment advice on this call. For investor education, you can visit SEBI's portal at investor.sebi.gov.in, or AMFI India at amfiindia.com/investor-corner. I can help you book a consultation with a human advisor. Would you like to do that?" |
| `refusal_pii` | "Please don't share personal details on this call. You'll receive a secure link after booking to submit your contact information." |
| `out_of_scope` | "I'm only able to help with advisor appointment scheduling today." |
| `timezone` | "All our appointment slots are in IST (India Standard Time, UTC+5:30). Please use a timezone converter to find your local equivalent. Would you like to book a slot?" |
| `farewell` | "Thank you for calling. Have a great day!" |
| `end_call` | "Thank you for reaching out. We'll be happy to help whenever you're ready. Have a wonderful day!" |
| `waitlist` | "I've added you to the waitlist. You'll receive a secure link to submit your contact details — we'll email you as soon as a matching slot opens up." |
| `booking_code_prompt` | "Please share your booking code so I can find your appointment." |
| `prepare_kyc_onboarding` | "For a KYC and Onboarding session, please keep the following ready: a government-issued photo ID — Aadhaar card, PAN card, or passport; an address proof such as a utility bill or bank statement; a cancelled cheque or recent bank statement for account linking; and your existing account or folio details if you have any. You don't need to share these on this call — bring them to the advisor session. Would you like to book an appointment?" |
| `prepare_sip_mandates` | "For a SIP and Mandates session, please keep ready: your bank account number and IFSC code for mandate setup; your existing folio or portfolio number if applicable; and the SIP amount and frequency you have in mind. Would you like to book an appointment?" |
| `prepare_statements_tax` | "For a Statements and Tax Documents session, please keep ready: your PAN card; your broker or fund house login credentials or account number; and the financial year or date range you need statements for. Would you like to book an appointment?" |
| `prepare_withdrawals` | "For a Withdrawals and Timelines session, please keep ready: your folio number or account details; your bank account details for redemption credit; and any specific fund or amount you wish to withdraw. Would you like to book an appointment?" |
| `prepare_account_changes` | "For an Account Changes and Nominee Updates session, please keep ready: a government-issued photo ID; your existing account or folio number; nominee details including name, date of birth, and relationship; and supporting documents for any name or address change. Would you like to book an appointment?" |

---

### 3. FSM Dialogue Strings — Hindi (hi-IN)

Full Hindi equivalents of all strings above. Key examples:

| Key | Agent Says |
|-----|------------|
| `greeting` | "नमस्ते! मैं Advisor Scheduling सहायक हूँ। बुकिंग, रिशेड्यूल, कैंसिल, स्लॉट देखना, या तैयारी की जानकारी — KYC, SIP, टैक्स, निकासी, या खाते में बदलाव के लिए।" |
| `disclaimer` | "एक जानकारी: सलाहकार केवल जानकारी देते हैं, निवेश सलाह नहीं। कॉल पर कोई व्यक्तिगत जानकारी नहीं ली जाती। क्या हम आगे बढ़ें?" |
| `topic_prompt` | "बढ़िया। आप किस विषय पर चर्चा करना चाहते हैं? KYC और ऑनबोर्डिंग, SIP और मैंडेट, स्टेटमेंट और टैक्स दस्तावेज़, निकासी, या खाते में बदलाव और नॉमिनी अपडेट।" |
| `time_prompt` | "इस सप्ताह या अगले सप्ताह कौन सा दिन और समय आपके लिए सुविधाजनक है?" |
| `refusal_advice` | "मैं इस कॉल पर निवेश सलाह देने में असमर्थ हूँ। SEBI का पोर्टल investor.sebi.gov.in या AMFI India का amfiindia.com/investor-corner देख सकते हैं। क्या आप बुकिंग करना चाहेंगे?" |
| `refusal_pii` | "कृपया इस कॉल पर व्यक्तिगत जानकारी साझा न करें। बुकिंग के बाद आपको एक सुरक्षित लिंक मिलेगा।" |
| `out_of_scope` | "मैं केवल सलाहकार अपॉइंटमेंट शेड्यूलिंग में मदद कर सकता हूँ।" |

---

### 4. Compliance Guard Safe Responses

Hardcoded in [`phase2/src/dialogue/compliance_guard.py`](phase2/src/dialogue/compliance_guard.py). Applied as a final safety layer before any response reaches the user.

```
Advice refusal:
"I'm not able to provide investment advice. I can help you book a consultation with an advisor. Would you like to schedule one?"

PII refusal:
"Please don't share personal details on this call. You'll receive a secure link after booking to submit your contact information."

Out-of-scope:
"I'm only able to help with advisor appointment scheduling today."
```

---

### 5. Advisor Approval Email

Auto-drafted in Gmail when a booking is confirmed ([`phase4/src/mcp/email_tool.py`](phase4/src/mcp/email_tool.py)).

**Subject:**
```
[Pre-Booking] {topic_label} — {booking_code} — {slot_start_ist}
```

**Body (HTML):** Addressed to the advisor, contains a table with booking code, topic, IST slot, advisor ID, status (TENTATIVE), calendar event ID, call ID, and created timestamp. Advisor clicks Send manually — no automatic PII transmission.

---

### 6. Google Calendar Event

Created as a TENTATIVE hold in [`phase4/src/mcp/calendar_tool.py`](phase4/src/mcp/calendar_tool.py).

```
Title:       Advisor Q&A — {topic_label} — {booking_code}

Description:
  Pre-booking via Voice Agent
  Booking Code : {booking_code}
  Topic        : {topic_label}
  Advisor ID   : {advisor_id}
  Call ID      : {call_id}
  Created      : {created_at_ist}
```

---

## Environment Variables

```env
# LLM
GROQ_API_KEY=...
ANTHROPIC_API_KEY=...

# TTS / STT
SARVAM_API_KEY=...
TTS_LANGUAGE=en-IN          # or hi-IN

# Google Workspace (MCP)
GOOGLE_CALENDAR_ID=...      # may be base64-encoded
GOOGLE_SERVICE_ACCOUNT_JSON=...   # full JSON inline (for Railway)
GOOGLE_SERVICE_ACCOUNT_PATH=...   # file path (for local)
GOOGLE_SHEET_ID=...
GOOGLE_SHEET_TAB_NAME=Advisor Pre-Bookings

# Gmail
GMAIL_ADDRESS=...
GMAIL_APP_PASSWORD=...
ADVISOR_EMAIL=...
ADVISOR_NAME=Financial Advisor
ADVISOR_ID=ADV-001

# Booking
SECURE_URL_BASE=https://yourdomain.com
SECURE_URL_SECRET=...
SECURE_URL_TTL_SECONDS=86400   # 24 hours
MOCK_CALENDAR_PATH=phase1/data/mock_calendar.json
```

---

## How to Run Locally

```bash
cd voice-agents
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
streamlit run phase5/ui/app.py --server.port=8501
```

Open http://localhost:8501 — select **Voice** mode, click **Start Recording**, speak.

---

## Submission Deliverables

| Deliverable | Status | Location |
|-------------|--------|----------|
| Working voice demo (live link) | ✅ | [railway.app link above] |
| Calendar hold screenshot | See below | Created on booking confirmation |
| Notes/Doc entry screenshot | See below | Google Sheets "Advisor Pre-Bookings" tab |
| Email draft screenshot | See below | Gmail Drafts — advisor reviews + clicks Send |
| Script file | ✅ | [`utterance_script.md`](utterance_script.md) |
| README (this file) | ✅ | `README.md` |

### Calendar Hold Title Format
```
Advisor Q&A — KYC and Onboarding — NL-A742
```
Status: TENTATIVE | Color: Banana Yellow | Timezone: Asia/Kolkata

### Sheets Row Format (Advisor Pre-Bookings tab)
```
booking_code | topic_key    | topic_label          | slot_start_ist              | slot_end_ist | advisor_id | status    | calendar_event_id | email_draft_id | created_at_ist          | call_id
NL-A742      | kyc_onboarding | KYC and Onboarding | Monday, 13/04/2026 02:00 PM IST | ... 02:30 PM | ADV-001 | TENTATIVE | <gcal_id>         | <draft_uid>    | 2026-04-09 14:32:00 IST | <uuid>
```

### Email Draft Subject Format
```
[Pre-Booking] KYC and Onboarding — NL-A742 — Monday, 13/04/2026 02:00 PM IST
```

---

## Compliance Notes

- **No PII collected on call** — phone, email, PAN, Aadhaar, account numbers are all blocked by two-pass scrubber
- **Disclaimer enforced** at every session start; agent cannot proceed without user acknowledgement
- **Investment advice** refused with SEBI + AMFI educational links provided
- **Secure URL** (HMAC-SHA256, 24h TTL) used to collect contact details off-call
- **All times in IST** — confirmed aloud on every booking
- **Approval-gated email** — advisor must manually click Send; no automatic PII transmission
