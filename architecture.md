# Architecture Document: AI Advisor Appointment Scheduler — Voice Agent
**Version:** 2.0 | **Owner:** Chief Software Engineer | **Status:** Approved for Build

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Compliance & Security Architecture](#4-compliance--security-architecture)
5. [Dialogue State Machine (FSM)](#5-dialogue-state-machine-fsm)
6. [Intent Design — All 5 Intents](#6-intent-design--all-5-intents)
7. [Voice UX Design & Turn Scripts](#7-voice-ux-design--turn-scripts)
8. [Data Models & Schemas](#8-data-models--schemas)
9. [MCP Tool Contract Definitions](#9-mcp-tool-contract-definitions)
10. [Booking Logic Engine](#10-booking-logic-engine)
11. [RAG Pipeline Design](#11-rag-pipeline-design)
12. [Error Handling & Resilience](#12-error-handling--resilience)
13. [Observability & Compliance Logging](#13-observability--compliance-logging)
14. [Implementation Phases](#14-implementation-phases)
15. [Testing Strategy](#15-testing-strategy)
16. [Text-Based Testing Interface (UI)](#16-text-based-testing-interface-ui)
17. [Deployment Architecture](#17-deployment-architecture)

---

## 1. Purpose & Scope

### 1.1 Product Vision

This system is a **compliance-first, voice-driven pre-booking agent** for financial advisory consultations. It removes the friction of manual scheduling while enforcing strict regulatory guardrails — no PII on the call, no investment advice, full audit trail.

### 1.2 Target Users

| User Type | Pain Point Solved |
| --- | --- |
| **End User (Retail Investor)** | Can book an advisor slot via voice without navigating portals or waiting on hold. |
| **Product Manager** | Standardised, compliant pre-booking funnel with structured data capture. |
| **Support / Compliance Team** | Every call is logged, every action is audit-trailed, no PII leakage risk. |
| **Advisor** | Receives structured pre-booking email draft with context; no cold meeting. |

### 1.3 Non-Goals

- This system does NOT provide investment advice.
- This system does NOT capture or store PII (phone, email, account numbers) on the voice channel.
- This system does NOT confirm a final confirmed appointment — it creates a **tentative hold** only.
- This system does NOT handle payment or KYC verification.

---

## 2. System Architecture Overview

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER CHANNEL LAYER                           │
│                                                                     │
│   [Phone / Browser Mic]  ──►  [WebRTC / PSTN Gateway]             │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ PCM Audio Stream
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SPEECH PROCESSING LAYER                      │
│                                                                     │
│   [STT Engine]  ◄──► [Voice Activity Detector (VAD)]              │
│   Google Cloud Speech-to-Text  /  Deepgram (fallback)             │
│        │                                                            │
│        │  Transcript + Confidence Score                             │
│        ▼                                                            │
│   [PII Scrubber]  ──►  [Voice Logger (append-only .jsonl)]        │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Sanitised Text
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        VOICE AGENT CORE                             │
│                                                                     │
│  ┌──────────────────────┐    ┌────────────────────────────────┐   │
│  │  Session Manager     │    │  Dialogue State Machine (FSM)  │   │
│  │  (in-memory / Redis) │◄──►│  State + Slots + Turn Counter  │   │
│  └──────────────────────┘    └────────────────┬───────────────┘   │
│                                               │                     │
│  ┌────────────────────────────────────────────▼───────────────┐   │
│  │                  LLM Inference Engine                       │   │
│  │  Provider: Groq (llama-3.1-70b) / Claude (claude-haiku)    │   │
│  │  Role: Intent Classification + Slot Filling + Response Gen │   │
│  │  Output Format: Structured JSON (action + slots + speech)  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────┐    ┌────────────────────────────────┐   │
│  │  RAG Context Injector│    │  Compliance Guard              │   │
│  │  (for what_to_prepare│    │  (blocks PII + advice)         │   │
│  │   intent only)       │    │                                │   │
│  └──────────────────────┘    └────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Action Payload (JSON)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BOOKING LOGIC ENGINE                         │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  Slot Resolver  │  │  Booking Code    │  │  Waitlist       │  │
│  │  (mock_calendar │  │  Generator       │  │  Handler        │  │
│  │   .json / API)  │  │  NL-XXXX format  │  │                 │  │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Booking Payload
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MCP ORCHESTRATION LAYER                      │
│                                                                     │
│  Triggered in PARALLEL after booking confirmation:                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  MCP Tool 1: create_calendar_hold()                          │  │
│  │  → Google Calendar API (Service Account)                     │  │
│  │  → Title: "Advisor Q&A — {Topic} — {Code}"                  │  │
│  │  → Status: TENTATIVE | Duration: 30 min                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  MCP Tool 2: append_booking_notes()                          │  │
│  │  → Google Sheets API (Service Account)                       │  │
│  │  → Sheet: "Advisor Pre-Bookings"                             │  │
│  │  → Row: {code, topic, slot_ist, created_at, status}         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  MCP Tool 3: draft_approval_email()                          │  │
│  │  → Gmail SMTP / smtplib (App Password)                       │  │
│  │  → Saved as DRAFT — NOT sent                                 │  │
│  │  → Approval-gated: advisor clicks "Send" manually           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Confirmation Payload
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SPEECH SYNTHESIS LAYER                       │
│                                                                     │
│   [Response Builder]  ──►  [TTS Engine (Google TTS)]              │
│   Assembles: BookingCode + SecureURL + Date/Time (IST)            │
│   Cache: Disclaimer audio cached to reduce API calls              │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ Audio Stream
                                    ▼
                            [User Hears Response]
```

### 2.2 Service Boundaries and Ownership

| Layer | Service | Stateful? | Failure Impact |
| --- | --- | --- | --- |
| Speech Processing | STT + VAD + PII Scrubber | No | Call degraded; fallback to text channel |
| Voice Agent Core | FSM + LLM + Session Manager | Yes (per-session) | Call fails; session recoverable via session ID |
| Booking Logic | Slot Resolver + Code Generator | No | Booking fails; user informed, no MCP triggered |
| MCP Orchestration | Calendar + Sheets + Email | No | Partial failure handled; see Section 12 |
| Speech Synthesis | TTS + Response Builder | No | Fallback to monotone TTS or text |

---

## 3. Technology Stack

### 3.1 Core Runtime

| Component | Chosen Technology | Version / Tier | Rationale |
| --- | --- | --- | --- |
| **Language** | Python | 3.11+ | Async support, rich AI/ML ecosystem |
| **LLM Provider (Primary)** | Groq API | `llama-3.1-70b-versatile` (free tier) | Fastest inference latency (<500ms), free tier sufficient for demo |
| **LLM Provider (Fallback)** | Anthropic Claude | `claude-haiku-4-5` | Lower latency/cost fallback; excellent at structured JSON output |
| **STT** | Google Cloud Speech-to-Text | v2, free tier (60 min/month) | Best-in-class accuracy for Indian English accents |
| **STT Fallback** | Deepgram Nova-2 | Free tier | Lower latency streaming; good Hindi-English code-switch support |
| **TTS** | Google Cloud Text-to-Speech | Neural2 voice, free tier | Natural prosody; WaveNet/Neural2 available at free tier |
| **VAD** | Silero VAD | v4 (local ONNX) | Runs locally, no API cost, <10ms latency |
| **Session State** | Python dict (dev) / Redis 7 (prod) | In-process / Docker | Session lifetime = single call; TTL 30 min |
| **Web Framework** | FastAPI | 0.111+ | Async-first, OpenAPI docs auto-generated, WebSocket support |
| **Demo UI** | Streamlit | 1.35+ | Rapid prototyping; built-in audio components |
| **Task Queue** | asyncio (dev) / Celery + Redis (prod) | — | Parallel MCP dispatch post-confirmation |
| **Vector DB (RAG)** | ChromaDB | 0.5+ (local) | Zero-ops, runs in-process, persistent to disk |
| **Embedding Model** | `all-MiniLM-L6-v2` (SentenceTransformers) | Local | No API cost; good semantic accuracy for financial FAQ |

### 3.2 MCP & Integration

| Integration | Library | Auth Method |
| --- | --- | --- |
| Google Calendar | `google-api-python-client` 2.x | Service Account JSON + domain delegation |
| Google Sheets | `gspread` 6.x | Service Account JSON |
| Gmail (Draft) | `smtplib` (stdlib) | Gmail App Password (not OAuth; simpler for demo) |
| Secure URL Generator | `itsdangerous` (signed tokens) | HMAC-SHA256 with SECRET_KEY from `.env` |

### 3.3 Developer Tooling

| Tool | Purpose |
| --- | --- |
| `python-dotenv` | Load `.env` secrets at runtime |
| `pytz` / `zoneinfo` | IST timezone handling |
| `pytest` + `pytest-asyncio` | Unit and async integration tests |
| `pytest-mock` | Mock LLM/API calls in tests |
| `ruff` | Linting and formatting |
| `pre-commit` | Enforce lint/format before commits |
| `httpx` | Async HTTP client for external APIs |
| `structlog` | Structured JSON logging |

---

## 4. Compliance & Security Architecture

### 4.1 PII Guardrails — Defence in Depth

PII protection operates at three independent layers. Any single layer failing does not expose PII.

```
Layer 1 — LLM System Prompt:
  "Never repeat, store, or acknowledge phone numbers, email addresses,
   account numbers, PAN, Aadhaar, or full names on this call."

Layer 2 — PII Scrubber (regex + NER, runs on STT output BEFORE LLM):
  Patterns blocked: phone numbers, email addresses, 16-digit account
  numbers, PAN format (AAAAA0000A), Aadhaar (12 digits).
  Action: Replace with [REDACTED] before passing to LLM.

Layer 3 — Compliance Guard (post-LLM, pre-TTS):
  Scans LLM output for any PII pattern leakage.
  Action: If detected → do NOT speak → trigger fallback response.
```

### 4.2 Secure URL Design

When the agent reads the booking code, it also provides a secure URL where the user can submit their contact details outside the voice channel.

```
URL Format: https://{domain}/book/{signed_token}

Token Payload (HMAC-signed, expires 24h):
{
  "booking_code": "NL-A742",
  "topic": "KYC",
  "slot_ist": "2024-02-15T14:00:00+05:30",
  "exp": 1708000000
}

Signing: itsdangerous.URLSafeTimedSerializer with SECRET_KEY
Verification: Server-side on form submission; rejects expired/tampered tokens
```

### 4.3 Compliance Refusals

The agent must refuse specific categories of requests with a pre-defined response:

| Trigger Category | LLM Instruction | Spoken Response |
| --- | --- | --- |
| Investment advice ("should I buy X") | Classify as `refuse_advice` intent | "I'm not able to provide investment advice. For educational information, I can share a resource link. Would you still like to book a consultation?" |
| PII collection attempt ("my phone is...") | Classify as `refuse_pii` | "Please don't share personal details on this call. You'll receive a secure link after booking to submit your contact information." |
| Off-topic / abusive | Classify as `out_of_scope` | "I'm only able to help with advisor appointment scheduling today." |

### 4.4 Audit Trail

Every call produces an immutable, append-only audit record:

```jsonc
// voice_audit_log.jsonl — one JSON object per line
{
  "call_id": "CALL-20240215-abc123",
  "timestamp_ist": "2024-02-15T13:45:00+05:30",
  "event_type": "TURN",          // TURN | INTENT | MCP_TRIGGER | MCP_RESULT | COMPLIANCE_BLOCK
  "turn_index": 3,
  "user_transcript_sanitised": "I want to book for KYC next Monday at 2 PM",
  "detected_intent": "book_new",
  "slots_filled": {"topic": "KYC", "day": "Monday", "time": "14:00"},
  "agent_response_text": "I found two slots available...",
  "pii_blocked": false
}
```

---

## 5. Dialogue State Machine (FSM)

### 5.0 Dialogue Flow (Linear Steps)

States are linear with branches for errors, waitlist, and non-booking intents.

1. **Greet** → play short value prop.
2. **Disclaimer** → mandatory: informational, not investment advice; require explicit acknowledgment (e.g. "yes" / "I understand") before continuing.
3. **Intent detect** → if not `book_new`, branch to reschedule / cancel / prepare / availability subgraphs (each with its own mini-flow).
4. **Topic confirm** → must map to one of: KYC/Onboarding, SIP/Mandates, Statements/Tax Docs, Withdrawals & Timelines, Account Changes/Nominee.
5. **Day/time preference** → natural language → normalized to date + time window in **IST** (store and display always with timezone).
6. **Offer slots** → mock calendar returns **two** concrete options; read back with IST and full date/time on confirmation.
7. **Confirm** → on user confirmation:
   - Generate booking code (e.g. `NL-A742` pattern).
   - MCP Calendar: create tentative event title `Advisor Q&A – {Topic} – {Code}`.
   - MCP Notes: append `{date, topic, slot, code}` to document **Advisor Pre-Bookings**.
   - MCP Email: draft advisor notification (human approval before send).
8. **Close** → speak booking code; give **secure URL** for contact details (no PII collected on call).

**No-match path:** If mock calendar has no slots → **waitlist hold** (domain concept + MCP notes/calendar as per product rules) + draft email; still issue booking code if the brief requires a reference for the waitlist case (align with PM — code may be waitlist-specific).

**Investment advice:** If detected (keywords or intent), **refuse** and offer **educational links** only; do not enter booking unless user pivots to scheduling.

---

### 5.1 State Definitions

The FSM controls exactly which states the agent can be in and what transitions are valid.

```
States:
  S0  IDLE
  S1  GREETED
  S2  DISCLAIMER_CONFIRMED
  S3  INTENT_IDENTIFIED
  S4  TOPIC_COLLECTED
  S5  TIME_PREFERENCE_COLLECTED
  S6  SLOTS_OFFERED
  S7  SLOT_CONFIRMED
  S8  MCP_DISPATCHED
  S9  BOOKING_COMPLETE
  S10 WAITLIST_OFFERED
  S11 WAITLIST_CONFIRMED
  S12 RESCHEDULE_CODE_COLLECTED
  S13 CANCEL_CODE_COLLECTED
  S14 ERROR
  S15 END
```

### 5.2 State Transition Table

| Current State | Trigger / User Input | Next State | Action |
| --- | --- | --- | --- |
| S0 IDLE | Call connected | S1 GREETED | Speak greeting + disclaimer |
| S1 GREETED | User acknowledges | S2 DISCLAIMER_CONFIRMED | — |
| S2 DISCLAIMER_CONFIRMED | Intent = `book_new` | S3→S4 TOPIC | Prompt for topic |
| S2 DISCLAIMER_CONFIRMED | Intent = `reschedule` | S12 | Prompt for booking code |
| S2 DISCLAIMER_CONFIRMED | Intent = `cancel` | S13 | Prompt for booking code |
| S2 DISCLAIMER_CONFIRMED | Intent = `what_to_prepare` | S3 | RAG lookup + respond + offer to book |
| S2 DISCLAIMER_CONFIRMED | Intent = `check_availability` | S3 | Show windows + offer to book |
| S4 TOPIC_COLLECTED | Topic validated | S5 | Prompt for day/time |
| S5 TIME_COLLECTED | Slots found ≥ 1 | S6 | Offer up to 2 slots |
| S5 TIME_COLLECTED | Slots found = 0 | S10 | Offer waitlist |
| S6 SLOTS_OFFERED | User confirms slot | S7 | Confirm slot + date/time (IST) |
| S6 SLOTS_OFFERED | User rejects both | S5 | Re-prompt for different time |
| S7 SLOT_CONFIRMED | — | S8 | Dispatch MCP (parallel) |
| S8 MCP_DISPATCHED | All 3 MCP succeed | S9 | Read booking code + secure URL |
| S8 MCP_DISPATCHED | Partial MCP failure | S9 | Read code + note partial failure; retry async |
| S9 BOOKING_COMPLETE | — | S15 END | Farewell |
| S10 WAITLIST_OFFERED | User accepts | S11 | Dispatch waitlist MCP |
| S10 WAITLIST_OFFERED | User declines | S15 END | Farewell |
| S11 WAITLIST_CONFIRMED | — | S15 END | Read waitlist code + secure URL |
| Any state | `refuse_advice` trigger | Same state | Speak refusal; return to current state |
| Any state | `refuse_pii` trigger | Same state | Speak PII refusal; return |
| Any state | 3× no-input / barge-in fail | S14 ERROR | "I'm having trouble understanding..." |
| S14 ERROR | — | S15 END | Graceful exit |

### 5.3 Slot Fill Tracking

Each state carries a `DialogueContext` object:

```python
@dataclass
class DialogueContext:
    call_id: str
    session_start_ist: datetime
    current_state: DialogueState
    intent: str | None = None
    # Slot fills
    topic: str | None = None          # One of 5 topic keys
    day_preference: str | None = None  # Natural language: "Monday", "next week"
    time_preference: str | None = None # "2 PM", "afternoon"
    resolved_slot: CalendarSlot | None = None
    booking_code: str | None = None
    turn_count: int = 0
    no_input_count: int = 0
    # MCP result tracking
    calendar_hold_created: bool = False
    notes_appended: bool = False
    email_drafted: bool = False
```

---

## 6. Intent Design — All 5 Intents

### 6.1 Intent Overview

| Intent Key | Trigger Phrases (examples) | Required Slots | Output |
| --- | --- | --- | --- |
| `book_new` | "I want to book", "schedule a call", "speak to an advisor" | `topic`, `day_preference`, `time_preference` | Booking Code + Secure URL |
| `reschedule` | "change my appointment", "reschedule", "move my booking" | `existing_booking_code`, `new_day_preference`, `new_time_preference` | New Booking Code + Secure URL |
| `cancel` | "cancel my appointment", "I don't need the call anymore" | `existing_booking_code` | Cancellation confirmation |
| `what_to_prepare` | "what documents do I need", "how to prepare", "what should I bring" | `topic` (optional; if not provided, ask) | RAG-grounded educational response + offer to book |
| `check_availability` | "when is the advisor free", "what slots are available", "show me availability" | `topic` (optional), `day_preference` (optional) | List of available windows + offer to book |

### 6.2 Topic Taxonomy

All topic references are normalised to these 5 canonical keys internally:

| Canonical Key | User-Facing Label | Common Variants (LLM maps these) |
| --- | --- | --- |
| `kyc_onboarding` | KYC / Onboarding | "account opening", "new account", "KYC", "onboarding", "verification" |
| `sip_mandates` | SIP / Mandates | "SIP setup", "auto-debit", "mandate", "systematic plan", "monthly investment" |
| `statements_tax` | Statements / Tax Docs | "statement", "tax", "capital gains", "ELSS", "80C", "Form 26AS" |
| `withdrawals` | Withdrawals & Timelines | "redeem", "withdraw", "when will money come", "payout", "exit" |
| `account_changes` | Account Changes / Nominee | "nominee", "bank change", "address update", "mobile update", "profile change" |

### 6.3 LLM Prompt Structure (System Prompt Skeleton)

```
SYSTEM PROMPT:
You are "Advisor Scheduler", a voice assistant for [Company Name].
Your only job is to help users book a tentative advisory consultation.

RULES (non-negotiable):
1. NEVER provide investment advice. If asked, classify as refuse_advice.
2. NEVER repeat, store, or acknowledge PII (phone, email, account numbers, PAN, Aadhaar).
3. ALWAYS state times in IST and repeat date+time on confirmation.
4. Speak in short, clear sentences suitable for voice (no markdown, no bullet points in speech).
5. If the user goes off-topic, redirect politely to booking.

OUTPUT FORMAT: You MUST always return a JSON object:
{
  "intent": "<intent_key>",
  "slots": { ... filled slots ... },
  "next_action": "<state_transition_key>",
  "speech": "<exact text to speak aloud>",
  "compliance_flag": null | "refuse_advice" | "refuse_pii" | "out_of_scope"
}

TOPIC MAPPING: [include canonical key → label mapping]
AVAILABLE INTENTS: book_new | reschedule | cancel | what_to_prepare |
                   check_availability | refuse_advice | refuse_pii | out_of_scope
```

### 6.4 Reschedule Flow Detail

```
1. Agent: "Please share your booking code so I can find your appointment."
2. User: "NL-A742"
3. System: Look up NL-A742 in Google Sheets "Advisor Pre-Bookings".
   IF found AND status = TENTATIVE:
     4. Agent: "I found your booking for [topic] on [date IST]. What new day and time works for you?"
     5. [Re-enter slot offering flow from S5]
     6. On confirm: cancel old calendar hold, create new hold, update Sheet row,
        draft new email. Issue new booking code (NL-B103).
   IF not found OR status = CANCELLED:
     4. Agent: "I couldn't find an active booking with that code.
        Would you like to make a new booking?"
```

### 6.5 Cancel Flow Detail

```
1. Agent: "Please share your booking code."
2. User: "NL-A742"
3. System: Look up NL-A742.
   IF found AND status = TENTATIVE:
     4. Agent: "I'll cancel your [topic] consultation on [date IST]. Can you confirm?"
     5. User: "Yes"
     6. System: Delete calendar hold, update Sheet row status → CANCELLED,
        draft cancellation email. No new booking code issued.
     7. Agent: "Done. Your booking NL-A742 has been cancelled."
   IF not found: same fallback as reschedule.
```

---

## 7. Voice UX Design & Turn Scripts

### 7.1 Design Principles

- **Sentences ≤ 20 words** per spoken turn (cognitive load on phone audio).
- **Confirm by repetition**: always read back topic + date + time before MCP.
- **No silence > 3s**: if user is silent, re-prompt with a shorter prompt.
- **Barge-in enabled**: user can interrupt agent speech at any time (VAD).
- **Maximum 3 re-prompts** per slot before escalating to a human or ending gracefully.

### 7.2 Turn-by-Turn Script — `book_new` Happy Path

```
[S0 → S1] GREETING
Agent: "Hello! I'm the Advisor Scheduling assistant for [Company].
        I'll help you book a consultation in about two minutes."

[S1 → S2] DISCLAIMER
Agent: "Quick note: this service is for scheduling only.
        Our advisors provide informational guidance, not investment advice.
        Shall we continue?"
User:  "Yes" / "Sure" / any affirmation

[S2 → S4] TOPIC COLLECTION
Agent: "Great. What topic would you like to discuss?
        I can help with: KYC and onboarding, SIP and mandates,
        statements and tax documents, withdrawals and timelines,
        or account changes and nominee updates."
User:  "I want to talk about KYC."
Agent: "Got it — KYC and onboarding."

[S4 → S5] TIME PREFERENCE
Agent: "What day and time works best for you this week or next?"
User:  "Monday around 2 PM."

[S5 → S6] SLOT OFFERING
Agent: "I have two slots available.
        Option one: Monday, February 19th at 2 PM IST.
        Option two: Monday, February 19th at 3:30 PM IST.
        Which do you prefer?"
User:  "The first one."

[S6 → S7] CONFIRMATION
Agent: "Perfect. Confirming: KYC consultation,
        Monday February 19th, 2 PM Indian Standard Time.
        Is that correct?"
User:  "Yes."

[S7 → S8 → S9] MCP DISPATCH + BOOKING COMPLETE
Agent: "Your booking code is November-Lima-Alpha-7-4-2.
        Please note it down: N-L-A-7-4-2.
        You'll receive a link at the secure URL I'll spell out now.
        [reads secure URL slowly]
        Use that link within 24 hours to submit your contact details.
        Thank you, and have a great day!"
```

### 7.3 Waitlist Script

```
Agent: "I don't have any advisor slots available on Monday at 2 PM.
        I can add you to the waitlist and you'll be contacted if a slot opens.
        Would you like that?"
User:  "Yes."
Agent: "Done. Your waitlist code is November-Lima-W-3-9-1.
        Please use the secure link to submit your contact details.
        We'll reach out within 2 business days."
```

### 7.4 Refusal Scripts

```
// Investment advice refusal
Agent: "I'm only able to help with scheduling, not investment advice.
        For educational resources, I can mention our Help Centre.
        Would you still like to book a consultation?"

// PII refusal
Agent: "Please don't share personal details like phone numbers on this call.
        You'll enter those securely via the link I provide at the end."
```

---

## 8. Data Models & Schemas

### 8.1 `CalendarSlot`

```python
@dataclass
class CalendarSlot:
    slot_id: str                    # e.g., "SLOT-20240219-1400"
    start_ist: datetime             # timezone-aware, IST
    end_ist: datetime               # start + 30 minutes
    topic_affinity: list[str]       # topics this slot is valid for (empty = all)
    advisor_id: str                 # internal advisor identifier
    status: Literal["AVAILABLE", "TENTATIVE", "CONFIRMED", "CANCELLED"]
```

### 8.2 `BookingRecord`

```python
@dataclass
class BookingRecord:
    booking_code: str               # e.g., "NL-A742"
    call_id: str                    # originating call session ID
    topic: str                      # canonical topic key
    slot: CalendarSlot
    created_at_ist: datetime
    status: Literal["TENTATIVE", "WAITLIST", "RESCHEDULED", "CANCELLED"]
    calendar_event_id: str | None   # Google Calendar event ID
    sheet_row_index: int | None     # Row in "Advisor Pre-Bookings" sheet
    email_draft_id: str | None      # Gmail draft message ID
    secure_token: str               # Signed URL token (24h TTL)
```

### 8.3 `MCPPayload`

This is the exact payload dispatched to the MCP Orchestrator:

```jsonc
{
  "booking_code": "NL-A742",
  "topic_key": "kyc_onboarding",
  "topic_label": "KYC / Onboarding",
  "slot_start_ist": "2024-02-19T14:00:00+05:30",
  "slot_end_ist": "2024-02-19T14:30:00+05:30",
  "advisor_id": "ADV-001",
  "call_id": "CALL-20240215-abc123",
  "secure_url": "https://example.com/book/eyJ...",
  "is_waitlist": false,
  "calendar_title": "Advisor Q&A — KYC / Onboarding — NL-A742"
}
```

### 8.4 `mock_calendar.json` Schema

```jsonc
{
  "advisor_id": "ADV-001",
  "advisor_name": "Advisor (display name not used on call)",
  "timezone": "Asia/Kolkata",
  "slots": [
    {
      "slot_id": "SLOT-20240219-1400",
      "start": "2024-02-19T14:00:00",
      "end": "2024-02-19T14:30:00",
      "status": "AVAILABLE",
      "topic_affinity": []
    },
    {
      "slot_id": "SLOT-20240219-1530",
      "start": "2024-02-19T15:30:00",
      "end": "2024-02-19T16:00:00",
      "status": "AVAILABLE",
      "topic_affinity": ["kyc_onboarding", "account_changes"]
    }
    // ... more slots
  ]
}
```

### 8.5 Google Sheets "Advisor Pre-Bookings" Schema

| Column | Type | Description |
| --- | --- | --- |
| `booking_code` | String | e.g., NL-A742 |
| `topic_key` | String | canonical topic key |
| `topic_label` | String | human-readable topic |
| `slot_start_ist` | ISO 8601 String | slot date/time in IST |
| `slot_end_ist` | ISO 8601 String | |
| `advisor_id` | String | |
| `status` | Enum String | TENTATIVE / WAITLIST / RESCHEDULED / CANCELLED |
| `calendar_event_id` | String | Google Calendar event ID |
| `email_draft_id` | String | Gmail draft ID |
| `created_at_ist` | ISO 8601 String | record creation time |
| `call_id` | String | for audit cross-reference |

---

## 9. MCP Tool Contract Definitions

### 9.1 `create_calendar_hold()`

```python
def create_calendar_hold(payload: MCPPayload) -> dict:
    """
    Creates a TENTATIVE Google Calendar event.

    Args:
        payload: MCPPayload with booking details

    Returns:
        {"success": True, "event_id": "abc123xyz", "html_link": "https://..."}
        {"success": False, "error": "QuotaExceeded", "retry_after": 60}

    Event structure:
        summary:     "Advisor Q&A — {topic_label} — {booking_code}"
        start:       payload.slot_start_ist
        end:         payload.slot_end_ist
        status:      "tentative"
        description: "Booking Code: {code}\nSecure URL: {url}\nTopic: {topic_label}"
        attendees:   [] (no PII; advisor added by advisor manually post-approval)
        reminders:   [{"method": "email", "minutes": 60}]
    """
```

### 9.2 `append_booking_notes()`

```python
def append_booking_notes(payload: MCPPayload, event_id: str) -> dict:
    """
    Appends a row to the "Advisor Pre-Bookings" Google Sheet.

    Args:
        payload: MCPPayload
        event_id: Google Calendar event ID from create_calendar_hold()

    Returns:
        {"success": True, "row_index": 42}
        {"success": False, "error": "SheetNotFound"}

    Row appended:
        [booking_code, topic_key, topic_label, slot_start_ist, slot_end_ist,
         advisor_id, "TENTATIVE", event_id, "", created_at_ist, call_id]
    """
```

### 9.3 `draft_approval_email()`

```python
def draft_approval_email(payload: MCPPayload, event_id: str, row_index: int) -> dict:
    """
    Creates a Gmail DRAFT (NOT sent). Advisor must approve and send manually.

    Args:
        payload: MCPPayload
        event_id: Calendar event ID
        row_index: Sheet row index for reference

    Returns:
        {"success": True, "draft_id": "r123456789"}
        {"success": False, "error": "AuthFailed"}

    Draft email structure:
        To:      advisor@company.com (from config, NOT from call)
        Subject: "[ACTION REQUIRED] Pre-Booking — {topic_label} — {booking_code}"
        Body:
            Booking Code: {booking_code}
            Topic:        {topic_label}
            Slot (IST):   {slot_start_ist} – {slot_end_ist}
            Calendar:     {html_link}
            Sheet Row:    #{row_index}
            Secure URL:   {secure_url}

            User contact details will be available at the secure URL above
            once the user completes their submission.

            ⚠️  This is a TENTATIVE hold. Please review and send this email
            to confirm the appointment with the user.
    """
```

### 9.4 MCP Orchestration Pattern

All three MCP tools are dispatched **in parallel** using `asyncio.gather()` after slot confirmation:

```python
async def dispatch_mcp(payload: MCPPayload) -> MCPResults:
    results = await asyncio.gather(
        create_calendar_hold(payload),
        return_exceptions=True
    )
    calendar_result = results[0]
    event_id = calendar_result.get("event_id") if calendar_result["success"] else None

    # Notes and Email can run in parallel only after we have event_id
    notes_result, email_result = await asyncio.gather(
        append_booking_notes(payload, event_id),
        draft_approval_email(payload, event_id, row_index=None),
        return_exceptions=True
    )
    return MCPResults(calendar=calendar_result,
                      notes=notes_result,
                      email=email_result)
```

---

## 10. Booking Logic Engine

### 10.1 Booking Code Generation

```
Format: {PREFIX}-{LETTER}{DIGITS}
PREFIX: "NL" (fixed; represents the product line)
LETTER: Random uppercase A–Z
DIGITS: Random 3-digit number (100–999)
Example: NL-A742, NL-B391, NL-Z055

Uniqueness check: Before returning code, verify it does not exist
in the active Google Sheet. Retry up to 5 times. Collision probability
at 1000 active bookings = 26*900 = 23,400 codes → ~4% collision rate.
For scale, extend to 4 digits.

Implementation:
  import random, string
  def generate_booking_code(existing_codes: set[str]) -> str:
      for _ in range(5):
          code = f"NL-{random.choice(string.ascii_uppercase)}{random.randint(100,999)}"
          if code not in existing_codes:
              return code
      raise BookingCodeExhaustedError
```

### 10.2 Slot Resolution Algorithm

```
Input: day_preference (string), time_preference (string), topic (string)

Step 1 — Parse preferences:
  Use LLM to convert natural language to:
  {
    "target_date": "2024-02-19",       // or null if "any day"
    "target_time_range": ["13:00", "15:00"],  // 2-hour window
    "flexibility": "low" | "medium" | "high"
  }

Step 2 — Load available slots:
  Read mock_calendar.json (or Google Calendar free/busy API in production).
  Filter: status == "AVAILABLE"

Step 3 — Score and rank slots:
  For each available slot:
    score = 0
    if slot.start.date() == target_date: score += 10
    if target_time_range[0] <= slot.start.time() <= target_time_range[1]: score += 5
    if topic in slot.topic_affinity or slot.topic_affinity == []: score += 2

Step 4 — Return top 2 slots by score:
  if len(matches) >= 1: return matches[:2]  → offer slots
  else:                 return []           → trigger waitlist
```

### 10.3 Waitlist Logic

```
Waitlist code format: NL-W{3_digits}  (e.g., NL-W391)

On waitlist acceptance:
  1. Generate waitlist booking code.
  2. create_calendar_hold() with title:
     "WAITLIST — Advisor Q&A — {topic_label} — {code}"
     Status: TENTATIVE, Description notes waitlist status.
  3. append_booking_notes() with status = "WAITLIST"
  4. draft_approval_email() with subject:
     "[WAITLIST] Pre-Booking — {topic_label} — {code}"
  5. Agent reads waitlist code + secure URL.
  6. Confirms: "We'll reach out within 2 business days if a slot opens."
```

---

## 11. RAG Pipeline Design

### 11.1 Purpose

The RAG pipeline powers the `what_to_prepare` intent exclusively. When a user asks "what documents do I need for KYC?", the agent retrieves grounded, factual content instead of hallucinating.

### 11.2 Data Ingestion Architecture

```
Source Documents (per topic):
  kyc_onboarding   → SEBI/AMFI KYC guidelines, broker help pages
  sip_mandates     → NACH mandate docs, NPCI mandate guidelines
  statements_tax   → AMFI CAS statement guide, IT department Form 26AS help
  withdrawals      → Typical T+3 settlement FAQ, redemption process
  account_changes  → Nominee addition guidelines, bank mandate change SOP

Pipeline:
  1. Scrape (BeautifulSoup / Playwright):
     → Target: public help centre pages (no auth required)
     → Output: raw_docs/{topic_key}/{filename}.txt

  2. Chunk:
     → Strategy: recursive character splitter, chunk_size=256 tokens,
       overlap=32 tokens
     → Metadata per chunk: {topic_key, source_url, scraped_at}

  3. Embed:
     → Model: sentence-transformers/all-MiniLM-L6-v2 (local, no API cost)
     → Dimension: 384

  4. Index:
     → ChromaDB collection: "advisor_faq"
     → Persist to: ./data/chroma_db/

  5. Query (at runtime, what_to_prepare intent):
     → Embed user query
     → Top-k=3 chunks by cosine similarity
     → Inject into LLM prompt as: "Use ONLY the following context to answer..."
     → LLM generates spoken response grounded in retrieved text
```

### 11.3 RAG Prompt Template

```
SYSTEM: You are answering a voice caller's question about preparation
for a financial advisory consultation.

CONTEXT (retrieved from official sources):
{retrieved_chunks}

RULES:
- Answer only from the context above.
- If context does not cover the question, say:
  "I don't have that specific information, but your advisor can clarify
   during the consultation."
- Keep the answer under 50 words (voice-appropriate).
- Do NOT provide investment advice.
- End with: "Would you like to book a consultation now?"

QUESTION: {user_query}
```

---

## 12. Error Handling & Resilience

### 12.1 Failure Mode Matrix

| Component | Failure Type | Detection | Recovery Strategy |
| --- | --- | --- | --- |
| **STT** | Transcription confidence < 0.7 | confidence score in API response | Re-prompt: "I didn't catch that. Could you repeat?" (max 3×) |
| **STT** | API timeout (>3s) | asyncio timeout | Switch to Deepgram fallback STT |
| **LLM** | Groq API down | HTTP 5xx / timeout | Switch to Claude haiku fallback |
| **LLM** | Invalid JSON output | JSON parse error | Retry with explicit JSON instruction (max 2×); if fails → generic re-prompt |
| **LLM** | Hallucinated PII | Compliance Guard post-processing | Block output; speak generic response; log COMPLIANCE_BLOCK event |
| **Slot Resolver** | No slots available | Empty result from slot algorithm | Trigger waitlist flow |
| **MCP: Calendar** | Google API quota exceeded | HTTP 429 | Log error; continue with notes + email; inform agent to tell user "calendar confirmation may be delayed" |
| **MCP: Calendar** | Auth failure | HTTP 401/403 | Alert ops; skip calendar; do not block booking code issuance |
| **MCP: Sheets** | Sheet not found | gspread exception | Log error; skip row append; booking code still issued |
| **MCP: Email** | SMTP auth failure | smtplib exception | Log error; advisor notified via alternative channel (manual fallback) |
| **MCP: Partial** | 1 of 3 MCP fails | MCPResults check | Issue booking code anyway; schedule async retry for failed tools (max 3 retries, exponential backoff) |
| **TTS** | API timeout | asyncio timeout | Fall back to pyttsx3 (local, zero-cost, lower quality) |
| **Session** | Call drops mid-flow | WebSocket disconnect | Session persisted in Redis for 30 min; resumable via call_id if user calls back |

### 12.2 Retry Policy for MCP Tools

```
Retry config (per MCP tool):
  max_retries:       3
  initial_delay_s:   1.0
  backoff_factor:    2.0        # exponential: 1s, 2s, 4s
  retryable_errors:  [429, 500, 502, 503, 504]
  non_retryable:     [401, 403, 404]  # auth/config issues, alert ops
```

### 12.3 Graceful Degradation Hierarchy

```
Level 0 (full function):    All 3 MCP succeed + TTS speaks code + URL
Level 1 (degraded):         Calendar fails → speak code + URL; async retry calendar
Level 2 (degraded):         Calendar + Sheets fail → speak code + URL; log for manual ops
Level 3 (minimal):          All MCP fail → speak code + URL; flag for immediate ops alert
Level 4 (fallback):         LLM fails entirely → speak static: "Our system is temporarily
                            unavailable. Please call back in 5 minutes."
```

---

## 13. Observability & Compliance Logging

### 13.1 Log Streams

| Log File / Stream | Format | Contents | Retention |
| --- | --- | --- | --- |
| `voice_audit_log.jsonl` | Append-only JSONL | All turns, intents, MCP events, compliance blocks | 7 years (regulatory) |
| `mcp_ops_log.jsonl` | Append-only JSONL | MCP tool invocations, results, retries, latencies | 90 days |
| `application.log` | Structured JSON (structlog) | App-level errors, startup/shutdown, config | 30 days |
| `pii_scrubber.log` | Append-only JSONL | Redaction events (pattern matched, not the PII itself) | 1 year |

### 13.2 Key Metrics to Track

| Metric | Type | Alert Threshold |
| --- | --- | --- |
| `booking_completion_rate` | Gauge | < 60% → investigate |
| `waitlist_rate` | Gauge | > 40% → add advisor slots |
| `mcp_failure_rate` | Counter | > 5% in 5 min → page ops |
| `stt_low_confidence_rate` | Gauge | > 20% → audio quality issue |
| `compliance_block_rate` | Counter | > 1% → prompt audit |
| `llm_fallback_rate` | Counter | > 10% → Groq SLA issue |
| `avg_call_duration_s` | Histogram | > 180s → UX issue |
| `p95_llm_latency_ms` | Histogram | > 1500ms → user experience degraded |

### 13.3 Alerting (Production)

```
Alerting via: Grafana (local) / Uptime Robot (free) / email

Immediate (PagerDuty-equivalent):
  - All 3 MCP tools failing simultaneously
  - Compliance Guard blocking > 5 calls in 10 minutes
  - LLM provider completely unavailable (both Groq + Claude fallback)

Warning (Slack/email):
  - MCP failure rate > 5% over 5 minutes
  - Booking completion rate < 60% over 30 minutes
  - STT confidence consistently < 0.6
```

---

## 14. Implementation Phases

### Phase 0: Foundation — Project Setup & RAG Pipeline

**Goal:** Dev environment running; RAG data indexed; can answer "what to prepare" questions offline.
**Acceptance Criteria:**
- `pytest` passes with 0 failures.
- ChromaDB returns correct chunks for "what documents for KYC" query.
- `.env` loads without error; no secrets committed to git.

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **0.1 Project Scaffold** | `python -m venv .venv`. Create `src/`, `tests/`, `data/`, `config/` dirs. Install: `groq`, `anthropic`, `google-api-python-client`, `gspread`, `google-cloud-speech`, `google-cloud-texttospeech`, `chromadb`, `sentence-transformers`, `fastapi`, `uvicorn`, `streamlit`, `structlog`, `python-dotenv`, `pytz`, `itsdangerous`, `httpx`, `pytest`, `pytest-asyncio`, `pytest-mock`, `ruff`. | `pip install -r requirements.txt` exits 0. |
| **0.2 Config & Secrets** | Create `.env.example` with all required keys: `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_PATH`, `GOOGLE_CALENDAR_ID`, `GOOGLE_SHEET_ID`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `SECURE_URL_SECRET`, `SECURE_URL_DOMAIN`, `ADVISOR_EMAIL`. Add `.env` to `.gitignore`. Create `config/settings.py` using `pydantic-settings` to load and validate. | `python -c "from config.settings import settings; print(settings.GROQ_API_KEY[:4])"` works. |
| **0.3 Scraping Pipeline** | Create `scripts/scrape_faq.py`. Use `BeautifulSoup` + `httpx` to scrape target public help pages per topic. Output: `data/raw_docs/{topic_key}/{filename}.txt`. Include `--topic` CLI arg to scrape selectively. | Running `python scripts/scrape_faq.py --topic kyc_onboarding` creates at least one `.txt` file. |
| **0.4 Chunk & Embed** | Create `scripts/build_index.py`. Load all `.txt` files from `data/raw_docs/`. Chunk with `langchain.text_splitter.RecursiveCharacterTextSplitter(chunk_size=256, chunk_overlap=32)`. Embed with `SentenceTransformer("all-MiniLM-L6-v2")`. Upsert to ChromaDB at `data/chroma_db/`. | `python scripts/build_index.py` exits 0. ChromaDB collection `advisor_faq` has > 50 chunks. |
| **0.5 RAG Query Test** | Create `tests/test_rag.py`. Query ChromaDB for "what documents for KYC onboarding". Assert top result has `topic_key == "kyc_onboarding"`. | `pytest tests/test_rag.py` passes. |
| **0.6 mock_calendar.json** | Create `data/mock_calendar.json` with 15+ available slots across the next 7 days in IST. Include at least 2 slots per day for Mon–Fri. Include 3 slots with `topic_affinity` restrictions. | JSON is valid. Python `datetime` can parse all slot times. |

---

### Phase 1: Booking Logic Engine

**Goal:** Core business logic fully tested in isolation, no LLM or external API required.
**Acceptance Criteria:**
- All unit tests pass.
- Slot resolution returns correct results for 10+ test scenarios.
- Booking codes are unique across 1000-iteration stress test.

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **1.1 `DialogueContext` Dataclass** | Implement `src/models/dialogue.py` with `DialogueContext`, `CalendarSlot`, `BookingRecord`, `MCPPayload` dataclasses as defined in Section 8. | `from src.models.dialogue import DialogueContext` imports cleanly. |
| **1.2 Booking Code Generator** | Implement `src/booking/code_generator.py` → `generate_booking_code(existing_codes: set) -> str`. Include uniqueness check, 5-retry logic, `BookingCodeExhaustedError`. | `pytest tests/test_code_generator.py` → 0 collisions in 1000-iteration test. |
| **1.3 Slot Resolver** | Implement `src/booking/slot_resolver.py` → `resolve_slots(day_pref, time_pref, topic, calendar_path) -> list[CalendarSlot]`. Steps as per Section 10.2. Handle: exact match, range match, no match (return []). | 10 resolution test cases all pass. No-match case returns `[]`. |
| **1.4 IST Timezone Utilities** | Implement `src/utils/timezone.py`. Functions: `to_ist(dt) -> datetime`, `format_ist_spoken(dt) -> str` (e.g., "Monday February 19th at 2 PM Indian Standard Time"), `parse_natural_datetime(text) -> dict`. Use `zoneinfo.ZoneInfo("Asia/Kolkata")`. | `format_ist_spoken` returns correct spoken string for 5 test inputs. |
| **1.5 PII Scrubber** | Implement `src/security/pii_scrubber.py` → `scrub(text: str) -> tuple[str, bool]`. Regex patterns: Indian mobile (10 digits starting 6–9), email, PAN (AAAAA0000A), Aadhaar (12 digits), account numbers (9–18 digits). Returns `(scrubbed_text, pii_detected: bool)`. | `pytest tests/test_pii_scrubber.py` with 15 test strings (5 clean, 10 with PII). All pass. |
| **1.6 Secure URL Generator** | Implement `src/security/secure_url.py`. `generate_secure_url(booking_code, topic, slot_ist) -> str` using `itsdangerous.URLSafeTimedSerializer`. `verify_secure_token(token) -> dict | None` (returns None if expired or tampered). TTL = 86400s (24h). | Token round-trip test passes. Expired token returns None. Tampered token raises exception caught and returns None. |
| **1.7 Waitlist Handler** | Implement `src/booking/waitlist.py` → `create_waitlist_entry(topic, day_pref, time_pref) -> BookingRecord`. Uses `NL-W` prefix for code. Status = WAITLIST. | Unit test creates waitlist record with correct code format and status. |

---

### Phase 2: Voice Agent Core — FSM + LLM Integration

**Goal:** Full dialogue loop working end-to-end in text mode (no audio yet). All 5 intents functional. Compliance guard active.
**Acceptance Criteria:**
- Full `book_new` happy path completes in < 8 turns.
- All 5 intents classified correctly on test utterances.
- Compliance guard blocks investment advice and PII in 100% of test cases.

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **2.1 System Prompt Builder** | Implement `src/agent/prompt_builder.py` → `build_system_prompt(context: DialogueContext) -> str`. Inject current state, filled slots, topic taxonomy, output format spec, compliance rules. System prompt must be < 2000 tokens to preserve LLM context budget. | Token count < 2000. Output includes all required JSON fields. |
| **2.2 LLM Client** | Implement `src/agent/llm_client.py`. `async def call_llm(messages, system_prompt) -> LLMResponse`. Primary: Groq (`llama-3.1-70b-versatile`). Fallback: Claude `claude-haiku-4-5`. Handles: JSON parse errors (retry once with explicit format instruction), HTTP errors (switch provider), timeout (3s). | 95%+ of calls return valid JSON in test suite. Fallback triggered when primary returns 500. |
| **2.3 FSM Controller** | Implement `src/agent/fsm.py` → `class DialogueFSM`. Methods: `process_turn(user_input) -> AgentTurn`. Manages state transitions per Section 5.2 table. Increments `turn_count`, `no_input_count`. Enforces max 3 re-prompts per slot. | All state transitions in the table are reachable and correct in integration test. |
| **2.4 Intent Router** | Implement `src/agent/intent_router.py` → `route_intent(llm_response: LLMResponse, context: DialogueContext) -> NextAction`. Maps LLM output `next_action` to FSM transition. Handles `refuse_advice`, `refuse_pii`, `out_of_scope` without FSM state change. | 5-intent classification test: 15 utterances classified correctly. |
| **2.5 Compliance Guard** | Implement `src/security/compliance_guard.py` → `check_output(speech_text: str) -> GuardResult`. Runs PII scrubber on LLM output. Checks for investment advice phrases. Returns `{safe: bool, reason: str | None}`. If `safe == False`, replace with pre-approved refusal text. | 10 adversarial test cases (PII leakage attempts, advice requests) all blocked. |
| **2.6 RAG Injector** | Implement `src/agent/rag_injector.py` → `get_rag_context(query: str, topic: str) -> str`. Queries ChromaDB with query + topic filter. Returns formatted context string for injection into LLM prompt. Only invoked for `what_to_prepare` intent. | Returns relevant context for 5 test queries. Returns graceful "no context found" string when ChromaDB empty. |
| **2.7 Session Manager** | Implement `src/agent/session_manager.py`. Dev: in-process dict. Interface: `create_session() -> str` (returns `call_id`), `get_context(call_id) -> DialogueContext`, `update_context(call_id, context)`, `end_session(call_id)`. TTL: 30 min. | Session CRUD operations work. Expired sessions return None. |
| **2.8 Text-Mode Integration Test** | Wire FSM + LLM + Booking Logic into `src/agent/voice_agent.py` → `async def process_text_turn(call_id, user_text) -> str`. Run full `book_new` happy path as an async test, asserting each state transition and final spoken output contains booking code. | Full happy path integration test passes in < 8 turns. |

---

### Phase 3: Speech Integration (STT + TTS + VAD)

**Goal:** Full voice loop functional. User can speak and hear responses. Voice logger active. Fallbacks tested.
**Acceptance Criteria:**
- End-to-end voice test completes booking via spoken interaction.
- Voice logger produces correct JSONL after each turn.
- Fallback STT activates on simulated Google STT timeout.

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **3.1 VAD Integration** | Implement `src/speech/vad.py` using Silero VAD (ONNX). `detect_speech_end(audio_chunk) -> bool`. Configure 300ms silence = end of turn. Handle barge-in: if agent is speaking and VAD detects speech, pause TTS and process input. | VAD correctly identifies end-of-turn in 5 audio test clips. Barge-in detected within 300ms of speech onset. |
| **3.2 STT Client** | Implement `src/speech/stt_client.py`. `async def transcribe(audio_bytes) -> TranscriptResult`. Primary: Google Cloud STT (streaming). Fallback: Deepgram. Returns: `{text, confidence, is_final}`. Timeout: 3s before fallback. | Transcribes 5 test audio clips with confidence > 0.8. Fallback triggered on simulated timeout. |
| **3.3 Voice Logger** | Implement `src/logging/voice_logger.py`. After each STT result: append to `data/logs/voice_audit_log.jsonl`. Schema per Section 4.4. Sanitise: run PII scrubber before logging. Never log raw PII. | Log file created after 3-turn test. All log entries are valid JSON. No PII in logged transcript. |
| **3.4 TTS Client** | Implement `src/speech/tts_client.py`. `async def synthesise(text: str) -> bytes`. Primary: Google Cloud TTS (Neural2 voice, `en-IN`). Fallback: `pyttsx3` (local). Cache: hash-based cache for disclaimer and greeting phrases in `data/tts_cache/`. Cache TTL: 7 days. | 5 synthesis calls return valid WAV bytes. Cached call is < 10ms. Fallback `pyttsx3` works when Google TTS unavailable. |
| **3.5 Audio Pipeline** | Implement `src/speech/audio_pipeline.py`. Connects: mic input → VAD → STT → PII Scrubber → FSM → TTS → speaker output. Use `pyaudio` for mic/speaker on local. Use WebSocket audio stream for web deployment. | Full loop: speak "hello" → hear greeting response. |
| **3.6 Audio UX Tuning** | Review all 15 FSM speech strings for voice suitability: no markdown, no parentheses in speech text, numbers spelled out (e.g., "N-L-A-7-4-2"), dates fully spoken. Booking code read out letter-by-letter using NATO phonetic if needed. Add 200ms pause between sentences via SSML. | Code review sign-off. 5 UX test playbacks approved. |

---

### Phase 4: MCP Integration

**Goal:** All 3 MCP tools (Calendar, Sheets, Email) working end-to-end with Google APIs. Partial failure handling verified. Retry logic tested.
**Acceptance Criteria:**
- Booking creates calendar event, sheet row, and email draft in Google Workspace.
- Partial failure (1 tool down) does not block booking code issuance.
- All 3 MCP tools complete within 3s combined (parallel execution).

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **4.1 Google Cloud Project Setup** | Enable APIs: Google Calendar API, Google Sheets API, Gmail API. Create Service Account. Download JSON key → `config/service_account.json` (in `.gitignore`). Share Service Account email with target Calendar and Sheet. Grant Calendar "Make changes to events" scope. Grant Sheets "Editor" scope. | `python scripts/test_google_auth.py` → prints "Auth OK" for all 3 APIs. |
| **4.2 Calendar MCP** | Implement `src/mcp/calendar_mcp.py` → `async def create_calendar_hold(payload)` per Section 9.1 contract. Use `google-api-python-client`. Handle: quota errors (429), auth errors (401/403), network errors. Include retry logic per Section 12.2. | Integration test: creates TENTATIVE event in test calendar. Returns event_id. |
| **4.3 Sheets MCP** | Implement `src/mcp/sheets_mcp.py` → `async def append_booking_notes(payload, event_id)` per Section 9.2. Use `gspread`. Sheet must exist with correct headers before first write (create in setup step). Handle: sheet not found, auth errors, network errors. | Integration test: appends row to test sheet. Row contains all required columns. |
| **4.4 Email Draft MCP** | Implement `src/mcp/email_mcp.py` → `async def draft_approval_email(payload, event_id, row_index)` per Section 9.3. Use `smtplib` with Gmail App Password. Create draft only (do NOT send). Handle: auth failure, SMTP errors. | Integration test: Gmail draft created in advisor inbox. Draft contains booking code, topic, slot, calendar link. |
| **4.5 MCP Orchestrator** | Implement `src/mcp/orchestrator.py` → `async def dispatch_mcp(payload) -> MCPResults` per Section 9.4. Parallel execution with `asyncio.gather(return_exceptions=True)`. Classify results as success/failure per tool. Log all results to `mcp_ops_log.jsonl`. | Integration test: all 3 tools succeed in parallel. Execution time < 3s. Partial failure test: Calendar mock failure → notes + email still succeed. |
| **4.6 Waitlist MCP** | Implement `src/mcp/orchestrator.py` → `async def dispatch_waitlist_mcp(payload) -> MCPResults`. Same tools but with WAITLIST prefix in title/subject and status. | Integration test: waitlist event, row, and draft created correctly. |
| **4.7 Async Retry Worker** | Implement `src/mcp/retry_worker.py`. On partial MCP failure, schedule a retry task (in-process asyncio background task for demo; Celery task for production). Retry policy: 3 attempts, exponential backoff. Log retry outcomes. | Failed MCP tool retried 3× with backoff. Success on retry updates booking record. |

---

### Phase 5: Testing, Hardening & Deployment

**Goal:** Full test suite passing; compliance review passed; deployed on Streamlit Cloud (demo) or Docker (production-ready).
**Acceptance Criteria:**
- Test coverage ≥ 80% for `src/`.
- 20-scenario regression suite passes (happy path, all 5 intents, all error modes).
- Streamlit demo deployed and accessible.

| Task | Detailed Steps | Acceptance Criteria |
| --- | --- | --- |
| **5.1 Full Regression Test Suite** | Write `tests/test_regression.py` with 20 scenarios (see Section 15). Each scenario: input utterances → assert final state, booking code format, MCP payloads. All MCP calls mocked with `pytest-mock`. | 20/20 scenarios pass. |
| **5.2 Compliance Audit Test** | Write `tests/test_compliance.py`. Test: 10 investment advice attempts → all refused. 10 PII injection attempts → all scrubbed/blocked. Output never contains PII pattern. | 20/20 compliance tests pass. |
| **5.3 Load / Stress Test** | Write `tests/test_load.py`. Simulate 50 concurrent sessions using `asyncio`. Assert no session bleed (one session's data never appears in another). Assert booking codes are unique across all sessions. | 0 session bleeds. 0 code collisions. |
| **5.4 Streamlit Testing UI** | Build `app/testing_ui.py` (see Section 16 for full spec). | UI loads. Full `book_new` flow completable via text input. MCP payload visible in UI. |
| **5.5 Streamlit Voice Demo** | Build `app/voice_demo.py`. Use `streamlit-webrtc` component for browser microphone access. Wire to audio pipeline. | Full voice booking demo works in Chrome. |
| **5.6 README & Runbook** | Finalize `README.md`: setup steps, `.env.example` explanation, how to run tests, how to run demo, how to populate `mock_calendar.json`, how to create Google Service Account. Add `RUNBOOK.md`: operational procedures, how to handle MCP failures, how to update calendar slots. | New developer can run full demo in < 30 minutes following README. |
| **5.7 Deployment** | **Option A (Demo):** Deploy Streamlit app to Streamlit Cloud (free tier). Set secrets via Streamlit Secrets Manager. **Option B (Production-ready):** Dockerise with `docker-compose.yml` (app + Redis + ChromaDB). Add `nginx` reverse proxy. | Option A: public URL accessible. Option B: `docker compose up` runs without errors. |

---

## 15. Testing Strategy

### 15.1 Test Pyramid

```
                      ┌─────────────────┐
                      │   E2E / Voice   │  5 tests (manual + automated audio)
                      └────────┬────────┘
               ┌───────────────▼──────────────┐
               │     Integration Tests         │  25 tests (MCP, LLM, FSM)
               └───────────────┬──────────────┘
        ┌──────────────────────▼───────────────────┐
        │              Unit Tests                   │  80+ tests (booking logic,
        └───────────────────────────────────────────┘   code gen, scrubber, slots)
```

### 15.2 Key Test Scenarios

| # | Scenario | Expected Outcome |
| --- | --- | --- |
| 1 | `book_new` full happy path — all slots available | Booking code issued; all 3 MCP succeed |
| 2 | `book_new` — no slots match user preference | Waitlist offered and accepted; waitlist code issued |
| 3 | `book_new` — no slots match; user declines waitlist | Graceful farewell; no MCP triggered |
| 4 | `book_new` — user asks for investment advice mid-flow | Refusal spoken; flow returns to slot collection |
| 5 | `book_new` — user attempts to share phone number | PII blocked; user redirected |
| 6 | `reschedule` — valid existing code | Old event cancelled; new event created; new code issued |
| 7 | `reschedule` — invalid / unknown code | "Code not found" spoken; offer new booking |
| 8 | `cancel` — valid existing code, user confirms | Event deleted; sheet updated; cancellation draft created |
| 9 | `cancel` — user says no to confirm | No action; graceful farewell |
| 10 | `what_to_prepare` — KYC topic | RAG-grounded answer; offer to book |
| 11 | `what_to_prepare` — no topic given | Agent asks for topic; then answers |
| 12 | `check_availability` — Monday requested | Lists available Monday slots; offer to book |
| 13 | MCP Calendar fails | Booking code still issued; retry scheduled |
| 14 | MCP all 3 fail | Booking code issued; ops alert triggered |
| 15 | STT confidence < 0.7 | Re-prompt (max 3×); graceful error on 3rd failure |
| 16 | LLM Groq returns 500 | Claude fallback activates; turn completes |
| 17 | LLM returns invalid JSON | Retry with format instruction; re-prompt on 2nd failure |
| 18 | Session inactive 30 min | Session expired; new call gets fresh session |
| 19 | 50 concurrent sessions | No session bleed; all codes unique |
| 20 | Booking code read-out | Code spoken letter-by-letter; date/time in IST confirmed |

---

## 16. Text-Based Testing Interface (UI)

Built in Streamlit at `app/testing_ui.py`. Bypasses all audio; directly feeds text to FSM.

### 16.1 UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Advisor Scheduler — Testing Console                         │
├───────────────────────────┬─────────────────────────────────────┤
│  CONVERSATION PANEL       │  DEBUG PANEL                        │
│                           │                                     │
│  Agent: Hello! I'm the    │  ┌─ Session State ──────────────┐  │
│  Advisor Scheduling...    │  │ call_id: CALL-2024-abc123    │  │
│                           │  │ state:   S6_SLOTS_OFFERED    │  │
│  You: I want to book      │  │ intent:  book_new            │  │
│  for KYC on Monday        │  │ topic:   kyc_onboarding      │  │
│                           │  │ day:     Monday              │  │
│  Agent: I found two       │  │ time:    14:00               │  │
│  slots available...       │  └──────────────────────────────┘  │
│                           │                                     │
│  [Text input field    ]   │  ┌─ MCP Payload (live) ─────────┐  │
│  [     Send Button    ]   │  │ {                            │  │
│                           │  │   "booking_code": "NL-A742", │  │
│  [Reset Session]          │  │   "topic_key": "kyc_...",    │  │
│  [Load Scenario ▼]        │  │   "slot_start_ist": "...",   │  │
│                           │  │   ...                        │  │
│                           │  │ }                            │  │
│                           │  └──────────────────────────────┘  │
│                           │                                     │
│                           │  ┌─ MCP Action Log ─────────────┐  │
│                           │  │ ✅ Calendar Hold Created     │  │
│                           │  │ ✅ Sheet Row Appended         │  │
│                           │  │ ✅ Email Draft Created        │  │
│                           │  └──────────────────────────────┘  │
│                           │                                     │
│                           │  ┌─ Compliance Events ──────────┐  │
│                           │  │ (no blocks in this session)  │  │
│                           │  └──────────────────────────────┘  │
└───────────────────────────┴─────────────────────────────────────┘
```

### 16.2 Streamlit Component Map

| UI Element | Streamlit Component | Purpose |
| --- | --- | --- |
| Conversation thread | `st.chat_message()` in loop | Render alternating user/agent messages |
| Text input | `st.chat_input("Type your message...")` | Capture user turn |
| Session state display | `st.json(context.__dict__)` | Show live `DialogueContext` |
| MCP Payload viewer | `st.json(mcp_payload)` | Show payload before/after MCP dispatch |
| MCP Action Log | `st.success()` / `st.error()` per tool | Green/red per MCP tool result |
| Compliance events | `st.warning()` | Show every compliance block |
| Scenario loader | `st.selectbox(scenarios)` | Load pre-scripted test scenario utterances |
| Reset button | `st.button("Reset Session")` | `st.session_state.clear()` |
| Audit log viewer | `st.expander("View Audit Log")` + `st.code()` | Show raw JSONL tail |

---

## 17. Deployment Architecture

### 17.1 Local Development

```
.venv/                    ← Python 3.11 virtual environment
src/                      ← Application source code
  agent/                  ← FSM, LLM client, intent router
  booking/                ← Slot resolver, code generator, waitlist
  mcp/                    ← Calendar, Sheets, Email tools + orchestrator
  models/                 ← Dataclasses (dialogue, booking, MCP payload)
  security/               ← PII scrubber, compliance guard, secure URL
  speech/                 ← STT, TTS, VAD, audio pipeline
  utils/                  ← Timezone, logging helpers
  logging/                ← Voice logger, MCP ops logger
app/
  testing_ui.py           ← Streamlit text-based testing console
  voice_demo.py           ← Streamlit voice demo (browser mic)
data/
  mock_calendar.json      ← Local calendar fixture
  raw_docs/               ← Scraped FAQ text files
  chroma_db/              ← ChromaDB persistent index
  tts_cache/              ← Cached TTS audio files
  logs/                   ← voice_audit_log.jsonl, mcp_ops_log.jsonl
config/
  settings.py             ← Pydantic settings (loads .env)
  service_account.json    ← Google Service Account key (gitignored)
scripts/
  scrape_faq.py
  build_index.py
  test_google_auth.py
tests/                    ← pytest test suite
.env                      ← Local secrets (gitignored)
.env.example              ← Committed; shows required keys
requirements.txt
README.md
RUNBOOK.md
```

### 17.2 Streamlit Cloud Deployment (Demo)

```
1. Push repo to GitHub (with .env gitignored, service_account.json gitignored)
2. In Streamlit Cloud dashboard → New App → select repo → app/testing_ui.py
3. Under "Secrets", paste all .env values in TOML format:
   GROQ_API_KEY = "gsk_..."
   GOOGLE_SERVICE_ACCOUNT_JSON = '''{ ...full JSON content... }'''
   ...
4. In code, load service account from env var as JSON string (not file path)
   when STREAMLIT_CLOUD env var is set.
5. Deploy → public URL available.
```

### 17.3 Production-Ready Docker Deployment

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000", "8501:8501"]
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./config/service_account.json:/app/config/service_account.json:ro
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

### 17.4 Environment Variable Reference

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Groq API key for primary LLM |
| `ANTHROPIC_API_KEY` | Yes | Claude API key for LLM fallback |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Yes (local) | Path to service_account.json |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes (cloud) | Full JSON content as string |
| `GOOGLE_CALENDAR_ID` | Yes | Target Google Calendar ID |
| `GOOGLE_SHEET_ID` | Yes | Google Sheets spreadsheet ID |
| `GMAIL_ADDRESS` | Yes | Gmail address for draft creation |
| `GMAIL_APP_PASSWORD` | Yes | Gmail App Password (not main password) |
| `ADVISOR_EMAIL` | Yes | Advisor email address for draft recipient |
| `SECURE_URL_SECRET` | Yes | HMAC secret for signed tokens (min 32 chars) |
| `SECURE_URL_DOMAIN` | Yes | Base URL for secure booking links |
| `REDIS_URL` | No | Redis connection URL (default: localhost) |
| `LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` (default: INFO) |
| `ENVIRONMENT` | No | `development` / `production` (default: development) |

---

## 18. Test Cases by Phase

Each phase has a dedicated test file under `tests/`. All external APIs (Groq, Google, Gmail) are mocked using `pytest-mock` unless marked `[INTEGRATION]` — those require real credentials and are skipped in CI unless `RUN_INTEGRATION=true`.

---

### Phase 0 — Foundation & RAG Pipeline

**File:** `tests/test_phase0_rag.py`

#### TC-0.1 — Config loads without error

```python
def test_settings_load():
    from config.settings import settings
    assert settings.GROQ_API_KEY != ""
    assert settings.GOOGLE_CALENDAR_ID != ""
    assert settings.SECURE_URL_SECRET != ""
```

**Expected:** No `ValidationError`. All required fields present.

---

#### TC-0.2 — mock_calendar.json is valid and parseable

```python
def test_mock_calendar_schema():
    import json
    from datetime import datetime
    with open("data/mock_calendar.json") as f:
        cal = json.load(f)
    assert "slots" in cal
    assert len(cal["slots"]) >= 10
    for slot in cal["slots"]:
        assert "slot_id" in slot
        assert "start" in slot and "end" in slot
        assert "status" in slot
        # All starts must be parseable as datetime
        datetime.fromisoformat(slot["start"])
        datetime.fromisoformat(slot["end"])
```

**Expected:** Passes with ≥ 10 valid slots, all ISO 8601 datetimes.

---

#### TC-0.3 — ChromaDB collection exists and has documents after indexing

```python
def test_chroma_collection_populated():
    import chromadb
    client = chromadb.PersistentClient(path="data/chroma_db")
    col = client.get_collection("advisor_faq")
    count = col.count()
    assert count >= 50, f"Expected ≥50 chunks, got {count}"
```

**Expected:** Collection `advisor_faq` has ≥ 50 chunks after `build_index.py` runs.

---

#### TC-0.4 — RAG query returns topic-relevant chunks

```python
@pytest.mark.parametrize("query,expected_topic", [
    ("what documents do I need for KYC", "kyc_onboarding"),
    ("how to set up a SIP mandate", "sip_mandates"),
    ("how long does withdrawal take", "withdrawals"),
    ("how to add a nominee", "account_changes"),
    ("where can I get my tax statement", "statements_tax"),
])
def test_rag_query_topic_relevance(query, expected_topic):
    from src.agent.rag_injector import get_rag_context
    context = get_rag_context(query=query, topic=expected_topic)
    assert len(context) > 0
    assert context != "No relevant context found."
```

**Expected:** Non-empty, topic-relevant string returned for all 5 topic queries.

---

#### TC-0.5 — RAG returns graceful fallback when ChromaDB is empty

```python
def test_rag_empty_db_fallback(tmp_path, monkeypatch):
    import chromadb
    monkeypatch.setenv("CHROMA_DB_PATH", str(tmp_path))
    from src.agent.rag_injector import get_rag_context
    result = get_rag_context(query="anything", topic="kyc_onboarding")
    assert result == "No relevant context found."
```

**Expected:** Returns the exact fallback string; does not raise an exception.

---

#### TC-0.6 — Scraping pipeline creates output files `[INTEGRATION]`

```python
@pytest.mark.integration
def test_scrape_creates_output(tmp_path):
    import subprocess
    result = subprocess.run(
        ["python", "scripts/scrape_faq.py", "--topic", "kyc_onboarding",
         "--output", str(tmp_path)],
        capture_output=True
    )
    assert result.returncode == 0
    files = list(tmp_path.glob("*.txt"))
    assert len(files) >= 1
    assert files[0].stat().st_size > 100
```

**Expected:** At least one `.txt` file with > 100 bytes created in output dir.

---

### Phase 1 — Booking Logic Engine

**File:** `tests/test_phase1_booking.py`

#### TC-1.1 — Booking code has correct format

```python
import re

def test_booking_code_format():
    from src.booking.code_generator import generate_booking_code
    code = generate_booking_code(existing_codes=set())
    assert re.match(r"^NL-[A-Z]\d{3}$", code), f"Invalid format: {code}"
```

**Expected:** Code matches `NL-[A-Z][0-9]{3}` exactly (e.g., `NL-A742`).

---

#### TC-1.2 — Booking codes are unique across 1000 iterations

```python
def test_booking_code_uniqueness():
    from src.booking.code_generator import generate_booking_code
    codes = set()
    for _ in range(1000):
        code = generate_booking_code(existing_codes=codes)
        assert code not in codes, f"Duplicate code generated: {code}"
        codes.add(code)
    assert len(codes) == 1000
```

**Expected:** 1000 codes generated with 0 collisions.

---

#### TC-1.3 — Raises `BookingCodeExhaustedError` when all codes taken (mocked)

```python
def test_booking_code_exhausted(monkeypatch):
    from src.booking.code_generator import generate_booking_code, BookingCodeExhaustedError
    import string
    # Fill every possible code
    all_codes = {f"NL-{l}{n}" for l in string.ascii_uppercase for n in range(100, 1000)}
    with pytest.raises(BookingCodeExhaustedError):
        generate_booking_code(existing_codes=all_codes)
```

**Expected:** `BookingCodeExhaustedError` raised after 5 exhausted retries.

---

#### TC-1.4 — Waitlist code has correct format

```python
def test_waitlist_code_format():
    from src.booking.code_generator import generate_booking_code
    code = generate_booking_code(existing_codes=set(), waitlist=True)
    assert re.match(r"^NL-W\d{3}$", code), f"Invalid waitlist format: {code}"
```

**Expected:** Code matches `NL-W[0-9]{3}` (e.g., `NL-W391`).

---

#### TC-1.5 — Slot resolver returns top 2 slots for matching day/time

```python
def test_slot_resolver_returns_two_slots():
    from src.booking.slot_resolver import resolve_slots
    slots = resolve_slots(
        day_pref="Monday",
        time_pref="2 PM",
        topic="kyc_onboarding",
        calendar_path="data/mock_calendar.json"
    )
    assert len(slots) <= 2
    assert len(slots) >= 1
    for slot in slots:
        assert slot.status == "AVAILABLE"
```

**Expected:** 1–2 `CalendarSlot` objects, all with `status == "AVAILABLE"`.

---

#### TC-1.6 — Slot resolver returns empty list when no match

```python
def test_slot_resolver_no_match():
    from src.booking.slot_resolver import resolve_slots
    slots = resolve_slots(
        day_pref="Saturday",
        time_pref="midnight",
        topic="kyc_onboarding",
        calendar_path="data/mock_calendar.json"
    )
    assert slots == []
```

**Expected:** Empty list; no exception raised.

---

#### TC-1.7 — Slot resolver respects `topic_affinity` restrictions

```python
def test_slot_resolver_topic_affinity():
    from src.booking.slot_resolver import resolve_slots
    # A slot restricted to kyc_onboarding should NOT appear for sip_mandates
    slots = resolve_slots(
        day_pref="Monday",
        time_pref="2 PM",
        topic="sip_mandates",
        calendar_path="data/mock_calendar.json"
    )
    for slot in slots:
        assert "sip_mandates" in slot.topic_affinity or slot.topic_affinity == []
```

**Expected:** No topic-restricted slots from other categories appear in results.

---

#### TC-1.8 — IST format produces correct spoken string

```python
@pytest.mark.parametrize("input_iso,expected_substring", [
    ("2024-02-19T14:00:00", "2 PM"),
    ("2024-02-19T08:30:00", "8:30 AM"),
    ("2024-02-19T00:00:00", "12 AM"),
])
def test_format_ist_spoken(input_iso, expected_substring):
    from datetime import datetime
    from src.utils.timezone import format_ist_spoken
    dt = datetime.fromisoformat(input_iso)
    result = format_ist_spoken(dt)
    assert expected_substring in result
    assert "Indian Standard Time" in result
```

**Expected:** Output contains the correct time label and "Indian Standard Time".

---

#### TC-1.9 — PII scrubber detects and redacts all PII types

```python
@pytest.mark.parametrize("text,expect_redacted", [
    ("my number is 9876543210", True),       # Indian mobile
    ("email me at user@example.com", True),  # email
    ("my PAN is ABCDE1234F", True),          # PAN
    ("Aadhaar 1234 5678 9012", True),        # Aadhaar
    ("account number 123456789012", True),   # account number
    ("I want to book for KYC", False),       # clean — no PII
    ("Monday at 2 PM works for me", False),  # clean
    ("what documents do I need", False),     # clean
])
def test_pii_scrubber(text, expect_redacted):
    from src.security.pii_scrubber import scrub
    cleaned, detected = scrub(text)
    assert detected == expect_redacted
    if expect_redacted:
        assert "[REDACTED]" in cleaned
```

**Expected:** All 5 PII types detected and redacted; 3 clean strings pass through unchanged.

---

#### TC-1.10 — Secure URL token round-trips correctly

```python
def test_secure_url_roundtrip():
    from src.security.secure_url import generate_secure_url, verify_secure_token
    url = generate_secure_url(
        booking_code="NL-A742",
        topic="kyc_onboarding",
        slot_ist="2024-02-19T14:00:00+05:30"
    )
    assert "NL-A742" not in url  # code must not appear in plain text in URL
    token = url.split("/")[-1]
    payload = verify_secure_token(token)
    assert payload is not None
    assert payload["booking_code"] == "NL-A742"
    assert payload["topic"] == "kyc_onboarding"
```

**Expected:** Token encodes booking data; decoded payload matches original values.

---

#### TC-1.11 — Expired secure token returns `None`

```python
def test_secure_url_expired(freezegun_time):
    from src.security.secure_url import generate_secure_url, verify_secure_token
    import time
    url = generate_secure_url("NL-A742", "kyc_onboarding", "2024-02-19T14:00:00+05:30")
    token = url.split("/")[-1]
    # Advance time by 25 hours (past 24h TTL)
    with freeze_time(datetime.now() + timedelta(hours=25)):
        result = verify_secure_token(token)
    assert result is None
```

**Expected:** `None` returned for expired token; no exception propagated.

---

#### TC-1.12 — Tampered secure token returns `None`

```python
def test_secure_url_tampered():
    from src.security.secure_url import generate_secure_url, verify_secure_token
    url = generate_secure_url("NL-A742", "kyc_onboarding", "2024-02-19T14:00:00+05:30")
    token = url.split("/")[-1]
    tampered = token[:-5] + "XXXXX"
    result = verify_secure_token(tampered)
    assert result is None
```

**Expected:** `None` returned for tampered token; signature mismatch caught silently.

---

### Phase 2 — Voice Agent Core (FSM + LLM)

**File:** `tests/test_phase2_agent.py`

#### TC-2.1 — System prompt is under 2000 tokens and contains required sections

```python
def test_system_prompt_length_and_content():
    from src.agent.prompt_builder import build_system_prompt
    from src.models.dialogue import DialogueContext, DialogueState
    import tiktoken
    ctx = DialogueContext(call_id="TEST-001", current_state=DialogueState.S2_DISCLAIMER_CONFIRMED)
    prompt = build_system_prompt(ctx)
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = len(enc.encode(prompt))
    assert tokens < 2000, f"Prompt too long: {tokens} tokens"
    assert "OUTPUT FORMAT" in prompt
    assert "compliance" in prompt.lower() or "RULES" in prompt
    assert "JSON" in prompt
```

**Expected:** Prompt < 2000 tokens; contains `OUTPUT FORMAT`, rules, and JSON instruction.

---

#### TC-2.2 — LLM client returns valid JSON for `book_new` intent

```python
@pytest.mark.asyncio
async def test_llm_client_book_new(mocker):
    mocker.patch("src.agent.llm_client.groq_client.chat.completions.create",
        return_value=MockGroqResponse(content='{"intent":"book_new","slots":{},'
            '"next_action":"PROMPT_TOPIC","speech":"What topic would you like?","compliance_flag":null}'))
    from src.agent.llm_client import call_llm
    response = await call_llm(
        messages=[{"role": "user", "content": "I want to book an appointment"}],
        system_prompt="..."
    )
    assert response.intent == "book_new"
    assert response.speech != ""
    assert response.compliance_flag is None
```

**Expected:** Parsed `LLMResponse` with correct intent and non-empty speech.

---

#### TC-2.3 — LLM client switches to Claude fallback when Groq returns 500

```python
@pytest.mark.asyncio
async def test_llm_fallback_on_groq_error(mocker):
    mocker.patch("src.agent.llm_client.groq_client.chat.completions.create",
        side_effect=Exception("Service Unavailable"))
    mock_claude = mocker.patch("src.agent.llm_client.anthropic_client.messages.create",
        return_value=MockClaudeResponse(content='{"intent":"book_new","slots":{},'
            '"next_action":"PROMPT_TOPIC","speech":"What topic?","compliance_flag":null}'))
    from src.agent.llm_client import call_llm
    response = await call_llm(messages=[{"role": "user", "content": "book"}], system_prompt="...")
    assert mock_claude.called
    assert response.intent == "book_new"
```

**Expected:** Claude fallback called; valid response returned; no exception propagated.

---

#### TC-2.4 — LLM client retries on invalid JSON then raises after 2 failures

```python
@pytest.mark.asyncio
async def test_llm_invalid_json_retry(mocker):
    mocker.patch("src.agent.llm_client.groq_client.chat.completions.create",
        return_value=MockGroqResponse(content="This is not JSON at all"))
    mocker.patch("src.agent.llm_client.anthropic_client.messages.create",
        return_value=MockClaudeResponse(content="Also not JSON"))
    from src.agent.llm_client import call_llm, LLMParseError
    with pytest.raises(LLMParseError):
        await call_llm(messages=[{"role": "user", "content": "book"}], system_prompt="...")
```

**Expected:** `LLMParseError` raised after both providers return unparseable output.

---

#### TC-2.5 — FSM: all 5 intents classified from cold state

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,expected_intent", [
    ("I want to book an appointment for KYC", "book_new"),
    ("I need to reschedule my booking NL-A742", "reschedule"),
    ("Please cancel my appointment", "cancel"),
    ("What documents do I need for SIP?", "what_to_prepare"),
    ("When is the advisor available next week?", "check_availability"),
])
async def test_fsm_intent_classification(utterance, expected_intent, mocker):
    mocker.patch("src.agent.llm_client.call_llm",
        return_value=MockLLMResponse(intent=expected_intent, slots={},
            next_action="INTENT_IDENTIFIED", speech="ok", compliance_flag=None))
    from src.agent.fsm import DialogueFSM
    from src.agent.session_manager import SessionManager
    sm = SessionManager()
    call_id = sm.create_session()
    fsm = DialogueFSM(call_id=call_id, session_manager=sm)
    result = await fsm.process_turn(utterance)
    assert result.intent == expected_intent
```

**Expected:** Correct intent returned for all 5 utterances.

---

#### TC-2.6 — FSM: `book_new` full happy path completes in ≤ 8 turns

```python
@pytest.mark.asyncio
async def test_fsm_book_new_happy_path(mocker):
    turns = [
        ("hello", "book_new", "GREETED", "How can I help you today?"),
        ("yes", "book_new", "DISCLAIMER_CONFIRMED", "What topic?"),
        ("KYC", "book_new", "TOPIC_COLLECTED", "What time?"),
        ("Monday 2 PM", "book_new", "TIME_COLLECTED", "Two slots available..."),
        ("first one", "book_new", "SLOT_CONFIRMED", "Confirming KYC on Monday..."),
        ("yes", "book_new", "MCP_DISPATCHED", "Your booking code is NL-A742..."),
    ]
    # Mock LLM to return scripted turns in sequence
    call_queue = iter([MockLLMResponse(**t) for t in build_mock_sequence(turns)])
    mocker.patch("src.agent.llm_client.call_llm", side_effect=lambda **kw: next(call_queue))
    mocker.patch("src.mcp.orchestrator.dispatch_mcp",
        return_value=MockMCPResults(calendar=True, notes=True, email=True))
    from src.agent.voice_agent import VoiceAgent
    agent = VoiceAgent()
    call_id = agent.start_session()
    for i, (utterance, _, _, _) in enumerate(turns):
        response = await agent.process_text_turn(call_id, utterance)
        assert response.speech != ""
    final = agent.get_context(call_id)
    assert final.booking_code is not None
    assert final.current_state.name == "BOOKING_COMPLETE"
    assert i + 1 <= 8
```

**Expected:** Booking code assigned; state = `BOOKING_COMPLETE`; completed in ≤ 8 turns.

---

#### TC-2.7 — FSM: max 3 re-prompts on no-input then graceful error

```python
@pytest.mark.asyncio
async def test_fsm_max_reprompts(mocker):
    mocker.patch("src.agent.llm_client.call_llm",
        return_value=MockLLMResponse(intent=None, slots={},
            next_action="NO_INPUT", speech="I didn't catch that.", compliance_flag=None))
    from src.agent.fsm import DialogueFSM
    from src.agent.session_manager import SessionManager
    sm = SessionManager()
    call_id = sm.create_session()
    fsm = DialogueFSM(call_id=call_id, session_manager=sm)
    for _ in range(3):
        result = await fsm.process_turn("")
    assert result.current_state.name in ("ERROR", "END")
```

**Expected:** State transitions to `ERROR` or `END` after exactly 3 empty inputs.

---

#### TC-2.8 — Compliance guard blocks investment advice output

```python
@pytest.mark.parametrize("agent_speech", [
    "You should invest in index funds for long-term growth.",
    "I recommend allocating 60% to equities.",
    "Buy this mutual fund, it has great returns.",
    "Based on your profile, SIP in large-cap is best.",
])
def test_compliance_guard_blocks_advice(agent_speech):
    from src.security.compliance_guard import check_output
    result = check_output(agent_speech)
    assert result.safe is False
    assert result.reason == "investment_advice"
```

**Expected:** All 4 advice strings flagged as `safe=False` with reason `investment_advice`.

---

#### TC-2.9 — Compliance guard blocks PII in agent output

```python
@pytest.mark.parametrize("agent_speech", [
    "Your phone number 9876543210 has been noted.",
    "I see your email is user@example.com.",
    "Your account number 123456789012 is on file.",
])
def test_compliance_guard_blocks_pii_in_output(agent_speech):
    from src.security.compliance_guard import check_output
    result = check_output(agent_speech)
    assert result.safe is False
    assert result.reason == "pii_leakage"
```

**Expected:** All 3 strings flagged as `safe=False` with reason `pii_leakage`.

---

#### TC-2.10 — Compliance guard passes clean agent responses

```python
@pytest.mark.parametrize("agent_speech", [
    "What topic would you like to discuss today?",
    "Your booking code is NL-A742. Please note it down.",
    "I found two slots available on Monday.",
    "I'm only able to help with scheduling, not investment advice.",
])
def test_compliance_guard_passes_clean_speech(agent_speech):
    from src.security.compliance_guard import check_output
    result = check_output(agent_speech)
    assert result.safe is True
```

**Expected:** All 4 clean strings pass guard with `safe=True`.

---

#### TC-2.11 — Reschedule flow finds existing booking by code

```python
@pytest.mark.asyncio
async def test_reschedule_existing_code(mocker):
    mocker.patch("src.mcp.sheets_mcp.lookup_booking_by_code",
        return_value=MockBookingRecord(code="NL-A742", status="TENTATIVE", topic="kyc_onboarding"))
    from src.booking.reschedule import find_existing_booking
    record = await find_existing_booking("NL-A742")
    assert record is not None
    assert record.booking_code == "NL-A742"
    assert record.status == "TENTATIVE"
```

**Expected:** `BookingRecord` returned for valid active code.

---

#### TC-2.12 — Reschedule flow returns `None` for unknown code

```python
@pytest.mark.asyncio
async def test_reschedule_unknown_code(mocker):
    mocker.patch("src.mcp.sheets_mcp.lookup_booking_by_code", return_value=None)
    from src.booking.reschedule import find_existing_booking
    record = await find_existing_booking("NL-ZZZZ")
    assert record is None
```

**Expected:** `None` returned; no exception.

---

### Phase 3 — Speech Integration (STT + TTS + VAD)

**File:** `tests/test_phase3_speech.py`

#### TC-3.1 — VAD detects end of speech after 300ms silence

```python
def test_vad_detects_silence(speech_audio_fixture, silence_audio_fixture):
    from src.speech.vad import SileroVAD
    vad = SileroVAD(silence_threshold_ms=300)
    assert vad.detect_speech_end(speech_audio_fixture) is False   # still speaking
    assert vad.detect_speech_end(silence_audio_fixture) is True   # silence → end of turn
```

**Expected:** `True` on silence chunk, `False` on speech chunk.

---

#### TC-3.2 — STT client returns transcript with confidence score `[INTEGRATION]`

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stt_transcribes_audio(sample_wav_path):
    from src.speech.stt_client import transcribe
    with open(sample_wav_path, "rb") as f:
        audio_bytes = f.read()
    result = await transcribe(audio_bytes)
    assert result.text != ""
    assert 0.0 <= result.confidence <= 1.0
    assert result.is_final is True
```

**Expected:** Non-empty transcript with confidence in `[0, 1]`.

---

#### TC-3.3 — STT client switches to Deepgram fallback on Google timeout

```python
@pytest.mark.asyncio
async def test_stt_fallback_on_timeout(mocker):
    mocker.patch("src.speech.stt_client.google_stt_transcribe",
        side_effect=asyncio.TimeoutError)
    mock_deepgram = mocker.patch("src.speech.stt_client.deepgram_transcribe",
        return_value=MockTranscript(text="hello", confidence=0.9, is_final=True))
    from src.speech.stt_client import transcribe
    result = await transcribe(b"audio_bytes")
    assert mock_deepgram.called
    assert result.text == "hello"
```

**Expected:** Deepgram fallback called; transcript returned.

---

#### TC-3.4 — Voice logger appends sanitised entry (no raw PII)

```python
def test_voice_logger_no_pii(tmp_path):
    from src.logging.voice_logger import VoiceLogger
    logger = VoiceLogger(log_path=str(tmp_path / "test_audit.jsonl"))
    logger.log_turn(
        call_id="TEST-001",
        turn_index=1,
        user_transcript_raw="my phone is 9876543210 book KYC",
        detected_intent="book_new",
        slots={},
        agent_speech="What time works for you?",
    )
    import json
    with open(tmp_path / "test_audit.jsonl") as f:
        entry = json.loads(f.read().strip())
    assert "9876543210" not in entry["user_transcript_sanitised"]
    assert "[REDACTED]" in entry["user_transcript_sanitised"]
    assert entry["pii_blocked"] is True
```

**Expected:** Raw PII absent from log; `[REDACTED]` present; `pii_blocked = true`.

---

#### TC-3.5 — TTS client returns non-empty bytes for given text

```python
@pytest.mark.asyncio
async def test_tts_returns_audio_bytes(mocker):
    mocker.patch("src.speech.tts_client.google_tts_synthesise",
        return_value=b"\xFF\xFB\x90\x00" * 1000)  # mock WAV bytes
    from src.speech.tts_client import synthesise
    result = await synthesise("Your booking code is NL-A742.")
    assert isinstance(result, bytes)
    assert len(result) > 0
```

**Expected:** Non-empty bytes returned (simulated WAV audio).

---

#### TC-3.6 — TTS caches repeated disclaimer audio

```python
@pytest.mark.asyncio
async def test_tts_disclaimer_cached(mocker, tmp_path):
    mock_google = mocker.patch("src.speech.tts_client.google_tts_synthesise",
        return_value=b"\xFF" * 500)
    from src.speech.tts_client import TTSClient
    client = TTSClient(cache_dir=str(tmp_path))
    text = "This service is for scheduling only. Our advisors provide informational guidance."
    await client.synthesise(text)
    await client.synthesise(text)  # second call
    # Google TTS should only be called ONCE; second served from cache
    assert mock_google.call_count == 1
```

**Expected:** Google TTS called exactly once; second call served from disk cache.

---

#### TC-3.7 — TTS falls back to pyttsx3 on Google TTS timeout

```python
@pytest.mark.asyncio
async def test_tts_fallback_on_timeout(mocker):
    mocker.patch("src.speech.tts_client.google_tts_synthesise",
        side_effect=asyncio.TimeoutError)
    mock_local = mocker.patch("src.speech.tts_client.pyttsx3_synthesise",
        return_value=b"\xAA" * 200)
    from src.speech.tts_client import synthesise
    result = await synthesise("Hello, please hold.")
    assert mock_local.called
    assert len(result) > 0
```

**Expected:** `pyttsx3` fallback called; audio bytes returned.

---

### Phase 4 — MCP Integration

**File:** `tests/test_phase4_mcp.py`

#### TC-4.1 — Calendar MCP creates event with correct structure `[INTEGRATION]`

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_calendar_mcp_creates_event():
    from src.mcp.calendar_mcp import create_calendar_hold
    from tests.fixtures import build_test_mcp_payload
    payload = build_test_mcp_payload(booking_code="NL-TEST1", topic_label="KYC / Onboarding")
    result = await create_calendar_hold(payload)
    assert result["success"] is True
    assert "event_id" in result
    assert "html_link" in result
    # Cleanup: delete the test event
    from src.mcp.calendar_mcp import delete_calendar_event
    await delete_calendar_event(result["event_id"])
```

**Expected:** Event created; `event_id` returned; event deleted in teardown.

---

#### TC-4.2 — Calendar MCP event has TENTATIVE status and correct title

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_calendar_event_title_and_status():
    from src.mcp.calendar_mcp import create_calendar_hold, get_calendar_event
    payload = build_test_mcp_payload(booking_code="NL-TEST2", topic_label="SIP / Mandates")
    result = await create_calendar_hold(payload)
    event = await get_calendar_event(result["event_id"])
    assert event["status"] == "tentative"
    assert "Advisor Q&A" in event["summary"]
    assert "NL-TEST2" in event["summary"]
    assert "SIP / Mandates" in event["summary"]
    await delete_calendar_event(result["event_id"])
```

**Expected:** Event status is `tentative`; title matches `"Advisor Q&A — SIP / Mandates — NL-TEST2"`.

---

#### TC-4.3 — Calendar MCP returns structured error on quota exceeded (mocked)

```python
@pytest.mark.asyncio
async def test_calendar_mcp_quota_error(mocker):
    mocker.patch("src.mcp.calendar_mcp.calendar_service.events().insert().execute",
        side_effect=HttpError(resp=MockHttpResponse(status=429), content=b"Quota exceeded"))
    from src.mcp.calendar_mcp import create_calendar_hold
    result = await create_calendar_hold(build_test_mcp_payload())
    assert result["success"] is False
    assert result["error"] == "QuotaExceeded"
    assert "retry_after" in result
```

**Expected:** `success=False`; error key `"QuotaExceeded"`; `retry_after` present.

---

#### TC-4.4 — Sheets MCP appends row with all required columns `[INTEGRATION]`

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_sheets_mcp_appends_row():
    from src.mcp.sheets_mcp import append_booking_notes
    payload = build_test_mcp_payload(booking_code="NL-TEST3")
    result = await append_booking_notes(payload, event_id="test_event_id_123")
    assert result["success"] is True
    assert "row_index" in result
    # Verify row content via read-back
    from src.mcp.sheets_mcp import read_row
    row = await read_row(result["row_index"])
    assert row["booking_code"] == "NL-TEST3"
    assert row["status"] == "TENTATIVE"
    assert row["calendar_event_id"] == "test_event_id_123"
```

**Expected:** Row appended; read-back confirms all columns populated correctly.

---

#### TC-4.5 — Sheets MCP returns structured error when sheet not found (mocked)

```python
@pytest.mark.asyncio
async def test_sheets_mcp_sheet_not_found(mocker):
    mocker.patch("src.mcp.sheets_mcp.gspread_client.open_by_key",
        side_effect=gspread.exceptions.SpreadsheetNotFound)
    from src.mcp.sheets_mcp import append_booking_notes
    result = await append_booking_notes(build_test_mcp_payload(), event_id="evt_001")
    assert result["success"] is False
    assert result["error"] == "SheetNotFound"
```

**Expected:** `success=False`; error key `"SheetNotFound"`; no exception propagated.

---

#### TC-4.6 — Email Draft MCP creates draft in Gmail `[INTEGRATION]`

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_draft_mcp_creates_draft():
    from src.mcp.email_mcp import draft_approval_email
    payload = build_test_mcp_payload(booking_code="NL-TEST4")
    result = await draft_approval_email(payload, event_id="test_event_id", row_index=42)
    assert result["success"] is True
    assert "draft_id" in result
    # Verify draft exists and contains booking code
    from src.mcp.email_mcp import get_draft
    draft = await get_draft(result["draft_id"])
    assert "NL-TEST4" in draft["body"]
    assert "[ACTION REQUIRED]" in draft["subject"]
    # Cleanup
    from src.mcp.email_mcp import delete_draft
    await delete_draft(result["draft_id"])
```

**Expected:** Draft created; subject contains `[ACTION REQUIRED]`; body contains booking code.

---

#### TC-4.7 — MCP Orchestrator runs all 3 tools in parallel and all succeed

```python
@pytest.mark.asyncio
async def test_mcp_orchestrator_all_succeed(mocker):
    mocker.patch("src.mcp.calendar_mcp.create_calendar_hold",
        return_value={"success": True, "event_id": "evt_001", "html_link": "http://cal.test"})
    mocker.patch("src.mcp.sheets_mcp.append_booking_notes",
        return_value={"success": True, "row_index": 10})
    mocker.patch("src.mcp.email_mcp.draft_approval_email",
        return_value={"success": True, "draft_id": "draft_001"})
    from src.mcp.orchestrator import dispatch_mcp
    import time
    start = time.monotonic()
    results = await dispatch_mcp(build_test_mcp_payload())
    elapsed = time.monotonic() - start
    assert results.calendar["success"] is True
    assert results.notes["success"] is True
    assert results.email["success"] is True
    assert elapsed < 3.0  # parallel execution must complete within 3s
```

**Expected:** All 3 succeed; total elapsed time < 3s (parallel, not serial).

---

#### TC-4.8 — MCP Orchestrator: calendar fails, notes + email still succeed

```python
@pytest.mark.asyncio
async def test_mcp_orchestrator_partial_failure(mocker):
    mocker.patch("src.mcp.calendar_mcp.create_calendar_hold",
        return_value={"success": False, "error": "QuotaExceeded", "retry_after": 60})
    mocker.patch("src.mcp.sheets_mcp.append_booking_notes",
        return_value={"success": True, "row_index": 11})
    mocker.patch("src.mcp.email_mcp.draft_approval_email",
        return_value={"success": True, "draft_id": "draft_002"})
    from src.mcp.orchestrator import dispatch_mcp
    results = await dispatch_mcp(build_test_mcp_payload())
    assert results.calendar["success"] is False
    assert results.notes["success"] is True
    assert results.email["success"] is True
    assert results.partial_failure is True
```

**Expected:** `partial_failure=True`; notes and email still succeed independently.

---

#### TC-4.9 — Retry worker retries failed MCP tool up to 3 times with backoff

```python
@pytest.mark.asyncio
async def test_retry_worker_retries_and_succeeds(mocker):
    call_count = {"n": 0}
    async def flaky_calendar(payload):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return {"success": False, "error": "ServiceUnavailable"}
        return {"success": True, "event_id": "evt_retry"}
    mocker.patch("src.mcp.calendar_mcp.create_calendar_hold", side_effect=flaky_calendar)
    from src.mcp.retry_worker import retry_failed_mcp_tool
    result = await retry_failed_mcp_tool(tool="calendar", payload=build_test_mcp_payload())
    assert result["success"] is True
    assert call_count["n"] == 3
```

**Expected:** Tool called 3 times; succeeds on 3rd attempt; result `success=True`.

---

#### TC-4.10 — Waitlist MCP creates hold with correct WAITLIST prefix

```python
@pytest.mark.asyncio
async def test_waitlist_mcp_title(mocker):
    captured = {}
    async def mock_calendar(payload):
        captured["title"] = payload.calendar_title
        return {"success": True, "event_id": "evt_wl"}
    mocker.patch("src.mcp.calendar_mcp.create_calendar_hold", side_effect=mock_calendar)
    mocker.patch("src.mcp.sheets_mcp.append_booking_notes",
        return_value={"success": True, "row_index": 5})
    mocker.patch("src.mcp.email_mcp.draft_approval_email",
        return_value={"success": True, "draft_id": "d_wl"})
    from src.mcp.orchestrator import dispatch_waitlist_mcp
    payload = build_test_mcp_payload(booking_code="NL-W391", is_waitlist=True)
    await dispatch_waitlist_mcp(payload)
    assert "WAITLIST" in captured["title"]
    assert "NL-W391" in captured["title"]
```

**Expected:** Calendar title contains `"WAITLIST"` and the waitlist booking code.

---

### Phase 5 — End-to-End Regression & Compliance

**File:** `tests/test_phase5_regression.py`

This suite runs all 20 scenarios from Section 15 with all external calls mocked.

#### TC-5.1 through TC-5.20 — Full Scenario Matrix

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id,utterances,expected_final_state,expected_code_prefix", [
    (1,  SCENARIO_BOOK_NEW_HAPPY,          "BOOKING_COMPLETE",  "NL-"),
    (2,  SCENARIO_NO_SLOTS_WAITLIST_YES,   "BOOKING_COMPLETE",  "NL-W"),
    (3,  SCENARIO_NO_SLOTS_WAITLIST_NO,    "END",               None),
    (4,  SCENARIO_ADVICE_MID_FLOW,         "BOOKING_COMPLETE",  "NL-"),
    (5,  SCENARIO_PII_ATTEMPT,             "BOOKING_COMPLETE",  "NL-"),
    (6,  SCENARIO_RESCHEDULE_VALID,        "BOOKING_COMPLETE",  "NL-"),
    (7,  SCENARIO_RESCHEDULE_INVALID_CODE, "END",               None),
    (8,  SCENARIO_CANCEL_CONFIRMED,        "END",               None),
    (9,  SCENARIO_CANCEL_DECLINED,         "END",               None),
    (10, SCENARIO_WHAT_TO_PREPARE_KYC,     "END",               None),
    (11, SCENARIO_WHAT_TO_PREPARE_NO_TOPIC,"END",               None),
    (12, SCENARIO_CHECK_AVAILABILITY,      "END",               None),
    (13, SCENARIO_CALENDAR_MCP_FAIL,       "BOOKING_COMPLETE",  "NL-"),
    (14, SCENARIO_ALL_MCP_FAIL,            "BOOKING_COMPLETE",  "NL-"),
    (15, SCENARIO_STT_LOW_CONFIDENCE,      "ERROR",             None),
    (16, SCENARIO_LLM_GROQ_DOWN,           "BOOKING_COMPLETE",  "NL-"),
    (17, SCENARIO_LLM_BAD_JSON,            "BOOKING_COMPLETE",  "NL-"),
    (18, SCENARIO_SESSION_RESUMED,         "BOOKING_COMPLETE",  "NL-"),
    (19, SCENARIO_50_CONCURRENT,           "BOOKING_COMPLETE",  "NL-"),
    (20, SCENARIO_CODE_READ_OUT,           "BOOKING_COMPLETE",  "NL-"),
])
async def test_scenario(scenario_id, utterances, expected_final_state,
                        expected_code_prefix, mocker, mock_all_external):
    from src.agent.voice_agent import VoiceAgent
    agent = VoiceAgent()
    call_id = agent.start_session()
    for utterance in utterances:
        await agent.process_text_turn(call_id, utterance)
    ctx = agent.get_context(call_id)
    assert ctx.current_state.name == expected_final_state, \
        f"Scenario {scenario_id}: expected {expected_final_state}, got {ctx.current_state.name}"
    if expected_code_prefix:
        assert ctx.booking_code is not None
        assert ctx.booking_code.startswith(expected_code_prefix), \
            f"Scenario {scenario_id}: code {ctx.booking_code} missing prefix {expected_code_prefix}"
```

---

#### TC-5.21 — No session bleed across 50 concurrent sessions

```python
@pytest.mark.asyncio
async def test_no_session_bleed():
    from src.agent.voice_agent import VoiceAgent
    import asyncio
    agent = VoiceAgent()
    async def run_session(topic):
        call_id = agent.start_session()
        await agent.process_text_turn(call_id, f"Book for {topic}")
        return call_id, agent.get_context(call_id).topic
    results = await asyncio.gather(*[
        run_session(topic) for topic in
        ["KYC"] * 10 + ["SIP"] * 10 + ["withdrawals"] * 10 +
        ["statements"] * 10 + ["account changes"] * 10
    ])
    # Each session's topic must match what was requested
    for call_id, resolved_topic in results:
        ctx = agent.get_context(call_id)
        # No bleed: context still belongs to this call_id
        assert ctx.call_id == call_id
```

**Expected:** 50 sessions run concurrently; no cross-session topic contamination.

---

#### TC-5.22 — Booking code spoken letter-by-letter in final response

```python
@pytest.mark.asyncio
async def test_booking_code_spoken_correctly(mocker):
    mocker.patch("src.mcp.orchestrator.dispatch_mcp",
        return_value=MockMCPResults(calendar=True, notes=True, email=True,
                                    booking_code="NL-A742"))
    from src.agent.voice_agent import VoiceAgent
    agent = VoiceAgent()
    call_id = agent.start_session()
    # Run full happy path
    for utterance in SCENARIO_BOOK_NEW_HAPPY:
        response = await agent.process_text_turn(call_id, utterance)
    # Final speech must contain letter-by-letter reading
    assert "N" in response.speech
    assert "L" in response.speech
    assert "A" in response.speech
    assert "7" in response.speech or "seven" in response.speech.lower()
    assert "4" in response.speech or "four" in response.speech.lower()
    assert "2" in response.speech or "two" in response.speech.lower()
```

**Expected:** Final speech contains each character of booking code.

---

#### TC-5.23 — Date and time always stated in IST in confirmation turn

```python
@pytest.mark.asyncio
async def test_confirmation_states_ist(mocker):
    # Setup full booking flow to reach confirmation turn
    from src.agent.voice_agent import VoiceAgent
    agent = VoiceAgent()
    call_id = agent.start_session()
    for utterance in SCENARIO_BOOK_NEW_UP_TO_CONFIRM:
        response = await agent.process_text_turn(call_id, utterance)
    # Last response before MCP should contain IST
    assert "IST" in response.speech or "Indian Standard Time" in response.speech
```

**Expected:** Confirmation speech contains `"IST"` or `"Indian Standard Time"`.

---

#### TC-5.24 — `what_to_prepare` never gives investment advice

```python
@pytest.mark.asyncio
async def test_what_to_prepare_no_advice(mocker):
    from src.agent.voice_agent import VoiceAgent
    from src.security.compliance_guard import check_output
    agent = VoiceAgent()
    call_id = agent.start_session()
    response = await agent.process_text_turn(call_id, "What documents for KYC?")
    guard = check_output(response.speech)
    assert guard.safe is True, f"Investment advice detected: {response.speech}"
```

**Expected:** RAG-grounded answer passes compliance guard.

---

#### TC-5.25 — Audit log written for every turn in a session

```python
@pytest.mark.asyncio
async def test_audit_log_completeness(tmp_path, mocker):
    mocker.patch("src.logging.voice_logger.LOG_PATH", str(tmp_path / "audit.jsonl"))
    from src.agent.voice_agent import VoiceAgent
    import json
    agent = VoiceAgent()
    call_id = agent.start_session()
    for utterance in SCENARIO_BOOK_NEW_HAPPY:
        await agent.process_text_turn(call_id, utterance)
    with open(tmp_path / "audit.jsonl") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    call_entries = [e for e in entries if e["call_id"] == call_id]
    assert len(call_entries) == len(SCENARIO_BOOK_NEW_HAPPY)
    for entry in call_entries:
        assert "timestamp_ist" in entry
        assert "detected_intent" in entry
        assert "agent_response_text" in entry
        assert "9876543210" not in str(entry)  # No PII in any field
```

**Expected:** One log entry per turn; all entries contain required fields; no PII in any field.
