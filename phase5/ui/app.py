"""
Phase 5 — Production Streamlit UI
Advisor Scheduling Voice & Text Agent — ZAY-G Style UI
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

st.set_page_config(
    page_title="Advisor Scheduling Agent",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Reset ────────────────────────────────────────────────────── */
/* Hide menu & footer but NOT the header — header contains sidebar toggle */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Hide only the Streamlit toolbar content, keep the sidebar button */
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* Make header transparent so it doesn't show as a bar */
[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
}

/* Keep sidebar collapse/expand button always visible */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    background: white !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: 2px 0 8px rgba(109,40,217,0.15) !important;
}

/* ── Background — warm lavender → periwinkle (matches ZAY-G) ─── */
.stApp {
    background: linear-gradient(160deg,
        #f3eeff 0%,
        #ebe6ff 20%,
        #dde8ff 55%,
        #d0e9f9 100%) !important;
    min-height: 100vh;
}

.block-container {
    padding: 1.2rem 2rem 0 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar — pure white, clean ─────────────────────────────── */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #ede9fe;
    box-shadow: 2px 0 16px rgba(109,40,217,0.06);
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1.2rem !important;
}

/* ── Override Streamlit primary button → indigo/violet ──────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6d28d9 0%, #5b21b6 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 16px rgba(109,40,217,0.35) !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
    box-shadow: 0 6px 20px rgba(109,40,217,0.45) !important;
    transform: translateY(-1px) !important;
}

/* Override secondary buttons */
.stButton > button[kind="secondary"] {
    border: 1.5px solid #7c3aed !important;
    color: #6d28d9 !important;
    border-radius: 12px !important;
    background: white !important;
}

/* ── Warning box override — clean white card ─────────────────── */
[data-testid="stAlert"] {
    background: #faf5ff !important;
    border: 1px solid #ddd6fe !important;
    border-radius: 14px !important;
    color: #4c1d95 !important;
}
[data-testid="stAlert"] p { color: #5b21b6 !important; }

/* ── Cards ────────────────────────────────────────────────────── */
.agent-card {
    background: rgba(255,255,255,0.82);
    backdrop-filter: blur(20px);
    border: 1px solid #ddd6fe;
    border-radius: 24px;
    padding: 28px 32px;
    box-shadow: 0 8px 32px rgba(109,40,217,0.08);
    margin-bottom: 18px;
}

/* ── Hero section ─────────────────────────────────────────────── */
.hero-wrap {
    display: flex; flex-direction: column;
    align-items: center; padding: 36px 0 16px;
    text-align: center;
}
.avatar-ring {
    width: 116px; height: 116px; border-radius: 50%;
    background: linear-gradient(145deg, #8b5cf6, #6d28d9);
    display: flex; align-items: center; justify-content: center;
    font-size: 52px;
    box-shadow: 0 10px 36px rgba(109,40,217,0.32),
                0 0 0 8px rgba(167,139,250,0.18),
                0 0 0 16px rgba(167,139,250,0.07);
    animation: float 3.5s ease-in-out infinite;
    margin-bottom: 22px;
}
@keyframes float {
    0%,100% { transform: translateY(0); }
    50%      { transform: translateY(-10px); }
}
.hero-title {
    font-size: 2rem; font-weight: 800;
    color: #4c1d95;
    margin-bottom: 8px; letter-spacing: -0.02em;
}
.hero-sub {
    color: #7c6fb0; font-size: 0.96rem; margin-bottom: 28px;
}

/* ── Chips ────────────────────────────────────────────────────── */
.chip-row {
    display: flex; flex-wrap: wrap; gap: 9px;
    justify-content: center; margin-top: 14px;
}
.chip {
    background: white;
    border: 1.5px solid #ddd6fe;
    border-radius: 22px; padding: 7px 16px;
    font-size: 0.83rem; color: #5b21b6;
    cursor: pointer; font-weight: 500;
    box-shadow: 0 2px 8px rgba(109,40,217,0.07);
    transition: all 0.18s;
}
.chip:hover {
    background: linear-gradient(135deg,#7c3aed,#6d28d9);
    color: white; border-color: transparent;
    box-shadow: 0 4px 14px rgba(109,40,217,0.3);
}

/* ── Chat bubbles ─────────────────────────────────────────────── */
.chat-wrap {
    display: flex; flex-direction: column;
    gap: 16px; padding: 8px 0 18px;
    max-height: 56vh; overflow-y: auto;
}
.chat-row {
    display: flex; align-items: flex-end; gap: 10px;
}
.chat-row.user-row { flex-direction: row-reverse; }

.avatar-sm {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px; flex-shrink: 0;
}
.avatar-sm.agent {
    background: linear-gradient(135deg, #8b5cf6, #6d28d9);
    box-shadow: 0 3px 10px rgba(109,40,217,0.25);
}
.avatar-sm.user {
    background: linear-gradient(135deg, #60a5fa, #3b82f6);
    box-shadow: 0 3px 10px rgba(59,130,246,0.25);
}

.bubble {
    max-width: 70%; padding: 13px 18px;
    font-size: 0.94rem; line-height: 1.56;
    word-break: break-word;
}
.bubble.agent {
    background: white;
    border-radius: 6px 18px 18px 18px;
    box-shadow: 0 2px 14px rgba(109,40,217,0.09);
    color: #1e1b4b;
}
.bubble.user {
    background: linear-gradient(135deg, #7c3aed, #5b21b6);
    border-radius: 18px 6px 18px 18px;
    color: white;
    box-shadow: 0 3px 14px rgba(109,40,217,0.28);
}

/* ── Status bar ───────────────────────────────────────────────── */
.status-bar {
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(14px);
    border: 1px solid #ddd6fe;
    border-radius: 14px; padding: 11px 22px;
    margin-bottom: 16px; font-size: 0.88rem;
    box-shadow: 0 2px 12px rgba(109,40,217,0.07);
}
.live-dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: #10b981; display: inline-block; margin-right: 8px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:0.35; transform:scale(1.45); }
}
.badge {
    border-radius: 8px; padding: 4px 13px;
    font-size: 0.79rem; font-weight: 600; letter-spacing: 0.04em;
}
.badge.agent-b { background:#ede9fe; color:#6d28d9; }
.badge.user-b  { background:#d1fae5; color:#065f46; }

/* ── Input card ───────────────────────────────────────────────── */
.input-card {
    background: rgba(255,255,255,0.82);
    backdrop-filter: blur(16px);
    border: 1.5px solid #ddd6fe;
    border-radius: 20px;
    padding: 14px 20px 10px;
    box-shadow: 0 4px 24px rgba(109,40,217,0.09);
    margin-top: 10px;
}

/* Audio input */
[data-testid="stAudioInput"] > div {
    background: #f5f3ff !important;
    border-radius: 14px !important;
    border: 1.5px solid #ddd6fe !important;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    border-radius: 14px !important;
    border: 1.5px solid #ddd6fe !important;
    background: white !important; color: #1e1b4b !important;
}
[data-testid="stChatInput"] button {
    background: linear-gradient(135deg,#7c3aed,#6d28d9) !important;
    border-radius: 10px !important; border: none !important;
}

/* Spinner */
[data-testid="stSpinner"] > div { border-top-color: #7c3aed !important; }

/* ── Radio buttons — override red → violet ────────────────────── */
[data-testid="stRadio"] label {
    color: #4c1d95 !important;
    font-size: 0.91rem !important;
}
/* Selected radio dot */
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] { display: none; }
div[role="radiogroup"] label div:first-child {
    border-color: #7c3aed !important;
}
div[role="radiogroup"] input:checked + div {
    background-color: #7c3aed !important;
    border-color: #7c3aed !important;
}
/* The inner filled circle of selected radio */
div[role="radiogroup"] input:checked ~ div svg { fill: #7c3aed !important; }

/* Streamlit radio uses SVG-based rendering in newer versions */
[data-baseweb="radio"] [data-checked="true"] > div {
    background-color: #7c3aed !important;
    border-color: #7c3aed !important;
}
[data-baseweb="radio"] > div {
    border-color: #c4b5fd !important;
}
[data-baseweb="radio"]:hover > div {
    border-color: #7c3aed !important;
}
/* Focus ring */
[data-baseweb="radio"] [data-focus-visible="true"] > div {
    box-shadow: 0 0 0 3px rgba(124,58,237,0.25) !important;
}

/* ── Sidebar nav ──────────────────────────────────────────────── */
.nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; border-radius: 12px;
    font-size: 0.91rem; font-weight: 500; color: #374151;
    cursor: pointer; margin-bottom: 4px; transition: all 0.15s;
}
.nav-item:hover   { background: #f5f3ff; color: #6d28d9; }
.nav-item.active  { background: #ede9fe; color: #6d28d9; font-weight: 600; }

/* ── Booking card ─────────────────────────────────────────────── */
.booking-card {
    background: linear-gradient(135deg,#f0fdf4,#dcfce7);
    border: 1.5px solid #86efac; border-radius: 18px;
    padding: 20px 24px; margin-bottom: 16px;
}

/* ── Metrics ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: white; border-radius: 14px;
    padding: 14px; border: 1px solid #ede9fe;
    box-shadow: 0 2px 10px rgba(109,40,217,0.07);
}
</style>
""", unsafe_allow_html=True)


