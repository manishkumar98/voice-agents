"""
app.py — Voice Agent Demo UI (Phase 0 + Phase 1)

Run with:
    streamlit run app.py
"""

import json
import os
import sys
from datetime import datetime

import streamlit as st

# ── Cross-phase sys.path setup ─────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))          # voice-agents/phase0/
_VOICE_AGENTS_ROOT = os.path.dirname(_HERE)                  # voice-agents/
for _phase in ("phase0", "phase1", "phase2"):
    _p = os.path.join(_VOICE_AGENTS_ROOT, _phase)
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    os.path.join(_VOICE_AGENTS_ROOT, "phase1", "data", "mock_calendar.json"),
)
# ───────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = _HERE

os.environ.setdefault("CHROMA_DB_PATH", os.path.join(PROJECT_ROOT, "data", "chroma_db"))
os.environ.setdefault("CHROMA_COLLECTION_NAME", "advisor_faq")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("RAG_TOP_K", "3")

import pytz
IST = pytz.timezone("Asia/Kolkata")

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Voice Agent — Build Progress",
    page_icon="🎙️",
    layout="wide",
)

st.title("🎙️ AI Advisor Voice Agent — Build Progress")
st.caption("Interactive demo of all components built so far. No external APIs required for Phases 0–1.")

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Build Phases")
    st.markdown("""
| Phase | What | Status |
|-------|------|--------|
| **0** | Foundation & RAG | ✅ Done |
| **1** | Booking Brain | ✅ Done |
| **2** | FSM + LLM Core | 🔜 Next |
| **3** | Voice I/O (STT/TTS) | ⏳ |
| **4** | Google Workspace | ⏳ |
| **5** | Deploy & UI Polish | ⏳ |
""")
    st.divider()
    st.markdown("**Phase 1 components**")
    st.markdown(
        "- 🔖 Booking Code Generator\n"
        "- 📅 Slot Resolver\n"
        "- 🛡️ PII Scrubber\n"
        "- 🔗 Secure URL Generator\n"
        "- 📋 Waitlist Handler"
    )
    st.divider()
    st.markdown("**5 FAQ Topics (Phase 0)**")
    st.markdown(
        "- KYC & Onboarding\n"
        "- SIP & Mandates\n"
        "- Statements & Tax\n"
        "- Withdrawals\n"
        "- Account Changes"
    )

# ─── Tabs ─────────────────────────────────────────────────────────────────────

