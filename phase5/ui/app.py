"""
Phase 5 — Production Streamlit UI
Advisor Scheduling Voice & Text Agent

Features:
  • Voice mode: mic recording → Groq Whisper STT → FSM → gTTS playback
  • Text mode: typed input → FSM → text response
  • SEBI disclaimer on entry
  • Turn-by-turn conversation transcript
  • Booking confirmation panel with MCP results
  • Session management with 30-minute TTL
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# ── sys.path setup ────────────────────────────────────────────────────────────
_ui_dir   = Path(__file__).resolve().parent
_p5_dir   = _ui_dir.parent
_root_dir = _p5_dir.parent

for _entry in [
    str(_root_dir / "phase0"),
    str(_root_dir / "phase1"),
    str(_root_dir / "phase2"),
    str(_root_dir / "phase3"),
    str(_root_dir / "phase4"),
]:
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

try:
    from dotenv import load_dotenv
    load_dotenv(str(_root_dir / ".env"))
except ImportError:
    pass

os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    str(_root_dir / "phase1" / "data" / "mock_calendar.json"),
)

# ── Imports ───────────────────────────────────────────────────────────────────
import io
import tempfile
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Advisor Scheduling Agent",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Lazy loaders (avoid crashing if optional packages missing) ─────────────────

def _load_groq():
    try:
        from groq import Groq
        return Groq()
    except ImportError:
        return None


def _stt(audio_bytes: bytes) -> str:
    """Transcribe audio via Groq Whisper. Returns text or empty string."""
    client = _load_groq()
    if not client:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        with open(tmp, "rb") as af:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("audio.wav", af, "audio/wav"),
                response_format="text",
            )
        os.unlink(tmp)
        return str(result).strip()
    except Exception as exc:
        st.warning(f"STT error: {exc}")
        return ""


def _tts(text: str) -> bytes | None:
    """Convert text to speech via gTTS. Returns WAV bytes or None."""
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang="en", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return None
    except Exception as exc:
        st.warning(f"TTS error: {exc}")
        return None


# ── Session state init ────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "p5_started":  False,
        "p5_history":  [],       # list of {"role": "agent"|"user", "text": str}
        "p5_ctx":      None,     # DialogueContext
        "p5_fsm":      None,     # DialogueFSM
        "p5_done":     False,
        "p5_mcp":      None,     # MCPResults if booking complete
        "p5_mode":     "text",   # "voice" | "text"
        "p5_disclaimer_shown": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── UI Layout ─────────────────────────────────────────────────────────────────

st.title("📅 Advisor Scheduling Agent")
st.caption("Phase 5 — Production UI | Powered by GPT-4o-mini · Groq Whisper · gTTS")

# ── SEBI Disclaimer ───────────────────────────────────────────────────────────

if not st.session_state.p5_disclaimer_shown:
    st.warning(
        "⚠️ **SEBI Disclaimer**: This service is for scheduling advisory appointments only. "
        "Our representatives provide informational guidance and do not offer investment advice "
        "as defined under SEBI (Investment Advisers) Regulations, 2013. "
        "By proceeding, you acknowledge that no investment advice will be provided during this interaction.",
        icon="⚠️",
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✅ I Understand, Proceed", type="primary"):
            st.session_state.p5_disclaimer_shown = True
            st.rerun()
    st.stop()

# ── Mode selector ──────────────────────────────────────────────────────────────

left, right = st.columns([3, 1])
with right:
    mode = st.radio("Input mode", ["text", "voice"], index=0,
                    horizontal=True, key="p5_mode_radio",
                    label_visibility="collapsed")
    st.session_state.p5_mode = mode

# ── Start button ──────────────────────────────────────────────────────────────

if not st.session_state.p5_started:
    with left:
        st.markdown("### Ready to start?")
        st.markdown("Click **Start Session** and the agent will greet you.")
        if st.button("▶️ Start Session", type="primary"):
            from src.dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.p5_fsm  = fsm
            st.session_state.p5_ctx  = ctx
            st.session_state.p5_started = True
            st.session_state.p5_history = [{"role": "agent", "text": greeting}]
            st.rerun()
    st.stop()

# ── Conversation display ───────────────────────────────────────────────────────

st.markdown("---")
chat_area = st.container()
with chat_area:
    for turn in st.session_state.p5_history:
        if turn["role"] == "agent":
            st.chat_message("assistant").markdown(turn["text"])
        else:
            st.chat_message("user").markdown(turn["text"])

# ── Booking complete panel ─────────────────────────────────────────────────────

ctx = st.session_state.p5_ctx
if ctx and ctx.current_state.name == "BOOKING_COMPLETE":
    st.success(f"✅ **Booking Confirmed** — Code: `{ctx.booking_code}`")
    mcp = st.session_state.p5_mcp
    if mcp:
        with st.expander("📋 Booking Details", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                status = "✅" if mcp.calendar_success else "❌"
                st.metric("Calendar", status, delta=f"{mcp.calendar.duration_ms:.0f}ms")
                if mcp.calendar_event_id:
                    st.caption(f"Event: `{mcp.calendar_event_id}`")
            with col2:
                status = "✅" if mcp.sheets_success else "❌"
                st.metric("Sheets", status, delta=f"{mcp.sheets.duration_ms:.0f}ms")
                if mcp.sheet_row_index:
                    st.caption(f"Row: {mcp.sheet_row_index}")
            with col3:
                status = "✅" if mcp.email_success else "❌"
                st.metric("Email", status, delta=f"{mcp.email.duration_ms:.0f}ms")
                if mcp.email_draft_id:
                    st.caption(f"Draft: `{mcp.email_draft_id}`")
    if st.button("🔄 Start New Session"):
        for k in ["p5_started", "p5_history", "p5_ctx", "p5_fsm",
                  "p5_done", "p5_mcp"]:
            del st.session_state[k]
        _init_state()
        st.rerun()
    st.stop()

# ── Terminal state check ───────────────────────────────────────────────────────

if ctx and ctx.current_state.is_terminal():
    st.info("Session ended. Click below to start a new one.")
    if st.button("🔄 New Session"):
        for k in ["p5_started", "p5_history", "p5_ctx", "p5_fsm", "p5_done", "p5_mcp"]:
            del st.session_state[k]
        _init_state()
        st.rerun()
    st.stop()

# ── Latest agent speech TTS ────────────────────────────────────────────────────

if st.session_state.p5_history:
    last = st.session_state.p5_history[-1]
    if last["role"] == "agent" and st.session_state.p5_mode == "voice":
        audio_bytes = _tts(last["text"])
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mp3", autoplay=False)
            st.success("🎙️ **YOUR TURN** — Record your response below")

# ── Input area ─────────────────────────────────────────────────────────────────

st.markdown("---")

def _process_user_input(user_text: str):
    """Run user_text through the FSM and update session state."""
    from src.dialogue.intent_router import IntentRouter
    from src.mcp.mcp_orchestrator import dispatch_mcp_sync, build_payload

    fsm = st.session_state.p5_fsm
    ctx = st.session_state.p5_ctx

    router = IntentRouter()
    try:
        llm_resp = router.route(user_text, ctx)
    except Exception as exc:
        st.error(f"Intent routing error: {exc}")
        return

    ctx, speech = fsm.process_turn(ctx, user_text, llm_resp)

    # If MCP dispatch just happened, capture results
    if ctx.current_state.name == "BOOKING_COMPLETE" and ctx.booking_code:
        try:
            payload = build_payload(ctx)
            results = dispatch_mcp_sync(payload)
            st.session_state.p5_mcp = results
            # Annotate flags on ctx
            ctx.calendar_hold_created = results.calendar_success
            ctx.notes_appended = results.sheets_success
            ctx.email_drafted = results.email_success
        except Exception:
            pass  # MCP failure doesn't block UI

    st.session_state.p5_ctx = ctx
    st.session_state.p5_history.append({"role": "user", "text": user_text})
    st.session_state.p5_history.append({"role": "agent", "text": speech})


if st.session_state.p5_mode == "voice":
    audio_input = st.audio_input("🎤 Record your message", key="p5_audio_input")
    if audio_input is not None:
        with st.spinner("Transcribing..."):
            transcript = _stt(audio_input.read())
        if transcript:
            st.caption(f"You said: *{transcript}*")
            _process_user_input(transcript)
            st.rerun()
        else:
            st.warning("Could not transcribe audio. Please try again or switch to text mode.")

else:
    # Text mode
    with st.form("p5_text_form", clear_on_submit=True):
        user_input = st.text_input("Your message:", placeholder="Type here and press Enter…",
                                   label_visibility="collapsed")
        submitted = st.form_submit_button("Send ➤")
    if submitted and user_input.strip():
        _process_user_input(user_input.strip())
        st.rerun()

# ── Sidebar: debug info ────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🔍 Session Debug")
    if ctx:
        st.json({
            "call_id":       ctx.call_id,
            "state":         ctx.current_state.name,
            "turn_count":    ctx.turn_count,
            "intent":        ctx.intent,
            "topic":         ctx.topic,
            "day":           ctx.day_preference,
            "time":          ctx.time_preference,
            "booking_code":  ctx.booking_code,
        })
    st.markdown("---")
    st.caption("Phase 5 · Advisor Scheduling Agent v1.0")
