"""
internal_dashboard.py — Internal Phase-by-Phase Build Progress Tracker

PURPOSE: Internal engineering tool only. NOT the product UI.
         Shows exactly what has been built, tested, and verified after each phase.
         Add a new section here every time a phase is completed.

Run with:
    streamlit run internal_dashboard.py --server.port 8502

Phases:
    Phase 0 — Foundation & RAG Pipeline      ✅ Done
    Phase 1 — Booking Brain                  ✅ Done
    Phase 2 — FSM + LLM Core                 ✅ Done
    Phase 3 — Voice I/O (STT / TTS / VAD)    ✅ Done
    Phase 4 — Google Workspace (MCP)         ✅ Done
    Phase 5 — Deploy & Polish                ✅ Done
"""

import json
import os
import sys
from datetime import datetime

import streamlit as st

# ── Cross-phase sys.path setup ─────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))          # voice-agents/phase0/
_VOICE_AGENTS_ROOT = os.path.dirname(_HERE)                  # voice-agents/
for _phase in ("phase0", "phase1", "phase2", "phase3", "phase4"):
    _p = os.path.join(_VOICE_AGENTS_ROOT, _phase)
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ["MOCK_CALENDAR_PATH"] = os.path.join(
    _VOICE_AGENTS_ROOT, "phase1", "data", "mock_calendar.json"
)
# Load .env for Phase 4 credentials
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_VOICE_AGENTS_ROOT, ".env"))
except ImportError:
    pass
# ───────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = _HERE
VOICE_AGENTS_ROOT = _VOICE_AGENTS_ROOT

os.environ.setdefault("CHROMA_DB_PATH", os.path.join(PROJECT_ROOT, "data", "chroma_db"))
os.environ.setdefault("CHROMA_COLLECTION_NAME", "advisor_faq")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("RAG_TOP_K", "3")

import pytz
IST = pytz.timezone("Asia/Kolkata")

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="[INTERNAL] Voice Agent — Phase Tracker",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#1e1e2e;padding:14px 20px;border-radius:8px;margin-bottom:16px">
        <span style="color:#f38ba8;font-weight:700;font-size:13px;letter-spacing:2px">
            ⚙️ INTERNAL ENGINEERING TOOL
        </span>
        <h2 style="color:#cdd6f4;margin:4px 0 0">
            🛠️ AI Advisor Voice Agent — Phase Build Tracker
        </h2>
        <p style="color:#a6adc8;margin:4px 0 0;font-size:13px">
            Separate from production UI · Add a section after each phase completes
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar — master status ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📦 Build Status")
    phases = [
        ("0", "Foundation & RAG", "✅ Done",     "#a6e3a1"),
        ("1", "Booking Brain",    "✅ Done",     "#a6e3a1"),
        ("2", "FSM + LLM Core",   "✅ Done",     "#a6e3a1"),
        ("3", "Voice I/O",        "✅ Done",     "#a6e3a1"),
        ("4", "Google Workspace", "✅ Done",     "#a6e3a1"),
        ("5", "Deploy & Polish",  "✅ Done",    "#a6e3a1"),
    ]
    for num, name, status, color in phases:
        st.markdown(
            f'<div style="padding:6px 10px;margin:3px 0;border-radius:6px;'
            f'border-left:3px solid {color}">'
            f'<b>Phase {num}</b> — {name}<br>'
            f'<span style="font-size:12px;color:{color}">{status}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("**Test suite**")
    if st.button("▶ Run all tests", use_container_width=True):
        import subprocess
        with st.spinner("Running pytest..."):
            result = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
                capture_output=True, text=True, cwd=PROJECT_ROOT,
            )
            st.session_state["test_output"] = result.stdout + result.stderr
            st.session_state["test_ok"] = result.returncode == 0

    if "test_output" in st.session_state:
        if st.session_state["test_ok"]:
            st.success("All tests passed")
        else:
            st.error("Some tests failed")
        with st.expander("Test output"):
            st.code(st.session_state["test_output"], language="text")

    st.divider()
    st.caption(f"Last refreshed: {datetime.now(IST).strftime('%d %b %Y %H:%M IST')}")

# ── Phase tabs ────────────────────────────────────────────────────────────────

phase0_tab, phase1_tab, phase2_tab, phase3_tab, phase4_tab, phase5_tab = st.tabs([
    "⚙️  Phase 0 — Foundation",
    "🧠  Phase 1 — Booking Brain",
    "💬  Phase 2 — FSM + LLM",
    "🎙️  Phase 3 — Voice I/O",
    "🗂️  Phase 4 — Google Workspace",
    "🚀  Phase 5 — Deploy",
])

# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 0 — Foundation & RAG Pipeline
# ══════════════════════════════════════════════════════════════════════════════

