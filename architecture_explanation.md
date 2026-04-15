# Architecture Explanation — Simple Guide

This project is a **voice-based appointment booking assistant** for financial advisors.
A user calls up, talks to an AI, and books a consultation slot — without typing anything.

---

## What does the system do?

A user calls → speaks to the AI agent → the agent books an advisor slot → user gets a booking code.

The agent can also:
- Reschedule an existing appointment
- Cancel an appointment
- Answer "what should I prepare for my meeting?"
- Show available time slots

---

## Phase 0 — Set Up the Foundation

**What we're doing:** Laying the groundwork before writing any real features.

- Install all tools and libraries the project needs
- Set up a local "FAQ database" (ChromaDB) so the agent can answer preparation questions like _"what documents do I need for KYC?"_
- Create a fake calendar file (`mock_calendar.json`) with 15+ available slots — used during development so we don't need to call Google Calendar every time
- Make sure basic config loading and test runner work

**Think of it like:** Setting up your kitchen before cooking — pots, ingredients, stove all ready.

---

## Phase 1 — Build the Booking Brain

**What we're doing:** Writing the core logic that handles appointments — no voice or AI yet, just pure business logic.

- **Booking code generator** — creates unique codes like `NL-A742` for each appointment
- **Slot resolver** — takes what the user said ("Monday at 2 PM") and finds the best matching calendar slot
- **PII scrubber** — strips out phone numbers, PAN, Aadhaar, email from any text before it reaches the AI
- **Secure URL generator** — creates a tamper-proof link the user can visit to submit their contact details (since we never take personal info over the call)
- **Waitlist handler** — if no slot is available, creates a waitlist entry with a code like `NL-W391`

**Think of it like:** Writing the rulebook — how slots are picked, how codes are made, how personal data is protected.

---

## Phase 2 — Build the Voice Agent Core

**What we're doing:** Connect the booking brain to an AI (LLM) and a conversation flow manager (FSM).

- **FSM (Finite State Machine)** — a step-by-step conversation manager. It knows which step the user is on (greeting → topic → time → confirm → done) and what to do next
- **LLM Integration** — connects to Groq (fast, free) or Claude (reliable) to understand what the user is saying and figure out their intent (book / reschedule / cancel / ask questions)
- **Intent Router** — looks at what the user said and routes to the right flow
- **Compliance Guard** — checks every AI response before it's spoken; blocks anything that sounds like investment advice or leaks personal data
- **Text-mode testing** — the full conversation flow works via text input/output, no audio needed yet

**Think of it like:** Building the brain and the script — the AI now knows how to hold a full conversation.

---

## Phase 3 — Add Voice (Speech In + Speech Out)

**What we're doing:** Hook up the microphone and speaker so users can actually speak and hear responses.

- **VAD (Voice Activity Detector)** — listens for when the user starts and stops talking (uses Silero, runs locally, very fast)
- **STT (Speech-to-Text)** — converts what the user says into text (Google Cloud primary, Deepgram as backup)
- **TTS (Text-to-Speech)** — converts the agent's text response into spoken audio (Google Cloud Neural2 voice)
- **Audio Pipeline** — connects all the pieces: mic → VAD → STT → scrubber → FSM → TTS → speaker
- **UX tuning** — makes sure the agent speaks naturally (no bullet points read aloud, booking codes spelled letter-by-letter, pauses between sentences)

**Think of it like:** Adding ears and a mouth to the brain we built in Phase 2.

---

## Phase 4 — Connect to Google Workspace (Calendar, Sheets, Gmail)

**What we're doing:** Make real bookings in the real world — not just in memory.

- **Google Calendar** — creates a TENTATIVE hold event on the advisor's calendar
- **Google Sheets** — logs the booking (code, topic, time, status) into a spreadsheet the advisor can see
- **Gmail** — creates a draft email (NOT auto-sent) for the advisor to review and approve before sending to the user
- **Orchestrator** — runs all 3 tools together after the user confirms a slot
- **Retry logic** — if one tool fails (e.g., Sheets is slow), it retries automatically in the background without blocking the user

**Think of it like:** Connecting the agent to the real office tools — booking goes from "confirmed in the call" to "visible in Google Calendar and inbox."

---

## Phase 5 — Test Everything & Deploy

**What we're doing:** Make sure the whole system is solid, then ship it.

- **Full regression tests** — 20 real conversation scenarios tested automatically (happy paths, edge cases, compliance violations, partial failures)
- **Coverage check** — at least 80% of the code must be covered by tests
- **Streamlit UI** — a simple web interface to test the agent by typing (great for demos)
- **Docker setup** — packages the whole app so it can be deployed anywhere
- **Streamlit Cloud** — easy public demo deployment
- **Compliance sign-off** — check that no PII leaks, all calls are logged, audit trail is intact

**Think of it like:** Final quality check before opening the doors to real users.

---

## AI Evals — Measuring Quality Automatically

**What we're doing:** Running automated tests that check whether the AI parts of the system are working well — not just whether the code runs, but whether the AI gives correct, safe, and helpful answers.

### Why do we need evals?

Unit tests check code logic ("does this function return the right number?"). But AI systems fail in different ways — the LLM might understand your question but misclassify it, or extract the wrong date, or accidentally give investment advice. Evals catch these.

### What we measure

| Eval | What it checks | Why it matters |
|------|----------------|---------------|
| **Intent Classification** | Does the LLM correctly identify what the user wants (book / reschedule / cancel / ask / end)? | Wrong intent = wrong flow triggered |
| **Slot Extraction** | Does it correctly pick up the topic, day, time, and booking code from what the user said? | Missing a booking code means the reschedule flow breaks |
| **Compliance / Safety** | Does it always refuse investment advice and reject personal data? | A single miss = regulatory violation |
| **Conversation Flows** | Does a full multi-turn conversation (booking, reschedule, cancel) complete correctly end-to-end? | Tests the FSM + AI + mocked booking tools together |
| **LLM-as-Judge** | Does a second AI (Claude) rate the agent's responses as professional, clear, and helpful? | Catches degraded tone that unit tests can't detect |

### How it works

1. Each eval loads a **golden dataset** — a list of test inputs with known correct outputs
2. The evaluator runs the actual system on each input
3. Results are compared to the expected output and scored
4. A summary report prints in the terminal with colour-coded pass/fail
5. Results are saved as JSON for tracking over time

### Running the evals

```bash
# Fast offline mode — no API keys needed (~3 seconds)
python3 evals/run_evals.py --offline --no-judge

# Full mode — uses Groq + Claude APIs
python3 evals/run_evals.py
```

**Think of it like:** A driving test for the AI — not just checking the car starts, but checking it actually drives correctly in real conditions.

---

## Quick Summary

| Phase | In Simple Words |
|-------|----------------|
| **Phase 0** | Set up the project, load FAQ data, create fake calendar |
| **Phase 1** | Write the booking rules — codes, slots, security, waitlist |
| **Phase 2** | Build the AI conversation flow — understands what you say and guides you through booking |
| **Phase 3** | Add voice — speak to it, hear it speak back |
| **Phase 4** | Connect to Google — real calendar events, spreadsheet logs, email drafts |
| **Phase 5** | Test everything, fix gaps, deploy for real users |
| **Evals** | Automatically measure AI quality — intent accuracy, slot extraction, compliance safety, response tone |
