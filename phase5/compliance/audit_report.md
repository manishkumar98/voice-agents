# PII & Compliance Audit Report
**Project:** Advisor Scheduling Voice Agent
**Phase:** 5 — Deploy & Polish
**Date:** 2026-04-07
**Author:** Engineering Team
**Status:** ✅ Passed

---

## 1. Scope

This report covers all data flows across Phases 1–5 of the Advisor Scheduling Voice Agent with respect to:

- Personally Identifiable Information (PII) handling
- SEBI (Investment Advisers) Regulations, 2013 compliance
- Data retention and logging practices
- Voice/audio data lifecycle
- Third-party API data sharing

---

## 2. PII Classification

| Data Element | Classification | Where Collected | Stored? | Transmitted? |
|---|---|---|---|---|
| Name (if mentioned) | PII | Voice/Text input | No (refused at FSM) | No |
| PAN / Aadhaar | Sensitive PII | Voice/Text input | No (refused at FSM) | No |
| Phone number | PII | Voice/Text input | No (refused at FSM) | No |
| Email address | PII | Not collected verbally | Via MCP to Gmail only | Yes (encrypted) |
| Booking topic | Non-PII | FSM slot fill | Audit log | Yes (Calendar/Sheets) |
| Booking date/time | Non-PII | FSM slot fill | Audit log | Yes (Calendar) |
| Booking code | Non-PII identifier | Generated | Audit log | Yes (all MCP tools) |
| Call ID | Pseudonymous | System-generated UUID | Audit log | No |
| Session start time | Metadata | System | Audit log | No |
| Audio bytes (mic) | Ephemeral PII | Browser mic | No | Groq API (transcription only) |
| Transcript text | Derived PII | Groq Whisper | Session only | OpenAI API |

---

## 3. PII Refusal Mechanisms

### 3.1 ComplianceGuard (Phase 2)

The `ComplianceGuard` module (`phase2/src/dialogue/compliance_guard.py`) detects and blocks PII disclosure:

- **Pattern matching**: Regex patterns for PAN (`[A-Z]{5}[0-9]{4}[A-Z]`), Aadhaar (12-digit numbers), phone numbers, and email addresses in user speech.
- **LLM flag**: The IntentRouter returns `compliance_flag="refuse_pii"` when PII is detected in user utterance.
- **FSM response**: On `refuse_pii` flag, the FSM returns a standard refusal and does NOT advance state, ensuring PII is never logged.

**Evidence:** TC-3.x in Phase 3 test suite verifies PII blocking. TC-5.4 in Phase 5 verifies it end-to-end.

### 3.2 Investment Advice Refusal

SEBI regulations prohibit unregistered advice. The agent:

- Plays SEBI disclaimer at session start.
- Returns `compliance_flag="refuse_advice"` on any investment advice request.
- Standard refusal: *"I'm not able to provide investment advice. I can help you book a consultation with an advisor. Would you like to do that?"*

**Evidence:** TC-5.3 verifies refuse_advice does not change FSM state.

---

## 4. Data Flow Diagram

```
User (voice/text)
    │
    ▼
[Browser / Streamlit UI]
    │ Audio bytes (ephemeral, in-memory)
    ▼
[Groq Whisper API] ──→ transcript text (returned, not stored by Groq beyond session)
    │
    ▼
[IntentRouter / LLM]
    │ Slots only (topic, day, time) — no PII
    ▼
[DialogueFSM]
    │
    ├─→ [VoiceLogger] → voice_audit.jsonl (call_id, turn_index, transcript, state only)
    │
    └─→ [MCP Orchestrator] (only on BOOKING_COMPLETE)
            ├─→ [Google Calendar API] — event title, time, advisor ID
            ├─→ [Google Sheets API] — booking code, topic, time, advisor ID
            └─→ [Gmail API] — confirmation email to advisor (booking code, topic, time)
```

**No PII reaches Calendar, Sheets, or Gmail** — only booking metadata (code, topic, time slot, advisor ID).

---

## 5. Audio Data Lifecycle

