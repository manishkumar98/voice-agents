"""
Phase 5 — Production Streamlit UI
Advisor Scheduling Voice & Text Agent

Features:
  • Voice mode: mic recording → Groq Whisper STT → FSM → natural TTS playback
  • Text mode: typed input → FSM → text response
  • Language toggle: Indian English (en-IN) ↔ Hindi (hi-IN)
  • TTS provider chain: Sarvam AI Bulbul → Google Cloud Neural2 → pyttsx3
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
import tempfile
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Advisor Scheduling Agent",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Audio helpers ──────────────────────────────────────────────────────────────

def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    """
    Transcribe audio via Groq Whisper (whisper-large-v3).
    language: "en-IN" (Indian English) or "hi-IN" (Hindi).
    Returns transcript text or empty string on failure.
    """
    try:
        from groq import Groq  # type: ignore[import]
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            st.warning("GROQ_API_KEY not set — STT unavailable.")
            return ""
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        _lang_map = {"en-IN": "en", "hi-IN": "hi"}
        whisper_lang = _lang_map.get(language, "en")
        try:
            with open(tmp, "rb") as af:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", af, "audio/wav"),
                    response_format="text",
                    language=whisper_lang,
                )
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return str(result).strip()
    except ImportError:
        st.warning("groq package not installed — install with: pip install groq")
        return ""
    except Exception as exc:
        st.warning(f"STT error: {exc}")
        return ""


def _tts(text: str, language: str = "en-IN") -> bytes | None:
    """
    Convert text to speech using the TTS engine (Sarvam → Google Neural2 → pyttsx3).
    language: "en-IN" (Indian English) or "hi-IN" (Hindi).
    Returns audio bytes or None on total failure.
    """
    # Set language env var so TTS engine providers pick it up
    os.environ["TTS_LANGUAGE"] = language
    try:
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine()
        result = engine.synthesise(text, language=language)
        if not result.is_empty:
            return result.audio_bytes
    except Exception:
        pass

    # Last-resort gTTS fallback (robotic but always available)
    try:
        import io as _io
        from gtts import gTTS  # type: ignore[import]
        _lang = "hi" if language == "hi-IN" else "en"
        _tld  = "co.in" if language == "en-IN" else "com"
        buf = _io.BytesIO()
        gTTS(text=text, lang=_lang, tld=_tld, slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
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
        "p5_lang":     "en-IN",  # "en-IN" | "hi-IN"
        "p5_disclaimer_shown": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── UI Layout ─────────────────────────────────────────────────────────────────

st.title("📅 Advisor Scheduling Agent")
st.caption("Phase 5 — Production UI | Sarvam AI Bulbul / Google Neural2 · Groq Whisper · Indian English & Hindi")

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

# ── Controls row: mode + language ─────────────────────────────────────────────

left, mid, right = st.columns([3, 1, 1])
with mid:
    mode = st.radio("Mode", ["text", "voice"], index=0,
                    horizontal=True, key="p5_mode_radio",
                    label_visibility="visible")
    st.session_state.p5_mode = mode
with right:
    lang_label = st.radio("Language", ["🇮🇳 English", "🇮🇳 हिंदी"], index=0,
                           horizontal=True, key="p5_lang_radio",
                           label_visibility="visible")
    st.session_state.p5_lang = "hi-IN" if "हिंदी" in lang_label else "en-IN"

# propagate language to env so TTS/STT engines pick it up
os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
os.environ["STT_LANGUAGE"] = st.session_state.p5_lang

# ── Start button ──────────────────────────────────────────────────────────────

if not st.session_state.p5_started:
    with left:
        _lang_display = "Hindi (हिंदी)" if st.session_state.p5_lang == "hi-IN" else "Indian English"
        st.markdown("### Ready to start?")
        st.markdown(f"Language: **{_lang_display}** · Mode: **{mode}**")
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
        lang = st.session_state.get("p5_lang", "en-IN")
        with st.spinner("Generating voice..."):
            audio_bytes = _tts(last["text"], language=lang)
        if audio_bytes:
            fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mp3"
            st.audio(audio_bytes, format=fmt, autoplay=False)
            _turn_label = "बोलिए 🎙️" if lang == "hi-IN" else "🎙️ YOUR TURN"
            st.success(f"**{_turn_label}** — Record your response below")

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


_cur_lang = st.session_state.get("p5_lang", "en-IN")

if st.session_state.p5_mode == "voice":
    _mic_label = "🎤 बोलिए (Hindi में)" if _cur_lang == "hi-IN" else "🎤 Record your message"
    audio_input = st.audio_input(_mic_label, key="p5_audio_input")
    if audio_input is not None:
        # Dedup guard: hash audio bytes so same recording isn't re-processed on rerun
        import hashlib as _hashlib
        _audio_bytes = audio_input.read()
        _audio_hash = _hashlib.md5(_audio_bytes).hexdigest()
        if st.session_state.get("_last_audio_hash") != _audio_hash:
            st.session_state["_last_audio_hash"] = _audio_hash
            with st.spinner("Transcribing..." if _cur_lang == "en-IN" else "सुन रहे हैं..."):
                transcript = _stt(_audio_bytes, language=_cur_lang)
            if transcript:
                st.caption(f"You said: *{transcript}*")
                _process_user_input(transcript)
            else:
                st.warning("Could not transcribe audio. Please try again or switch to text mode.")
            st.rerun()

else:
    # Text mode
    _placeholder = "यहाँ टाइप करें..." if _cur_lang == "hi-IN" else "Type your message..."
    user_input = st.chat_input(_placeholder)
    if user_input and user_input.strip():
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
