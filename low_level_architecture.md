# Low-Level Architecture: AI Advisor Appointment Scheduler — Voice Agent
**Version:** 1.0 | **Scope:** Phase 0–2 Implementation Detail | **Status:** Reference

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Module Dependency Graph](#2-module-dependency-graph)
3. [Config & Environment](#3-config--environment)
4. [Booking Module — Phase 1](#4-booking-module--phase-1)
   - 4.1 slot_resolver.py
   - 4.2 booking_code_generator.py
   - 4.3 waitlist_handler.py
   - 4.4 waitlist_queue.py
   - 4.5 pii_scrubber.py
   - 4.6 secure_url_generator.py
5. [Dialogue Module — Phase 2](#5-dialogue-module--phase-2)
   - 5.1 states.py
   - 5.2 fsm.py
   - 5.3 intent_router.py
   - 5.4 compliance_guard.py
   - 5.5 session_manager.py
6. [RAG Module — Phase 0](#6-rag-module--phase-0)
7. [Data Models & Schemas](#7-data-models--schemas)
8. [Sequence Diagrams — Key Flows](#8-sequence-diagrams--key-flows)
9. [FSM State Transition Matrix](#9-fsm-state-transition-matrix)
10. [Slot Resolution Algorithm](#10-slot-resolution-algorithm)
11. [Error Handling Strategy](#11-error-handling-strategy)
12. [Testing Architecture](#12-testing-architecture)
13. [AI Evals Architecture](#13-ai-evals-architecture)

---

## 1. Repository Layout

```
voice-agents/phase0/
│
├── app.py                          # Streamlit voice demo UI (entry point)
├── console.py                      # CLI text-mode console runner
├── internal_dashboard.py           # Phase build-tracker dashboard (Streamlit)
├── pytest.ini                      # Pytest configuration
├── .env.example                    # Environment variable template
│
├── config/
│   ├── __init__.py
│   ├── settings.py                 # Pydantic BaseSettings — all env vars typed
│   └── service_account.json        # Google Cloud service account (dummy/dev)
│
├── src/
│   ├── __init__.py
│   │
│   ├── booking/                    # Phase 1 — Booking Brain
│   │   ├── __init__.py
│   │   ├── slot_resolver.py        # NL → calendar slots
│   │   ├── booking_code_generator.py
│   │   ├── waitlist_handler.py     # WaitlistEntry dataclass + factory
│   │   ├── waitlist_queue.py       # Thread-safe FIFO queue + slot promotion
│   │   ├── pii_scrubber.py         # Two-pass regex + NER PII scrubber
│   │   └── secure_url_generator.py # HMAC-signed booking URLs
│   │
│   ├── dialogue/                   # Phase 2 — FSM + LLM Core
│   │   ├── __init__.py
│   │   ├── states.py               # Enums, dataclasses: DialogueState, DialogueContext, LLMResponse
│   │   ├── fsm.py                  # DialogueFSM — 16-state controller
│   │   ├── intent_router.py        # LLM intent extraction + rule fallback
│   │   ├── compliance_guard.py     # Post-LLM safety gate
│   │   └── session_manager.py      # TTL-based session store
│   │
│   └── agent/                      # Phase 0 — RAG
│       ├── __init__.py
│       └── rag_injector.py         # ChromaDB FAQ lookup
│
├── data/
│   ├── mock_calendar.json           # Advisor availability (dev fixture)
│   ├── chroma_db/                   # Persistent ChromaDB index (SQLite)
│   ├── raw_docs/                    # Source FAQ documents (per topic)
│   │   ├── kyc_onboarding/
│   │   ├── sip_mandates/
│   │   ├── statements_tax/
│   │   ├── withdrawals/
│   │   └── account_changes/
│   ├── logs/
│   │   ├── voice_audit_log.jsonl    # Append-only call transcript log
│   │   └── mcp_ops_log.jsonl        # MCP tool result log
│   └── tts_cache/                   # TTS audio cache (Phase 3)
│
├── tests/
│   ├── conftest.py
│   ├── test_phase0_rag.py
│   ├── test_phase1_booking.py
│   └── test_phase2_dialogue.py
│
└── scripts/
    ├── build_index.py               # ChromaDB index builder
    └── scrape_faq.py                # FAQ source scraper
```

---

## 2. Module Dependency Graph

```
app.py / console.py
    │
    ├──► src/dialogue/session_manager.py
    │         └──► src/dialogue/fsm.py
    │                   ├──► src/dialogue/states.py          (types only)
    │                   ├──► src/booking/slot_resolver.py
    │                   ├──► src/booking/booking_code_generator.py
    │                   ├──► src/booking/waitlist_handler.py
    │                   ├──► src/booking/secure_url_generator.py
    │                   └──► src/booking/waitlist_queue.py
    │
    ├──► src/dialogue/intent_router.py
    │         ├──► src/dialogue/states.py
    │         └──► src/booking/pii_scrubber.py
    │
    └──► src/dialogue/compliance_guard.py
              └──► src/dialogue/states.py

src/agent/rag_injector.py          (standalone; used by intent_router for what_to_prepare)

config/settings.py                 (imported by most modules via os.environ or direct import)
```

**Key design rule:** `fsm.py` is the only file that imports from multiple submodules. All other modules are self-contained with minimal cross-imports.

---

## 3. Config & Environment

### 3.1 settings.py — Pydantic BaseSettings

All configuration is read from `.env` and typed via Pydantic. No hard-coded secrets anywhere.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── LLM Providers ────────────────────────────────────────────────────────
    GROQ_API_KEY: str
    ANTHROPIC_API_KEY: str
    GROQ_MODEL: str                  = "llama-3.3-70b-versatile"
    ANTHROPIC_MODEL: str             = "claude-haiku-4-5-20251001"
    LLM_TIMEOUT_SECONDS: int         = 3

    # ── Google Workspace ──────────────────────────────────────────────────────
    GOOGLE_SERVICE_ACCOUNT_PATH: str
    GOOGLE_CALENDAR_ID: str          = "primary"
    GOOGLE_SHEET_ID: str
    GOOGLE_SHEET_TAB_NAME: str       = "Advisor Pre-Bookings"

    # ── Gmail ─────────────────────────────────────────────────────────────────
    GMAIL_ADDRESS: str
    GMAIL_APP_PASSWORD: str
    GMAIL_SMTP_HOST: str             = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int             = 587
    ADVISOR_EMAIL: str
    ADVISOR_NAME: str

    # ── Security ──────────────────────────────────────────────────────────────
    SECURE_URL_SECRET: str           # min 32 chars, random
    SECURE_URL_DOMAIN: str           = "http://localhost:8501"
    SECURE_URL_TTL_SECONDS: int      = 86400           # 24 hours

    # ── Session Management ────────────────────────────────────────────────────
    SESSION_TTL_SECONDS: int         = 1800            # 30 min
    REDIS_URL: str                   = "redis://localhost:6379/0"

    # ── RAG / ChromaDB ────────────────────────────────────────────────────────
    CHROMA_DB_PATH: str              = "data/chroma_db"
    CHROMA_COLLECTION_NAME: str      = "advisor_faq"
    RAG_TOP_K: int                   = 3
    EMBEDDING_MODEL: str             = "all-MiniLM-L6-v2"

    # ── Booking Logic ─────────────────────────────────────────────────────────
    MOCK_CALENDAR_PATH: str          = "data/mock_calendar.json"
    ADVISOR_ID: str                  = "ADV-001"
    CALENDAR_SLOT_DURATION_MINUTES: int = 30
    CALENDAR_HOLD_EXPIRY_HOURS: int  = 48
    MAX_REPROMPTS: int               = 3
    MAX_TURNS_PER_CALL: int          = 20

    # ── STT / TTS ─────────────────────────────────────────────────────────────
    DEEPGRAM_API_KEY: str
    STT_CONFIDENCE_THRESHOLD: float  = 0.7
    STT_SILENCE_TIMEOUT_SECONDS: int = 3
    TTS_VOICE_NAME: str              = "en-IN-Neural2-A"
    TTS_CACHE_DIR: str               = "data/tts_cache"
    TTS_CACHE_TTL_DAYS: int          = 7

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str                   = "INFO"
    VOICE_AUDIT_LOG_PATH: str        = "data/logs/voice_audit_log.jsonl"
    MCP_OPS_LOG_PATH: str            = "data/logs/mcp_ops_log.jsonl"
    LOG_TO_STDOUT: bool              = True

    # ── Application ───────────────────────────────────────────────────────────
    ENVIRONMENT: str                 = "development"
    APP_HOST: str                    = "0.0.0.0"
    APP_PORT: int                    = 8000
    STREAMLIT_PORT: int              = 8501
    COMPANY_NAME: str                = "YourCompany"
    RUN_INTEGRATION: bool            = False

settings = Settings()
```

### 3.2 Runtime Environment Variables (Override at Process Level)

| Variable | Purpose | Default |
|---|---|---|
| `MOCK_CALENDAR_PATH` | Override mock calendar path | `data/mock_calendar.json` |
| `CHROMA_DB_PATH` | Override ChromaDB location | `data/chroma_db` |
| `GROQ_API_KEY` | LLM primary | — |
| `ANTHROPIC_API_KEY` | LLM fallback | — |
| `SECURE_URL_SECRET` | HMAC signing key | — |

---

## 4. Booking Module — Phase 1

### 4.1 slot_resolver.py

Converts natural language day/time preferences into concrete `CalendarSlot` objects from `mock_calendar.json`.

#### Classes

```python
@dataclass
class CalendarSlot:
    slot_id: str
    start: datetime            # IST-aware (Asia/Kolkata)
    end: datetime              # IST-aware
    status: str                # always "AVAILABLE" after filter
    topic_affinity: list[str]  # [] = accepts any topic

    def start_ist_str(self) -> str:
        """Returns: 'Monday, 06/04/2026 at 10:00 AM IST'"""
        return self.start.strftime("%A, %d/%m/%Y at %I:%M %p IST")
```

#### Key Parsing Tables

```python
_DAY_MAP: dict[str, int] = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

_TIME_BAND_MAP: dict[str, tuple[int, int]] = {
    "morning":   (9, 12),
    "afternoon": (12, 17),
    "evening":   (17, 20),
    "night":     (18, 21),
    "noon":      (12, 14),
    "midday":    (11, 14),
}

_MONTH_MAP: dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, ... "december": 12, "dec": 12,
}
```

#### Functions

```python
def _parse_day_preference(
    day_pref: str,
    reference_date: datetime | None = None,
) -> tuple[list[datetime], bool]:
    """
    Input:  "Monday", "next Tuesday", "tomorrow", "6th April", "this week"
    Output: ([candidate_dates...], confident: bool)

    confident=False only for "this week" / "next week" range fallbacks.

    Logic:
      1. "today" / "tomorrow"  → direct offset from reference_date
      2. Ordinal day-of-month  → re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b")
                                  with optional month name + 4-digit year
      3. Weekday name          → (target_weekday - current_weekday) % 7,
                                  "next X" forces +7 days minimum
      4. Fallback range        → today+1..+7 (or +8..+15 for "next week")
    """

def _parse_time_preference(
    time_pref: str,
) -> tuple[tuple[int, int] | None, bool]:
    """
    Input:  "2pm", "10:30am", "afternoon", "morning", "any"
    Output: ((start_hour, end_hour), confident: bool)

    Logic:
      1. Band detection (longest-match): afternoon > morning > noon, etc.
      2. Explicit numeric: re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")
         - am/pm explicit → apply directly
         - am/pm absent + band present → infer from band context
         - am/pm absent + hour ≤ 6 → assume PM
      3. Returns 1-hour window: (hour-1, hour+2) for explicit times
      4. Returns band range for band-only matches
      5. Returns None for "any" / empty string
    """

def parse_datetime_summary(
    day_pref: str,
    time_pref: str,
    reference_date: datetime | None = None,
) -> tuple[str, bool]:
    """
    Returns (human_readable_summary, needs_confirmation).
    Used by FSM to echo interpretation back to user before searching.
    Example: ("Monday, 07/04/2026 at 2:00 PM IST", False)
    """

def resolve_slots(
    day_preference: str,
    time_preference: str,
    topic: str | None = None,
    calendar_path: str | None = None,
    max_results: int = 2,
    reference_date: datetime | None = None,
) -> list[CalendarSlot]:
    """
    Main entry point. Returns up to max_results AVAILABLE slots.

    Steps:
      1. Load mock_calendar.json
      2. Filter status == "AVAILABLE"
      3. Filter by topic_affinity (empty affinity list = accepts any topic)
      4. Parse day/time preferences → candidate_dates, time_band
      5. Filter by date match (slot_date in candidate_dates)
      6. Filter by time band (start_h <= slot.start.hour < end_h)
         → if time filter leaves nothing, keep day-matched (graceful degradation)
      7. Sort by start time, return [:max_results]
    """
```

---

### 4.2 booking_code_generator.py

```python
_SAFE_CHARS: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
# Excludes 0/O and 1/I to prevent reading confusion over voice

def generate_booking_code(
    existing_codes: set[str] | None = None,
) -> str:
    """
    Format: NL-{4 chars from _SAFE_CHARS}
    Example: NL-A742, NL-B3K9
    Uniqueness: Up to 5 retry attempts against existing_codes set.
    Raises: BookingCodeExhaustedError after 5 collisions.
    """

def generate_waitlist_code(
    existing_codes: set[str] | None = None,
) -> str:
    """
    Format: NL-W{3 chars from _SAFE_CHARS}
    Example: NL-W391, NL-WX2K
    Visual prefix "W" distinguishes waitlist from confirmed bookings.
    """

def is_valid_booking_code(code: str) -> bool
def is_valid_waitlist_code(code: str) -> bool
```

---

### 4.3 waitlist_handler.py

```python
VALID_STATUSES = {"ACTIVE", "FULFILLED", "EXPIRED", "CANCELLED"}

@dataclass
class WaitlistEntry:
    waitlist_code: str          # NL-W{3chars}
    topic: str                  # canonical topic key
    day_preference: str         # original NL string from user
    time_preference: str        # original NL string from user
    created_at: datetime        # IST-aware
    status: str = "ACTIVE"

    def to_dict(self) -> dict
    def summary(self) -> str
        """Returns: 'NL-W391 | kyc_onboarding | Monday morning | ACTIVE'"""

def create_waitlist_entry(
    topic: str,
    day_preference: str,
    time_preference: str,
    existing_codes: set[str] | None = None,
    reference_time: datetime | None = None,
) -> WaitlistEntry:
    """
    Factory: generates unique waitlist code, creates IST-timestamped entry.
    Does NOT add to queue — caller must do queue.add(entry).
    """

def cancel_waitlist_entry(entry: WaitlistEntry) -> WaitlistEntry:
    """Returns a new WaitlistEntry with status='CANCELLED'."""
```

---

### 4.4 waitlist_queue.py

```python
_TIME_BANDS: dict[str, tuple[int, int]] = {
    "morning": (9, 12), "afternoon": (12, 17),
    "evening": (17, 20), "night": (18, 21),
}

def _time_pref_matches_slot(time_preference: str, slot: CalendarSlot) -> bool:
    """True if slot.start.hour falls within time_preference band.
    Falls back to True (match) if preference is vague / 'any'."""

def _topic_matches_slot(topic: str, slot: CalendarSlot) -> bool:
    """True if slot.topic_affinity is empty or contains topic."""

@dataclass
class PromotionResult:
    promoted_entry: WaitlistEntry
    freed_slot: CalendarSlot
    position_was: int           # 1-based ACTIVE queue position before promotion

class WaitlistQueue:
    """
    Thread-safe (threading.Lock) FIFO waitlist queue.
    State: list[WaitlistEntry] — all entries including CANCELLED/FULFILLED.

    Invariant: ACTIVE entries are ordered FIFO by created_at.
    """

    def add(self, entry: WaitlistEntry) -> int:
        """Append entry, return 1-based ACTIVE position."""

    def on_cancellation(
        self, freed_slot: CalendarSlot,
    ) -> Optional[PromotionResult]:
        """
        Called when a booking is cancelled and its slot freed.
        Finds first ACTIVE entry where topic+time match freed_slot.
        Returns PromotionResult (caller must update entry status to FULFILLED).
        Returns None if no matching ACTIVE entry.
        """

    def position(self, waitlist_code: str) -> Optional[int]
    def cancel_entry(self, waitlist_code: str) -> bool
    def active_entries(self) -> list[WaitlistEntry]
    def all_entries(self) -> list[WaitlistEntry]
    def active_count(self) -> int
    def snapshot(self) -> list[dict]

# Module-level singleton (shared across the process)
_global_queue: WaitlistQueue = WaitlistQueue()

def get_global_queue() -> WaitlistQueue:
    return _global_queue
```

---

### 4.5 pii_scrubber.py

Two-pass scrubbing: contextual (intent phrase + value) then standalone (bare pattern).

```python
_REDACT: str = "[REDACTED]"

# Pass 1 — Contextual patterns (e.g., "my number is 9876543210")
_CONTEXTUAL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone",   re.compile(r"(?:my\s+(?:phone|number|mobile)[\s\w]*?is\s*)(\+?91[\s-]?)?[6-9]\d{9}", re.I)),
    ("email",   re.compile(r"(?:my\s+(?:email|id|mail)[\s\w]*?is\s*)[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.\w+", re.I)),
    ("pan",     re.compile(r"(?:my\s+(?:pan|permanent\s+account)[\s\w]*?is\s*)[A-Z]{5}[0-9]{4}[A-Z]", re.I)),
    ("aadhaar", re.compile(r"(?:my\s+(?:aadhaar|uid|aadhar)[\s\w]*?is\s*)[\d\s]{12,14}", re.I)),
    ("account", re.compile(r"(?:my\s+(?:account|card)[\s\w]*?is\s*)\d{16}", re.I)),
]

# Pass 2 — Standalone patterns (bare values without intent phrase)
_PHONE_RE:   re.Pattern  # (+91/0)? + 6-9 leading + 9 more digits
_EMAIL_RE:   re.Pattern  # standard email
_PAN_RE:     re.Pattern  # AAAAA0000A (5 alpha + 4 num + 1 alpha)
_AADHAAR_RE: re.Pattern  # 12 digits (with optional spaces every 4)
_ACCOUNT_16_RE: re.Pattern  # 16 consecutive digits

@dataclass
class PIIScrubResult:
    cleaned_text: str
    pii_found: bool
    categories: list[str]           # e.g., ["phone", "email"]
    context_detected: list[str]     # from pass 1
    pattern_detected: list[str]     # from pass 2

    def detection_summary(self) -> str

def scrub_pii(text: str) -> PIIScrubResult:
    """Run both passes. Returns cleaned text + metadata."""

def contains_pii(text: str) -> bool:
    """Quick check: returns True if any PII found."""
```

---

### 4.6 secure_url_generator.py

```python
_DEFAULT_SALT: str = "voice-agent-booking-v1"

def _get_serializer(secret: str) -> URLSafeTimedSerializer:
    """itsdangerous serializer with HMAC-SHA256."""

def generate_secure_url(
    booking_code: str,
    topic: str,
    slot_ist: str | datetime,      # ISO string or datetime object
    secret: str | None = None,     # falls back to settings.SECURE_URL_SECRET
    domain: str | None = None,     # falls back to settings.SECURE_URL_DOMAIN
) -> str:
    """
    Payload signed into token:
    {
      "booking_code": "NL-A742",
      "topic": "kyc_onboarding",
      "slot_ist": "2026-04-07T14:00:00+05:30"
    }
    Output: https://{domain}/book/{signed_token}
    Token expires in settings.SECURE_URL_TTL_SECONDS (default 24h).
    """

def verify_secure_url(
    token: str,
    secret: str | None = None,
    max_age_seconds: int | None = None,
) -> dict:
    """
    Raises itsdangerous.BadSignature or itsdangerous.SignatureExpired on failure.
    Returns decoded payload dict on success.
    """

def extract_token_from_url(url: str) -> str:
    """Strips domain prefix, returns raw token string."""
```

---

## 5. Dialogue Module — Phase 2

### 5.1 states.py

Core type definitions. No business logic — pure data.

```python
# ── Taxonomy ──────────────────────────────────────────────────────────────────

TOPIC_LABELS: dict[str, str] = {
    "kyc_onboarding":  "KYC and Onboarding",
    "sip_mandates":    "SIP and Mandates",
    "statements_tax":  "Statements and Tax Documents",
    "withdrawals":     "Withdrawals and Timelines",
    "account_changes": "Account Changes and Nominee",
}

VALID_TOPICS: set[str] = set(TOPIC_LABELS.keys())

VALID_INTENTS: set[str] = {
    "book_new", "reschedule", "cancel",
    "what_to_prepare", "check_availability",
    "refuse_advice", "refuse_pii", "out_of_scope",
}

COMPLIANCE_FLAGS: set[str | None] = {None, "refuse_advice", "refuse_pii", "out_of_scope"}

# ── FSM States ────────────────────────────────────────────────────────────────

class DialogueState(Enum):
    IDLE                      = "S0"
    GREETED                   = "S1"
    DISCLAIMER_CONFIRMED      = "S2"
    INTENT_IDENTIFIED         = "S3"
    TOPIC_COLLECTED           = "S4"
    TIME_PREFERENCE_COLLECTED = "S5"
    SLOTS_OFFERED             = "S6"
    SLOT_CONFIRMED            = "S7"
    MCP_DISPATCHED            = "S8"
    BOOKING_COMPLETE          = "S9"
    WAITLIST_OFFERED          = "S10"
    WAITLIST_CONFIRMED        = "S11"
    RESCHEDULE_CODE_COLLECTED = "S12"
    CANCEL_CODE_COLLECTED     = "S13"
    ERROR                     = "S14"
    END                       = "S15"

    def is_terminal(self) -> bool:
        return self in (DialogueState.END, DialogueState.ERROR)

    def label(self) -> str:
        return f"{self.value} {self.name}"

# ── Dialogue Context ──────────────────────────────────────────────────────────

@dataclass
class DialogueContext:
    call_id: str
    session_start_ist: datetime
    current_state: DialogueState = DialogueState.IDLE

    # Intent
    intent: str | None = None

    # Slot fills — book_new
    topic: str | None = None
    day_preference: str | None = None
    time_preference: str | None = None
    resolved_slot: dict | None = None           # {slot_id, start (ISO), start_ist (readable)}
    offered_slots: list[dict] = field(default_factory=list)  # all slots presented to user
    booking_code: str | None = None
    secure_url: str | None = None

    # Slot fills — reschedule / cancel
    existing_booking_code: str | None = None

    # Waitlist
    waitlist_code: str | None = None

    # Turn tracking
    turn_count: int = 0
    no_input_count: int = 0

    # MCP results (Phase 4)
    calendar_hold_created: bool = False
    notes_appended: bool = False
    email_drafted: bool = False

    def slots_filled(self) -> dict
    def missing_booking_slots(self) -> list[str]  # ["topic"] | ["day_preference"] | []
    def is_booking_ready(self) -> bool             # topic + day + time + resolved_slot all set
    def apply_slots(self, slots: dict) -> None     # Merges LLM-extracted slots (non-None only)

# ── LLM Response ──────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    intent: str
    slots: dict = field(default_factory=dict)
    speech: str = ""
    compliance_flag: str | None = None
    raw_response: str = ""

    def is_compliant(self) -> bool:
        return self.compliance_flag is None

    def is_refusal(self) -> bool:
        return self.compliance_flag in ("refuse_advice", "refuse_pii", "out_of_scope")

    def validate(self) -> list[str]:
        """Returns list of validation errors. Empty = valid."""
```

---

### 5.2 fsm.py

The FSM is **stateless** — all state lives in `DialogueContext`. `DialogueFSM` is a pure function dispatcher.

#### Class Overview

```python
class DialogueFSM:
    MAX_NO_INPUT: int = 3
    IST = pytz.timezone("Asia/Kolkata")

    # Static response templates
    _GREETING: str      = "Hello! I'm the Advisor Scheduling assistant..."
    _DISCLAIMER: str    = "Quick note: this service is for scheduling only..."
    _TOPIC_PROMPT: str  = "Great. What topic would you like to discuss?..."
    _WAITLIST_OFFER: str = "I don't have slots on that day. Would you like to join the waitlist?"
```

#### Public Interface

```python
def start(
    call_id: str | None = None,
) -> tuple[DialogueContext, str]:
    """
    Initialises DialogueContext at S0 IDLE.
    Returns context at S1 GREETED + combined greeting+disclaimer speech.
    """

def process_turn(
    ctx: DialogueContext,
    user_input: str,
    llm_response: LLMResponse,
) -> tuple[DialogueContext, str]:
    """
    Core dispatcher. Called once per turn.

    Steps:
      1. Increment ctx.turn_count
      2. Handle silence (empty user_input → no_input_count, maybe → S14)
      3. Handle compliance refusals (stay in current state, speak refusal)
      4. Route to state handler by ctx.current_state
      5. Return (updated_ctx, speech_string)
    """
```

#### State Handler Map

| State | Handler | Notes |
|---|---|---|
| S1 GREETED | `_from_greeted()` | Affirm → S2 |
| S2 DISCLAIMER_CONFIRMED | `_from_disclaimer()` | Route by intent |
| S3 INTENT_IDENTIFIED | `_collect_topic()` | Prompt for topic |
| S4 TOPIC_COLLECTED | `_offer_slots()` | Prompt for day/time if missing, else resolve |
| S5 TIME_PREFERENCE_COLLECTED | `_offer_slots()` | Resolve + offer |
| S6 SLOTS_OFFERED | `_from_slots_offered()` | User picks slot / asks question / re-searches |
| S7 SLOT_CONFIRMED | `_dispatch_mcp()` | Mock MCP → S9, speak booking code |
| S10 WAITLIST_OFFERED | `_from_waitlist_offered()` | Accept → S11, decline → S15 |
| S12 RESCHEDULE_CODE_COLLECTED | `_handle_code_flow()` | Validate code, re-enter slot flow |
| S13 CANCEL_CODE_COLLECTED | `_handle_code_flow()` | Validate code, confirm cancellation |

#### `_offer_slots()` — 4-Step Expansion

Guarantees exactly 2 slots are always offered. Expands search scope if needed.

```
Step 1: resolve_slots(day, time, topic, max_results=2)
        → if ≥ 2 results → done

Step 2: resolve_slots(day, "any", topic, max_results=2)
        → same day, any time
        → if results → merge with step 1 results

Step 3: resolve_slots("this week", "any", topic, max_results=2)
        → this week, any time
        → deduplicate by slot_id

Step 4: resolve_slots("next week", "any", topic, max_results=2)
        → if still < 2 after all steps → offer waitlist

Preamble speech varies:
  - All from exact day+time → "I found {n} slot(s) on {day} at {time}."
  - Mix of day + nearby days  → "I found slots near {day}."
  - All expanded              → "No exact match — here are the nearest available slots."
```

#### `_from_slots_offered()` — Slot Selection Logic

```
On each turn in S6:
  1. New preference detected?
     → if resp.slots has new day_preference or time_preference
     → re-run _offer_slots() with updated preference

  2. Question detected?
     → if "?" in user_input or question_words (is, are, does, can, available...) present
     → re-run _offer_slots() for new day, stay in S6

  3. Slot selected?
     → "option 1" / "first" / "1" → offered_slots[0]
     → "option 2" / "second" / "2" → offered_slots[1]
     → apply resolved_slot, move to S7

  4. Rejection / waitlist?
     → "waitlist" / "add me" / "notify me" → S10
     → "no" / "different" / "other" → re-prompt for new day/time

  5. Default (unclear) → re-prompt: "Please say Option 1, Option 2, or let me know a different time."
```

#### `_dispatch_mcp()` — Mock Booking Confirmation

```python
def _dispatch_mcp(ctx: DialogueContext) -> tuple[DialogueContext, str]:
    """
    In Phase 2 (mock), this:
      1. Generates booking_code via generate_booking_code()
      2. Generates secure_url via generate_secure_url()
      3. Sets ctx.calendar_hold_created = True (mock)
      4. Sets ctx.notes_appended = True (mock)
      5. Sets ctx.email_drafted = True (mock)
      6. Moves to S9 BOOKING_COMPLETE
      7. Returns speech: "Your booking is confirmed. {topic} on {slot_time}.
                          Your booking code is {code}. Please note it down.
                          You'll receive a secure link to submit your contact details.
                          Thank you for calling!"

    Note: slot_time comes from ctx.resolved_slot["start_ist"] which already
    ends with " IST" — do NOT append " IST" again in the f-string.
    """
```

---

### 5.3 intent_router.py

```python
LLMCallable = Callable[[str, str], str]  # (system_prompt, user_message) -> raw_response

class IntentRouter:
    def __init__(self, llm_callable: Optional[LLMCallable] = None) -> None:
        """
        LLM priority:
          1. Groq llama-3.3-70b-versatile  (if GROQ_API_KEY set)
          2. Anthropic claude-haiku-4-5     (if ANTHROPIC_API_KEY set)
          3. Rule-based fallback            (always available)

        llm_callable param: inject a custom callable for testing.
        """

    @property
    def is_online(self) -> bool:
        """True if at least one LLM API is configured and reachable."""

    def route(
        self,
        user_input: str,
        ctx: DialogueContext,
    ) -> LLMResponse:
        """
        1. Scrub PII from user_input
        2. Build context-aware user message (state + filled slots appended)
        3. Call LLM or fall back to rule-based
        4. Parse JSON response → LLMResponse
        5. Validate + sanitize; return safe defaults on parse error
        """
```

#### System Prompt Structure

```
You are "Advisor Scheduler", a voice assistant for {COMPANY_NAME}.

RULES (non-negotiable):
1. NEVER provide investment advice. If asked, use compliance_flag: "refuse_advice".
2. NEVER repeat or acknowledge PII. If user shares it, use compliance_flag: "refuse_pii".
3. If user goes off-topic, use compliance_flag: "out_of_scope".
4. ALWAYS state times in IST.
5. Speak in short, clear sentences (voice, no markdown).

OUTPUT FORMAT (strict JSON):
{
  "intent": "<intent_key>",
  "slots": { "topic": "...", "day_preference": "...", "time_preference": "..." },
  "speech": "<exact text to speak>",
  "compliance_flag": null | "refuse_advice" | "refuse_pii" | "out_of_scope"
}

VALID INTENTS: book_new | reschedule | cancel | what_to_prepare |
               check_availability | refuse_advice | refuse_pii | out_of_scope

TOPIC MAPPING:
  kyc_onboarding  → KYC / Onboarding, account opening, verification
  sip_mandates    → SIP, auto-debit, mandate, systematic plan
  statements_tax  → statement, tax, capital gains, Form 26AS
  withdrawals     → redeem, withdraw, payout, exit
  account_changes → nominee, bank change, address/mobile update
```

#### Rule-Based Fallback

```python
def _rule_based_parse(user_input: str, ctx: DialogueContext) -> LLMResponse:
    """
    Used when both LLMs are unavailable.
    Keyword matching:
      - "reschedule" / "move" / "change"  → reschedule intent
      - "cancel" / "remove"               → cancel intent
      - "kyc" / "onboard"                 → book_new + topic=kyc_onboarding
      - "sip" / "mandate"                 → book_new + topic=sip_mandates
      - "monday"–"sunday" in text         → extracts day_preference
      - "morning" / "afternoon" / Xpm     → extracts time_preference
      - "yes" / "sure" / "ok"             → book_new (affirmation)
      - Investment keywords               → refuse_advice flag
      - Default                           → book_new (safest fallback)
    """
```

---

### 5.4 compliance_guard.py

Post-LLM safety gate. Runs on the LLM's generated `speech` field before it reaches TTS.

```python
@dataclass
class ComplianceResult:
    is_compliant: bool
    flag: str | None               # None | "refuse_advice" | "refuse_pii" | "out_of_scope"
    safe_speech: str               # Replacement text if non-compliant
    reason: str = ""

    def effective_speech(self, original: str) -> str:
        """Returns original if compliant, safe_speech otherwise."""

class ComplianceGuard:
    # Investment advice detection patterns
    _ADVICE_PATTERNS: list[re.Pattern] = [
        re.compile(r"\b(should|recommend|advise|suggest)\b.*\b(invest|buy|sell|fund|stock)\b", re.I),
        re.compile(r"\b(best|good|top)\b.*\b(fund|investment|stock|scheme)\b", re.I),
        ...
    ]

    # PII leakage detection (same patterns as pii_scrubber)
    _PII_LEAK_PATTERNS: list[re.Pattern]

    _SAFE_ADVICE: str = (
        "I'm not able to provide investment advice. "
        "For educational information, please visit our Help Centre. "
        "Would you still like to book a consultation?"
    )
    _SAFE_PII: str = (
        "Please don't share personal details on this call. "
        "You'll receive a secure link after booking to submit your contact information."
    )
    _SAFE_SCOPE: str = (
        "I'm only able to help with advisor appointment scheduling today."
    )

    def check(self, llm_output: str) -> ComplianceResult:
        """
        Scans text for:
          1. Investment advice patterns  → flag: "refuse_advice"
          2. PII leakage patterns        → flag: "refuse_pii"
          3. (out_of_scope handled by LLM intent, not regex here)
        Returns ComplianceResult with safe alternative text.
        """

    def check_and_gate(self, llm_output: str) -> str:
        """Convenience: returns safe speech directly."""
```

---

### 5.5 session_manager.py

```python
TTL_MINUTES: int = 30

class SessionManager:
    """
    Thread-safe (threading.Lock) in-memory session store.
    Storage: dict[session_id: str, (ctx: DialogueContext, last_active: datetime)]
    TTL: configurable (default 30 min). Expired sessions auto-pruned on access.
    """

    def __init__(self, ttl_minutes: int = TTL_MINUTES) -> None

    def create_session(self, ctx: DialogueContext) -> str:
        """Store context under new UUID4 session_id. Return session_id."""

    def get_session(self, session_id: str) -> Optional[DialogueContext]:
        """Return context if session exists and not expired. Returns None otherwise."""

    def update_session(self, session_id: str, ctx: DialogueContext) -> bool:
        """Update context and refresh TTL. Returns False if session not found."""

    def close_session(self, session_id: str) -> bool:
        """Explicit deletion. Returns False if not found."""

    def active_count(self) -> int
    def all_session_ids(self) -> list[str]
    def _is_expired(self, last_active: datetime) -> bool
    def _prune(self) -> None:
        """Remove all expired sessions (called on every access, O(n))."""
```

---

## 6. RAG Module — Phase 0

### rag_injector.py

```python
def get_rag_context(
    query: str,
    topic: str,
    top_k: int | None = None,   # defaults to settings.RAG_TOP_K (3)
) -> str:
    """
    1. Load or reuse ChromaDB client (persistent at CHROMA_DB_PATH)
    2. Get collection "advisor_faq"
    3. Embed query using all-MiniLM-L6-v2 (local, no API cost)
    4. Query top_k chunks filtered by topic metadata
    5. Format results as:
       "[Source: {source_url}]\n{chunk_text}\n\n..."
    6. Returns "No relevant context found." if collection empty or no match
    """
```

### ChromaDB Schema

```python
# Each document stored with metadata:
{
    "id": "kyc_onboarding_chunk_042",
    "document": "To complete KYC, you need a valid photo ID...",
    "metadata": {
        "topic_key": "kyc_onboarding",
        "source_url": "https://example.com/help/kyc",
        "scraped_at": "2026-03-01T10:00:00",
        "chunk_index": 42,
    }
}
```

### Index Build Pipeline (scripts/build_index.py)

```
1. Read all .txt files from data/raw_docs/{topic_key}/
2. Chunk: recursive character splitter
   - chunk_size = 256 tokens
   - overlap = 32 tokens
3. Embed: sentence-transformers/all-MiniLM-L6-v2 (384-dim vectors)
4. Upsert into ChromaDB collection "advisor_faq"
5. Persist to data/chroma_db/ (SQLite-backed)
```

---

## 7. Data Models & Schemas

### 7.1 mock_calendar.json

```jsonc
{
  "advisor_id": "ADV-001",
  "advisor_name": "Advisor (display name not used on call)",
  "timezone": "Asia/Kolkata",
  "slots": [
    {
      "slot_id": "SLOT-20260406-1000",    // unique ID
      "start": "2026-04-06T10:00:00",     // naive IST (no tz suffix)
      "end":   "2026-04-06T10:30:00",
      "status": "AVAILABLE",              // AVAILABLE | BOOKED | HOLD
      "topic_affinity": []                // [] = accepts any topic
    },
    {
      "slot_id": "SLOT-20260407-1400",
      "start": "2026-04-07T14:00:00",
      "end":   "2026-04-07T14:30:00",
      "status": "AVAILABLE",
      "topic_affinity": ["kyc_onboarding", "account_changes"]
    }
  ]
}
```

### 7.2 MCPPayload (Phase 4 Interface)

```jsonc
{
  "booking_code":   "NL-A742",
  "topic_key":      "kyc_onboarding",
  "topic_label":    "KYC and Onboarding",
  "slot_start_ist": "2026-04-07T14:00:00+05:30",
  "slot_end_ist":   "2026-04-07T14:30:00+05:30",
  "advisor_id":     "ADV-001",
  "call_id":        "CALL-20260407-abc123",
  "secure_url":     "https://example.com/book/eyJib29...",
  "is_waitlist":    false,
  "calendar_title": "Advisor Q&A — KYC and Onboarding — NL-A742"
}
```

### 7.3 Voice Audit Log (data/logs/voice_audit_log.jsonl)

One JSON object per line, append-only.

```jsonc
{
  "call_id":                  "CALL-20260407-abc123",
  "timestamp_ist":            "2026-04-07T14:23:01+05:30",
  "event_type":               "TURN",            // TURN | INTENT | MCP_TRIGGER | MCP_RESULT | COMPLIANCE_BLOCK
  "turn_index":               3,
  "state_before":             "S4",
  "state_after":              "S5",
  "user_transcript_sanitised": "I want to book KYC on Monday at 2 PM",
  "detected_intent":          "book_new",
  "slots_filled":             {"topic": "kyc_onboarding", "day_preference": "Monday", "time_preference": "2 PM"},
  "agent_response_text":      "I found 2 slots on Monday...",
  "pii_blocked":              false,
  "compliance_flag":          null
}
```

### 7.4 LLM JSON Contract

The FSM passes this to IntentRouter; IntentRouter sends it to LLM and expects this exact format back:

```jsonc
// Input context (appended to user message):
{
  "current_state": "S4",
  "filled_slots": {"topic": "kyc_onboarding"},
  "missing_slots": ["day_preference", "time_preference"]
}

// Expected LLM output:
{
  "intent": "book_new",
  "slots": {
    "topic": "kyc_onboarding",       // may repeat known slot for confirmation
    "day_preference": "Monday",
    "time_preference": "2 PM"
  },
  "speech": "Got it. What day and time works for you?",
  "compliance_flag": null
}
```

---

## 8. Sequence Diagrams — Key Flows

### 8.1 Happy Path — Book New

```
User                FSM                 IntentRouter        SlotResolver        BookingCode
 │                   │                       │                   │                  │
 │── "yes" ─────────►│                       │                   │                  │
 │                   │── route(S1, "yes") ──►│                   │                  │
 │                   │◄── LLMResponse(book_new) ─────────────────│                  │
 │◄── disclaimer ────│                       │                   │                  │
 │                   │  [S1→S2]              │                   │                  │
 │                   │                       │                   │                  │
 │── "KYC" ─────────►│                       │                   │                  │
 │                   │── route(S2, "KYC") ──►│                   │                  │
 │                   │◄── LLMResponse(book_new, topic=kyc) ──────│                  │
 │◄── "What day?" ───│                       │                   │                  │
 │                   │  [S2→S4]              │                   │                  │
 │                   │                       │                   │                  │
 │── "Mon 2pm" ─────►│                       │                   │                  │
 │                   │── route(S4, ...) ────►│                   │                  │
 │                   │◄── LLMResponse(day=Mon, time=2pm) ────────│                  │
 │                   │──────── resolve_slots(Mon, 2pm, kyc) ────►│                  │
 │                   │◄──────── [Slot1, Slot2] ─────────────────►│                  │
 │◄── "Option1/2" ───│                       │                   │                  │
 │                   │  [S4→S6]              │                   │                  │
 │                   │                       │                   │                  │
 │── "option 1" ────►│                       │                   │                  │
 │                   │  resolved_slot = offered_slots[0]         │                  │
 │◄── "Confirm?" ────│                       │                   │                  │
 │                   │  [S6→S7]              │                   │                  │
 │                   │                       │                   │                  │
 │── "yes" ─────────►│                       │                   │                  │
 │                   │──────────────────────────────── generate_booking_code() ────►│
 │                   │◄──────────────────────────────── "NL-A742" ─────────────────│
 │                   │── generate_secure_url(NL-A742, kyc, slot) ─────────────────►│
 │◄── booking code ──│                       │                   │                  │
 │   + secure URL    │  [S7→S8→S9→S15]      │                   │                  │
```

### 8.2 Waitlist Path

```
User                FSM                 SlotResolver
 │                   │                       │
 │── "Mon 4pm" ─────►│                       │
 │                   │── resolve(Mon, 4pm) ──►│
 │                   │◄── [] (no slots) ──────│
 │                   │── expand step 2/3/4 ──►│
 │                   │◄── [] (still none) ────│
 │◄── "Waitlist?" ───│                       │
 │                   │  [→S10]               │
 │── "yes" ─────────►│                       │
 │                   │── create_waitlist_entry()
 │                   │── waitlist_queue.add()
 │◄── waitlist code ─│                       │
 │                   │  [S10→S11→S15]        │
```

### 8.3 Compliance Refusal (mid-flow)

```
User                FSM                 IntentRouter        ComplianceGuard
 │                   │                       │                   │
 │── "should I buy mutual funds?" ──────────►│                   │
 │                   │◄── LLMResponse(compliance_flag=refuse_advice)
 │                   │──────────────────────────── check(speech) ►│
 │                   │◄──────────────────────── safe_speech ───────│
 │◄── refusal msg ───│                       │                   │
 │                   │  [state unchanged, stays in S4/S5/S6]     │
```

---

## 9. FSM State Transition Matrix

| From State | Trigger | To State | Action |
|---|---|---|---|
| S0 IDLE | call connected | S1 GREETED | Speak greeting + disclaimer |
| S1 GREETED | affirmation | S2 DISCLAIMER_CONFIRMED | — |
| S1 GREETED | no input × 3 | S14 ERROR | Speak error |
| S2 DISCLAIMER_CONFIRMED | intent=book_new | S3/S4 | Prompt for topic |
| S2 DISCLAIMER_CONFIRMED | intent=reschedule | S12 | Prompt for booking code |
| S2 DISCLAIMER_CONFIRMED | intent=cancel | S13 | Prompt for booking code |
| S2 DISCLAIMER_CONFIRMED | intent=what_to_prepare | S3 | RAG lookup + offer to book |
| S2 DISCLAIMER_CONFIRMED | intent=check_availability | S3 | Show windows + offer to book |
| S4 TOPIC_COLLECTED | topic validated | S5 | Prompt for day/time |
| S5 TIME_PREFERENCE_COLLECTED | slots ≥ 1 | S6 | Offer up to 2 slots |
| S5 TIME_PREFERENCE_COLLECTED | slots = 0 (all 4 steps) | S10 | Offer waitlist |
| S6 SLOTS_OFFERED | new day/time preference | S6 | Re-resolve slots, stay |
| S6 SLOTS_OFFERED | question about availability | S6 | Re-resolve for asked day |
| S6 SLOTS_OFFERED | slot selection (1 or 2) | S7 | Confirm slot + IST time |
| S6 SLOTS_OFFERED | "waitlist" / "add me" | S10 | Offer waitlist |
| S6 SLOTS_OFFERED | rejection / "different" | S5 | Re-prompt for day/time |
| S7 SLOT_CONFIRMED | — | S8 | Dispatch MCP |
| S8 MCP_DISPATCHED | success | S9 | Read booking code + secure URL |
| S8 MCP_DISPATCHED | partial failure | S9 | Read code; note partial failure |
| S9 BOOKING_COMPLETE | farewell | S15 END | Speak farewell |
| S10 WAITLIST_OFFERED | accept | S11 | Dispatch waitlist MCP |
| S10 WAITLIST_OFFERED | decline | S15 END | Speak farewell |
| S11 WAITLIST_CONFIRMED | — | S15 END | Read waitlist code + secure URL |
| S12 RESCHEDULE_CODE_COLLECTED | code valid | S5 | Re-enter slot flow |
| S12 RESCHEDULE_CODE_COLLECTED | code not found | S12 | Re-prompt |
| S13 CANCEL_CODE_COLLECTED | code valid + confirmed | S15 END | Speak cancellation + farewell |
| S13 CANCEL_CODE_COLLECTED | code not found | S13 | Re-prompt |
| Any | compliance_flag set | Same | Speak refusal, return to same state |
| Any | no_input_count = 3 | S14 ERROR | Speak error |
| S14 ERROR | — | S15 END | Graceful exit |

---

## 10. Slot Resolution Algorithm

The full 4-step expansion in `_offer_slots()`:

```
Given: ctx.day_preference, ctx.time_preference, ctx.topic

STEP 1 — Exact match
  slots = resolve_slots(day, time, topic, max_results=4)
  if len(slots) >= 2: present slots[:2], DONE

STEP 2 — Same day, any time
  extra = resolve_slots(day, "any", topic, max_results=4)
  slots = _merge(slots, extra)         # deduplicate by slot_id
  if len(slots) >= 2: present slots[:2], DONE

STEP 3 — This week, any time
  week_slots = resolve_slots("this week", "any", topic, max_results=4)
  slots = _merge(slots, week_slots)
  if len(slots) >= 2: present slots[:2], DONE

STEP 4 — Next week, any time
  next_slots = resolve_slots("next week", "any", topic, max_results=4)
  slots = _merge(slots, next_slots)
  if len(slots) >= 2: present slots[:2], DONE

FALLBACK — No slots found at all
  → transition to S10 (waitlist)

Speech preamble logic:
  all slots on requested day+time → "I found {n} slot(s) on {day} at {time}."
  slots on requested day (diff time) → "I found slots on {day}, though not at {time}."
  slots on different days → "I found the nearest available slots."

_merge(a, b):
  seen = {s.slot_id for s in a}
  return a + [s for s in b if s.slot_id not in seen]
```

---

## 11. Error Handling Strategy

### 11.1 Silence / No-Input

```
no_input_count tracks consecutive empty turns.
Threshold: MAX_NO_INPUT = 3

Turn 1 silence: "I didn't catch that. Could you repeat?"
Turn 2 silence: "Still having trouble hearing you. Please try again."
Turn 3 silence: → S14 ERROR → S15 END
  Speech: "I'm having trouble understanding. Please call back when ready. Goodbye."
```

### 11.2 LLM Failure Cascade

```
Groq call fails (timeout / 5xx)
  → Try Anthropic Claude haiku (same prompt)
  → If Anthropic fails
    → Use rule-based _rule_based_parse()
    → Log warning: "LLM unavailable, using rule-based fallback"
```

### 11.3 Slot Resolution — Zero Results

```
All 4 expansion steps return 0 slots
  → _offer_slots() transitions to S10 WAITLIST_OFFERED
  → Speech: "I checked all available times and don't have a suitable slot right now.
             I can add you to the waitlist and contact you when one opens up.
             Would you like that?"
```

### 11.4 MCP Partial Failure (Phase 4)

```
create_calendar_hold() fails:
  → Log error; do NOT proceed to notes/email
  → ctx.calendar_hold_created = False
  → Still speak booking code (record in Sheets manually later)
  → "Your booking has been registered. Our team will send a calendar invite shortly."

append_booking_notes() fails:
  → Log error; async retry queue
  → Continue to email draft

draft_approval_email() fails:
  → Log error; advisor team notified via ops log
  → Continue; booking code is the source of truth
```

### 11.5 Invalid Booking Code (Reschedule / Cancel)

```
User provides code → system looks up in Google Sheets (Phase 4) / mock dict (Phase 2)

Code not found OR status = CANCELLED:
  → Re-prompt: "I couldn't find an active booking with that code. Please double-check
                and try again, or say 'new booking' to schedule fresh."
  → Max 2 re-prompts, then → S15 END
```

---

## 12. Testing Architecture

### 12.1 Test Files

| File | Scope | Strategy |
|---|---|---|
| `test_phase0_rag.py` | RAG injector | Mock ChromaDB; test query routing + formatting |
| `test_phase1_booking.py` | Booking module | Unit tests; mock `mock_calendar.json` via tmp file |
| `test_phase2_dialogue.py` | FSM + Intent Router | Inject mock LLMResponse; no real LLM calls |

### 12.2 Key Test Patterns

```python
# FSM testing — inject pre-built LLMResponse, bypass LLM
fsm = DialogueFSM()
ctx, greeting = fsm.start()

resp = LLMResponse(intent="book_new", slots={"topic": "kyc_onboarding"}, speech="KYC please")
ctx, speech = fsm.process_turn(ctx, "KYC please", resp)
assert ctx.current_state == DialogueState.TIME_PREFERENCE_COLLECTED

# Slot resolver testing — use reference_date to make tests deterministic
from datetime import datetime
import pytz
REF = datetime(2026, 4, 7, 12, 0, tzinfo=pytz.timezone("Asia/Kolkata"))

slots = resolve_slots("Monday", "afternoon", reference_date=REF, calendar_path="tests/fixtures/cal.json")
assert len(slots) >= 1
assert slots[0].start.weekday() == 0  # Monday

# PII scrubber testing
result = scrub_pii("my number is 9876543210")
assert result.pii_found is True
assert "9876543210" not in result.cleaned_text
assert "[REDACTED]" in result.cleaned_text
```

### 12.3 Training Set (data/training_set.py)

12 executable dialogue flows covering all paths:

| Flow | Scenario |
|---|---|
| 1 | Happy path — pick option 1 |
| 2 | Requested time unavailable — fallback slots offered |
| 3 | User changes preference mid-flow |
| 4 | User asks availability question in S6 |
| 5 | No suitable slot — join waitlist |
| 6 | Decline waitlist → end call |
| 7 | Reschedule existing booking |
| 8 | Cancel existing booking |
| 9 | Compliance refusal (investment advice) → then books |
| 10 | Out-of-scope question → then books |
| 11 | 3× silence → error → farewell |
| 12 | Happy path — pick option 2 (with reference transcript) |

Run all flows:
```bash
python3 data/training_set.py
```

---

---

## 13. AI Evals Architecture

### 13.1 Overview

The evals suite at `evals/` provides automated measurement of AI component quality. Unlike unit/integration tests (which verify code correctness), evals verify **model behaviour** — intent classification accuracy, slot extraction F1, compliance recall, conversation flow correctness, and response quality.

### 13.2 Directory Structure

```
evals/
├── datasets/
│   ├── intent_classification.json   # 45 cases: 10 intent types, EN + Hindi
│   ├── slot_extraction.json         # 20 cases: topic, day, time, booking code
│   ├── compliance.json              # 20 cases: advice refusal, PII, out-of-scope
│   └── conversation_flows.json      # 10 multi-turn flows with expected final states
├── evaluators/
│   ├── intent_eval.py               # IntentRouter accuracy per category
│   ├── slot_eval.py                 # Slot precision / recall / F1
│   ├── compliance_eval.py           # Safety recall for refuse_advice + refuse_pii
│   ├── conversation_eval.py         # FSM end-to-end flows (mocked MCP + src.booking)
│   └── llm_judge.py                 # Claude rates agent responses (tone/clarity/compliance)
├── results/                         # JSON output from each run (timestamped)
└── run_evals.py                     # Main runner — CLI flags, rich terminal output
```

### 13.3 Eval Suites

#### Suite 1 — Intent Classification (`intent_eval.py`)
- **What:** Feeds each test utterance through `IntentRouter.route()` and compares predicted intent to expected.
- **Metrics:** Overall accuracy + per-category breakdown (basic, compliance, hindi, code_variations, etc.)
- **Why:** The LLM chain (Groq → Claude → rule-based) must correctly distinguish 10 intents across languages, accents, and phrasing.
- **Failure modes caught:** Rule-based fallback classifying all ambiguous inputs as `book_new`; Hindi reschedule phrases misclassified.

#### Suite 2 — Slot Extraction (`slot_eval.py`)
- **What:** Routes each test input and checks `LLMResponse.slots` against expected slot values (fuzzy substring match).
- **Metrics:** Per-slot precision, recall, F1 for `topic`, `day_preference`, `time_preference`, `existing_booking_code`.
- **Why:** Incorrect slot extraction causes downstream FSM failures (wrong topic booked, reschedule fails to find code).
- **Key result:** Booking code extraction achieves 1.000 F1 even for Whisper variants like "N L A B 2 3".

#### Suite 3 — Compliance / Safety (`compliance_eval.py`)
- **What:** Routes compliance-sensitive inputs and checks `LLMResponse.compliance_flag` or mapped intent.
- **Metrics:** Per-flag F1 + **safety false negatives** (FN on `refuse_advice`/`refuse_pii` tracked separately as a critical metric).
- **Why:** A compliance false negative (agent fails to refuse investment advice or accepts PII) is a regulatory violation under SEBI.
- **Target:** Safety recall = 1.0 for `refuse_advice` and `refuse_pii`.

#### Suite 4 — Conversation Flows (`conversation_eval.py`)
- **What:** Runs multi-turn dialogue scenarios through `DialogueFSM.process_turn()` with:
  - `IntentRouter` for per-turn NLU
  - `src.booking.*` mocked via `unittest.mock.patch.dict(sys.modules, ...)`
  - MCP orchestrator mocked (`dispatch_mcp_sync`, `reschedule_booking_mcp_sync`, `cancel_booking_mcp_sync`)
- **Metrics:** Flow pass rate — each flow checks final state, booking code presence, topic correctness.
- **Scenarios covered:** New booking (KYC/SIP), reschedule, cancel (confirm + abort), what-to-prepare, compliance refusal, no-input x3 → ERROR, end-call, Hindi booking.

#### Suite 5 — LLM-as-Judge (`llm_judge.py`)
- **What:** Claude (`claude-haiku-4-5-20251001`) scores 8 sample agent responses on:
  - `tone` (1–5): Professional, warm, not robotic
  - `compliance` (0/1): No investment advice; no PII accepted
  - `clarity` (1–5): Clear and easy to understand
  - `helpfulness` (1–5): Advances the user's goal
- **Why:** Unit tests cannot detect degraded response quality (e.g., cold/robotic tone, vague refusals, unhelpful reprompts).
- **Requires:** `ANTHROPIC_API_KEY` in environment.

### 13.4 Mocking Strategy for Conversation Flows

The conversation eval faces a Python namespace conflict: phase2 owns the `src.*` package namespace, but phase1 provides `src.booking.*` which the FSM imports lazily. The solution:

```python
# Inject mock src.booking.* modules into sys.modules at test time
with mock.patch.dict(sys.modules, _make_booking_modules()):
    ctx, speech = fsm.process_turn(ctx, user_input, llm_resp)
```

`_make_booking_modules()` returns a dict of `types.ModuleType` objects registered as:
- `src.booking` — package stub
- `src.booking.slot_resolver` — returns 2 mock `CalendarSlot` objects with real `datetime` fields
- `src.booking.booking_code_generator` — returns `NL-EVAL01`, `NL-EVAL02`, ...
- `src.booking.secure_url_generator` — returns a mock URL
- `src.booking.waitlist_handler` — returns a mock waitlist entry
- `src.booking.waitlist_queue` — returns a mock queue with `size() = 0`

This means conversation evals run in ~3 seconds with zero external API calls.

### 13.5 Running Evals

```bash
# Fast offline mode — rule-based fallback, no API (3 seconds)
python3 evals/run_evals.py --offline --no-judge

# Full LLM mode — uses Groq + Claude APIs
python3 evals/run_evals.py

# Single suite
python3 evals/run_evals.py --only flows

# Exit code: 1 if any suite scores below 70%
```

### 13.6 Baseline Scores (Rule-Based Offline Mode)

| Suite | Metric | Score | Notes |
|-------|--------|-------|-------|
| Intent Classification | Accuracy | 68.9% | Rule-based floor; LLM mode ~95%+ |
| Slot Extraction | Full Match Rate | 85.0% | Booking code F1 = 1.000 |
| Compliance | Accuracy | 50.0% | Rule-based misses PII + out-of-scope; LLM handles both |
| Conversation Flows | Pass Rate | 90.0% | 9/10 flows pass end-to-end |
| LLM Judge | — | Requires API | ~4.2/5 tone, 100% compliance pass |

---

*End of Low-Level Architecture Document*