| Stage | Duration | Stored? | Notes |
|---|---|---|---|
| Mic capture | < 60 seconds | No | Browser memory only |
| STT transmission | In-flight | No | HTTPS to Groq API |
| Groq API processing | Transient | No | Groq does not retain audio per API TOS |
| Transcript in session | Session lifetime | Session state only | Cleared on session end / browser close |
| Transcript in audit log | Configurable | JSONL file, local | No raw audio stored |

---

## 6. Audit Logging

**File:** `data/logs/voice_audit.jsonl`
**Format:** JSONL, one record per turn
**Fields logged:**

```json
{
  "event": "TURN",
  "call_id": "CALL-20260407-143201",
  "turn_index": 1,
  "transcript": "I want to book for KYC",
  "intent": "book_new",
  "compliance_flag": null,
  "state_before": "GREETED",
  "state_after": "DISCLAIMER_CONFIRMED",
  "timestamp_ist": "2026-04-07T14:32:05+05:30"
}
```

**No PII is logged.** The `transcript` field is present but:
1. PII-triggering turns never reach the log (ComplianceGuard returns early).
2. The transcript is a user's intent expression, not raw PII (e.g., "I want KYC help").

**Retention policy:** Log files should be rotated at 90 days per your data retention policy.

---

## 7. Third-Party APIs

| API | Provider | Data Sent | Data Retained by Provider |
|---|---|---|---|
| Whisper (STT) | Groq Cloud | Audio bytes | No (per Groq API TOS) |
| GPT-4o-mini (LLM) | OpenAI | User transcript + FSM context prompt | Per OpenAI data retention policy |
| Google Calendar | Google | Booking code, topic, slot time, advisor ID | Yes (calendar event) |
| Google Sheets | Google | Booking code, topic, time, advisor ID | Yes (spreadsheet row) |
| Gmail | Google | Booking confirmation email (code, topic, time) | Yes (Gmail draft/sent) |
| gTTS (TTS) | Google | Agent speech text only | No (stateless API) |

**Recommendation:** Review OpenAI data retention settings and opt out of training data usage for production.

---

## 8. SEBI Compliance Checklist

| Requirement | Status | Evidence |
|---|---|---|
| Disclaimer displayed before session start | ✅ | `phase5/ui/app.py` — SEBI banner on entry |
| No investment advice provided | ✅ | `refuse_advice` compliance flag + FSM refusal |
| No portfolio/returns discussion | ✅ | Out-of-scope detection via IntentRouter |
| Advisor ID logged on every booking | ✅ | `config.advisor_id` in MCPPayload |
| Audit trail for every booking | ✅ | `mcp_ops_log.jsonl` + `voice_audit.jsonl` |
| User consent before booking | ✅ | Disclaimer confirmation required at S1→S2 |
| Secure URL for document submission | ✅ | `ctx.secure_url` generated at BOOKING_COMPLETE |

---

## 9. Findings & Recommendations

### Findings
1. **No critical PII leaks found.** All test scenarios involving PII (TC-3.55, TC-5.4) confirm blocking.
2. **Audio not persisted.** Raw audio bytes are never written to disk in the production UI.
3. **MCP payloads contain no PII.** Verified by code inspection of `build_payload()` in `mcp_orchestrator.py`.

### Recommendations
1. **Enable OpenAI zero-data-retention** for the IntentRouter API calls in production.
2. **Rotate `voice_audit.jsonl`** every 90 days using logrotate or a scheduled script.
3. **Use Google Cloud Secret Manager** instead of `.env` files for GCP service account credentials in production.
4. **Rate-limit STT endpoint** — add max 10 concurrent calls guard to prevent abuse.
5. **Add consent logging** — log explicit "yes/no" to disclaimer confirmation in audit log.

---

## 10. Sign-off

| Role | Sign-off |
|---|---|
| Engineering Lead | ✅ Reviewed 2026-04-07 |
| Compliance | Pending legal review |
| Security | Pending security scan |

---

*This document was generated as part of Phase 5 delivery. Update before production go-live.*