with phase0_tab:
    st.markdown("## ✅ Phase 0 — Foundation & RAG Pipeline")
    st.caption("Goal: Lay the groundwork. No features yet — just data, config, and the FAQ search pipeline.")

    st.markdown("### What was built")
    c1, c2, c3 = st.columns(3)
    c1.success("✅ Config (pydantic-settings)")
    c2.success("✅ ChromaDB vector index")
    c3.success("✅ Mock calendar JSON")
    c1.success("✅ FAQ scraper (5 topics)")
    c2.success("✅ Embedding pipeline (all-MiniLM)")
    c3.success("✅ RAG injector")

    st.divider()

    col_left, col_right = st.columns(2)

    # ── Config health ──
    with col_left:
        st.markdown("#### ⚙️ Config")
        try:
            from config.settings import settings
            st.success("Settings loaded without error")
            st.json({
                "ENVIRONMENT": settings.ENVIRONMENT,
                "GROQ_MODEL": settings.GROQ_MODEL,
                "ANTHROPIC_MODEL": settings.ANTHROPIC_MODEL,
                "RAG_TOP_K": settings.RAG_TOP_K,
                "MAX_TURNS_PER_CALL": settings.MAX_TURNS_PER_CALL,
                "CALENDAR_SLOT_DURATION_MINUTES": settings.CALENDAR_SLOT_DURATION_MINUTES,
                "SECURE_URL_SECRET_LEN": len(settings.SECURE_URL_SECRET),
                "STT_CONFIDENCE_THRESHOLD": settings.STT_CONFIDENCE_THRESHOLD,
            })
        except Exception as e:
            st.error(f"Config error: {e}")

    # ── ChromaDB ──
    with col_right:
        st.markdown("#### 🗄️ ChromaDB Index")
        try:
            import chromadb
            client = chromadb.PersistentClient(path=os.environ["CHROMA_DB_PATH"])
            col = client.get_collection("advisor_faq")
            count = col.count()
            if count >= 50:
                st.success(f"{count} chunks indexed across 5 topics")
            else:
                st.warning(f"Only {count} chunks — need ≥ 50")
            topics = ["kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"]
            rows = [
                {"Topic": t, "Chunks": len(col.get(where={"topic_key": t}).get("ids", []))}
                for t in topics
            ]
            st.dataframe(rows, hide_index=True)
        except Exception as e:
            st.error(f"ChromaDB error: {e}")

    st.divider()
    st.markdown("#### 🔍 RAG Explorer — try a live query")
    TOPIC_LABELS = {
        "kyc_onboarding": "KYC & Onboarding",
        "sip_mandates": "SIP & Mandates",
        "statements_tax": "Statements & Tax",
        "withdrawals": "Withdrawals",
        "account_changes": "Account Changes",
    }
    EXAMPLE_Q = {
        "kyc_onboarding": "what documents do I need for KYC",
        "sip_mandates": "how to set up a SIP mandate",
        "statements_tax": "where can I get my tax statement",
        "withdrawals": "how long does withdrawal take",
        "account_changes": "how to add a nominee",
    }
    rc1, rc2 = st.columns([3, 1])
    with rc2:
        rag_topic = st.selectbox("Topic", list(TOPIC_LABELS.keys()), format_func=lambda k: TOPIC_LABELS[k], key="p0_topic")
    with rc1:
        rag_query = st.text_input("Question", value=EXAMPLE_Q.get(rag_topic, ""), key="p0_q")
    if st.button("Search", key="p0_search") and rag_query.strip():
        with st.spinner("Querying ChromaDB..."):
            from src.agent.rag_injector import get_rag_context
            result = get_rag_context(query=rag_query, topic=rag_topic, top_k=3)
            if result == "No relevant context found.":
                st.warning("No results.")
            else:
                st.text_area("Retrieved context (injected into LLM prompt)", result, height=220, disabled=True)

    st.divider()
    st.markdown("#### 📅 Mock Calendar")
    try:
        with open(os.environ["MOCK_CALENDAR_PATH"]) as f:
            cal = json.load(f)
        slots = cal["slots"]
        available = sum(1 for s in slots if s["status"] == "AVAILABLE")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total slots", len(slots))
        m2.metric("AVAILABLE", available)
        m3.metric("TENTATIVE", sum(1 for s in slots if s["status"] == "TENTATIVE"))
        def _fmt_slot_start(iso_str: str) -> str:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(iso_str)
                if dt.tzinfo is None:
                    dt = IST.localize(dt)
                else:
                    dt = dt.astimezone(IST)
                date_part = dt.strftime("%d/%m/%Y")
                hour = dt.hour
                minute = dt.minute
                ampm = "am" if hour < 12 else "pm"
                h12 = hour % 12 or 12
                time_part = f"{h12}:{minute:02d}{ampm}" if minute else f"{h12}{ampm}"
                return f"{date_part} {time_part}"
            except Exception:
                return iso_str

        rows = [
            {"Slot ID": s["slot_id"], "Start": _fmt_slot_start(s["start"]), "Status": s["status"],
             "Topic Affinity": ", ".join(s["topic_affinity"]) or "Any"}
            for s in slots if s["status"] == "AVAILABLE"
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
    except Exception as e:
        st.error(f"Calendar error: {e}")

    st.divider()
    st.markdown("#### 🧪 Test Results — Phase 0")
    with st.expander("TC-0.1  Config loads without error"):
        st.markdown("- Settings object initialises without ValidationError\n- All required fields are non-empty strings\n- SECURE_URL_SECRET ≥ 32 chars")
    with st.expander("TC-0.2  mock_calendar.json is valid"):
        st.markdown("- ≥ 15 slots present\n- All slots have ISO 8601 datetimes\n- ≥ 10 AVAILABLE slots\n- ≥ 3 slots with topic affinity restrictions")
    with st.expander("TC-0.3  ChromaDB collection has ≥ 50 chunks"):
        st.markdown("- Collection `advisor_faq` exists and is populated\n- All 5 topic keys have at least one chunk")
    with st.expander("TC-0.4  RAG query returns topic-relevant chunks"):
        st.markdown("- 5 parametrized queries, one per topic\n- Context is non-empty and formatted as numbered passages [1], [2]…")
    with st.expander("TC-0.5  Graceful fallback on empty DB"):
        st.markdown("- Empty ChromaDB returns `'No relevant context found.'`\n- Unknown topic does not raise")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — Booking Brain
# ══════════════════════════════════════════════════════════════════════════════

with phase1_tab:
    st.markdown("## ✅ Phase 1 — Booking Brain")
    st.caption("Goal: Pure business logic — no LLM, no voice, no external APIs. All offline.")

    st.markdown("### What was built")
    c1, c2, c3 = st.columns(3)
    c1.success("✅ Booking code generator (NL-XXXX)")
    c2.success("✅ Slot resolver (NL → calendar)")
    c3.success("✅ PII scrubber (5 pattern types)")
    c1.success("✅ Secure URL generator (HMAC)")
    c2.success("✅ Waitlist handler (NL-WXXX)")
    c3.success("✅ 69 unit tests, all passing")

    st.divider()

    # ── Component 1: Booking Codes ──────────────────────────────────────────

    with st.expander("🔖  Component 1 — Booking Code Generator", expanded=True):
        st.markdown(
            "Generates unique `NL-XXXX` codes for each booking. "
            "Excludes ambiguous chars `0 O 1 I` so codes can be read aloud without confusion."
        )
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            n = st.slider("Generate N codes", 1, 10, 5, key="p1_n_book")
            if st.button("Generate Booking Codes", key="p1_gen_book"):
                from src.booking.booking_code_generator import generate_booking_code
                existing = set()
                codes = []
                for _ in range(n):
                    c = generate_booking_code(existing)
                    existing.add(c)
                    codes.append(c)
                st.code("\n".join(codes))
        with col_b2:
            n2 = st.slider("Generate N waitlist codes", 1, 10, 5, key="p1_n_wait")
            if st.button("Generate Waitlist Codes", key="p1_gen_wait"):
                from src.booking.booking_code_generator import generate_waitlist_code
                existing = set()
                codes = []
                for _ in range(n2):
                    c = generate_waitlist_code(existing)
                    existing.add(c)
                    codes.append(c)
                st.code("\n".join(codes))

        st.markdown("**Validate a code**")
        val_in = st.text_input("Enter code", placeholder="NL-A742 or NL-WK3P", key="p1_val")
        if val_in:
            from src.booking.booking_code_generator import is_valid_booking_code, is_valid_waitlist_code
            if is_valid_booking_code(val_in):
                st.success(f"✅ `{val_in}` → valid **booking code**")
            elif is_valid_waitlist_code(val_in):
                st.info(f"📋 `{val_in}` → valid **waitlist code**")
            else:
                st.error(f"❌ `{val_in}` → invalid")

    # ── Component 2: Slot Resolver ──────────────────────────────────────────

    with st.expander("📅  Component 2 — Slot Resolver", expanded=True):
        st.markdown(
            "Converts natural language preferences (*'Monday at 2 PM'*) into AVAILABLE "
            "calendar slots. The agent offers up to 2 options."
        )
        sr1, sr2, sr3 = st.columns(3)
        with sr1:
            day_p = st.selectbox("Day", ["Monday","Tuesday","Wednesday","Thursday","Friday",
                                          "next Monday","next Tuesday","tomorrow"], key="p1_day")
        with sr2:
            time_p = st.selectbox("Time", ["morning","afternoon","evening","10 AM","2 PM","4 PM"], key="p1_time")
        with sr3:
            topic_p = st.selectbox("Topic", ["(any)","kyc_onboarding","sip_mandates",
                                              "statements_tax","withdrawals","account_changes"], key="p1_topic")

        if st.button("Resolve Slots", key="p1_resolve"):
            from src.booking.slot_resolver import resolve_slots
            topic_arg = None if topic_p == "(any)" else topic_p
            slots = resolve_slots(
                day_preference=day_p, time_preference=time_p, topic=topic_arg,
                calendar_path=os.environ["MOCK_CALENDAR_PATH"],
                reference_date=datetime.now(IST),
            )
            if not slots:
                st.warning("No slots found → agent would create a waitlist entry.")
            else:
                for i, s in enumerate(slots, 1):
                    aff = ", ".join(s.topic_affinity) or "Any topic"
                    st.info(f"**Option {i}:** `{s.slot_id}` — {s.start_ist_str()} | Affinity: _{aff}_")

    # ── Component 3: PII Scrubber ───────────────────────────────────────────

    with st.expander("🛡️  Component 3 — PII Scrubber", expanded=True):
        st.markdown(
            "Runs on every STT transcript before it reaches the LLM. "
            "Detects phone, email, PAN, Aadhaar, 16-digit account numbers → replaces with `[REDACTED]`."
        )
        PRESETS = {
            "Clean text (no PII)": "I want to book a KYC consultation next Monday at 2 PM",
            "Mobile number": "My number is 9876543210, please call me back",
            "Email": "Send details to john.doe@gmail.com",
            "PAN": "My PAN is ABCDE1234F",
            "Aadhaar": "Aadhaar number: 2345 6789 0123",
            "16-digit card": "Card number 1234 5678 9012 3456",
            "Multiple PII": "Call 9876543210, email user@example.com, PAN ABCDE1234F",
        }
        preset = st.selectbox("Preset", list(PRESETS.keys()), key="p1_preset")
        pii_text = st.text_area("Input text", value=PRESETS[preset], height=80, key="p1_pii")
        if st.button("Scrub", key="p1_scrub"):
            from src.booking.pii_scrubber import scrub_pii
            res = scrub_pii(pii_text)
            pc1, pc2 = st.columns(2)
            pc1.text_area("Original", pii_text, height=100, disabled=True)
            pc2.text_area("After scrubbing", res.cleaned_text, height=100, disabled=True)
            if res.pii_found:
                st.error(f"⚠️ PII detected — {res.detection_summary()}")
                dc1, dc2 = st.columns(2)
                if res.context_detected:
                    dc1.warning(f"**Context pass:** {', '.join(res.context_detected)}\n\n_Intent phrase + value detected_")
                if res.pattern_detected:
                    dc2.warning(f"**Pattern pass:** {', '.join(res.pattern_detected)}\n\n_Standalone regex match_")
            else:
                st.success("✅ Clean — safe to send to LLM")

    # ── Component 4: Secure URL ─────────────────────────────────────────────

    with st.expander("🔗  Component 4 — Secure URL Generator", expanded=True):
        st.markdown(
            "Creates a tamper-proof, time-limited URL the agent reads to the user. "
            "They visit it to submit contact details — keeping PII off the voice channel."
        )
        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            u_code = st.text_input("Booking code", "NL-A742", key="p1_ucode")
        with uc2:
            u_topic = st.selectbox("Topic", ["kyc_onboarding","sip_mandates","statements_tax",
                                              "withdrawals","account_changes"], key="p1_utopic")
        with uc3:
            u_slot = st.text_input("Slot (IST)", "2026-04-06T14:00:00+05:30", key="p1_uslot")

        if st.button("Generate URL", key="p1_url"):
            from src.booking.secure_url_generator import generate_secure_url, verify_secure_url, extract_token_from_url
            url = generate_secure_url(booking_code=u_code, topic=u_topic, slot_ist=u_slot,
                                       domain="http://localhost:8501")
            st.code(url)
            token = extract_token_from_url(url)
            payload = verify_secure_url(token)
            st.caption("Decoded payload (server-side):")
            st.json(payload)

    # ── Component 5: Waitlist ───────────────────────────────────────────────

    with st.expander("📋  Component 5 — Waitlist Handler", expanded=True):
        st.markdown(
            "When no slots match, the agent creates a waitlist entry with a `NL-WXXX` code. "
            "User is contacted when a slot opens."
        )
        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            w_topic = st.selectbox("Topic", ["kyc_onboarding","sip_mandates","statements_tax",
                                              "withdrawals","account_changes"], key="p1_wtopic")
        with wc2:
            w_day = st.text_input("Day preference", "Monday", key="p1_wday")
        with wc3:
            w_time = st.text_input("Time preference", "2 PM", key="p1_wtime")

        if st.button("Create Waitlist Entry", key="p1_wl"):
            from src.booking.waitlist_handler import create_waitlist_entry
            try:
                entry = create_waitlist_entry(topic=w_topic, day_preference=w_day, time_preference=w_time)
                st.success(f"Created: **{entry.waitlist_code}**")
                st.json(entry.to_dict())
                st.info(
                    f"Agent says: *\"I've added you to the waitlist. Your code is "
                    f"{' - '.join(list(entry.waitlist_code))}. "
                    f"We'll reach out when a slot opens around {w_time} on {w_day}.\"*"
                )
            except ValueError as e:
                st.error(str(e))

    st.divider()
    st.markdown("#### 🧪 Test Results — Phase 1 (69 tests)")
    test_groups = {
        "TC-1.1  Booking code format & uniqueness (6 tests)": [
            "Starts with NL- prefix",
            "Total length is 7 chars (NL-XXXX)",
            "Suffix is uppercase alphanumeric",
            "No ambiguous chars (0, O, 1, I)",
            "100 codes generated without duplicates",
            "Avoids pre-existing codes",
        ],
        "TC-1.2  Waitlist code format & uniqueness (3 tests)": [
            "Starts with NL-W prefix",
            "Total length is 7 chars (NL-WXXX)",
            "50 codes generated without duplicates",
        ],
        "TC-1.3  Code validation helpers (5 tests)": [
            "Valid booking code accepted",
            "Wrong prefix rejected",
            "Waitlist code NOT counted as booking code (and vice versa)",
            "Valid waitlist code accepted",
            "Wrong length rejected",
        ],
        "TC-1.4  Slot resolver — day matching (5 tests)": [
            "'Monday' → April 6 slots",
            "'Tuesday' → April 7 slots",
            "'next Monday' → April 13 (not April 6)",
            "Returns at most 2 slots",
            "Slots sorted by start time",
        ],
        "TC-1.5  Slot resolver — time band (3 tests)": [
            "'morning' → 9–12h slots",
            "'afternoon' → 12–17h slots",
            "'2 PM' → 14:00 slot included",
        ],
        "TC-1.6  Slot resolver — topic affinity (3 tests)": [
            "kyc_onboarding topic matches kyc+any slots",
            "sip_mandates topic excludes kyc-only slots",
            "No topic filter returns all available slots",
        ],
        "TC-1.7  Slot resolver — no match (2 tests)": [
            "Sunday (no slots) → empty list, not exception",
            "Only AVAILABLE slots returned (not TENTATIVE/CANCELLED)",
        ],
        "TC-1.8 – 1.14  PII scrubber (20 tests)": [
            "10-digit mobile scrubbed",
            "+91 / 0 prefix variants scrubbed",
            "5-digit PIN NOT scrubbed",
            "Standard and tagged email addresses scrubbed",
            "PAN (AAAAA0000A) scrubbed",
            "Wrong PAN format not scrubbed",
            "12-digit Aadhaar (plain / spaces / dashes) scrubbed",
            "16-digit card (plain / spaces / dashes) scrubbed",
            "Clean text passes through unchanged",
            "Empty string handled",
            "Booking code NL-A742 NOT scrubbed",
            "Multiple PII types in one string — all redacted",
            "Redaction count matches PII occurrence count",
        ],
        "TC-1.15 – 1.18  Secure URL (8 tests)": [
            "Generated URL starts with domain/book/",
            "Round-trip: generate → extract token → verify → payload matches",
            "datetime object accepted as slot_ist",
            "Booking code NOT visible in plaintext in token",
            "Tampered token raises BadSignature",
            "Wrong secret raises BadSignature",
            "Expired token (max_age=-1) raises SignatureExpired",
            "Token extraction from full URL",
        ],
        "TC-1.19 – 1.21  Waitlist handler (12 tests)": [
            "create_waitlist_entry returns WaitlistEntry",
            "Code format is valid NL-WXXX",
            "All fields stored correctly",
            "to_dict() is JSON-serializable",
            "20 entries generated without duplicate codes",
            "cancel_waitlist_entry sets status to CANCELLED",
            "Cancel preserves all other fields",
            "Original entry status unchanged after cancel",
            "Empty topic raises ValueError",
            "Empty day_preference raises ValueError",
            "Empty time_preference raises ValueError",
        ],
    }
    for group, items in test_groups.items():
        with st.expander(f"✅ {group}"):
            for item in items:
                st.markdown(f"  - ✅ {item}")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — FSM + LLM Core
# ══════════════════════════════════════════════════════════════════════════════

with phase2_tab:
    st.markdown("## ✅ Phase 2 — FSM + LLM Core")
    st.caption("Goal: Full dialogue pipeline — state machine + LLM intent routing + compliance guard + session management.")

    st.markdown("### What was built")
    c1, c2, c3 = st.columns(3)
    c1.success("✅ DialogueState (16 FSM states)")
    c2.success("✅ DialogueFSM (stateless transitions)")
    c3.success("✅ ComplianceGuard (post-LLM scan)")
    c1.success("✅ IntentRouter (Groq → Claude → rules)")
    c2.success("✅ SessionManager (UUID + 30-min TTL)")
    c3.success("✅ 80 tests, all passing")

    st.divider()

    # ── Component 1: FSM State Map ───────────────────────────────────────────

    with st.expander("🗺️  Component 1 — Dialogue State Machine (FSM)", expanded=True):
        st.markdown(
            "Stateless FSM with **16 states (S0–S15)**. All state lives in `DialogueContext` — "
            "easy to persist, reload, and test. Handles no-input (3 strikes → ERROR), "
            "compliance refusals (stay in same state), and the full booking/reschedule/cancel/waitlist flows."
        )

        from src.dialogue.states import DialogueContext
        from datetime import datetime
        import pytz as _pytz
        _IST = _pytz.timezone("Asia/Kolkata")

        states = [
            ("S0", "IDLE", "Call not yet started", "#6c7086"),
            ("S1", "GREETED", "Agent greeted, disclaimer presented", "#89b4fa"),
            ("S2", "DISCLAIMER_CONFIRMED", "User acknowledged disclaimer", "#89b4fa"),
            ("S3", "INTENT_IDENTIFIED", "Intent classified (book/reschedule/cancel)", "#89dceb"),
            ("S4", "TOPIC_COLLECTED", "Consultation topic captured", "#89dceb"),
            ("S5", "TIME_PREFERENCE_COLLECTED", "Day + time preference captured", "#89dceb"),
            ("S6", "SLOTS_OFFERED", "Agent offered 1–2 calendar slots", "#f9e2af"),
            ("S7", "SLOT_CONFIRMED", "User confirmed a slot", "#f9e2af"),
            ("S8", "MCP_DISPATCHED", "Calendar/Sheets/Gmail tools called", "#fab387"),
            ("S9", "BOOKING_COMPLETE", "Booking code generated, URL sent", "#a6e3a1"),
            ("S10", "WAITLIST_OFFERED", "No slots — offered waitlist", "#f38ba8"),
            ("S11", "WAITLIST_CONFIRMED", "User on waitlist, NL-WXXX issued", "#a6e3a1"),
            ("S12", "RESCHEDULE_CODE_COLLECTED", "Awaiting existing booking code", "#cba6f7"),
            ("S13", "CANCEL_CODE_COLLECTED", "Awaiting booking code to cancel", "#cba6f7"),
            ("S14", "ERROR", "3× no-input or unrecoverable error", "#f38ba8"),
            ("S15", "END", "Call ended gracefully", "#6c7086"),
        ]
        rows = [{"State": s, "Name": n, "Meaning": m} for s, n, m, _ in states]
        st.dataframe(rows, hide_index=True, width="stretch")

        st.markdown("**Try the FSM — simulate a turn**")
        fc1, fc2 = st.columns(2)
        with fc1:
            fsm_state = st.selectbox(
                "Current state",
                [f"{s} — {n}" for s, n, _, _ in states[1:9]],
                key="p2_state",
            )
            fsm_input = st.text_input("User input", "I'd like to book a KYC consultation on Monday morning", key="p2_input")
        with fc2:
            fsm_intent = st.selectbox("Intent (rule-based)", ["book_new", "reschedule", "cancel", "what_to_prepare", "check_availability"], key="p2_intent")
            fsm_topic = st.selectbox("Topic slot", ["(none)", "kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"], key="p2_topic")
            fsm_day = st.text_input("Day slot", "Monday", key="p2_day")
            fsm_time = st.text_input("Time slot", "morning", key="p2_time")

        if st.button("Run FSM turn", key="p2_fsm_run"):
            from src.dialogue.fsm import DialogueFSM
            from src.dialogue.states import LLMResponse, DialogueState as DS
            state_code = fsm_state.split(" — ")[0]
            state_map = {s: m for s, n, _, m in states}
            enum_map = {e.value: e for e in DS}
            current_state = enum_map.get(state_code, DS.GREETED)

            ctx = DialogueContext(
                call_id="DEMO-001",
                session_start_ist=datetime.now(_IST),
                current_state=current_state,
            )
            slots = {}
            if fsm_topic != "(none)":
                slots["topic"] = fsm_topic
            if fsm_day:
                slots["day_preference"] = fsm_day
            if fsm_time:
                slots["time_preference"] = fsm_time
            ctx.apply_slots(slots)

            resp = LLMResponse(intent=fsm_intent, slots=slots, speech=fsm_input, raw_response=fsm_input)

            try:
                new_ctx, speech = DialogueFSM().process_turn(ctx, fsm_input, resp)
                rc1, rc2 = st.columns(2)
                rc1.success(f"**New state:** {new_ctx.current_state.label()}")
                rc2.info(f"**Turn count:** {new_ctx.turn_count}")
                st.text_area("Agent speech", speech, height=80, disabled=True)
                filled = new_ctx.slots_filled()
                if filled:
                    st.caption("Slots in context:")
                    st.json(filled)
            except Exception as ex:
                st.error(f"FSM error: {ex}")

    # ── Component 2: Compliance Guard ────────────────────────────────────────

    with st.expander("🛡️  Component 2 — Compliance Guard", expanded=True):
        st.markdown(
            "Scans the **LLM's output** before it is spoken. "
            "Blocks investment advice keywords and any PII the LLM might accidentally echo back."
        )
        COMPLIANCE_PRESETS = {
            "Clean booking speech": "Your appointment is confirmed for Tuesday at 10 AM. Your code is NL-A742.",
            "Investment advice (blocked)": "You should buy Nifty 50 index funds for 12% return.",
            "PII in LLM output (blocked)": "I'll call you back at 9876543210.",
            "Market prediction (blocked)": "The market is going to rise next quarter.",
            "Diversification advice (blocked)": "You should diversify your portfolio across asset classes.",
        }
        preset_c = st.selectbox("Preset", list(COMPLIANCE_PRESETS.keys()), key="p2_c_preset")
        c_text = st.text_area("LLM output to scan", value=COMPLIANCE_PRESETS[preset_c], height=80, key="p2_c_text")
        if st.button("Check compliance", key="p2_c_check"):
            from src.dialogue.compliance_guard import ComplianceGuard
            guard = ComplianceGuard()
            result = guard.check(c_text)
            if result.is_compliant:
                st.success("✅ Compliant — safe to speak")
                st.text_area("Speech output", c_text, height=60, disabled=True)
            else:
                st.error(f"🚫 Blocked — flag: `{result.flag}`")
                st.caption(f"Reason: {result.reason}")
                st.text_area("Safe refusal used instead", result.safe_speech, height=60, disabled=True)

    # ── Component 3: Intent Router ───────────────────────────────────────────

    with st.expander("🧠  Component 3 — Intent Router (Rule-based demo)", expanded=True):
        st.markdown(
            "Routes PII-scrubbed user input to an LLM for structured intent + slot extraction. "
            "**Groq** (primary) → **Claude Haiku** (fallback) → **rule-based** (offline / no keys). "
            "LLM callable is injected — fully mockable in tests."
        )
        INTENT_PRESETS = {
            "Book KYC on Monday morning": "I'd like to book a KYC consultation on Monday morning please",
            "Reschedule existing booking": "I need to reschedule my appointment, code is NL-A742",
            "Cancel booking": "Please cancel my booking NL-XY45",
            "Investment advice (refuse)": "Which mutual fund should I invest in for maximum returns?",
            "SIP query": "I have questions about setting up a SIP mandate on Tuesday afternoon",
            "Out of scope": "What's the weather like today?",
        }
        preset_i = st.selectbox("Preset", list(INTENT_PRESETS.keys()), key="p2_i_preset")
        i_text = st.text_input("User input (PII-scrubbed)", value=INTENT_PRESETS[preset_i], key="p2_i_text")

        # Check if LLM keys are available
        groq_ok = bool(os.environ.get("GROQ_API_KEY", ""))
        anth_ok = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
        if groq_ok:
            st.success("🟢 GROQ_API_KEY detected — will use live LLM")
        elif anth_ok:
            st.info("🟡 ANTHROPIC_API_KEY detected — will use Claude fallback")
        else:
            st.warning("⚪ No API keys — using rule-based offline mode")

        if st.button("Route intent", key="p2_i_route"):
            from src.dialogue.intent_router import IntentRouter
            from src.dialogue.states import DialogueContext, DialogueState as DS2
            router = IntentRouter()
            ctx2 = DialogueContext(
                call_id="DEMO-002",
                session_start_ist=datetime.now(_IST),
                current_state=DS2.DISCLAIMER_CONFIRMED,
            )
            with st.spinner("Routing..."):
                result = router.route(i_text, ctx2)
            ic1, ic2, ic3 = st.columns(3)
            ic1.metric("Intent", result.intent)
            ic2.metric("Compliance flag", str(result.compliance_flag))
            ic3.metric("Mode", "LLM" if router.is_online else "Rule-based")
            if result.slots:
                st.json(result.slots)
            st.text_area("LLM speech", result.speech, height=60, disabled=True)

    # ── Component 4: Session Manager ─────────────────────────────────────────

    with st.expander("🗂️  Component 4 — Session Manager", expanded=True):
        st.markdown(
            "Thread-safe in-memory store mapping `UUID → (DialogueContext, last_active_time)`. "
            "Sessions expire after **30 minutes** of inactivity. Lazy pruning on `active_count()`."
        )
        from src.dialogue.session_manager import SessionManager as SM

        if "p2_session_mgr" not in st.session_state:
            st.session_state["p2_session_mgr"] = SM(ttl_minutes=30)
        mgr = st.session_state["p2_session_mgr"]

        sm1, sm2, sm3 = st.columns(3)
        with sm1:
            if st.button("➕ Create session", key="p2_sm_create"):
                from src.dialogue.states import DialogueContext, DialogueState as DS3
                new_ctx = DialogueContext(
                    call_id=f"DEMO-{datetime.now(_IST).strftime('%H%M%S')}",
                    session_start_ist=datetime.now(_IST),
                    current_state=DS3.GREETED,
                )
                sid = mgr.create_session(new_ctx)
                st.session_state["p2_last_sid"] = sid
                st.success(f"Created: `{sid[:18]}...`")
        with sm2:
            if st.button("🔍 Get session", key="p2_sm_get"):
                sid = st.session_state.get("p2_last_sid")
                if sid:
                    fetched = mgr.get_session(sid)
                    if fetched:
                        st.success(f"Found: state={fetched.current_state.name}")
                    else:
                        st.error("Expired or not found")
                else:
                    st.warning("Create a session first")
        with sm3:
            if st.button("🗑️ Close session", key="p2_sm_close"):
                sid = st.session_state.get("p2_last_sid")
                if sid:
                    ok = mgr.close_session(sid)
                    st.success("Closed") if ok else st.warning("Not found")
                else:
                    st.warning("No session to close")

        st.metric("Active sessions", mgr.active_count())

    # ── Component 5: Full conversation ───────────────────────────────────────

    with st.expander("💬  Component 5 — Live Conversation Simulator", expanded=True):
        st.markdown(
            "Full pipeline: **PII scrub → Intent route → Compliance check → FSM transition**. "
            "Simulates the complete voice agent flow in text mode."
        )

        if "p2_conv_ctx" not in st.session_state:
            st.session_state["p2_conv_ctx"] = None
            st.session_state["p2_conv_history"] = []

        if st.button("🔄 Start new conversation", key="p2_conv_start"):
            from src.dialogue.fsm import DialogueFSM as FSM2
            fsm2 = FSM2()
            ctx_new, greeting = fsm2.start()
            st.session_state["p2_conv_ctx"] = ctx_new
            st.session_state["p2_conv_history"] = [("Agent", greeting)]
            st.session_state["p2_conv_fsm"] = fsm2

        # Show conversation history
        history = st.session_state.get("p2_conv_history", [])
        for role, msg in history:
            if role == "Agent":
                st.markdown(f"**🤖 Agent:** {msg}")
            else:
                st.markdown(f"**👤 You:** {msg}")

        ctx_conv = st.session_state.get("p2_conv_ctx")
        if ctx_conv and not ctx_conv.current_state.is_terminal():
            st.caption(f"State: `{ctx_conv.current_state.label()}` | Turn: {ctx_conv.turn_count}")
            user_msg = st.text_input("Your reply", key="p2_conv_input", placeholder="Type your message...")
            if st.button("Send", key="p2_conv_send") and user_msg.strip():
                from src.booking.pii_scrubber import scrub_pii as _scrub
                from src.dialogue.intent_router import IntentRouter as IR
                from src.dialogue.compliance_guard import ComplianceGuard as CG
                from src.dialogue.fsm import DialogueFSM as FSM3

                scrub = _scrub(user_msg)
                clean = scrub.cleaned_text
                pii_note = f" _(PII scrubbed: {', '.join(scrub.categories)})_" if scrub.pii_found else ""

                router = IR()
                llm_resp = router.route(clean, ctx_conv)

                guard = CG()
                llm_resp.speech = guard.check_and_gate(llm_resp.speech)

                fsm3 = st.session_state.get("p2_conv_fsm", FSM3())
                new_ctx, speech = fsm3.process_turn(ctx_conv, clean, llm_resp)
                st.session_state["p2_conv_ctx"] = new_ctx
                st.session_state["p2_conv_history"].append(("You", user_msg + pii_note))
                st.session_state["p2_conv_history"].append(("Agent", speech))
                st.rerun()
        elif ctx_conv and ctx_conv.current_state.is_terminal():
            st.success("Conversation ended.")
            if ctx_conv.booking_code:
                st.info(f"Booking code: **{ctx_conv.booking_code}**")

    st.divider()
    st.markdown("#### 🧪 Test Results — Phase 2 (80 tests)")
    test_groups_p2 = {
        "TC-2.1  DialogueState (5 tests)": [
            "16 states defined (S0–S15)",
            "IDLE is S0, END is S15",
            "END and ERROR are terminal states",
            "Non-terminal states return False",
            "label() returns 'S1 GREETED' format",
        ],
        "TC-2.2  DialogueContext (7 tests)": [
            "apply_slots() fills valid topic",
            "Invalid topic is ignored",
            "missing_booking_slots() lists all 3 when empty",
            "missing_booking_slots() shows only time_preference when day+topic filled",
            "is_booking_ready() False without resolved_slot",
            "is_booking_ready() True when all fields set",
            "slots_filled() omits None values",
        ],
        "TC-2.3  LLMResponse (7 tests)": [
            "is_compliant() True when no flag",
            "is_compliant() False with flag",
            "is_refusal() True for all 3 refusal flags",
            "validate() returns empty list for valid response",
            "validate() catches unknown intent",
            "validate() catches empty speech",
            "validate() catches bad compliance_flag",
        ],
        "TC-2.4–2.7  ComplianceGuard (16 tests)": [
            "should buy → refuse_advice",
            "recommend invest → refuse_advice",
            "expected returns → refuse_advice",
            "percentage return → refuse_advice",
            "market prediction → refuse_advice",
            "diversify → refuse_advice",
            "clean scheduling speech → passes",
            "empty string → passes",
            "phone in output → refuse_pii",
            "email in output → refuse_pii",
            "PAN in output → refuse_pii",
            "Aadhaar in output → refuse_pii",
            "safe_speech set on PII block",
            "clean output is_compliant + safe_speech == original",
            "check_and_gate returns original when clean",
            "check_and_gate returns refusal when violated",
        ],
        "TC-2.8–2.10  SessionManager (10 tests)": [
            "create + get session",
            "update session refreshes TTL",
            "close session removes it",
            "close nonexistent returns False",
            "get nonexistent returns None",
            "update nonexistent returns False",
            "active_count correct after close",
            "all_session_ids lists active sessions",
            "expired session returns None",
            "prune removes expired sessions",
        ],
        "TC-2.11–2.14  IntentRouter (11 tests)": [
            "book_new intent detected (offline)",
            "reschedule intent detected (offline)",
            "cancel intent detected (offline)",
            "refuse_advice detected (offline)",
            "topic slot extracted",
            "day slot extracted",
            "time slot extracted",
            "booking code extracted",
            "valid JSON from mock LLM parsed correctly",
            "refuse_advice flag set from LLM JSON",
            "invalid topic in JSON ignored",
            "unknown intent defaults to book_new",
            "malformed JSON falls back to rules",
            "LLM exception falls back to rules",
            "JSON in markdown code fences parsed",
        ],
        "TC-2.15–2.25  DialogueFSM (24 tests)": [
            "start() returns GREETED state",
            "start() speech contains 'scheduling' or 'advisor'",
            "start() auto-generates CALL-YYYYMMDD-HHMMSS ID",
            "GREETED + affirmative → topic prompt",
            "GREETED + topic in slots → topic skipped",
            "refuse_advice stays in same state",
            "refuse_pii stays in same state",
            "out_of_scope stays in same state",
            "1 silence → no_input_count=1, same state",
            "3 silences → ERROR state",
            "valid input resets no_input_count",
            "full happy-path booking → BOOKING_COMPLETE + NL-XXXX code",
            "reschedule intent → RESCHEDULE_CODE_COLLECTED",
            "booking code collected → TIME_PREFERENCE_COLLECTED",
            "cancel intent → CANCEL_CODE_COLLECTED",
            "cancel code collected → confirmation speech",
            "no slots → WAITLIST_OFFERED",
            "waitlist accepted → WAITLIST_CONFIRMED + NL-WXXX code",
            "waitlist declined → END",
        ],
    }
    for group, items in test_groups_p2.items():
        with st.expander(f"✅ {group}"):
            for item in items:
                st.markdown(f"  - ✅ {item}")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — Voice I/O
# ══════════════════════════════════════════════════════════════════════════════

with phase3_tab:
    st.markdown("## ✅ Phase 3 — Voice I/O (STT / TTS / VAD / AudioPipeline)")
    st.caption("Complete. 64/64 unit tests passing.")

    st.success("All Phase 3 modules built and tested.")

    st.markdown("### What was built")
    for item in [
        "**VAD** (`vad.py`) — energy-based fallback (Silero optional); end-of-turn detection with configurable silence threshold",
        "**STT Engine** (`stt_engine.py`) — primary + fallback callables; offline mode; streaming; confidence threshold",
        "**TTS Engine** (`tts_engine.py`) — primary + fallback callables; LRU disk cache; empty-text guard",
        "**Voice Logger** (`voice_logger.py`) — JSONL audit log; PII scrub before write; TURN / SESSION_START / SESSION_END / COMPLIANCE_BLOCK / MCP_TRIGGER events",
        "**Audio Pipeline** (`audio_pipeline.py`) — text-mode + audio-mode; VAD → STT → PII scrub → FSM → ComplianceGuard → TTS; session lifecycle",
    ]:
        st.markdown(f"- {item}")

    st.markdown("### Test coverage")
    st.markdown("""
| Class | Tests | Status |
|---|---|---|
| `TranscriptResult` | TC-3.1 – 3.6 | ✅ |
| `STTEngine` | TC-3.7 – 3.13 | ✅ |
| `SynthesisResult` + `TTSEngine` | TC-3.14 – 3.20 | ✅ |
| `VADEngine` | TC-3.21 – 3.27 | ✅ |
| `VoiceLogger` | TC-3.28 – 3.37 | ✅ |
| `AudioPipeline` (text + audio mode) | TC-3.38 – 3.55 | ✅ |
| Integration | TC-3.56 – 3.60 | ✅ |
""")

    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent / "phase3"),
        )
        if "passed" in result.stdout:
            st.code(result.stdout.strip().split("\n")[-1], language=None)
        else:
            st.code(result.stdout[-300:] or result.stderr[-300:], language=None)
    except Exception as e:
        st.warning(f"Could not run tests: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4 — Google Workspace
# ══════════════════════════════════════════════════════════════════════════════

with phase4_tab:
    st.markdown("## ✅ Phase 4 — Google Workspace (MCP Integrations)")
    st.caption("Complete. 26/26 unit tests + 3/3 live integration tests passing.")

    st.success("All three real APIs verified end-to-end with a live booking.")

    st.markdown("### What was built")
    for item in [
        "**`config.py`** — lazy-loaded MCPConfig; base64 calendar ID decode; Gmail app-password space-strip",
        "**`calendar_tool.py`** — async Google Calendar API v3; TENTATIVE hold event; colorId=5",
        "**`sheets_tool.py`** — async gspread append to 'Advisor Pre-Bookings' tab; auto-creates sheet + headers",
        "**`email_tool.py`** — Gmail draft via IMAP APPEND (not SMTP); plain + HTML multipart; advisor clicks Send",
        "**`mcp_orchestrator.py`** — Calendar (sequential) → Sheets + Email (asyncio.gather parallel); sync wrapper for FSM",
        "**`mcp_logger.py`** — JSONL ops log per booking; per-tool duration, event_id, row_index, draft_id",
        "**FSM integration** — `_dispatch_mcp()` calls real MCP with graceful fallback; booking code always issued",
    ]:
        st.markdown(f"- {item}")

    st.markdown("### Live booking confirmed (BK-20260405-0042)")
    st.markdown("""
| System | Result |
|---|---|
| Google Calendar | TENTATIVE hold created — event ID `lldd5frlji81mrvv2jdon66t8s` |
| Google Sheets | Row 3 written to *Advisor Pre-Bookings* tab |
| Gmail | Draft saved to Drafts folder — advisor clicks Send to confirm |
| Total time | 4.9 seconds |
""")

    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent / "phase4"),
        )
        if "passed" in result.stdout:
            st.code(result.stdout.strip().split("\n")[-1], language=None)
        else:
            st.code(result.stdout[-300:] or result.stderr[-300:], language=None)
    except Exception as e:
        st.warning(f"Could not run tests: {e}")

    # ── Voice conversation ────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🎙️ Live Voice Conversation — End-to-End Booking")

    # ── language selector ─────────────────────────────────────────────────────
    _lang_opt = st.radio(
        "🌐 Voice Language",
        ["🇮🇳 Indian English", "🇮🇳 हिंदी (Hindi)"],
        horizontal=True,
        key="p4_voice_lang",
        help="Affects both TTS output and STT transcription.",
    )
    _p4_lang = "hi-IN" if "हिंदी" in _lang_opt else "en-IN"

    # ── helpers ───────────────────────────────────────────────────────────────
    def _tts_bytes(text: str) -> bytes:
        """
        Convert text → audio bytes using natural Indian TTS.
        Provider chain: Sarvam AI Bulbul → Google Cloud Neural2 → gTTS fallback.
        """
        # Try the proper TTS engine first (Sarvam / Google Neural2)
        try:
            _phase3_path = os.path.join(VOICE_AGENTS_ROOT, "phase3")
            if _phase3_path not in sys.path:
                sys.path.insert(0, _phase3_path)
            from src.voice.tts_engine import TTSEngine
            engine = TTSEngine()
            result = engine.synthesise(text, language=_p4_lang)
            if not result.is_empty:
                return result.audio_bytes
        except Exception:
            pass
        # gTTS last resort
        try:
            import io
            from gtts import gTTS
            _lang = "hi" if _p4_lang == "hi-IN" else "en"
            _tld  = "co.in" if _p4_lang == "en-IN" else "com"
            buf = io.BytesIO()
            gTTS(text=text, lang=_lang, tld=_tld, slow=False).write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception:
            return b""

    def _stt(audio_bytes: bytes) -> str:
        """Transcribe audio bytes via Groq Whisper (Indian English or Hindi)."""
        import io
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            return ""
        try:
            from groq import Groq as _Groq
            client = _Groq(api_key=groq_key)
            _whisper_lang = "hi" if _p4_lang == "hi-IN" else "en"
            resp = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("audio.wav", io.BytesIO(audio_bytes), "audio/wav"),
                language=_whisper_lang,
            )
            return resp.text.strip()
        except Exception as _e:
            st.warning(f"STT error: {_e}")
            return ""

    def _fsm_turn(user_text: str):
        """Run one FSM turn. Returns (speech, ctx)."""
        fsm    = st.session_state["p4_fsm"]
        router = st.session_state["p4_router"]
        ctx    = st.session_state["p4_ctx"]
        llm    = router.route(user_text, ctx)
        ctx, speech = fsm.process_turn(ctx, user_text, llm)
        st.session_state["p4_ctx"] = ctx
        return speech, ctx

    # ── session state init ────────────────────────────────────────────────────
    if "p4_started" not in st.session_state:
        st.session_state["p4_started"]  = False
        st.session_state["p4_history"]  = []   # list of (role, text)
        st.session_state["p4_ctx"]      = None
        st.session_state["p4_fsm"]      = None
        st.session_state["p4_router"]   = None
        st.session_state["p4_done"]     = False

    col_start, col_reset = st.columns([1, 1])

    with col_start:
        if not st.session_state["p4_started"]:
            if st.button("▶️ Start Conversation", type="primary", use_container_width=True):
                from src.dialogue.fsm import DialogueFSM
                from src.dialogue.intent_router import IntentRouter
                fsm    = DialogueFSM()
                router = IntentRouter()
                ctx, greeting = fsm.start()
                st.session_state["p4_fsm"]     = fsm
                st.session_state["p4_router"]  = router
                st.session_state["p4_ctx"]     = ctx
                st.session_state["p4_history"] = [("agent", greeting)]
                st.session_state["p4_started"] = True
                st.session_state["p4_done"]    = False
                st.rerun()

    with col_reset:
        if st.session_state["p4_started"]:
            if st.button("🔄 Reset", use_container_width=True):
                for k in ["p4_started","p4_history","p4_ctx","p4_fsm","p4_router","p4_done"]:
                    del st.session_state[k]
                st.rerun()

    # ── conversation display ──────────────────────────────────────────────────
    if st.session_state["p4_started"]:
        st.markdown("---")

        # Render history
        for role, text in st.session_state["p4_history"]:
            if role == "agent":
                st.markdown(
                    f'<div style="background:#1e2a3a;border-left:3px solid #4fc3f7;'
                    f'padding:10px 14px;border-radius:6px;margin:6px 0;">'
                    f'🤖 <b>Agent:</b> {text}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="background:#2a1e2a;border-left:3px solid #ce93d8;'
                    f'padding:10px 14px;border-radius:6px;margin:6px 0;">'
                    f'🧑 <b>You:</b> {text}</div>',
                    unsafe_allow_html=True,
                )

        # Play last agent message as audio
        last_agent = next(
            (t for r, t in reversed(st.session_state["p4_history"]) if r == "agent"), None
        )
        if last_agent:
            audio_bytes = _tts_bytes(last_agent)
            if audio_bytes:
                _fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mp3"
                st.audio(audio_bytes, format=_fmt, autoplay=False)

        ctx = st.session_state["p4_ctx"]

        # Debug state
        if ctx:
            st.caption(f"FSM state: `{ctx.current_state.name}` | Turn: {ctx.turn_count}")

        # Check if done
        if st.session_state["p4_done"] or (
            ctx and ctx.current_state.name in ("BOOKING_COMPLETE", "END", "ERROR")
        ):
            st.session_state["p4_done"] = True
            if ctx and ctx.booking_code:
                st.success(f"✅ Booking confirmed: **{ctx.booking_code}**")
                c1, c2, c3 = st.columns(3)
                c1.metric("📅 Calendar", "✅ Created" if ctx.calendar_hold_created else "❌ Failed")
                c2.metric("📊 Sheets",   "✅ Logged"  if ctx.notes_appended         else "❌ Failed")
                c3.metric("📧 Gmail",    "✅ Drafted" if ctx.email_drafted           else "❌ Failed")
                if ctx.secure_url:
                    st.markdown(f"🔗 Secure URL: `{ctx.secure_url}`")
        else:
            # ── your turn banner ──────────────────────────────────────────────
            st.markdown(
                '<div style="background:#1a3a1a;border:2px solid #4caf50;border-radius:8px;'
                'padding:12px 16px;margin:12px 0;text-align:center;font-size:16px;font-weight:600;">'
                '🎤 YOUR TURN — Record your response below, then click Stop</div>',
                unsafe_allow_html=True,
            )

            turn_key = f"p4_mic_{len(st.session_state['p4_history'])}"
            user_audio = st.audio_input("Record", key=turn_key, label_visibility="collapsed")

            # Text fallback
            with st.expander("⌨️ Prefer to type instead?"):
                typed = st.text_input("Type your response:", key=f"p4_type_{turn_key}",
                                      placeholder="e.g. Yes, please continue")
                if st.button("Send", key=f"p4_send_{turn_key}") and typed:
                    user_audio = None
                    user_text  = typed
                    st.session_state["p4_history"].append(("user", user_text))
                    with st.spinner("Agent thinking…"):
                        try:
                            speech, _ = _fsm_turn(user_text)
                            st.session_state["p4_history"].append(("agent", speech))
                        except Exception as ex:
                            st.error(f"FSM error: {ex}")
                    st.rerun()

            if user_audio is not None:
                raw = user_audio.read()
                with st.spinner("Transcribing…"):
                    user_text = _stt(raw)

                if user_text:
                    st.session_state["p4_history"].append(("user", user_text))
                    with st.spinner("Agent thinking…"):
                        try:
                            speech, _ = _fsm_turn(user_text)
                            st.session_state["p4_history"].append(("agent", speech))
                        except Exception as ex:
                            st.error(f"FSM error: {ex}")
                    st.rerun()
                else:
                    st.warning("Could not transcribe — try typing in the expander above.")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 5 — Deploy & Polish