(
    tab_health,
    tab_codes,
    tab_slots,
    tab_pii,
    tab_url,
    tab_waitlist,
    tab_rag,
    tab_calendar,
) = st.tabs([
    "🩺 System Health",
    "🔖 Booking Codes",
    "📅 Slot Resolver",
    "🛡️ PII Scrubber",
    "🔗 Secure URL",
    "📋 Waitlist",
    "🔍 RAG Explorer",
    "🗓️ Mock Calendar",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB: System Health
# ══════════════════════════════════════════════════════════════════════════════

with tab_health:
    st.subheader("System Health — Phase 0 + Phase 1")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("#### ⚙️ Config")
        try:
            from config.settings import settings
            st.success("Loaded")
            st.json({
                "ENVIRONMENT": settings.ENVIRONMENT,
                "GROQ_MODEL": settings.GROQ_MODEL,
                "RAG_TOP_K": settings.RAG_TOP_K,
                "MAX_TURNS_PER_CALL": settings.MAX_TURNS_PER_CALL,
                "SECURE_URL_SECRET_LEN": len(settings.SECURE_URL_SECRET),
                "STT_CONFIDENCE_THRESHOLD": settings.STT_CONFIDENCE_THRESHOLD,
            })
        except Exception as e:
            st.error(f"Config failed: {e}")

    with col2:
        st.markdown("#### 🗄️ ChromaDB")
        try:
            import chromadb
            client = chromadb.PersistentClient(path=os.environ["CHROMA_DB_PATH"])
            col = client.get_collection("advisor_faq")
            count = col.count()
            st.success(f"{count} chunks")
            topics = ["kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"]
            topic_counts = {t: len(col.get(where={"topic_key": t}).get("ids", [])) for t in topics}
            st.dataframe(
                {"Topic": list(topic_counts.keys()), "Chunks": list(topic_counts.values())},
                hide_index=True,
            )
        except Exception as e:
            st.error(f"ChromaDB: {e}")

    with col3:
        st.markdown("#### 📅 Mock Calendar")
        try:
            with open(os.environ["MOCK_CALENDAR_PATH"]) as f:
                cal = json.load(f)
            slots = cal["slots"]
            available = sum(1 for s in slots if s["status"] == "AVAILABLE")
            st.success(f"{len(slots)} slots")
            st.metric("AVAILABLE", available)
            st.metric("TENTATIVE", sum(1 for s in slots if s["status"] == "TENTATIVE"))
            st.metric("Advisor", cal.get("advisor_id", "N/A"))
        except Exception as e:
            st.error(f"Calendar: {e}")

    with col4:
        st.markdown("#### 🔖 Phase 1 Modules")
        modules = {
            "booking_code_generator": "src.booking.booking_code_generator",
            "slot_resolver": "src.booking.slot_resolver",
            "pii_scrubber": "src.booking.pii_scrubber",
            "secure_url_generator": "src.booking.secure_url_generator",
            "waitlist_handler": "src.booking.waitlist_handler",
        }
        all_ok = True
        for name, module_path in modules.items():
            try:
                __import__(module_path)
                st.markdown(f"✅ `{name}`")
            except Exception as e:
                st.markdown(f"❌ `{name}` — {e}")
                all_ok = False
        if all_ok:
            st.success("All modules loaded")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Booking Codes
# ══════════════════════════════════════════════════════════════════════════════

with tab_codes:
    st.subheader("🔖 Booking Code Generator")
    st.markdown(
        "Generates unique codes for each booking (`NL-XXXX`) and waitlist entry (`NL-WXXX`). "
        "Ambiguous characters (0, O, 1, I) are excluded to avoid confusion when read aloud."
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Booking Codes")
        n_booking = st.slider("How many to generate", 1, 20, 5, key="n_booking")
        if st.button("Generate Booking Codes", type="primary"):
            from src.booking.booking_code_generator import generate_booking_code
            codes = set()
            generated = []
            for _ in range(n_booking):
                code = generate_booking_code(existing_codes=codes)
                codes.add(code)
                generated.append(code)
            for c in generated:
                st.code(c, language=None)

        with st.expander("Format rules"):
            st.markdown("""
- Prefix: `NL-` (constant brand identifier)
- Suffix: 4 characters from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`
- Excluded: `0`, `O`, `1`, `I` (visually ambiguous)
- Total length: 7 characters
- Example: `NL-A742`, `NL-B3K9`
""")

    with col_b:
        st.markdown("#### Waitlist Codes")
        n_waitlist = st.slider("How many to generate", 1, 20, 5, key="n_waitlist")
        if st.button("Generate Waitlist Codes", type="primary"):
            from src.booking.booking_code_generator import generate_waitlist_code
            codes = set()
            generated = []
            for _ in range(n_waitlist):
                code = generate_waitlist_code(existing_codes=codes)
                codes.add(code)
                generated.append(code)
            for c in generated:
                st.code(c, language=None)

        with st.expander("Format rules"):
            st.markdown("""
- Prefix: `NL-W` (W marks it as a Waitlist code)
- Suffix: 3 characters from safe alphabet
- Total length: 7 characters
- Example: `NL-WK3P`, `NL-W39K`
- Visually distinct from booking codes at a glance
""")

    st.divider()
    st.markdown("#### Code Validator")
    code_input = st.text_input("Enter a code to validate", placeholder="e.g. NL-A742 or NL-WK3P")
    if code_input:
        from src.booking.booking_code_generator import is_valid_booking_code, is_valid_waitlist_code
        if is_valid_booking_code(code_input):
            st.success(f"✅ `{code_input}` is a valid **booking code**")
        elif is_valid_waitlist_code(code_input):
            st.info(f"📋 `{code_input}` is a valid **waitlist code**")
        else:
            st.error(f"❌ `{code_input}` is **not a valid** code")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Slot Resolver
# ══════════════════════════════════════════════════════════════════════════════

with tab_slots:
    st.subheader("📅 Slot Resolver")
    st.markdown(
        "Translates natural language day/time preferences into matching AVAILABLE calendar slots. "
        "This is what the voice agent uses after the user says *'Monday around 2 PM'*."
    )

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        day_pref = st.selectbox(
            "Day preference",
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "next Monday", "next Tuesday", "tomorrow", "today"],
        )
    with col_s2:
        time_pref = st.selectbox(
            "Time preference",
            ["morning", "afternoon", "evening", "10 AM", "2 PM", "4 PM", "noon"],
        )
    with col_s3:
        topic_sel = st.selectbox(
            "Topic (optional filter)",
            ["(no filter)", "kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"],
        )

    if st.button("🔍 Find Slots", type="primary"):
        from src.booking.slot_resolver import resolve_slots
        topic_arg = None if topic_sel == "(no filter)" else topic_sel
        ref = datetime.now(IST)
        slots = resolve_slots(
            day_preference=day_pref,
            time_preference=time_pref,
            topic=topic_arg,
            calendar_path=os.environ["MOCK_CALENDAR_PATH"],
            reference_date=ref,
        )
        if not slots:
            st.warning(
                f"No AVAILABLE slots found for **{day_pref}** / **{time_pref}**"
                + (f" / topic `{topic_arg}`" if topic_arg else "")
                + ". The agent would offer the waitlist."
            )
        else:
            st.success(f"Found {len(slots)} slot(s) — the agent would offer these to the user:")
            for i, s in enumerate(slots, 1):
                affinity_str = ", ".join(s.topic_affinity) if s.topic_affinity else "Any topic"
                st.info(
                    f"**Option {i}:** {s.start_ist_str()}  \n"
                    f"Slot ID: `{s.slot_id}` | Duration: 30 min | Topic affinity: _{affinity_str}_"
                )

    with st.expander("How slot resolution works"):
        st.markdown("""
1. **Day parsing** — "Monday" → next Monday's date from today; "next Monday" → the week after
2. **Time band mapping** — "morning" → 9–12h, "afternoon" → 12–17h, "2 PM" → 13–16h window
3. **Topic affinity filter** — slots with `topic_affinity=[]` accept any topic; slots with a list only match those topics
4. **Availability filter** — only `AVAILABLE` slots are returned (not TENTATIVE/CONFIRMED/CANCELLED)
5. **Result** — up to 2 slots sorted by start time (the agent offers both and lets the user choose)
""")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: PII Scrubber
# ══════════════════════════════════════════════════════════════════════════════

with tab_pii:
    st.subheader("🛡️ PII Scrubber")
    st.markdown(
        "Runs on every STT transcript **before** it reaches the LLM. "
        "Detects and replaces personal data with `[REDACTED]` so it never enters the AI pipeline."
    )

    st.markdown("#### What gets detected")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        st.markdown("""
**📱 Phone numbers**
- Indian mobile (10-digit starting 6–9)
- With +91, 91, or 0 prefix
- e.g. `9876543210`, `+919876543210`
""")
        st.markdown("""
**📧 Email addresses**
- Standard RFC format
- e.g. `user@gmail.com`
""")
    with col_p2:
        st.markdown("""
**🪪 PAN numbers**
- Format: 5 letters + 4 digits + 1 letter
- e.g. `ABCDE1234F`
""")
        st.markdown("""
**🔢 Aadhaar numbers**
- 12-digit, with spaces or dashes
- e.g. `2345 6789 0123`
""")
    with col_p3:
        st.markdown("""
**💳 16-digit account/card numbers**
- With or without spaces/dashes
- e.g. `1234 5678 9012 3456`
""")

    st.divider()

    example_texts = {
        "Clean query (no PII)": "I want to book a consultation about KYC next Monday at 2 PM",
        "Phone number": "My number is 9876543210, please call me",
        "Email address": "Send the details to john.doe@gmail.com",
        "PAN number": "My PAN is ABCDE1234F for tax filing",
        "Aadhaar number": "Aadhaar: 2345 6789 0123",
        "Multiple PII types": "Call 9876543210 or email me at user@example.com, PAN ABCDE1234F",
        "16-digit card number": "My account 1234 5678 9012 3456 needs updating",
    }

    preset = st.selectbox("Try an example", list(example_texts.keys()))
    pii_input = st.text_area(
        "Text to scrub (edit freely)",
        value=example_texts[preset],
        height=100,
    )

    if st.button("🛡️ Scrub PII", type="primary") and pii_input.strip():
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii(pii_input)

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("**Original text**")
            st.text_area("", value=pii_input, height=120, disabled=True, key="orig")
        with col_r2:
            st.markdown("**After scrubbing**")
            st.text_area("", value=result.cleaned_text, height=120, disabled=True, key="clean")

        if result.pii_found:
            st.error(f"⚠️ {result.detection_summary()}")
            dc1, dc2 = st.columns(2)
            if result.context_detected:
                dc1.warning(f"**Context pass** (intent phrase + value): `{', '.join(result.context_detected)}`")
            if result.pattern_detected:
                dc2.warning(f"**Pattern pass** (standalone regex): `{', '.join(result.pattern_detected)}`")
        else:
            st.success("✅ No PII detected — text is clean to send to the LLM.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Secure URL
# ══════════════════════════════════════════════════════════════════════════════

with tab_url:
    st.subheader("🔗 Secure URL Generator")
    st.markdown(
        "After booking, the agent reads a **tamper-proof, time-limited URL** to the user. "
        "The user visits it to submit contact details (phone/email) **off the voice channel** — "
        "keeping all PII out of the call recording."
    )

    col_u1, col_u2 = st.columns([2, 1])
    with col_u1:
        booking_code_in = st.text_input("Booking code", value="NL-A742")
        topic_in = st.selectbox(
            "Topic",
            ["kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"],
            key="url_topic",
        )
        slot_in = st.text_input("Slot datetime (IST)", value="2026-04-06T14:00:00+05:30")
    with col_u2:
        st.markdown("#### Token settings")
        ttl_hours = st.slider("Expires after (hours)", 1, 72, 24)
        custom_secret = st.text_input(
            "HMAC secret (leave blank to use env default)",
            type="password",
            placeholder="optional override",
        )

    if st.button("🔗 Generate Secure URL", type="primary"):
        from src.booking.secure_url_generator import generate_secure_url, verify_secure_url, extract_token_from_url
        secret = custom_secret.strip() or None
        try:
            url = generate_secure_url(
                booking_code=booking_code_in,
                topic=topic_in,
                slot_ist=slot_in,
                secret=secret,
                domain="http://localhost:8501",
            )
            st.success("URL generated successfully")
            st.code(url, language=None)

            token = extract_token_from_url(url)
            st.markdown("**Token (signed, base64-encoded — booking code is NOT visible in plaintext):**")
            st.code(token, language=None)

            # Verify it round-trips
            payload = verify_secure_url(token, secret=secret, max_age_seconds=ttl_hours * 3600)
            st.markdown("**Decoded payload (server-side after user visits the URL):**")
            st.json(payload)

        except Exception as e:
            st.error(f"Error: {e}")

    with st.expander("How the secure URL works"):
        st.markdown("""
1. **Payload** — `{booking_code, topic, slot_ist}` is serialised and **HMAC-signed** using `itsdangerous`
2. **Token** — the signature + payload is base64-encoded (booking code is NOT in plaintext in the URL)
3. **URL** — `http://domain/book/{token}` is read out to the user letter-by-letter
4. **Verification** — when the user visits, the server checks the signature and expiry (default 24h)
5. **Tamper detection** — any modification to the token causes `BadSignature` and the form is rejected
6. **Expiry** — tokens older than TTL raise `SignatureExpired` — user must call back to get a new URL
""")

    st.divider()
    st.markdown("#### Token Verifier")
    token_to_verify = st.text_input("Paste a token to verify", placeholder="e.g. eyJ...")
    verify_secret = st.text_input("Secret used to sign it", type="password", key="vsecret")
    if st.button("Verify Token") and token_to_verify.strip():
        from src.booking.secure_url_generator import verify_secure_url
        from itsdangerous import BadSignature, SignatureExpired
        try:
            payload = verify_secure_url(
                token_to_verify.strip(),
                secret=verify_secret.strip() or None,
            )
            st.success("✅ Valid token")
            st.json(payload)
        except SignatureExpired:
            st.error("❌ Token has expired")
        except BadSignature:
            st.error("❌ Invalid or tampered token")
        except Exception as e:
            st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Waitlist
# ══════════════════════════════════════════════════════════════════════════════

with tab_waitlist:
    st.subheader("📋 Waitlist Handler")
    st.markdown(
        "When no AVAILABLE slot matches the user's request, the agent creates a **waitlist entry**. "
        "The user gets a `NL-WXXX` code and is contacted when a slot opens."
    )

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        w_topic = st.selectbox(
            "Topic",
            ["kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"],
            key="w_topic",
        )
        w_day = st.text_input("Day preference", value="Monday")
        w_time = st.text_input("Time preference", value="2 PM")

    with col_w2:
        st.markdown("#### Waitlist entry fields")
        st.markdown("""
| Field | Description |
|---|---|
| `waitlist_code` | Unique `NL-WXXX` code read to user |
| `topic` | What they wanted to discuss |
| `day_preference` | When they wanted (natural language) |
| `time_preference` | What time they wanted |
| `created_at` | IST timestamp of the call |
| `status` | ACTIVE → FULFILLED / EXPIRED / CANCELLED |
""")

    if st.button("📋 Create Waitlist Entry", type="primary"):
        from src.booking.waitlist_handler import create_waitlist_entry
        try:
            entry = create_waitlist_entry(
                topic=w_topic,
                day_preference=w_day,
                time_preference=w_time,
            )
            st.success(f"Waitlist entry created: **{entry.waitlist_code}**")
            st.json(entry.to_dict())

            st.markdown("**What the agent would say:**")
            st.info(
                f"\"I've added you to the waitlist. Your waitlist code is "
                f"{' - '.join(list(entry.waitlist_code))}. "
                f"We'll contact you when a {entry.topic.replace('_', ' ')} slot opens "
                f"around {entry.time_preference} on {entry.day_preference}.\""
            )
        except ValueError as e:
            st.error(f"Validation error: {e}")

    st.divider()
    st.markdown("#### Waitlist vs Booking Flow")
    st.markdown("""
```
User says: "Monday at 2 PM"
              │
              ▼
    resolve_slots() → finds AVAILABLE slots?
              │
    ┌─────────┴──────────┐
    │ YES (≥1 slot)      │ NO (0 slots)
    │                    │
    ▼                    ▼
Offer slot(s)     create_waitlist_entry()
    │                    │
    ▼                    ▼
Booking code        Waitlist code
  NL-XXXX             NL-WXXX
```
""")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: RAG Explorer (Phase 0)
# ══════════════════════════════════════════════════════════════════════════════

with tab_rag:
    st.subheader("🔍 RAG FAQ Explorer (Phase 0)")
    st.markdown(
        "Retrieves relevant FAQ chunks from ChromaDB to ground the agent's answers. "
        "Used when the user asks *'what should I prepare?'*"
    )

    TOPIC_LABELS = {
        "kyc_onboarding": "KYC & Onboarding",
        "sip_mandates": "SIP & Mandates",
        "statements_tax": "Statements & Tax",
        "withdrawals": "Withdrawals",
        "account_changes": "Account Changes",
    }
    example_queries = {
        "kyc_onboarding": "what documents do I need for KYC",
        "sip_mandates": "how to set up a SIP mandate",
        "statements_tax": "where can I get my tax statement",
        "withdrawals": "how long does withdrawal take",
        "account_changes": "how to add a nominee",
    }

    col_q, col_t = st.columns([3, 1])
    with col_t:
        rag_topic = st.selectbox("Topic", list(TOPIC_LABELS.keys()), format_func=lambda k: TOPIC_LABELS[k])
    with col_q:
        rag_query = st.text_input("Your question", value=example_queries.get(rag_topic, ""))

    top_k = st.slider("Chunks to retrieve (top_k)", 1, 5, 3)

    if st.button("🔍 Search RAG", type="primary") and rag_query.strip():
        with st.spinner("Querying ChromaDB..."):
            try:
                from src.agent.rag_injector import get_rag_context
                result = get_rag_context(query=rag_query, topic=rag_topic, top_k=top_k)
                if result == "No relevant context found.":
                    st.warning("No relevant context found.")
                else:
                    st.success("Context retrieved — this gets injected into the LLM system prompt:")
                    st.text_area("Retrieved context", value=result, height=280, disabled=True)
            except Exception as e:
                st.error(f"RAG error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Mock Calendar (Phase 0)
# ══════════════════════════════════════════════════════════════════════════════

with tab_calendar:
    st.subheader("🗓️ Mock Calendar Slots (Phase 0)")
    st.markdown("Advisor's simulated calendar — used so we don't need Google Calendar API during development.")

    try:
        with open(os.environ["MOCK_CALENDAR_PATH"]) as f:
            cal = json.load(f)
        slots = cal["slots"]

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            status_filter = st.multiselect(
                "Status",
                ["AVAILABLE", "TENTATIVE", "CONFIRMED", "CANCELLED"],
                default=["AVAILABLE", "TENTATIVE"],
            )
        with col_f2:
            topic_filter = st.multiselect(
                "Topic affinity (empty = show all)",
                ["kyc_onboarding", "sip_mandates", "statements_tax", "withdrawals", "account_changes"],
            )

        filtered = [s for s in slots if s["status"] in status_filter]
        if topic_filter:
            filtered = [
                s for s in filtered
                if not s["topic_affinity"] or any(t in s["topic_affinity"] for t in topic_filter)
            ]

        st.caption(f"Showing {len(filtered)} of {len(slots)} slots")
        rows = [
            {
                "Slot ID": s["slot_id"],
                "Start": s["start"],
                "End": s["end"],
                "Status": s["status"],
                "Topic Affinity": ", ".join(s["topic_affinity"]) if s["topic_affinity"] else "Any",
            }
            for s in filtered
        ]
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.info("No slots match the current filters.")
    except Exception as e:
        st.error(f"Could not load mock calendar: {e}")