# ── Audio helpers ──────────────────────────────────────────────────────────────

def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            st.warning("GROQ_API_KEY not set.")
            return ""
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes); tmp = f.name
        wl = {"en-IN": "en", "hi-IN": "hi"}.get(language, "en")
        try:
            with open(tmp, "rb") as af:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", af, "audio/wav"),
                    response_format="text", language=wl,
                )
        finally:
            try: os.unlink(tmp)
            except OSError: pass
        return str(result).strip()
    except Exception as exc:
        st.warning(f"STT error: {exc}"); return ""


def _tts(text: str, language: str = "en-IN") -> bytes | None:
    os.environ["TTS_LANGUAGE"] = language
    try:
        from src.voice.tts_engine import TTSEngine
        r = TTSEngine().synthesise(text, language=language)
        if not r.is_empty: return r.audio_bytes
    except Exception: pass
    try:
        import io as _io
        from gtts import gTTS
        buf = _io.BytesIO()
        gTTS(text=text, lang="hi" if language=="hi-IN" else "en",
             tld="co.in" if language=="en-IN" else "com", slow=False).write_to_fp(buf)
        buf.seek(0); return buf.read()
    except Exception as exc:
        st.warning(f"TTS error: {exc}"); return None


def _inject_auto_record_js():
    components.html("""
    <script>
    (function() {
        var pdoc = window.parent.document;
        function clickMic() {
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (!inp) return;
            var btn = inp.querySelector('button');
            if (btn) btn.click();
        }
        function attachAudio() {
            var audios = pdoc.querySelectorAll('audio');
            if (!audios.length) { setTimeout(attachAudio, 200); return; }
            var a = audios[audios.length-1];
            if (a.ended) { setTimeout(clickMic, 400); return; }
            a.addEventListener('ended', function(){ setTimeout(clickMic, 400); }, {once:true});
        }
        setTimeout(attachAudio, 350);
    })();
    </script>
    """, height=0)