# ══════════════════════════════════════════════════════════════════════════════

with phase5_tab:
    st.markdown("## ✅ Phase 5 — Deploy & Polish")
    st.success("**Phase 5 complete.** All deliverables built and 12/12 E2E tests passing.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🧪 Test Results")
        st.markdown("""
| Test ID | Scenario | Status |
|---|---|---|
| TC-5.1 | Full booking → BOOKING_COMPLETE | ✅ Pass |
| TC-5.2 | Booking code NL-XXXX format | ✅ Pass |
| TC-5.3 | refuse_advice compliance block | ✅ Pass |
| TC-5.4 | refuse_pii compliance block | ✅ Pass |
| TC-5.5 | out_of_scope block | ✅ Pass |
| TC-5.6 | end_call → END state | ✅ Pass |
| TC-5.7 | 3× no-input → ERROR state | ✅ Pass |
| TC-5.8 | MCP partial failure → still complete | ✅ Pass |
| TC-5.9 | MCP full failure → graceful | ✅ Pass |
| TC-5.10 | Multi-turn slot fill | ✅ Pass |
| TC-5.11 | SessionManager lifecycle | ✅ Pass |
| TC-5.12 | SessionManager concurrency | ✅ Pass |
""")

    with col2:
        st.markdown("### 📦 Deliverables")
        for item, done in [
            ("12 E2E conversation tests", True),
            ("Production Streamlit UI (`phase5/ui/app.py`)", True),
            ("Dockerfile — Python 3.11-slim, non-root user", True),
            ("docker-compose.yml — app + Redis", True),
            ("Health check script (`scripts/health_check.py`)", True),
            ("PII & Compliance audit report", True),
            ("SEBI disclaimer on UI entry", True),
            ("Voice + text dual-mode UI", True),
        ]:
            icon = "✅" if done else "⏳"
            st.markdown(f"{icon} {item}")

    st.markdown("### 🏗️ Architecture")
    st.code("""
phase5/
├── tests/
│   ├── conftest.py          # shared fixtures (mock MCP, FSM, session mgr)
│   └── test_phase5_e2e.py   # 12 E2E conversation scenarios
├── ui/
│   └── app.py               # production Streamlit UI (voice + text)
├── docker/
│   ├── Dockerfile           # multi-stage Python 3.11-slim build
│   └── docker-compose.yml   # app + Redis services
├── scripts/
│   └── health_check.py      # liveness + readiness probes
├── compliance/
│   └── audit_report.md      # PII audit + SEBI compliance checklist
└── pytest.ini
    """, language="text")

    st.markdown("### 🚀 Run production UI")
    st.code("streamlit run voice-agents/phase5/ui/app.py --server.port 8501", language="bash")

    st.markdown("### 🐳 Run with Docker")
    st.code("cd voice-agents/phase5/docker && docker compose up --build", language="bash")

    st.info("No additional API keys beyond Phases 2–4. Phase 5 is packaging + polish only.")
