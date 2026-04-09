"""
Phase 5 — Production Streamlit UI
Advisor Scheduling Voice & Text Agent — Continuous Calling Mode

Features:
  • Continuous voice flow: agent speaks → auto-starts mic → user speaks → loops
  • autoplay=True for new agent messages; TTS cached to avoid re-generation on reruns
  • JS injection: auto-clicks mic button when agent audio ends
  • Text mode: typed input → FSM → text response
  • Language toggle: Indian English (en-IN) ↔ Hindi (hi-IN)
  • TTS provider chain: Sarvam AI Bulbul → Google Cloud Neural2 → gTTS
  • SEBI disclaimer on entry
  • Turn-by-turn conversation transcript
  • Booking confirmation panel with MCP results
"""
from __future__ import annotations

import sys
import os
import hashlib
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

os.environ["MOCK_CALENDAR_PATH"] = str(_root_dir / "phase1" / "data" / "mock_calendar.json")

# ── Imports ───────────────────────────────────────────────────────────────────
import tempfile
import streamlit as st
import streamlit.components.v1 as components

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Advisor Scheduling Agent",
    page_icon="📞",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* Call status bar */
.call-bar {
    background: linear-gradient(135deg, #0f1923, #1a2e3b);
    border: 1px solid #2a4a5e;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.live-dot {
    display: inline-block;
    width: 10px; height: 10px;
    background: #00e676;
    border-radius: 50%;
    margin-right: 8px;
    animation: blink 1.4s infinite;
}
@keyframes blink {
    0%,100% { opacity: 1; }
    50%      { opacity: 0.3; }
}
.agent-turn-badge {
    background: #1565c0;
    color: #e3f2fd;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 0.82em;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.user-turn-badge {
    background: #1b5e20;
    color: #e8f5e9;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 0.82em;
    font-weight: 600;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)


# ── Audio helpers ──────────────────────────────────────────────────────────────

def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            st.warning("GROQ_API_KEY not set — STT unavailable.")
            return ""
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        whisper_lang = {"en-IN": "en", "hi-IN": "hi"}.get(language, "en")
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
        st.warning("groq package not installed — pip install groq")
        return ""
    except Exception as exc:
        st.warning(f"STT error: {exc}")
        return ""


def _tts(text: str, language: str = "en-IN") -> bytes | None:
    os.environ["TTS_LANGUAGE"] = language
    try:
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine()
        result = engine.synthesise(text, language=language)
        if not result.is_empty:
            return result.audio_bytes
    except Exception:
        pass
    try:
        import io as _io
        from gtts import gTTS
        _lang = "hi" if language == "hi-IN" else "en"
        _tld  = "co.in" if language == "en-IN" else "com"
        buf = _io.BytesIO()
        gTTS(text=text, lang=_lang, tld=_tld, slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as exc:
        st.warning(f"TTS error: {exc}")
        return None


def _inject_auto_record_js():
    """
    After agent audio plays, automatically click the mic record button.
    Uses window.parent.document to reach the main Streamlit DOM from the iframe.
    """
    components.html("""
    <script>
    (function() {
        var pdoc = window.parent.document;

        function clickMic() {
            var input = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (!input) return false;
            var btn = input.querySelector('button');
            if (btn) { btn.click(); return true; }
            return false;
        }

        function attachToAudio() {
            var audios = pdoc.querySelectorAll('audio');
            if (!audios.length) { setTimeout(attachToAudio, 200); return; }
            var audio = audios[audios.length - 1];

            // Already ended (very short clip or cached)
            if (audio.ended) { setTimeout(clickMic, 400); return; }

            audio.addEventListener('ended', function() {
                setTimeout(clickMic, 400);
            }, { once: true });

            // Fallback: if audio never fires 'ended' within 30s, give up
        }

        // Small delay so Streamlit finishes rendering the audio element
        setTimeout(attachToAudio, 300);
    })();
    </script>
    """, height=0)


# ── Session state init ────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "p5_started":  False,
        "p5_history":  [],
        "p5_ctx":      None,
        "p5_fsm":      None,
        "p5_done":     False,
        "p5_mcp":      None,
        "p5_mode":     "voice",   # default to voice for calling agent feel
        "p5_lang":     "en-IN",
        "p5_disclaimer_shown": False,
        "_tts_hash":   "",        # hash of last synthesised text
        "_tts_audio":  None,      # cached audio bytes
        "_tts_played": "",        # hash of last auto-played text
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ── SEBI Disclaimer ───────────────────────────────────────────────────────────

if not st.session_state.p5_disclaimer_shown:
    st.markdown("## 📞 Advisor Scheduling Agent")
    st.warning(
        "⚠️ **SEBI Disclaimer**: This service is for scheduling advisory appointments only. "
        "Our representatives provide informational guidance and do not offer investment advice "
        "as defined under SEBI (Investment Advisers) Regulations, 2013. "
        "By proceeding, you acknowledge that no investment advice will be provided.",
        icon="⚠️",
    )
    if st.button("✅ I Understand, Proceed", type="primary"):
        st.session_state.p5_disclaimer_shown = True
        st.rerun()
    st.stop()

# ── Controls row ──────────────────────────────────────────────────────────────

ctrl_l, ctrl_m, ctrl_r = st.columns([3, 1, 1])
with ctrl_m:
    mode = st.radio("Mode", ["voice", "text"], index=0,
                    horizontal=True, key="p5_mode_radio")
    st.session_state.p5_mode = mode
with ctrl_r:
    lang_label = st.radio("Language", ["🇮🇳 English", "🇮🇳 हिंदी"], index=0,
                           horizontal=True, key="p5_lang_radio")
    st.session_state.p5_lang = "hi-IN" if "हिंदी" in lang_label else "en-IN"

os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
os.environ["STT_LANGUAGE"] = st.session_state.p5_lang

# ── Start session ─────────────────────────────────────────────────────────────

if not st.session_state.p5_started:
    with ctrl_l:
        _lang_display = "Hindi (हिंदी)" if st.session_state.p5_lang == "hi-IN" else "Indian English"
        st.markdown(f"**Language:** {_lang_display} · **Mode:** {mode}")
        if st.button("📞 Start Call", type="primary"):
            from src.dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.p5_fsm     = fsm
            st.session_state.p5_ctx     = ctx
            st.session_state.p5_started = True
            st.session_state.p5_history = [{"role": "agent", "text": greeting}]
            # Reset TTS cache so greeting is auto-played
            st.session_state["_tts_hash"]   = ""
            st.session_state["_tts_played"] = ""
            st.rerun()
    st.stop()

# ── Call status bar ───────────────────────────────────────────────────────────

ctx = st.session_state.p5_ctx
_history = st.session_state.p5_history
_last = _history[-1] if _history else None
_is_voice = st.session_state.p5_mode == "voice"
_lang = st.session_state.get("p5_lang", "en-IN")

_state_label = ctx.current_state.name.replace("_", " ").title() if ctx else "—"

if _last and _last["role"] == "agent":
    _turn_html = '<span class="agent-turn-badge">🤖 Agent Speaking</span>'
else:
    _lbl = "बोलिए 🎙️" if _lang == "hi-IN" else "🎙️ Your Turn"
    _turn_html = f'<span class="user-turn-badge">{_lbl}</span>'

st.markdown(f"""
<div class="call-bar">
  <div><span class="live-dot"></span><strong>LIVE CALL</strong>
       &nbsp;&nbsp;<span style="color:#8899aa;font-size:0.85em">{_state_label}</span></div>
  <div>{_turn_html}</div>
</div>
""", unsafe_allow_html=True)

# ── Conversation transcript ───────────────────────────────────────────────────

st.markdown("---")
for turn in _history:
    if turn["role"] == "agent":
        st.chat_message("assistant").markdown(turn["text"])
    else:
        st.chat_message("user").markdown(turn["text"])

# ── Booking complete panel ────────────────────────────────────────────────────

if ctx and ctx.current_state.name == "BOOKING_COMPLETE":
    st.success(f"✅ **Booking Confirmed** — Code: `{ctx.booking_code}`")
    mcp = st.session_state.p5_mcp
    if mcp:
        with st.expander("📋 Booking Details", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Calendar", "✅" if mcp.calendar_success else "❌",
                          delta=f"{mcp.calendar.duration_ms:.0f}ms")
                if mcp.calendar_event_id:
                    st.caption(f"Event: `{mcp.calendar_event_id}`")
            with c2:
                st.metric("Sheets", "✅" if mcp.sheets_success else "❌",
                          delta=f"{mcp.sheets.duration_ms:.0f}ms")
                if mcp.sheet_row_index:
                    st.caption(f"Row: {mcp.sheet_row_index}")
            with c3:
                st.metric("Email", "✅" if mcp.email_success else "❌",
                          delta=f"{mcp.email.duration_ms:.0f}ms")
                if mcp.email_draft_id:
                    st.caption(f"Draft: `{mcp.email_draft_id}`")
    if st.button("📞 Start New Call"):
        for k in ["p5_started", "p5_history", "p5_ctx", "p5_fsm",
                  "p5_done", "p5_mcp", "_tts_hash", "_tts_audio", "_tts_played"]:
            st.session_state.pop(k, None)
        _init_state()
        st.rerun()
    st.stop()

# ── Terminal state ────────────────────────────────────────────────────────────

if ctx and ctx.current_state.is_terminal():
    st.info("Call ended.")
    if st.button("📞 New Call"):
        for k in ["p5_started", "p5_history", "p5_ctx", "p5_fsm",
                  "p5_done", "p5_mcp", "_tts_hash", "_tts_audio", "_tts_played"]:
            st.session_state.pop(k, None)
        _init_state()
        st.rerun()
    st.stop()

# ── TTS: play latest agent message ───────────────────────────────────────────

st.markdown("---")

if _last and _last["role"] == "agent" and _is_voice:
    agent_text = _last["text"]
    text_hash  = hashlib.md5(agent_text.encode()).hexdigest()

    # Generate TTS only when text changes (cache avoids re-synthesis on reruns)
    if st.session_state["_tts_hash"] != text_hash:
        with st.spinner("Generating voice..." if _lang == "en-IN" else "आवाज़ बना रहे हैं..."):
            audio_bytes = _tts(agent_text, language=_lang)
        st.session_state["_tts_hash"]  = text_hash
        st.session_state["_tts_audio"] = audio_bytes
    else:
        audio_bytes = st.session_state["_tts_audio"]

    # Autoplay only for new (not-yet-played) messages
    should_autoplay = st.session_state["_tts_played"] != text_hash

    if audio_bytes:
        fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mp3"
        st.audio(audio_bytes, format=fmt, autoplay=should_autoplay)

        if should_autoplay:
            st.session_state["_tts_played"] = text_hash
            # Auto-click the mic button after audio ends
            _inject_auto_record_js()

# ── Input area ────────────────────────────────────────────────────────────────

def _process_user_input(user_text: str):
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

    if ctx.current_state.name == "BOOKING_COMPLETE" and ctx.booking_code:
        try:
            payload = build_payload(ctx)
            results = dispatch_mcp_sync(payload)
            st.session_state.p5_mcp = results
            ctx.calendar_hold_created = results.calendar_success
            ctx.notes_appended        = results.sheets_success
            ctx.email_drafted         = results.email_success
        except Exception:
            pass

    st.session_state.p5_ctx = ctx
    st.session_state.p5_history.append({"role": "user",  "text": user_text})
    st.session_state.p5_history.append({"role": "agent", "text": speech})
    # Reset TTS played flag so new agent message autoplays
    st.session_state["_tts_played"] = ""


if _is_voice:
    _mic_label = "🎤 बोलिए (Hindi में)" if _lang == "hi-IN" else "🎤 Speak now"
    audio_input = st.audio_input(_mic_label, key="p5_audio_input")
    if audio_input is not None:
        _audio_bytes = audio_input.read()
        _audio_hash  = hashlib.md5(_audio_bytes).hexdigest()
        if st.session_state.get("_last_audio_hash") != _audio_hash:
            st.session_state["_last_audio_hash"] = _audio_hash
            with st.spinner("Transcribing..." if _lang == "en-IN" else "सुन रहे हैं..."):
                transcript = _stt(_audio_bytes, language=_lang)
            if transcript:
                st.caption(f"_{transcript}_")
                _process_user_input(transcript)
            else:
                st.warning("Could not transcribe. Please try again.")
            st.rerun()
else:
    _placeholder = "यहाँ टाइप करें..." if _lang == "hi-IN" else "Type your message..."
    user_input = st.chat_input(_placeholder)
    if user_input and user_input.strip():
        _process_user_input(user_input.strip())
        st.rerun()

# ── Sidebar: debug ────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🔍 Session Debug")
    if ctx:
        st.json({
            "call_id":      ctx.call_id,
            "state":        ctx.current_state.name,
            "turn_count":   ctx.turn_count,
            "intent":       ctx.intent,
            "topic":        ctx.topic,
            "day":          ctx.day_preference,
            "time":         ctx.time_preference,
            "booking_code": ctx.booking_code,
        })
    st.markdown("---")
    st.caption("Phase 5 · Advisor Scheduling Agent v2.0 · Continuous Call Mode")
