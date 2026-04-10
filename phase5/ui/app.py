"""
Phase 5 — Production Streamlit UI
Advisor Scheduling Voice & Text Agent
"""
from __future__ import annotations

import sys
import os
import hashlib
from pathlib import Path

# ── sys.path setup ─────────────────────────────────────────────────────────
_ui_dir   = Path(__file__).resolve().parent
_p5_dir   = _ui_dir.parent
_root_dir = _p5_dir.parent

for _entry in [
    str(_root_dir / "phase0"), str(_root_dir / "phase1"),
    str(_root_dir / "phase2"), str(_root_dir / "phase3"),
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

import tempfile
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Advisor Scheduling Agent",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

/* Full page gradient */
.stApp {
    background: linear-gradient(160deg, #f3eeff 0%, #ebe6ff 25%, #dde8ff 60%, #d0e9f9 100%) !important;
}
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* ── Top navbar ────────────────────────────────────────────────── */
.navbar {
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid #ddd6fe;
    padding: 12px 32px;
    position: sticky; top: 0; z-index: 999;
}
.navbar-logo {
    display: flex; align-items: center; gap: 10px;
}
.navbar-logo-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, #8b5cf6, #6d28d9);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    box-shadow: 0 3px 10px rgba(109,40,217,0.3);
}
.navbar-brand { font-weight: 700; font-size: 1.05rem; color: #1e1b4b; }
.navbar-sub   { font-size: 0.75rem; color: #7c3aed; }

/* ── Main content wrapper ─────────────────────────────────────── */
.main-wrap {
    max-width: 780px; margin: 0 auto;
    padding: 0 20px 40px;
}

/* ── Hero ─────────────────────────────────────────────────────── */
.hero-wrap {
    display: flex; flex-direction: column;
    align-items: center; padding: 48px 0 24px;
    text-align: center;
}
.avatar-ring {
    width: 110px; height: 110px; border-radius: 50%;
    background: linear-gradient(145deg, #8b5cf6, #6d28d9);
    display: flex; align-items: center; justify-content: center;
    font-size: 50px;
    box-shadow: 0 10px 36px rgba(109,40,217,0.30),
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
    color: #3b0764; margin-bottom: 8px;
}
.hero-sub { color: #7c6fb0; font-size: 0.96rem; }

/* ── Controls card ────────────────────────────────────────────── */
.controls-card {
    background: white;
    border: 1.5px solid #ddd6fe;
    border-radius: 18px;
    padding: 16px 24px;
    margin: 18px 0;
    box-shadow: 0 4px 20px rgba(109,40,217,0.07);
    display: flex; align-items: center; gap: 32px;
}

/* ── Chips ────────────────────────────────────────────────────── */
.chip-row {
    display: flex; flex-wrap: wrap; gap: 9px;
    justify-content: center; margin: 18px 0 0;
}
.chip {
    background: white; border: 1.5px solid #ddd6fe;
    border-radius: 22px; padding: 7px 16px;
    font-size: 0.83rem; color: #5b21b6; font-weight: 500;
    box-shadow: 0 2px 8px rgba(109,40,217,0.07);
}

/* ── Status bar ───────────────────────────────────────────────── */
.status-bar {
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(255,255,255,0.80); backdrop-filter: blur(14px);
    border: 1.5px solid #ddd6fe; border-radius: 14px;
    padding: 11px 22px; margin: 16px 0;
    box-shadow: 0 2px 12px rgba(109,40,217,0.06);
    font-size: 0.88rem;
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
.badge { border-radius: 8px; padding: 4px 13px; font-size: 0.79rem; font-weight: 600; }
.badge.agent-b { background:#ede9fe; color:#6d28d9; }
.badge.user-b  { background:#d1fae5; color:#065f46; }

/* ── Chat bubbles ─────────────────────────────────────────────── */
.chat-wrap {
    display: flex; flex-direction: column;
    gap: 14px; padding: 8px 0 16px;
}
.chat-row { display: flex; align-items: flex-end; gap: 10px; }
.chat-row.user-row { flex-direction: row-reverse; }
.avatar-sm {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px; flex-shrink: 0;
}
.avatar-sm.agent { background: linear-gradient(135deg,#8b5cf6,#6d28d9); box-shadow:0 3px 10px rgba(109,40,217,.25); }
.avatar-sm.user  { background: linear-gradient(135deg,#60a5fa,#3b82f6); box-shadow:0 3px 10px rgba(59,130,246,.25); }
.bubble { max-width: 72%; padding: 13px 18px; font-size: 0.94rem; line-height: 1.56; word-break: break-word; }
.bubble.agent { background:white; border-radius:6px 18px 18px 18px; box-shadow:0 2px 14px rgba(109,40,217,.09); color:#1e1b4b; }
.bubble.user  { background:linear-gradient(135deg,#7c3aed,#5b21b6); border-radius:18px 6px 18px 18px; color:white; box-shadow:0 3px 14px rgba(109,40,217,.28); }

/* ── Input card ───────────────────────────────────────────────── */
.input-card {
    background: rgba(255,255,255,0.85); backdrop-filter:blur(16px);
    border: 1.5px solid #ddd6fe; border-radius: 20px;
    padding: 16px 20px 12px;
    box-shadow: 0 4px 24px rgba(109,40,217,0.09);
    margin-top: 12px;
}

/* ── Buttons ───────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg,#6d28d9,#5b21b6) !important;
    color: white !important; border: none !important;
    border-radius: 14px !important; font-weight: 600 !important;
    box-shadow: 0 4px 16px rgba(109,40,217,.35) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg,#7c3aed,#6d28d9) !important;
    transform: translateY(-1px) !important;
}

/* ── Alert/warning ─────────────────────────────────────────────── */
[data-testid="stAlert"] {
    background: #faf5ff !important; border: 1px solid #ddd6fe !important;
    border-radius: 14px !important;
}
[data-testid="stAlert"] p { color: #5b21b6 !important; }

/* ── Audio / Chat input ────────────────────────────────────────── */
[data-testid="stAudioInput"] > div {
    background: #f5f3ff !important; border-radius:14px !important; border:1.5px solid #ddd6fe !important;
}
[data-testid="stChatInput"] textarea {
    border-radius:14px !important; border:1.5px solid #ddd6fe !important; background:white !important;
}
[data-testid="stChatInput"] button {
    background:linear-gradient(135deg,#7c3aed,#6d28d9) !important; border-radius:10px !important; border:none !important;
}

/* ── Metrics ───────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background:white; border-radius:14px; padding:14px;
    border:1px solid #ede9fe; box-shadow:0 2px 10px rgba(109,40,217,.07);
}

/* ── Booking card ──────────────────────────────────────────────── */
.booking-card {
    background:linear-gradient(135deg,#f0fdf4,#dcfce7);
    border:1.5px solid #86efac; border-radius:18px; padding:20px 24px; margin-bottom:16px;
}

/* Hide Streamlit sidebar toggle since we don't use sidebar */
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ── Audio helpers ──────────────────────────────────────────────────────────

def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            st.warning("GROQ_API_KEY not set."); return ""
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes); tmp = f.name
        wl = {"en-IN": "en", "hi-IN": "hi"}.get(language, "en")
        try:
            with open(tmp, "rb") as af:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3", file=("audio.wav", af, "audio/wav"),
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


def _render_chat(history: list):
    parts = ['<div class="chat-wrap">']
    for turn in history:
        txt = turn["text"].replace("<","&lt;").replace(">","&gt;")
        if turn["role"] == "agent":
            parts.append(f'<div class="chat-row"><div class="avatar-sm agent">🤖</div><div class="bubble agent">{txt}</div></div>')
        else:
            parts.append(f'<div class="chat-row user-row"><div class="avatar-sm user">👤</div><div class="bubble user">{txt}</div></div>')
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────

def _init_state():
    for k, v in {
        "p5_started": False, "p5_history": [], "p5_ctx": None,
        "p5_fsm": None, "p5_mcp": None,
        "p5_mode": "voice", "p5_lang": "en-IN",
        "p5_disclaimer_shown": False,
        "_tts_hash": "", "_tts_audio": None, "_tts_played": "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Contact Details Form (secure URL landing page) ─────────────────────────
_booking_token = st.query_params.get("booking_token", "")
if _booking_token:
    sys.path.insert(0, str(_root_dir / "phase1"))
    sys.path.insert(0, str(_root_dir / "phase4"))

    st.markdown("""
    <style>
    .cf-page {
        min-height: 100vh;
        background: linear-gradient(160deg, #f3eeff 0%, #ebe6ff 30%, #dde8ff 70%, #d0e9f9 100%);
        display: flex; flex-direction: column; align-items: center;
        padding: 0 0 60px;
    }
    .cf-topbar {
        width: 100%; background: rgba(255,255,255,0.88);
        backdrop-filter: blur(16px); border-bottom: 1px solid #ddd6fe;
        padding: 14px 32px; display: flex; align-items: center; gap: 12px;
        margin-bottom: 40px;
    }
    .cf-logo { width:36px;height:36px;border-radius:10px;
        background:linear-gradient(135deg,#8b5cf6,#6d28d9);
        display:flex;align-items:center;justify-content:center;font-size:18px; }
    .cf-brand { font-weight:700;font-size:1rem;color:#1e1b4b; }
    .cf-sub   { font-size:0.75rem;color:#7c3aed; }
    .cf-card {
        background: white; border: 1.5px solid #ddd6fe;
        border-radius: 24px; padding: 36px 40px;
        box-shadow: 0 12px 40px rgba(109,40,217,0.10);
        width: 100%; max-width: 480px;
    }
    .cf-header { text-align:center; margin-bottom: 28px; }
    .cf-icon { font-size: 3rem; margin-bottom: 10px; }
    .cf-title { font-size:1.55rem; font-weight:800; color:#3b0764; margin-bottom:6px; }
    .cf-desc  { color:#7c6fb0; font-size:0.92rem; line-height:1.5; }
    .cf-booking-strip {
        background: linear-gradient(135deg,#f5f3ff,#ede9fe);
        border: 1px solid #c4b5fd; border-radius: 14px;
        padding: 14px 18px; margin-bottom: 24px;
        display: flex; flex-direction:column; gap:4px;
    }
    .cf-code { font-size:1.2rem;font-weight:800;color:#6d28d9;letter-spacing:2px; }
    .cf-meta { font-size:0.85rem;color:#5b21b6; }
    .cf-divider { border:none;border-top:1.5px solid #ede9fe;margin:20px 0; }
    .cf-success {
        text-align:center; padding: 12px 0 4px;
    }
    .cf-success-icon { font-size:4rem; margin-bottom:12px; }
    .cf-success-title { font-size:1.4rem;font-weight:800;color:#065f46;margin-bottom:8px; }
    .cf-success-desc  { color:#047857;font-size:0.92rem;line-height:1.6; }
    .cf-summary {
        background:#f0fdf4;border:1.5px solid #86efac;
        border-radius:14px;padding:16px 20px;margin-top:20px;text-align:left;
    }
    .cf-summary-row { display:flex;gap:10px;margin-bottom:6px;font-size:0.88rem;color:#065f46; }
    .cf-summary-label { font-weight:600;min-width:60px; }
    @keyframes cf-pop {
        0%   { opacity:0; transform:scale(0.85) translateY(20px); }
        60%  { transform:scale(1.04) translateY(-4px); }
        100% { opacity:1; transform:scale(1) translateY(0); }
    }
    .cf-animate { animation: cf-pop 0.55s ease forwards; }
    </style>
    """, unsafe_allow_html=True)

    # session keys scoped to this token
    _sk_done  = f"cf_done_{_booking_token[:12]}"
    _sk_name  = f"cf_name_{_booking_token[:12]}"
    _sk_email = f"cf_email_{_booking_token[:12]}"
    _sk_phone = f"cf_phone_{_booking_token[:12]}"
    _sk_err   = f"cf_err_{_booking_token[:12]}"

    # Topbar
    st.markdown("""
    <div class="cf-topbar">
      <div class="cf-logo">📞</div>
      <div>
        <div class="cf-brand">AdvisorBot</div>
        <div class="cf-sub">Appointment Scheduling</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, fc, _ = st.columns([1, 5, 1])
    with fc:
        try:
            from src.booking.secure_url_generator import verify_secure_url
            from src.dialogue.states import TOPIC_LABELS
            payload     = verify_secure_url(_booking_token)
            booking_code= payload.get("booking_code", "")
            topic_key   = payload.get("topic", "")
            slot_ist    = payload.get("slot_ist", "")
            topic_label = TOPIC_LABELS.get(topic_key, topic_key.replace("_", " ").title())

            # ── SUCCESS STATE ──────────────────────────────────────────────
            if st.session_state.get(_sk_done):
                _sent_email = st.session_state.get(_sk_email, "")
                _sent_name  = st.session_state.get(_sk_name, "")
                _sent_phone = st.session_state.get(_sk_phone, "")
                st.markdown(f"""
                <div class="cf-card cf-animate">
                  <div class="cf-success">
                    <div class="cf-success-icon">🎉</div>
                    <div class="cf-success-title">All Done!</div>
                    <div class="cf-success-desc">
                      A confirmation email has been sent to<br>
                      <strong>{_sent_email}</strong>.<br><br>
                      Please check your inbox (and spam folder).
                    </div>
                  </div>
                  <div class="cf-summary">
                    <div class="cf-summary-row"><span class="cf-summary-label">📌 Code</span><b>{booking_code}</b></div>
                    <div class="cf-summary-row"><span class="cf-summary-label">📚 Topic</span>{topic_label}</div>
                    <div class="cf-summary-row"><span class="cf-summary-label">🕐 Slot</span>{slot_ist} (IST)</div>
                    <div class="cf-summary-row"><span class="cf-summary-label">👤 Name</span>{_sent_name}</div>
                    <div class="cf-summary-row"><span class="cf-summary-label">📧 Email</span>{_sent_email}</div>
                    <div class="cf-summary-row"><span class="cf-summary-label">📞 Phone</span>{_sent_phone}</div>
                  </div>
                  <p style="text-align:center;color:#9ca3af;font-size:0.8rem;margin-top:20px;">
                    An advisor will reach out to confirm your appointment.<br>
                    To reschedule or cancel, call us and quote your booking code.
                  </p>
                </div>
                """, unsafe_allow_html=True)

            # ── FORM STATE ─────────────────────────────────────────────────
            else:
                # Booking strip
                st.markdown(f"""
                <div class="cf-card">
                  <div class="cf-header">
                    <div class="cf-icon">📋</div>
                    <div class="cf-title">Complete Your Booking</div>
                    <div class="cf-desc">Enter your contact details below.<br>
                    You'll receive a confirmation email once you submit.</div>
                  </div>
                  <div class="cf-booking-strip">
                    <div class="cf-code">🔖 {booking_code}</div>
                    <div class="cf-meta">📚 {topic_label}</div>
                    <div class="cf-meta">🕐 {slot_ist} (IST)</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Show previous errors if any
                if st.session_state.get(_sk_err):
                    for e in st.session_state[_sk_err]:
                        st.error(e)
                    st.session_state[_sk_err] = []

                with st.form("contact_form", clear_on_submit=False):
                    name    = st.text_input("Full Name", placeholder="e.g. Rahul Sharma")
                    email   = st.text_input("Email Address", placeholder="you@example.com")
                    phone   = st.text_input("Phone Number", placeholder="e.g. 9876543210")
                    consent = st.checkbox(
                        "I agree to receive an appointment confirmation email at the address above."
                    )
                    submitted = st.form_submit_button(
                        "Send Confirmation Email",
                        type="primary",
                        use_container_width=True,
                    )

                if submitted:
                    errors = []
                    if not name.strip():
                        errors.append("Name is required.")
                    if not email.strip() or "@" not in email:
                        errors.append("Enter a valid email address.")
                    if not phone.strip():
                        errors.append("Phone number is required.")
                    if not consent:
                        errors.append("Please tick the consent checkbox to receive the confirmation email.")

                    if errors:
                        st.session_state[_sk_err] = errors
                        st.rerun()
                    else:
                        with st.spinner("Sending confirmation email…"):
                            try:
                                from src.mcp.email_tool import send_user_confirmation
                                send_user_confirmation(
                                    to_name     = name.strip(),
                                    to_email    = email.strip(),
                                    booking_code= booking_code,
                                    topic_label = topic_label,
                                    slot_ist    = slot_ist,
                                )
                                st.session_state[_sk_done]  = True
                                st.session_state[_sk_name]  = name.strip()
                                st.session_state[_sk_email] = email.strip()
                                st.session_state[_sk_phone] = phone.strip()
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not send email: {exc}. Please try again.")

        except Exception:
            st.markdown("""
            <div class="cf-card" style="text-align:center;padding:48px 32px;">
              <div style="font-size:3rem;margin-bottom:16px;">⏰</div>
              <div style="font-size:1.2rem;font-weight:700;color:#7f1d1d;margin-bottom:8px;">Link Expired or Invalid</div>
              <div style="color:#9ca3af;font-size:0.9rem;">This secure link has expired (24-hour TTL) or is no longer valid.<br>
              Please call us again to receive a new booking link.</div>
            </div>
            """, unsafe_allow_html=True)

    st.stop()

# ── Top Navbar (always visible) ────────────────────────────────────────────

st.markdown("""
<div class="navbar">
  <div class="navbar-logo">
    <div class="navbar-logo-icon">📞</div>
    <div>
      <div class="navbar-brand">AdvisorBot</div>
      <div class="navbar-sub">Scheduling Agent</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Main content area ──────────────────────────────────────────────────────
# Centre column with padding
_, main_col, _ = st.columns([1, 6, 1])

with main_col:

    os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
    os.environ["STT_LANGUAGE"] = st.session_state.p5_lang
    _lang    = st.session_state.p5_lang
    _is_voice = st.session_state.p5_mode == "voice"

    # ── SEBI Disclaimer ────────────────────────────────────────────────────
    if not st.session_state.p5_disclaimer_shown:
        st.markdown("""
        <div class="hero-wrap">
            <div class="avatar-ring">📞</div>
            <div class="hero-title">Advisor Scheduling Agent</div>
            <div class="hero-sub">AI-powered financial appointment booking</div>
        </div>
        """, unsafe_allow_html=True)

        st.warning(
            "**SEBI Disclaimer**: This service is for scheduling advisory appointments only. "
            "Our representatives provide informational guidance and do not offer investment advice "
            "as defined under SEBI (Investment Advisers) Regulations, 2013.",
            icon="⚠️",
        )
        if st.button("✅ I Understand — Start", type="primary", use_container_width=True):
            st.session_state.p5_disclaimer_shown = True
            st.rerun()
        st.stop()

    # ── Mode + Language controls ───────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1, 1])
    with c2:
        mode = st.radio("Mode", ["voice", "text"], horizontal=True, key="p5_mode_radio")
        st.session_state.p5_mode = mode
    with c3:
        lang_lbl = st.radio("Language", ["🇮🇳 English", "🇮🇳 हिंदी"], horizontal=True, key="p5_lang_radio")
        st.session_state.p5_lang = "hi-IN" if "हिंदी" in lang_lbl else "en-IN"

    os.environ["TTS_LANGUAGE"] = st.session_state.p5_lang
    os.environ["STT_LANGUAGE"] = st.session_state.p5_lang
    _lang     = st.session_state.p5_lang
    _is_voice = st.session_state.p5_mode == "voice"

    # ── Start screen ───────────────────────────────────────────────────────
    if not st.session_state.p5_started:
        st.markdown("""
        <div class="hero-wrap">
            <div class="avatar-ring">📞</div>
            <div class="hero-title">How can I help you today?</div>
            <div class="hero-sub">Book a financial advisory consultation in under 2 minutes</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📞 Start Call", type="primary", use_container_width=True):
            from src.dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.p5_fsm     = fsm
            st.session_state.p5_ctx     = ctx
            st.session_state.p5_started = True
            st.session_state.p5_history = [{"role": "agent", "text": greeting}]
            st.session_state["_tts_hash"] = ""
            st.session_state["_tts_played"] = ""
            st.rerun()

        st.markdown("""
        <div class="chip-row">
            <div class="chip">💼 KYC & Onboarding</div>
            <div class="chip">📈 SIP & Mandates</div>
            <div class="chip">📄 Statements & Tax</div>
            <div class="chip">💸 Withdrawals</div>
            <div class="chip">🔄 Account Changes</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # ── Active call ────────────────────────────────────────────────────────
    ctx      = st.session_state.p5_ctx
    _history = st.session_state.p5_history
    _last    = _history[-1] if _history else None

    _state_lbl = ctx.current_state.name.replace("_"," ").title() if ctx else "—"
    if _last and _last["role"] == "agent":
        _badge = '<span class="badge agent-b">🤖 Agent Speaking</span>'
    else:
        _lbl = "बोलिए 🎙️" if _lang == "hi-IN" else "🎙️ Your Turn"
        _badge = f'<span class="badge user-b">{_lbl}</span>'

    st.markdown(f"""
    <div class="status-bar">
      <div><span class="live-dot"></span>
           <strong style="color:#1e1b4b;">LIVE</strong>
           <span style="color:#9ca3af;margin-left:8px;font-size:0.82rem;">{_state_lbl}</span>
      </div>
      {_badge}
    </div>
    """, unsafe_allow_html=True)

    # ── Booking complete ───────────────────────────────────────────────────
    if ctx and ctx.current_state.name == "BOOKING_COMPLETE":
        _render_chat(_history)
        _secure_url = ctx.secure_url or ""
        st.markdown(f"""
        <div class="booking-card">
          <div style="font-size:1.2rem;font-weight:700;color:#065f46;margin-bottom:8px;">✅ Booking Confirmed</div>
          <div style="color:#047857;margin-bottom:8px;">Code: <code style="background:#bbf7d0;padding:2px 8px;border-radius:6px;">{ctx.booking_code}</code></div>
          {"" if not _secure_url else f'<div style="margin-top:8px;font-size:0.9rem;color:#374151;">📎 Submit your contact details to receive a confirmation email:<br><a href="{_secure_url}" target="_blank" style="color:#6d28d9;font-weight:600;word-break:break-all;">{_secure_url}</a></div>'}
        </div>""", unsafe_allow_html=True)
        mcp = st.session_state.p5_mcp
        if mcp:
            mc1, mc2, mc3 = st.columns(3)
            with mc1: st.metric("📅 Calendar", "✅" if mcp.calendar_success else "❌", f"{mcp.calendar.duration_ms:.0f}ms")
            with mc2: st.metric("📊 Sheets",   "✅" if mcp.sheets_success   else "❌", f"{mcp.sheets.duration_ms:.0f}ms")
            with mc3: st.metric("📧 Email",    "✅" if mcp.email_success    else "❌", f"{mcp.email.duration_ms:.0f}ms")
        if st.button("📞 Start New Call", type="primary", use_container_width=True):
            for k in ["p5_started","p5_history","p5_ctx","p5_fsm","p5_mcp","_tts_hash","_tts_audio","_tts_played"]:
                st.session_state.pop(k, None)
            _init_state(); st.rerun()
        st.stop()

    if ctx and ctx.current_state.is_terminal():
        _render_chat(_history)
        st.info("Call ended.")
        if st.button("📞 New Call", type="primary", use_container_width=True):
            for k in ["p5_started","p5_history","p5_ctx","p5_fsm","p5_mcp","_tts_hash","_tts_audio","_tts_played"]:
                st.session_state.pop(k, None)
            _init_state(); st.rerun()
        st.stop()

    # ── Chat transcript ────────────────────────────────────────────────────
    _render_chat(_history)

    # ── TTS playback ───────────────────────────────────────────────────────
    if _last and _last["role"] == "agent" and _is_voice:
        text_hash = hashlib.md5(_last["text"].encode()).hexdigest()
        if st.session_state["_tts_hash"] != text_hash:
            with st.spinner("Generating voice..." if _lang=="en-IN" else "आवाज़ बना रहे हैं..."):
                audio_bytes = _tts(_last["text"], language=_lang)
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

    # ── Input ──────────────────────────────────────────────────────────────
    def _process(user_text: str):
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
        st.session_state.p5_history.append({"role":"user",  "text": user_text})
        st.session_state.p5_history.append({"role":"agent", "text": speech})
        st.session_state["_tts_played"] = ""

    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    if _is_voice:
        _mic_lbl = "🎤 बोलिए (Hindi में)" if _lang=="hi-IN" else "🎤 Speak now"
        audio_input = st.audio_input(_mic_lbl, key="p5_audio_input")
        if audio_input is not None:
            _ab    = audio_input.read()
            _ahash = hashlib.md5(_ab).hexdigest()
            if st.session_state.get("_last_audio_hash") != _ahash:
                st.session_state["_last_audio_hash"] = _ahash
                with st.spinner("Transcribing..." if _lang=="en-IN" else "सुन रहे हैं..."):
                    transcript = _stt(_ab, language=_lang)
                if transcript:
                    st.markdown(f'<div style="color:#7c3aed;font-size:0.85rem;">🗣 <em>{transcript}</em></div>', unsafe_allow_html=True)
                    _process(transcript)
                else:
                    st.warning("Could not transcribe. Please try again.")
                st.rerun()
    else:
        _ph = "यहाँ टाइप करें..." if _lang=="hi-IN" else "Chat here..."
        user_input = st.chat_input(_ph)
        if user_input and user_input.strip():
            _process(user_input.strip()); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Topic chips (before topic selected)
    if ctx and not ctx.topic and ctx.current_state.name in ("INTENT_IDENTIFIED","DISCLAIMER_CONFIRMED"):
        st.markdown("""
        <div class="chip-row">
            <div class="chip">💼 KYC</div><div class="chip">📈 SIP</div>
            <div class="chip">📄 Statements</div><div class="chip">💸 Withdrawals</div>
            <div class="chip">🔄 Account Changes</div>
        </div>
        """, unsafe_allow_html=True)
