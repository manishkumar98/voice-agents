# Voice Agent — Advisor Appointment Scheduler

A production-grade, compliance-first voice agent that books tentative advisor consultation slots.
Callers speak naturally; the agent collects topic + time preference, offers two real calendar slots,
confirms the booking, generates a booking code, and triggers Google Calendar / Sheets / Gmail via MCP.

---

## Live Demo

**Streamlit App:** [https://voice-agent-production.up.railway.app](https://voice-agent-production.up.railway.app)

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
├── railway.toml                     # Railway deployment config
├── requirements.txt
├── utterance_script.md              # Demo phrases for all 10 flows
└── README.md                        # This file
```

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