def _render_chat_html(history: list):
    """Render conversation as beautiful styled chat bubbles."""
    parts = ['<div class="chat-wrap">']
    for turn in history:
        txt = turn["text"].replace("<", "&lt;").replace(">", "&gt;")
        if turn["role"] == "agent":
            parts.append(f"""
            <div class="chat-row">
                <div class="avatar-sm agent">🤖</div>
                <div class="bubble agent">{txt}</div>
            </div>""")
        else:
            parts.append(f"""
            <div class="chat-row user-row">
                <div class="avatar-sm user">👤</div>
                <div class="bubble user">{txt}</div>
            </div>""")
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────

def _init_state():
    for k, v in {
        "p5_started": False, "p5_history": [], "p5_ctx": None,
        "p5_fsm": None, "p5_done": False, "p5_mcp": None,
        "p5_mode": "voice", "p5_lang": "en-IN",
        "p5_disclaimer_shown": False,
        "_tts_hash": "", "_tts_audio": None, "_tts_played": "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
        <div style="width:38px;height:38px;border-radius:10px;
             background:linear-gradient(135deg,#a78bfa,#7c3aed);
             display:flex;align-items:center;justify-content:center;font-size:20px;">📞</div>
        <div>
            <div style="font-weight:700;font-size:1.05rem;color:#1e1b4b;">AdvisorBot</div>
            <div style="font-size:0.75rem;color:#7c3aed;">Scheduling Agent</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Search bar look
    st.markdown('<div style="background:rgba(124,58,237,0.07);border-radius:10px;'
                'padding:8px 14px;color:#9ca3af;font-size:0.88rem;margin-bottom:16px;">'
                '🔍 &nbsp;Search history...</div>', unsafe_allow_html=True)

    # Nav items
    _active = "active" if st.session_state.p5_started else ""
    st.markdown(f"""
    <div class="nav-item {_active}">📞 &nbsp;Current Call</div>
    <div class="nav-item">📚 &nbsp;Session History</div>
    <div class="nav-item">⚙️ &nbsp;Settings</div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid rgba(124,58,237,0.15);margin:16px 0;">', unsafe_allow_html=True)

    # Mode + Language controls
    st.markdown('<div style="font-size:0.8rem;font-weight:600;color:#6b7280;'
                'margin-bottom:8px;letter-spacing:0.05em;">MODE</div>', unsafe_allow_html=True)
    mode = st.radio("", ["voice", "text"], horizontal=True, key="p5_mode_radio",
                    label_visibility="collapsed")
    st.session_state.p5_mode = mode

    st.markdown('<div style="font-size:0.8rem;font-weight:600;color:#6b7280;'
                'margin-top:12px;margin-bottom:8px;letter-spacing:0.05em;">LANGUAGE</div>',
                unsafe_allow_html=True)
    lang_label = st.radio("", ["🇮🇳 English", "🇮🇳 हिंदी"], horizontal=True, key="p5_lang_radio",
                           label_visibility="collapsed")
    st.session_state.p5_lang = "hi-IN" if "हिंदी" in lang_label else "en-IN"

    os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
    os.environ["STT_LANGUAGE"] = st.session_state.p5_lang

    # Session history from current call
    if st.session_state.p5_history:
        st.markdown('<hr style="border:none;border-top:1px solid rgba(124,58,237,0.15);margin:16px 0;">',
                    unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;font-weight:600;color:#6b7280;'
                    'margin-bottom:8px;letter-spacing:0.05em;">THIS CALL</div>', unsafe_allow_html=True)
        for i, turn in enumerate(st.session_state.p5_history):
            if turn["role"] == "user":
                preview = turn["text"][:38] + ("…" if len(turn["text"]) > 38 else "")
                st.markdown(f'<div style="font-size:0.8rem;color:#6b7280;padding:4px 0;">'
                             f'↗ {preview}</div>', unsafe_allow_html=True)

    # Debug
    ctx_dbg = st.session_state.p5_ctx
    if ctx_dbg:
        st.markdown('<hr style="border:none;border-top:1px solid rgba(124,58,237,0.15);margin:16px 0;">',
                    unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;font-weight:600;color:#6b7280;'
                    'margin-bottom:8px;letter-spacing:0.05em;">DEBUG</div>', unsafe_allow_html=True)
        st.json({
            "state":    ctx_dbg.current_state.name,
            "topic":    ctx_dbg.topic,
            "day":      ctx_dbg.day_preference,
            "time":     ctx_dbg.time_preference,
            "booking":  ctx_dbg.booking_code,
        })

# ── Propagate language ─────────────────────────────────────────────────────────
os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
os.environ["STT_LANGUAGE"] = st.session_state.p5_lang
_lang = st.session_state.p5_lang
_is_voice = st.session_state.p5_mode == "voice"

# ── SEBI Disclaimer ───────────────────────────────────────────────────────────

if not st.session_state.p5_disclaimer_shown:
    st.markdown("""
    <div class="hero-wrap">
        <div class="avatar-ring">📞</div>
        <div class="hero-title">Advisor Scheduling Agent</div>
        <div class="hero-sub">AI-powered financial appointment booking</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="agent-card">', unsafe_allow_html=True)
    st.warning(
        "**SEBI Disclaimer**: This service is for scheduling advisory appointments only. "
        "Our representatives provide informational guidance and do not offer investment advice "
        "as defined under SEBI (Investment Advisers) Regulations, 2013.",
        icon="⚠️",
    )
    if st.button("✅ I Understand — Start", type="primary", use_container_width=True):
        st.session_state.p5_disclaimer_shown = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ── Hero / Start screen ───────────────────────────────────────────────────────

if not st.session_state.p5_started:
    st.markdown("""
    <div class="hero-wrap">
        <div class="avatar-ring">📞</div>
        <div class="hero-title">How can I help you today?</div>
        <div class="hero-sub">Book a financial advisory consultation in under 2 minutes</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="agent-card" style="max-width:600px;margin:0 auto;">', unsafe_allow_html=True)
    _lang_display = "Hindi (हिंदी)" if _lang == "hi-IN" else "Indian English"
    st.markdown(f'<div style="text-align:center;color:#6b7280;margin-bottom:16px;font-size:0.92rem;">'
                f'Language: <strong style="color:#7c3aed">{_lang_display}</strong> &nbsp;·&nbsp; '
                f'Mode: <strong style="color:#7c3aed">{st.session_state.p5_mode}</strong></div>',
                unsafe_allow_html=True)
    if st.button("📞 Start Call", type="primary", use_container_width=True):
        from src.dialogue.fsm import DialogueFSM
        fsm = DialogueFSM()
        ctx, greeting = fsm.start()
        st.session_state.p5_fsm = fsm
        st.session_state.p5_ctx = ctx
        st.session_state.p5_started = True
        st.session_state.p5_history = [{"role": "agent", "text": greeting}]
        st.session_state["_tts_hash"] = ""
        st.session_state["_tts_played"] = ""
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Topic chips
    st.markdown("""
    <div class="chip-row" style="margin-top:24px;">
        <div class="chip">💼 KYC & Onboarding</div>
        <div class="chip">📈 SIP & Mandates</div>
        <div class="chip">📄 Statements & Tax</div>
        <div class="chip">💸 Withdrawals</div>
        <div class="chip">🔄 Account Changes</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Active call UI ────────────────────────────────────────────────────────────

ctx = st.session_state.p5_ctx
_history = st.session_state.p5_history
_last = _history[-1] if _history else None

# Status bar
_state_lbl = ctx.current_state.name.replace("_", " ").title() if ctx else "—"
if _last and _last["role"] == "agent":
    _badge = '<span class="badge agent-b">🤖 Agent Speaking</span>'
else:
    _lbl = "बोलिए 🎙️" if _lang == "hi-IN" else "🎙️ Your Turn"
    _badge = f'<span class="badge user-b">{_lbl}</span>'

st.markdown(f"""
<div class="status-bar">
  <div style="display:flex;align-items:center;">
    <span class="live-dot"></span>
    <strong style="color:#1e1b4b;">LIVE&nbsp;</strong>
    <span style="color:#9ca3af;margin-left:8px;font-size:0.82rem;">{_state_lbl}</span>
  </div>
  {_badge}
</div>
""", unsafe_allow_html=True)

# ── Booking complete ──────────────────────────────────────────────────────────

if ctx and ctx.current_state.name == "BOOKING_COMPLETE":
    _render_chat_html(_history)
    st.markdown(f"""
    <div class="booking-card">
        <div style="font-size:1.2rem;font-weight:700;color:#065f46;margin-bottom:4px;">
            ✅ Booking Confirmed
        </div>
        <div style="color:#047857;font-size:0.95rem;">
            Code: <code style="background:#bbf7d0;padding:2px 8px;border-radius:6px;">
            {ctx.booking_code}</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    mcp = st.session_state.p5_mcp
    if mcp:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("📅 Calendar", "✅" if mcp.calendar_success else "❌",
                      f"{mcp.calendar.duration_ms:.0f}ms")
        with c2:
            st.metric("📊 Sheets", "✅" if mcp.sheets_success else "❌",
                      f"{mcp.sheets.duration_ms:.0f}ms")
        with c3:
            st.metric("📧 Email", "✅" if mcp.email_success else "❌",
                      f"{mcp.email.duration_ms:.0f}ms")

    if st.button("📞 Start New Call", type="primary", use_container_width=True):
        for k in ["p5_started","p5_history","p5_ctx","p5_fsm","p5_done","p5_mcp",
                  "_tts_hash","_tts_audio","_tts_played"]:
            st.session_state.pop(k, None)
        _init_state(); st.rerun()
    st.stop()

# ── Terminal state ────────────────────────────────────────────────────────────

if ctx and ctx.current_state.is_terminal():
    _render_chat_html(_history)
    st.info("Call ended.")
    if st.button("📞 New Call", type="primary", use_container_width=True):
        for k in ["p5_started","p5_history","p5_ctx","p5_fsm","p5_done","p5_mcp",
                  "_tts_hash","_tts_audio","_tts_played"]:
            st.session_state.pop(k, None)
        _init_state(); st.rerun()
    st.stop()

# ── Chat transcript ───────────────────────────────────────────────────────────

_render_chat_html(_history)

# ── TTS playback ──────────────────────────────────────────────────────────────

if _last and _last["role"] == "agent" and _is_voice:
    agent_text = _last["text"]
    text_hash  = hashlib.md5(agent_text.encode()).hexdigest()

    if st.session_state["_tts_hash"] != text_hash:
        with st.spinner("Generating voice..." if _lang == "en-IN" else "आवाज़ बना रहे हैं..."):
            audio_bytes = _tts(agent_text, language=_lang)
        st.session_state["_tts_hash"]  = text_hash
        st.session_state["_tts_audio"] = audio_bytes
    else:
        audio_bytes = st.session_state["_tts_audio"]

    should_autoplay = st.session_state["_tts_played"] != text_hash

    if audio_bytes:
        fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mp3"
        st.audio(audio_bytes, format=fmt, autoplay=should_autoplay)
        if should_autoplay:
            st.session_state["_tts_played"] = text_hash
            _inject_auto_record_js()

# ── Input area ────────────────────────────────────────────────────────────────

def _process_user_input(user_text: str):
    from src.dialogue.intent_router import IntentRouter
    from src.mcp.mcp_orchestrator import dispatch_mcp_sync, build_payload
    fsm = st.session_state.p5_fsm
    ctx = st.session_state.p5_ctx
    try:
        llm_resp = IntentRouter().route(user_text, ctx)
    except Exception as exc:
        st.error(f"Routing error: {exc}"); return
    ctx, speech = fsm.process_turn(ctx, user_text, llm_resp)
    if ctx.current_state.name == "BOOKING_COMPLETE" and ctx.booking_code:
        try:
            res = dispatch_mcp_sync(build_payload(ctx))
            st.session_state.p5_mcp = res
            ctx.calendar_hold_created = res.calendar_success
            ctx.notes_appended        = res.sheets_success
            ctx.email_drafted         = res.email_success
        except Exception: pass
    st.session_state.p5_ctx = ctx
    st.session_state.p5_history.append({"role": "user",  "text": user_text})
    st.session_state.p5_history.append({"role": "agent", "text": speech})
    st.session_state["_tts_played"] = ""


st.markdown('<div class="input-card">', unsafe_allow_html=True)

if _is_voice:
    _mic_lbl = "🎤 बोलिए (Hindi में)" if _lang == "hi-IN" else "🎤 Speak now"
    audio_input = st.audio_input(_mic_lbl, key="p5_audio_input")
    if audio_input is not None:
        _ab   = audio_input.read()
        _ahash = hashlib.md5(_ab).hexdigest()
        if st.session_state.get("_last_audio_hash") != _ahash:
            st.session_state["_last_audio_hash"] = _ahash
            with st.spinner("Transcribing..." if _lang == "en-IN" else "सुन रहे हैं..."):
                transcript = _stt(_ab, language=_lang)
            if transcript:
                st.markdown(f'<div style="color:#7c3aed;font-size:0.85rem;'
                             f'margin-bottom:4px;">🗣 <em>{transcript}</em></div>',
                             unsafe_allow_html=True)
                _process_user_input(transcript)
            else:
                st.warning("Could not transcribe. Please try again.")
            st.rerun()
else:
    _ph = "यहाँ टाइप करें..." if _lang == "hi-IN" else "Chat here..."
    user_input = st.chat_input(_ph)
    if user_input and user_input.strip():
        _process_user_input(user_input.strip()); st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Quick topic chips (only shown after greeting before topic is selected)
if ctx and not ctx.topic and ctx.current_state.name in ("INTENT_IDENTIFIED", "DISCLAIMER_CONFIRMED"):
    st.markdown("""
    <div class="chip-row" style="margin-top:14px;">
        <div class="chip">💼 KYC</div>
        <div class="chip">📈 SIP</div>
        <div class="chip">📄 Statements</div>
        <div class="chip">💸 Withdrawals</div>
        <div class="chip">🔄 Account Changes</div>
    </div>
    """, unsafe_allow_html=True)
