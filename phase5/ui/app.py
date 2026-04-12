"""
Phase 5 — Production Streamlit UI
Pure Voice Agent — phone-call experience, no text transcript.
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
os.environ.setdefault("TTS_PACE", "1.0")

import tempfile
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Dalal Street Advisors",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS  (Dezerv-inspired: charcoal + warm gold) ────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Reset Streamlit chrome ──────────────────────────────────────── */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="collapsedControl"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

/* ── Base: deep charcoal, gold accent ────────────────────────────── */
:root {
    --bg-base:    #0A0C14;
    --bg-card:    #10131F;
    --bg-glass:   rgba(255,255,255,0.04);
    --border:     rgba(255,255,255,0.08);
    --gold-1:     #C9A84C;
    --gold-2:     #E8C96D;
    --gold-glow:  rgba(201,168,76,0.18);
    --gold-dim:   rgba(201,168,76,0.55);
    --text-1:     #F5F0E8;
    --text-2:     #9A9080;
    --text-3:     #6B6358;
    --green:      #22C55E;
    --red:        #EF4444;
}

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
section.main > div {
    background: var(--bg-base) !important;
    color: var(--text-1) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
    margin: 0 !important;
}

/* ── DSA Site Header ──────────────────────────────────────────────── */
.dsa-header {
    position: sticky; top: 0; z-index: 100;
    background: rgba(10,12,20,0.95);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 48px; height: 64px;
    width: 100%; box-sizing: border-box;
}
.dsa-logo-wrap { display: flex; align-items: center; gap: 12px; text-decoration: none; }
.dsa-logo-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, var(--gold-1), #8a6820);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.dsa-logo-text { font-size: 1.05rem; font-weight: 800; color: var(--text-1); letter-spacing: -0.02em; }
.dsa-logo-sub  { font-size: 0.65rem; color: var(--gold-dim); letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500; }
.dsa-nav { display: flex; gap: 32px; align-items: center; }
.dsa-nav a {
    font-size: 0.85rem; font-weight: 500; color: var(--text-2);
    text-decoration: none; letter-spacing: 0.01em;
    transition: color 0.2s;
}
.dsa-nav a:hover { color: var(--gold-2); }
.dsa-header-cta {
    background: linear-gradient(135deg, var(--gold-1), #8a6820);
    color: #0A0C14; font-weight: 700; font-size: 0.82rem;
    border: none; border-radius: 100px; padding: 9px 22px;
    cursor: pointer; letter-spacing: 0.02em;
    transition: all 0.2s;
    text-decoration: none; display: inline-block;
}
.dsa-header-cta:hover { background: linear-gradient(135deg, var(--gold-2), var(--gold-1)); }
@media (max-width: 768px) {
    .dsa-nav { display: none; }
    .dsa-header { padding: 0 20px; }
}

/* ── DSA Site Footer ──────────────────────────────────────────────── */
.dsa-footer {
    background: #07080F;
    border-top: 1px solid var(--border);
    padding: 48px 48px 32px;
    margin-top: 0;
}
.dsa-footer-grid {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1fr;
    gap: 40px; max-width: 1200px; margin: 0 auto 40px;
}
.dsa-footer-brand p { font-size: 0.85rem; color: var(--text-3); line-height: 1.7; margin-top: 12px; max-width: 280px; }
.dsa-footer-col h4 { font-size: 0.78rem; font-weight: 700; color: var(--gold-dim); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 16px; }
.dsa-footer-col a  { display: block; font-size: 0.84rem; color: var(--text-3); text-decoration: none; margin-bottom: 10px; transition: color 0.2s; }
.dsa-footer-col a:hover { color: var(--text-1); }
.dsa-footer-bottom {
    border-top: 1px solid var(--border); padding-top: 24px;
    display: flex; justify-content: space-between; align-items: flex-start;
    max-width: 1200px; margin: 0 auto;
    flex-wrap: wrap; gap: 12px;
}
.dsa-footer-copy { font-size: 0.78rem; color: var(--text-3); line-height: 1.6; max-width: 640px; }
.dsa-footer-sebi { font-size: 0.75rem; color: var(--text-3); text-align: right; }
.dsa-footer-sebi span { color: var(--gold-dim); font-weight: 600; }
@media (max-width: 768px) {
    .dsa-footer-grid { grid-template-columns: 1fr 1fr; }
    .dsa-footer { padding: 40px 20px 24px; }
    .dsa-footer-bottom { flex-direction: column; }
    .dsa-footer-sebi { text-align: left; }
}

/* ── Homepage: hero ──────────────────────────────────────────────── */
.hp-hero {
    min-height: 520px;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center;
    padding: 80px 24px 56px;
    background:
        radial-gradient(ellipse 70% 60% at 50% 0%, rgba(201,168,76,0.09) 0%, transparent 65%);
    position: relative;
}
.hp-hero-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(201,168,76,0.10); border: 1px solid rgba(201,168,76,0.28);
    border-radius: 100px; padding: 5px 18px;
    font-size: 0.73rem; font-weight: 700; color: var(--gold-2);
    letter-spacing: 0.09em; text-transform: uppercase; margin-bottom: 28px;
}
.hp-hero-title {
    font-size: 3.4rem; font-weight: 800; line-height: 1.13;
    color: var(--text-1); letter-spacing: -0.04em; margin-bottom: 18px;
    max-width: 760px;
}
.hp-hero-title span {
    background: linear-gradient(135deg, var(--gold-1) 0%, var(--gold-2) 60%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hp-hero-sub {
    font-size: 1.1rem; color: var(--text-2); line-height: 1.7;
    max-width: 540px; margin-bottom: 40px; font-weight: 400;
}
.hp-hero-actions { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; justify-content: center; }
.hp-cta-primary {
    background: linear-gradient(135deg, var(--gold-1), #8a6820);
    color: #0A0C14; font-weight: 700; font-size: 1rem;
    border: none; border-radius: 100px; padding: 15px 40px;
    cursor: pointer; letter-spacing: 0.02em;
    box-shadow: 0 4px 28px rgba(201,168,76,0.35);
    transition: all 0.2s;
}
.hp-cta-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 40px rgba(201,168,76,0.50); }
.hp-cta-secondary {
    background: transparent; color: var(--text-2);
    border: 1px solid var(--border); border-radius: 100px;
    padding: 14px 32px; font-size: 0.95rem; cursor: pointer;
    transition: all 0.2s;
}
.hp-cta-secondary:hover { border-color: rgba(201,168,76,0.4); color: var(--gold-2); }

/* ── Homepage: stats ──────────────────────────────────────────────── */
.hp-stats {
    display: flex; justify-content: center; gap: 1px;
    background: var(--border); border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}
.hp-stat {
    flex: 1; max-width: 220px; background: var(--bg-base);
    padding: 28px 20px; text-align: center;
}
.hp-stat-val { font-size: 1.7rem; font-weight: 800; color: var(--gold-2); letter-spacing: -0.03em; margin-bottom: 4px; }
.hp-stat-lbl { font-size: 0.76rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.07em; font-weight: 500; }

/* ── Homepage: sections wrapper ──────────────────────────────────── */
.hp-section { max-width: 1200px; margin: 0 auto; padding: 72px 48px; }
.hp-section-sm { max-width: 1200px; margin: 0 auto; padding: 40px 48px; }
@media (max-width: 768px) {
    .hp-section, .hp-section-sm { padding: 48px 20px; }
    .hp-hero-title { font-size: 2.2rem; }
}
.hp-section-tag {
    font-size: 0.72rem; font-weight: 700; color: var(--gold-dim);
    letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;
}
.hp-section-title {
    font-size: 2rem; font-weight: 800; color: var(--text-1);
    letter-spacing: -0.03em; margin-bottom: 12px; line-height: 1.2;
}
.hp-section-sub { font-size: 1rem; color: var(--text-2); line-height: 1.65; max-width: 520px; }

/* ── Homepage: service cards ─────────────────────────────────────── */
.hp-services-grid {
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 14px; margin-top: 40px;
}
@media (max-width: 900px) { .hp-services-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 540px) { .hp-services-grid { grid-template-columns: 1fr; } }
.hp-service-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 16px; padding: 24px 20px;
    transition: all 0.25s; cursor: default;
}
.hp-service-card:hover {
    border-color: rgba(201,168,76,0.4);
    background: rgba(201,168,76,0.04);
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}
.hp-svc-icon { font-size: 2rem; margin-bottom: 14px; }
.hp-svc-title { font-size: 0.92rem; font-weight: 700; color: var(--text-1); margin-bottom: 8px; }
.hp-svc-desc  { font-size: 0.8rem; color: var(--text-3); line-height: 1.6; }

/* ── Homepage: process steps ─────────────────────────────────────── */
.hp-steps { display: flex; gap: 0; margin-top: 40px; flex-wrap: wrap; }
.hp-step { flex: 1; min-width: 180px; padding: 0 24px 0 0; position: relative; }
.hp-step:not(:last-child)::after {
    content: '→'; position: absolute; right: 0; top: 8px;
    color: var(--text-3); font-size: 1.2rem;
}
.hp-step-num {
    width: 36px; height: 36px; border-radius: 50%;
    background: rgba(201,168,76,0.12); border: 1px solid rgba(201,168,76,0.3);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem; font-weight: 700; color: var(--gold-2);
    margin-bottom: 14px;
}
.hp-step-title { font-size: 0.9rem; font-weight: 700; color: var(--text-1); margin-bottom: 6px; }
.hp-step-desc  { font-size: 0.8rem; color: var(--text-3); line-height: 1.6; }

/* ── Homepage: CTA section ───────────────────────────────────────── */
.hp-cta-section {
    background: linear-gradient(135deg, rgba(201,168,76,0.07), rgba(201,168,76,0.02));
    border: 1px solid rgba(201,168,76,0.18); border-radius: 24px;
    padding: 56px 48px; text-align: center; margin-top: 0;
}
.hp-cta-title { font-size: 2rem; font-weight: 800; color: var(--text-1); letter-spacing: -0.03em; margin-bottom: 12px; }
.hp-cta-sub   { font-size: 1rem; color: var(--text-2); line-height: 1.6; max-width: 480px; margin: 0 auto 36px; }

/* ── Homepage: testimonials ──────────────────────────────────────── */
.hp-testimonials { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin-top: 40px; }
@media (max-width: 768px) { .hp-testimonials { grid-template-columns: 1fr; } }
.hp-testi-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 16px; padding: 24px 22px;
}
.hp-testi-stars { color: var(--gold-2); font-size: 0.9rem; margin-bottom: 12px; }
.hp-testi-text  { font-size: 0.87rem; color: var(--text-2); line-height: 1.7; margin-bottom: 16px; font-style: italic; }
.hp-testi-author { font-size: 0.8rem; font-weight: 700; color: var(--text-1); }
.hp-testi-role   { font-size: 0.75rem; color: var(--text-3); }

/* ── Chart section wrapper ───────────────────────────────────────── */
.hp-chart-wrap {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 16px; padding: 20px 16px 8px;
}
.hp-chart-title { font-size: 0.88rem; font-weight: 700; color: var(--text-1); margin-bottom: 4px; }
.hp-chart-sub   { font-size: 0.75rem; color: var(--text-3); margin-bottom: 12px; }

/* ── Call UI centering (inside wide layout) ─────────────────────── */
.call-page-wrap { max-width: 680px; margin: 0 auto; padding: 0 20px; }

/* ── Ambient glow background ─────────────────────────────────────── */
.stApp::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(ellipse 80% 40% at 50% -5%, rgba(201,168,76,0.07) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 85% 100%, rgba(201,168,76,0.04) 0%, transparent 60%);
}

/* ── Landing screen ──────────────────────────────────────────────── */
.lp-wrap {
    display: flex; flex-direction: column;
    align-items: center; text-align: center;
    padding: 56px 0 16px;
}
.lp-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(201,168,76,0.10);
    border: 1px solid rgba(201,168,76,0.28);
    border-radius: 100px; padding: 5px 16px;
    font-size: 0.75rem; font-weight: 600;
    color: var(--gold-2); letter-spacing: 0.06em;
    text-transform: uppercase; margin-bottom: 28px;
}
.lp-badge-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--gold-1); animation: gold-blink 2s infinite;
}
@keyframes gold-blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }

.lp-title {
    font-size: 2.4rem; font-weight: 800; line-height: 1.15;
    color: var(--text-1); letter-spacing: -0.03em;
    margin-bottom: 14px;
}
.lp-title span {
    background: linear-gradient(135deg, var(--gold-1), var(--gold-2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.lp-sub {
    font-size: 1rem; color: var(--text-2); line-height: 1.65;
    max-width: 400px; margin-bottom: 36px; font-weight: 400;
}

/* ── Stat strip ──────────────────────────────────────────────────── */
.stat-strip {
    display: flex; gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: 16px; overflow: hidden;
    width: 100%; max-width: 440px;
    margin-bottom: 40px;
}
.stat-cell {
    flex: 1; background: var(--bg-card);
    padding: 14px 10px; text-align: center;
}
.stat-val {
    font-size: 1.15rem; font-weight: 700;
    color: var(--gold-2); margin-bottom: 2px;
}
.stat-lbl { font-size: 0.72rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }

/* ── Disclaimer box ──────────────────────────────────────────────── */
.disclaimer-box {
    background: rgba(201,168,76,0.05);
    border: 1px solid rgba(201,168,76,0.18);
    border-radius: 12px; padding: 14px 20px;
    font-size: 0.8rem; color: var(--text-2);
    max-width: 440px; text-align: left;
    margin-bottom: 32px; line-height: 1.65;
}
.disclaimer-box strong { color: var(--gold-2); }

/* ── Caller / active call ────────────────────────────────────────── */
.call-wrap {
    display: flex; flex-direction: column;
    align-items: center; padding: 48px 0 16px;
    text-align: center;
}

/* Outer ring — changes per state */
.ring-outer {
    width: 168px; height: 168px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 28px; position: relative;
}
.ring-outer.idle {
    background: var(--bg-card);
    box-shadow: 0 0 0 1px var(--border);
}
.ring-outer.speaking {
    background: linear-gradient(145deg, #1a1408, #120e04);
    box-shadow:
        0 0 0 2px var(--gold-1),
        0 0 0 14px var(--gold-glow),
        0 0 0 30px rgba(201,168,76,0.06),
        0 0 60px 0px rgba(201,168,76,0.12);
    animation: gold-pulse 1.6s ease-in-out infinite;
}
.ring-outer.listening {
    background: linear-gradient(145deg, #071a10, #051408);
    box-shadow:
        0 0 0 2px #22c55e,
        0 0 0 14px rgba(34,197,94,0.14),
        0 0 0 30px rgba(34,197,94,0.05);
    animation: green-pulse 2s ease-in-out infinite;
}
@keyframes gold-pulse {
    0%,100% { box-shadow: 0 0 0 2px var(--gold-1), 0 0 0 14px var(--gold-glow), 0 0 0 30px rgba(201,168,76,0.06), 0 0 60px 0 rgba(201,168,76,0.12); }
    50%      { box-shadow: 0 0 0 2px var(--gold-2), 0 0 0 22px rgba(201,168,76,0.26), 0 0 0 44px rgba(201,168,76,0.09), 0 0 80px 0 rgba(201,168,76,0.18); }
}
@keyframes green-pulse {
    0%,100% { box-shadow: 0 0 0 2px #22c55e, 0 0 0 14px rgba(34,197,94,0.14), 0 0 0 30px rgba(34,197,94,0.05); }
    50%      { box-shadow: 0 0 0 2px #4ade80, 0 0 0 22px rgba(34,197,94,0.22), 0 0 0 44px rgba(34,197,94,0.08); }
}

.caller-avatar {
    width: 128px; height: 128px; border-radius: 50%;
    background: linear-gradient(145deg, #1e1608, #120e04);
    border: 1.5px solid rgba(201,168,76,0.30);
    display: flex; align-items: center; justify-content: center;
    font-size: 58px;
    box-shadow: inset 0 1px 0 rgba(201,168,76,0.15);
}

.caller-name {
    font-size: 1.35rem; font-weight: 700;
    color: var(--text-1); margin-bottom: 4px;
    letter-spacing: -0.02em;
}
.caller-firm {
    font-size: 0.82rem; color: var(--gold-dim);
    letter-spacing: 0.08em; text-transform: uppercase;
    font-weight: 500; margin-bottom: 28px;
}

/* ── Status pill ─────────────────────────────────────────────────── */
.status-pill {
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--bg-glass);
    border: 1px solid var(--border);
    border-radius: 100px; padding: 7px 20px;
    font-size: 0.82rem; color: var(--text-2);
    margin-bottom: 32px; letter-spacing: 0.02em;
}
.s-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.s-dot.gold  { background: var(--gold-1); animation: gold-blink 0.9s infinite; }
.s-dot.green { background: var(--green);  animation: gold-blink 1.4s infinite; }
.s-dot.dim   { background: var(--text-3); }

/* ── Agent caption ───────────────────────────────────────────────── */
.agent-caption {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px; padding: 16px 22px;
    font-size: 0.9rem; color: var(--text-2);
    text-align: center; max-width: 500px;
    line-height: 1.7; margin-bottom: 28px;
    min-height: 50px; font-style: italic;
}

/* ── Backend status line ─────────────────────────────────────────── */
.backend-status {
    font-size: 0.78rem; color: var(--gold-1);
    text-align: center; letter-spacing: 0.04em;
    min-height: 18px; margin-top: -18px; margin-bottom: 18px;
    font-style: italic; opacity: 0.85;
}
/* ── Live VAD status (JS-updated, real-time) ─────────────────────── */
.vad-live-status {
    font-size: 0.85rem; font-weight: 600; letter-spacing: 0.04em;
    text-align: center; min-height: 24px; margin-bottom: 10px;
    padding: 5px 18px; border-radius: 100px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--text-2); display: inline-block;
    transition: color 0.3s, background 0.3s, border-color 0.3s;
}
.vad-live-wrap { text-align: center; margin-bottom: 10px; min-height: 36px; }

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--gold-1), #A8873A) !important;
    color: #0A0C14 !important;
    border: none !important;
    border-radius: 100px !important;
    font-weight: 700 !important; font-size: 0.95rem !important;
    padding: 13px 44px !important; letter-spacing: 0.02em !important;
    box-shadow: 0 4px 24px rgba(201,168,76,0.35) !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--gold-2), var(--gold-1)) !important;
    box-shadow: 0 6px 32px rgba(201,168,76,0.50) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: var(--text-3) !important;
    border: 1px solid var(--border) !important;
    border-radius: 100px !important;
    font-weight: 500 !important; font-size: 0.85rem !important;
    padding: 9px 28px !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: rgba(239,68,68,0.40) !important;
    color: #fca5a5 !important;
}

/* ── Audio input (off-screen, JS-controlled) ─────────────────────── */
[data-testid="stAudioInput"] {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    pointer-events: none !important;
}

/* ── Booking confirmed card ──────────────────────────────────────── */
.booking-success {
    background: linear-gradient(145deg, #0D1008, #0A0C06);
    border: 1px solid rgba(201,168,76,0.30);
    border-radius: 20px; padding: 32px 28px;
    text-align: center; max-width: 480px;
    margin: 0 auto 24px;
    box-shadow: 0 0 0 1px rgba(201,168,76,0.08), 0 20px 60px rgba(0,0,0,0.5);
}
.booking-success-icon { font-size: 2.8rem; margin-bottom: 10px; }
.booking-success-title {
    font-size: 1.2rem; font-weight: 700;
    color: var(--gold-2); margin-bottom: 4px; letter-spacing: -0.02em;
}
.booking-code-badge {
    display: inline-block;
    background: rgba(201,168,76,0.10);
    border: 1px solid rgba(201,168,76,0.35);
    border-radius: 8px; padding: 7px 22px;
    font-size: 1.4rem; font-weight: 800;
    color: var(--gold-2); letter-spacing: 4px;
    margin: 12px 0 14px; font-variant-numeric: tabular-nums;
}
.booking-link {
    background: var(--bg-glass);
    border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 16px;
    font-size: 0.82rem; color: var(--text-2);
    word-break: break-all; margin-top: 10px; line-height: 1.6;
}
.booking-link a { color: var(--gold-dim); font-weight: 600; }

/* ── MCP metrics ─────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important; padding: 14px !important;
}
[data-testid="stMetricLabel"] p { color: var(--text-3) !important; font-size: 0.78rem !important; }
[data-testid="stMetricValue"] div { color: var(--text-1) !important; font-size: 1.1rem !important; }

/* ── Language toggle ─────────────────────────────────────────────── */
[data-testid="stRadio"] > div { flex-direction: row !important; }
[data-testid="stRadio"] label { color: var(--text-3) !important; font-size: 0.82rem !important; }
[data-testid="stRadio"] label[data-checked="true"] { color: var(--gold-2) !important; }

/* ── Global text overrides ───────────────────────────────────────── */
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
.stSpinner > div { color: var(--gold-dim) !important; }
[data-testid="stButton"] button { font-family: 'Inter', sans-serif !important; }
[data-testid="stWarning"], [data-testid="stInfo"] {
    background: rgba(201,168,76,0.06) !important;
    border: 1px solid rgba(201,168,76,0.20) !important;
    border-radius: 10px !important;
}

/* ── Divider line ────────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 24px 0 !important; }
</style>
""", unsafe_allow_html=True)


# ── Audio helpers ──────────────────────────────────────────────────────────

def _stt(audio_bytes: bytes, language: str = "en-IN") -> str:
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            return ""
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        wl = {"en-IN": "en", "hi-IN": "hi"}.get(language, "en")
        try:
            with open(tmp, "rb") as af:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3", file=("audio.wav", af, "audio/wav"),
                    response_format="text", language=wl,
                )
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return str(result).strip()
    except Exception:
        return ""


def _tts(text: str, language: str = "en-IN") -> bytes | None:
    os.environ["TTS_LANGUAGE"] = language
    try:
        from src.voice.tts_engine import TTSEngine
        r = TTSEngine().synthesise(text, language=language)
        if not r.is_empty:
            return r.audio_bytes
    except Exception:
        pass
    try:
        import io as _io
        from gtts import gTTS
        buf = _io.BytesIO()
        gTTS(text=text, lang="hi" if language == "hi-IN" else "en",
             tld="co.in" if language == "en-IN" else "com", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def _start_listen_js(turn_id: str):
    """Inject VAD + mic-start only (no audio). Used when TTS fails."""
    components.html(f"""
    <script>
    (function() {{
        var TURN = '{turn_id}_listen';
        var pdoc = window.parent.document;
        if (window.parent.__vadTurn === TURN) return;
        window.parent.__vadTurn = TURN;
        if (typeof window.parent.__vadStop === 'function') {{ window.parent.__vadStop(); }}

        // ── Simple fixed-threshold VAD ──────────────────────────────────────
        var ONSET_LEVEL   = 18;    // RMS level to declare speech started
        var SILENCE_LEVEL = 12;    // RMS level below which = silence
        var MIN_SPEECH_MS = 200;   // ignore blips shorter than this
        var SILENCE_MS    = 2000;  // 2s quiet after speech → stop
        var NO_INPUT_MS   = 10000; // give up if user never speaks

        var vadStream = null, audioCtx = null, noInputTimer = null, checkRAF = null;
        var micStarted = false;

        function setStatus(msg, color) {{
            var el = pdoc.getElementById('vad-live-status');
            if (!el) return;
            el.textContent = msg;
            el.style.color = color || '';
            el.style.borderColor = color ? color.replace('1)', '0.35)') : '';
        }}

        function getRecordBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Record"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var fb = inp.querySelector('button'); if (fb) return fb; }}
            console.warn('VAD: Record button not found — available buttons:', pdoc.querySelectorAll('button').length);
            return null;
        }}
        function getStopBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var btns = inp.querySelectorAll('button'); if (btns.length > 1) return btns[btns.length-1]; if (btns.length === 1) return btns[0]; }}
            return null;
        }}
        function stop() {{
            clearTimeout(noInputTimer);
            if (checkRAF) {{ cancelAnimationFrame(checkRAF); checkRAF = null; }}
            if (vadStream) {{ vadStream.getTracks().forEach(function(t){{ t.stop(); }}); vadStream = null; }}
            if (audioCtx) {{ try{{ audioCtx.close(); }}catch(e){{}} audioCtx = null; }}
            window.parent.__vadStop = null;
            if (micStarted) {{
                setStatus('Processing your response…', 'rgba(201,168,76,1)');
                var btn = getStopBtn(); if (btn) btn.click(); micStarted = false;
            }}
        }}
        window.parent.__vadStop = stop;

        function rms(data) {{
            var s = 0;
            for (var i = 0; i < data.length; i++) s += data[i] * data[i];
            return Math.sqrt(s / data.length);
        }}

        function runVADOnStream(stream) {{
            vadStream = stream;
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            var analyser = audioCtx.createAnalyser();
            analyser.fftSize = 512;
            audioCtx.createMediaStreamSource(stream).connect(analyser);
            var data = new Uint8Array(analyser.frequencyBinCount);

            // ── Phase 1: calibrate background noise for 1.5 s ──────────────
            var CALIB_MS = 1500;
            var calibSamples = [], calibDone = false;
            var onsetLevel = ONSET_LEVEL, silenceLevel = SILENCE_LEVEL;

            setStatus('📡 Calibrating mic…', 'rgba(201,168,76,0.7)');

            function calibrate() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                calibSamples.push(rms(data));
                if (Date.now() - calibStart < CALIB_MS) {{
                    checkRAF = requestAnimationFrame(calibrate);
                }} else {{
                    // Compute ambient RMS (median of samples)
                    calibSamples.sort(function(a,b){{return a-b;}});
                    var ambient = calibSamples[Math.floor(calibSamples.length / 2)];
                    onsetLevel   = Math.max(ONSET_LEVEL,   ambient * 3.0);
                    silenceLevel = Math.max(SILENCE_LEVEL, ambient * 1.8);
                    console.log('VAD: ambient=' + ambient.toFixed(1) + ' onset=' + onsetLevel.toFixed(1) + ' silence=' + silenceLevel.toFixed(1));
                    calibDone = true;
                    setStatus('🎙 Listening — speak now', 'rgba(34,197,94,1)');
                    noInputTimer = setTimeout(function() {{
                        if (!hasSpeech) {{ setStatus('No speech detected, retrying…', 'rgba(239,68,68,1)'); stop(); }}
                    }}, NO_INPUT_MS);
                    checkRAF = requestAnimationFrame(check);
                }}
            }}

            // ── Phase 2: actual VAD ─────────────────────────────────────────
            var hasSpeech = false, speechStart = null, silenceStart = null;

            function check() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                var level = rms(data);

                if (!hasSpeech) {{
                    if (level > onsetLevel) {{
                        if (!speechStart) speechStart = Date.now();
                        else if (Date.now() - speechStart >= MIN_SPEECH_MS) {{
                            hasSpeech = true;
                            silenceStart = null;
                            setStatus('🗣 User speaking…', 'rgba(34,197,94,1)');
                            clearTimeout(noInputTimer);
                        }}
                    }} else {{
                        speechStart = null;
                    }}
                }} else {{
                    if (level < silenceLevel) {{
                        if (!silenceStart) {{ silenceStart = Date.now(); setStatus('🗣 User speaking… (paused)', 'rgba(201,168,76,1)'); }}
                        else if (Date.now() - silenceStart > SILENCE_MS) {{ stop(); return; }}
                    }} else {{
                        silenceStart = null;
                        setStatus('🗣 User speaking…', 'rgba(34,197,94,1)');
                    }}
                }}
                checkRAF = requestAnimationFrame(check);
            }}

            var calibStart = Date.now();
            checkRAF = requestAnimationFrame(calibrate);
        }}

        var _micRetries = 0;
        function startMic() {{
            var btn = getRecordBtn();
            if (!btn) {{
                if (_micRetries === 0) {{ setStatus('⏳ Waiting for mic…', ''); console.warn('VAD: Record btn not found, retrying...'); }}
                if (++_micRetries < 50) {{ setTimeout(startMic, 150); return; }}
                setStatus('❌ Mic unavailable', 'rgba(239,68,68,1)');
                console.error('VAD: gave up finding Record button after 50 retries');
                return;
            }}
            console.log('VAD[listen]: clicking Record btn, aria-label=' + (btn.getAttribute('aria-label') || 'none'));
            setStatus('🎙 Mic starting…', 'rgba(34,197,94,0.7)');
            micStarted = true;
            btn.click();
            navigator.mediaDevices.getUserMedia({{ audio: true, video: false }})
            .then(function(stream) {{ console.log('VAD[listen]: getUserMedia OK'); runVADOnStream(stream); }})
            .catch(function(e){{ setStatus('❌ Mic permission denied', 'rgba(239,68,68,1)'); console.warn('VAD mic error:', e); }});
        }}
        startMic();
    }})();
    </script>
    """, height=0)


def _play_and_listen_js(audio_bytes: bytes, turn_id: str):
    """
    Play TTS audio via browser Audio API (no st.audio widget, no downloads),
    kill any previous VAD, then auto-start mic + fresh VAD.
    """
    import base64
    b64  = base64.b64encode(audio_bytes).decode()
    fmt  = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"

    components.html(f"""
    <script>
    (function() {{
        var TURN = '{turn_id}';
        var pdoc = window.parent.document;

        // Guard: skip if this exact turn already ran (Streamlit sometimes re-runs)
        if (window.parent.__vadTurn === TURN) return;
        window.parent.__vadTurn = TURN;

        // Kill any VAD from a previous turn's iframe
        if (typeof window.parent.__vadStop === 'function') {{ window.parent.__vadStop(); }}

        // ── Speech-band VAD (same parameters as listen-only VAD)
        // ── Simple fixed-threshold VAD ──────────────────────────────────────
        var ONSET_LEVEL   = 18;    // RMS level to declare speech started
        var SILENCE_LEVEL = 12;    // RMS level below which = silence
        var MIN_SPEECH_MS = 200;   // ignore blips shorter than this
        var SILENCE_MS    = 2000;  // 2s quiet after speech → stop
        var NO_INPUT_MS   = 10000; // give up if user never speaks

        var vadStream = null, audioCtx = null;
        var noInputTimer = null, checkRAF = null;
        var micStarted = false;

        function setStatus(msg, color) {{
            var el = pdoc.getElementById('vad-live-status');
            if (!el) return;
            el.textContent = msg;
            el.style.color = color || '';
            el.style.borderColor = color ? color.replace('1)', '0.35)') : '';
        }}

        function getRecordBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Record"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var fb = inp.querySelector('button'); if (fb) return fb; }}
            console.warn('VAD: Record button not found — buttons in doc:', pdoc.querySelectorAll('button').length);
            return null;
        }}
        function getStopBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var btns = inp.querySelectorAll('button'); if (btns.length > 1) return btns[btns.length-1]; if (btns.length === 1) return btns[0]; }}
            return null;
        }}

        function stopRecordingAndVAD() {{
            clearTimeout(noInputTimer);
            if (checkRAF) {{ cancelAnimationFrame(checkRAF); checkRAF = null; }}
            if (vadStream) {{ vadStream.getTracks().forEach(function(t){{ t.stop(); }}); vadStream = null; }}
            if (audioCtx)  {{ try {{ audioCtx.close(); }} catch(e) {{}} audioCtx = null; }}
            window.parent.__vadStop = null;
            if (micStarted) {{
                micStarted = false;
                setStatus('Processing your response…', 'rgba(201,168,76,1)');
                var btn = getStopBtn();
                if (btn) btn.click();
            }}
        }}

        window.parent.__vadStop = stopRecordingAndVAD;

        function rms(data) {{
            var s = 0;
            for (var i = 0; i < data.length; i++) s += data[i] * data[i];
            return Math.sqrt(s / data.length);
        }}

        function runVADOnStream(stream) {{
            vadStream = stream;
            audioCtx  = new (window.AudioContext || window.webkitAudioContext)();
            var analyser = audioCtx.createAnalyser();
            analyser.fftSize = 512;
            audioCtx.createMediaStreamSource(stream).connect(analyser);
            var data = new Uint8Array(analyser.frequencyBinCount);

            // ── Phase 1: calibrate background noise for 1.5 s ──────────────
            var CALIB_MS = 1500;
            var calibSamples = [];
            var onsetLevel = ONSET_LEVEL, silenceLevel = SILENCE_LEVEL;

            setStatus('📡 Calibrating mic…', 'rgba(201,168,76,0.7)');

            function calibrate() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                calibSamples.push(rms(data));
                if (Date.now() - calibStart < CALIB_MS) {{
                    checkRAF = requestAnimationFrame(calibrate);
                }} else {{
                    calibSamples.sort(function(a,b){{return a-b;}});
                    var ambient = calibSamples[Math.floor(calibSamples.length / 2)];
                    onsetLevel   = Math.max(ONSET_LEVEL,   ambient * 3.0);
                    silenceLevel = Math.max(SILENCE_LEVEL, ambient * 1.8);
                    console.log('VAD[play]: ambient=' + ambient.toFixed(1) + ' onset=' + onsetLevel.toFixed(1) + ' silence=' + silenceLevel.toFixed(1));
                    setStatus('🎙 Listening — speak now', 'rgba(34,197,94,1)');
                    noInputTimer = setTimeout(function() {{
                        if (!hasSpeech) {{ setStatus('No speech detected, retrying…', 'rgba(239,68,68,1)'); stopRecordingAndVAD(); }}
                    }}, NO_INPUT_MS);
                    checkRAF = requestAnimationFrame(check);
                }}
            }}

            // ── Phase 2: actual VAD ─────────────────────────────────────────
            var hasSpeech = false, speechStart = null, silenceStart = null;

            function check() {{
                if (!vadStream) return;
                analyser.getByteTimeDomainData(data);
                var level = rms(data);

                if (!hasSpeech) {{
                    if (level > onsetLevel) {{
                        if (!speechStart) speechStart = Date.now();
                        else if (Date.now() - speechStart >= MIN_SPEECH_MS) {{
                            hasSpeech = true;
                            silenceStart = null;
                            setStatus('🗣 User speaking…', 'rgba(34,197,94,1)');
                            clearTimeout(noInputTimer);
                        }}
                    }} else {{
                        speechStart = null;
                    }}
                }} else {{
                    if (level < silenceLevel) {{
                        if (!silenceStart) {{ silenceStart = Date.now(); setStatus('🗣 User speaking… (paused)', 'rgba(201,168,76,1)'); }}
                        else if (Date.now() - silenceStart > SILENCE_MS) {{ stopRecordingAndVAD(); return; }}
                    }} else {{
                        silenceStart = null;
                        setStatus('🗣 User speaking…', 'rgba(34,197,94,1)');
                    }}
                }}
                checkRAF = requestAnimationFrame(check);
            }}

            var calibStart = Date.now();
            checkRAF = requestAnimationFrame(calibrate);
        }}

        var _micRetries = 0;
        function startMicAndVAD() {{
            var btn = getRecordBtn();
            if (!btn) {{
                if (_micRetries === 0) {{ setStatus('⏳ Waiting for mic…', ''); console.warn('VAD[play]: Record btn not found, retrying...'); }}
                if (++_micRetries < 50) {{ setTimeout(startMicAndVAD, 150); return; }}
                setStatus('❌ Mic unavailable — Record button not found', 'rgba(239,68,68,1)');
                console.error('VAD[play]: gave up finding Record button after 50 retries');
                return;
            }}
            console.log('VAD[play]: clicking Record btn, aria-label=' + (btn.getAttribute('aria-label') || 'none') + ' data-testid=' + (btn.getAttribute('data-testid') || 'none'));
            setStatus('🎙 Mic starting…', 'rgba(34,197,94,0.7)');
            micStarted = true;
            btn.click();
            navigator.mediaDevices.getUserMedia({{ audio: true, video: false }})
            .then(function(stream) {{ console.log('VAD[play]: getUserMedia OK'); runVADOnStream(stream); }})
            .catch(function(e) {{ setStatus('❌ Mic permission denied', 'rgba(239,68,68,1)'); console.warn('VAD[play]: getUserMedia error:', e); }});
        }}

        /* ── Decode and play audio ────────────────────────── */
        var b64  = '{b64}';
        var mime = '{fmt}';
        var raw  = atob(b64);
        var buf  = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
        var blob = new Blob([buf], {{ type: mime }});
        var url  = URL.createObjectURL(blob);
        var audio = new Audio(url);
        audio.playbackRate = 1.0;

        setStatus('🔊 Agent speaking…', 'rgba(201,168,76,1)');
        audio.addEventListener('canplaythrough', function() {{ console.log('VAD[play]: audio ready, duration=' + audio.duration + 's'); }}, {{ once: true }});
        audio.addEventListener('ended', function() {{
            console.log('VAD[play]: audio ended, starting mic');
            setStatus('Agent finished — mic starting…', 'rgba(201,168,76,0.6)');
            URL.revokeObjectURL(url);
            setTimeout(startMicAndVAD, 50);
        }}, {{ once: true }});

        console.log('VAD[play]: calling audio.play(), turn=' + TURN);
        audio.play().catch(function(e) {{
            console.warn('VAD: autoplay blocked:', e);
            setStatus('⚠ Audio blocked by browser — speak now', 'rgba(239,68,68,1)');
            URL.revokeObjectURL(url);
            startMicAndVAD();
        }});
    }})();
    </script>
    """, height=0)


# ── Session state ──────────────────────────────────────────────────────────

def _init_state():
    for k, v in {
        "p5_started": False,
        "p5_ctx": None,
        "p5_fsm": None,
        "p5_mcp": None,
        "p5_lang": "en-IN",
        "p5_agent_speech": "",   # last agent utterance (shown as caption)
        "_tts_hash": "",
        "_tts_audio": None,
        "_tts_played": "",
        "_last_audio_hash": "",
        "_backend_status": "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Waitlist Contact Form (secure URL landing page for waitlist) ────────────
_waitlist_token = st.query_params.get("waitlist_token", "")
# Also handle booking_token that starts with NL-W (waitlist codes reuse booking_token param)
_raw_token = st.query_params.get("booking_token", "")
# Detect if this booking_token is actually a waitlist entry
_is_waitlist_token = False
if _raw_token:
    try:
        sys.path.insert(0, str(_root_dir / "phase1"))
        from src.booking.secure_url_generator import verify_secure_url as _vsu
        _tok_payload = _vsu(_raw_token)
        if _tok_payload.get("booking_code", "").startswith("NL-W"):
            _is_waitlist_token = True
            _waitlist_token = _raw_token
    except Exception:
        pass

if _waitlist_token and _is_waitlist_token:
    sys.path.insert(0, str(_root_dir / "phase1"))
    sys.path.insert(0, str(_root_dir / "phase4"))

    _wl_done  = f"wl_done_{_waitlist_token[:12]}"
    _wl_name  = f"wl_name_{_waitlist_token[:12]}"
    _wl_email = f"wl_email_{_waitlist_token[:12]}"
    _wl_err   = f"wl_err_{_waitlist_token[:12]}"

    try:
        from src.booking.secure_url_generator import verify_secure_url
        from src.dialogue.states import TOPIC_LABELS
        _wl_payload   = verify_secure_url(_waitlist_token)
        _wl_code      = _wl_payload.get("booking_code", "")
        _wl_topic_key = _wl_payload.get("topic", "")
        _wl_pref      = _wl_payload.get("slot_ist", "")
        _wl_topic_lbl = TOPIC_LABELS.get(_wl_topic_key, _wl_topic_key.replace("_", " ").title())

        if st.session_state.get(_wl_done):
            st.markdown(f"""
            <div style="max-width:480px;margin:60px auto;background:#0a0c14;border:1px solid rgba(34,197,94,0.3);
                 border-radius:20px;padding:36px;text-align:center;color:#f5f0e8;">
              <div style="font-size:3rem;margin-bottom:12px;">✅</div>
              <div style="font-size:1.2rem;font-weight:700;color:#4ade80;margin-bottom:8px;">You're on the list!</div>
              <div style="color:#9a9080;font-size:0.9rem;line-height:1.6;">
                We'll email <strong style="color:#f5f0e8;">{st.session_state.get(_wl_email,'')}</strong>
                the moment a <strong style="color:#c9a84c;">{_wl_topic_lbl}</strong> slot opens.<br><br>
                Your waitlist code: <strong style="color:#c9a84c;">{_wl_code}</strong>
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="max-width:480px;margin:60px auto;background:#10131f;border:1px solid rgba(201,168,76,0.25);
                 border-radius:20px;padding:36px;color:#f5f0e8;">
              <div style="text-align:center;margin-bottom:24px;">
                <div style="font-size:2.5rem;margin-bottom:8px;">📋</div>
                <div style="font-size:1.3rem;font-weight:700;color:#e8c96d;">Join the Waitlist</div>
                <div style="color:#9a9080;font-size:0.88rem;margin-top:6px;">
                  We'll email you when a <strong style="color:#c9a84c;">{_wl_topic_lbl}</strong>
                  slot matching <em>{_wl_pref}</em> opens up.
                </div>
              </div>
              <div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.2);
                   border-radius:10px;padding:12px 16px;margin-bottom:20px;font-size:0.85rem;color:#9a9080;">
                Waitlist Code: <strong style="color:#e8c96d;letter-spacing:2px;">{_wl_code}</strong>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.get(_wl_err):
                for e in st.session_state[_wl_err]:
                    st.error(e)
                st.session_state[_wl_err] = []

            with st.form("waitlist_contact_form", clear_on_submit=False):
                _wn = st.text_input("Full Name", placeholder="e.g. Rahul Sharma")
                _we = st.text_input("Email Address", placeholder="you@example.com")
                _wc = st.checkbox("I agree to receive an email notification when a slot opens.")
                _ws = st.form_submit_button("Save My Details", type="primary", use_container_width=True)

            if _ws:
                _errs = []
                if not _wn.strip():
                    _errs.append("Name is required.")
                if not _we.strip() or "@" not in _we:
                    _errs.append("Enter a valid email address.")
                if not _wc:
                    _errs.append("Please tick the consent checkbox.")
                if _errs:
                    st.session_state[_wl_err] = _errs
                    st.rerun()
                else:
                    try:
                        from src.booking.waitlist_queue import get_global_queue
                        _q = get_global_queue()
                        _q.update_email(_wl_code, _wn.strip(), _we.strip())
                        st.session_state[_wl_done]  = True
                        st.session_state[_wl_name]  = _wn.strip()
                        st.session_state[_wl_email] = _we.strip()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save details: {exc}")
    except Exception:
        st.markdown("""
        <div style="max-width:480px;margin:60px auto;background:#10131f;border:1px solid rgba(239,68,68,0.3);
             border-radius:20px;padding:36px;text-align:center;color:#f5f0e8;">
          <div style="font-size:3rem;margin-bottom:12px;">⏰</div>
          <div style="font-size:1.1rem;font-weight:700;color:#ef4444;margin-bottom:8px;">Link Expired</div>
          <div style="color:#9a9080;font-size:0.9rem;">This waitlist link has expired. Please call us again.</div>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


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
    .cf-success { text-align:center; padding: 12px 0 4px; }
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

    _sk_done  = f"cf_done_{_booking_token[:12]}"
    _sk_name  = f"cf_name_{_booking_token[:12]}"
    _sk_email = f"cf_email_{_booking_token[:12]}"
    _sk_phone = f"cf_phone_{_booking_token[:12]}"
    _sk_err   = f"cf_err_{_booking_token[:12]}"

    st.markdown("""
    <div class="cf-topbar">
      <div class="cf-logo">📈</div>
      <div>
        <div class="cf-brand">Dalal Street Advisors</div>
        <div class="cf-sub">SEBI Registered · IA-0000347</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, fc, _ = st.columns([1, 5, 1])
    with fc:
        try:
            from src.booking.secure_url_generator import verify_secure_url
            from src.dialogue.states import TOPIC_LABELS
            payload      = verify_secure_url(_booking_token)
            booking_code = payload.get("booking_code", "")
            topic_key    = payload.get("topic", "")
            slot_ist     = payload.get("slot_ist", "")
            topic_label  = TOPIC_LABELS.get(topic_key, topic_key.replace("_", " ").title())

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
            else:
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
                        "Send Confirmation Email", type="primary", use_container_width=True,
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
                                    to_name=name.strip(), to_email=email.strip(),
                                    booking_code=booking_code, topic_label=topic_label,
                                    slot_ist=slot_ist,
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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN VOICE AGENT UI
# ═══════════════════════════════════════════════════════════════════════════

_lang = st.session_state.p5_lang
os.environ["TTS_LANGUAGE"] = _lang
os.environ["STT_LANGUAGE"] = _lang

# Language is set by the homepage radio and persists in session_state.p5_lang
_lang = st.session_state.p5_lang
os.environ["TTS_LANGUAGE"] = _lang

# ── Process user turn ──────────────────────────────────────────────────────
def _process(user_text: str):
    from src.dialogue.intent_router import IntentRouter
    fsm = st.session_state.p5_fsm
    ctx = st.session_state.p5_ctx
    try:
        st.session_state["_backend_status"] = "Understanding intent…"
        llm_resp = IntentRouter().route(user_text, ctx)
    except Exception as exc:
        st.error(f"Routing error: {exc}")
        return
    st.session_state["_backend_status"] = "Processing…"
    ctx, speech = fsm.process_turn(ctx, user_text, llm_resp)
    # MCP dispatch is handled inside fsm.process_turn — do NOT call it again here
    st.session_state.p5_ctx = ctx
    # Guard: if FSM returns empty speech the UI gets stuck (no TTS → no mic).
    # Fall back to a gentle re-prompt so the call stays alive.
    if not speech:
        speech = ("I didn't catch that — could you say that again?"
                  if _lang == "en-IN"
                  else "मुझे सुनाई नहीं दिया — क्या आप दोबारा कह सकते हैं?")
    st.session_state.p5_agent_speech = speech
    # Use a unique reset token so _play_and_listen_js always fires after _process(),
    # even if speech text and turn_count are identical to the previous turn.
    import time as _t
    st.session_state["_tts_played"] = f"_reset_{_t.time()}"


# ── PRE-CALL LANDING / HOMEPAGE ────────────────────────────────────────────
if not st.session_state.p5_started:
    import plotly.graph_objects as go

    _hi = _lang == "hi-IN"

    # ── Site Header ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="dsa-header">
      <div class="dsa-logo-wrap">
        <div class="dsa-logo-icon">📈</div>
        <div>
          <div class="dsa-logo-text">Dalal Street Advisors</div>
          <div class="dsa-logo-sub">SEBI Registered · IA-0000347</div>
        </div>
      </div>
      <nav class="dsa-nav">
        <a href="#">{"Services" if not _hi else "सेवाएँ"}</a>
        <a href="#">{"About" if not _hi else "हमारे बारे में"}</a>
        <a href="#">{"Research" if not _hi else "रिसर्च"}</a>
        <a href="#">{"Contact" if not _hi else "संपर्क"}</a>
      </nav>
    </div>
    """, unsafe_allow_html=True)

    # ── Language toggle bar (below header) ────────────────────────────────
    st.markdown("""
    <div style="background:rgba(10,12,20,0.85);border-bottom:1px solid rgba(255,255,255,0.05);
         display:flex;justify-content:flex-end;align-items:center;padding:6px 48px;gap:8px;">
      <span style="font-size:0.72rem;color:#6B6358;letter-spacing:0.05em;text-transform:uppercase;">Language</span>
    </div>
    """, unsafe_allow_html=True)
    _lang_col_l, _lang_col_r = st.columns([9, 1])
    with _lang_col_r:
        lang_lbl2 = st.radio("", ["EN", "HI"], horizontal=True,
                              key="p5_lang_radio_home", label_visibility="collapsed")
    st.session_state.p5_lang = "hi-IN" if lang_lbl2 == "HI" else "en-IN"
    _lang = st.session_state.p5_lang
    _hi   = _lang == "hi-IN"

    # ── Hero Section ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hp-hero">
      <div class="hp-hero-badge">
        <span class="lp-badge-dot"></span>
        {"AI-Powered · SEBI Registered · Since 2015" if not _hi else "AI-संचालित · SEBI पंजीकृत · 2015 से"}
      </div>
      <div class="hp-hero-title">
        {"Expert Advisory.<br><span>Smarter Scheduling.</span><br>Just Your Voice." if not _hi
         else "विशेषज्ञ सलाह।<br><span>स्मार्ट शेड्यूलिंग।</span><br>बस आपकी आवाज़।"}
      </div>
      <div class="hp-hero-sub">
        {"Book a 15-minute consultation with SEBI-registered advisors — KYC, SIP, tax docs, withdrawals, or account changes. Our AI agent handles scheduling instantly."
         if not _hi else
         "SEBI-पंजीकृत सलाहकारों के साथ 15 मिनट की परामर्श बुक करें — KYC, SIP, टैक्स, निकासी, या खाता बदलाव। हमारा AI एजेंट तुरंत शेड्यूल करता है।"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Hero CTA button (Streamlit, so it works)
    _hero_l, _hero_c, _hero_r = st.columns([3, 2, 3])
    with _hero_c:
        _btn_lbl = ("🎙  Start Advisor Call" if not _hi else "🎙  कॉल शुरू करें")
        if st.button(_btn_lbl, type="primary", use_container_width=True, key="hero_cta"):
            from src.dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.p5_fsm          = fsm
            st.session_state.p5_ctx          = ctx
            st.session_state.p5_started      = True
            st.session_state.p5_agent_speech = greeting
            st.session_state["_tts_hash"]    = ""
            st.session_state["_tts_played"]  = ""
            st.rerun()

    # ── Stats Strip ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hp-stats">
      <div class="hp-stat">
        <div class="hp-stat-val">₹2,400 Cr</div>
        <div class="hp-stat-lbl">{"Assets Under Advisory" if not _hi else "प्रबंधित संपत्ति"}</div>
      </div>
      <div class="hp-stat">
        <div class="hp-stat-val">14,000+</div>
        <div class="hp-stat-lbl">{"Active Clients" if not _hi else "सक्रिय ग्राहक"}</div>
      </div>
      <div class="hp-stat">
        <div class="hp-stat-val">10 Yrs</div>
        <div class="hp-stat-lbl">{"Market Experience" if not _hi else "बाज़ार अनुभव"}</div>
      </div>
      <div class="hp-stat">
        <div class="hp-stat-val">4.8 ★</div>
        <div class="hp-stat-lbl">{"Client Rating" if not _hi else "ग्राहक रेटिंग"}</div>
      </div>
      <div class="hp-stat">
        <div class="hp-stat-val">98%</div>
        <div class="hp-stat-lbl">{"Satisfaction Rate" if not _hi else "संतुष्टि दर"}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Analytics Section (Charts) ─────────────────────────────────────────
    st.markdown(f"""
    <div class="hp-section">
      <div class="hp-section-tag">{"Performance Analytics" if not _hi else "प्रदर्शन विश्लेषण"}</div>
      <div class="hp-section-title">{"Data-Driven Advisory" if not _hi else "डेटा-आधारित सलाह"}</div>
      <div class="hp-section-sub">
        {"Our advisors are backed by 10 years of market data, delivering consistent returns across all market cycles."
         if not _hi else
         "हमारे सलाहकार 10 वर्षों के बाज़ार डेटा से समर्थित हैं, सभी बाज़ार चक्रों में लगातार रिटर्न देते हैं।"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    _chart_l, _chart_r = st.columns(2, gap="medium")

    with _chart_l:
        st.markdown('<div class="hp-chart-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-title">{"Portfolio Growth Index" if not _hi else "पोर्टफोलियो वृद्धि सूचकांक"}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-sub">{"₹1 Lakh invested in 2015 → ₹4.2 Lakh in 2025" if not _hi else "2015 में ₹1 लाख → 2025 में ₹4.2 लाख"}</div>', unsafe_allow_html=True)

        years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
        dsa   = [100, 118, 142, 133, 157, 148, 195, 178, 224, 276, 342]
        nifty = [100, 104, 128, 115, 130, 122, 168, 150, 194, 230, 272]

        fig_growth = go.Figure()
        fig_growth.add_trace(go.Scatter(
            x=years, y=dsa, name="DSA Model Portfolio",
            line=dict(color="#C9A84C", width=2.5),
            fill="tozeroy", fillcolor="rgba(201,168,76,0.06)",
            mode="lines+markers", marker=dict(size=5, color="#C9A84C"),
        ))
        fig_growth.add_trace(go.Scatter(
            x=years, y=nifty, name="Nifty 50",
            line=dict(color="#6B6358", width=1.5, dash="dot"),
            mode="lines", marker=dict(size=4, color="#6B6358"),
        ))
        fig_growth.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#9A9080", size=11),
            margin=dict(l=0, r=0, t=10, b=0),
            height=240,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=10, color="#9A9080")),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                       zeroline=False, tickfont=dict(size=10),
                       tickformat=".0f", ticksuffix=""),
            hovermode="x unified",
        )
        st.plotly_chart(fig_growth, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with _chart_r:
        st.markdown('<div class="hp-chart-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-title">{"Asset Allocation Strategy" if not _hi else "परिसंपत्ति आवंटन रणनीति"}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-sub">{"Recommended balanced portfolio for moderate risk" if not _hi else "मध्यम जोखिम के लिए अनुशंसित संतुलित पोर्टफोलियो"}</div>', unsafe_allow_html=True)

        alloc_labels = ["Large Cap Equity", "Mid Cap Equity", "Debt & Bonds", "Gold ETF", "Liquid Funds"]
        alloc_values = [35, 25, 25, 10, 5]
        alloc_colors = ["#C9A84C", "#E8C96D", "#4A5568", "#8B7355", "#2D3748"]

        fig_alloc = go.Figure(go.Pie(
            labels=alloc_labels, values=alloc_values,
            hole=0.58,
            marker=dict(colors=alloc_colors, line=dict(color="#10131F", width=2)),
            textfont=dict(size=10, color="#F5F0E8"),
            hovertemplate="%{{label}}<br>%{{value}}%<extra></extra>",
        ))
        fig_alloc.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#9A9080", size=11),
            margin=dict(l=0, r=0, t=10, b=0),
            height=240,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=9, color="#9A9080")),
            showlegend=True,
            annotations=[dict(text="<b>Balanced</b>", x=0.5, y=0.5, font_size=12,
                              font_color="#C9A84C", showarrow=False)],
        )
        st.plotly_chart(fig_alloc, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Second chart row: Sector exposure + Monthly SIP growth ────────────
    _chart2_l, _chart2_r = st.columns(2, gap="medium")

    with _chart2_l:
        st.markdown('<div class="hp-chart-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-title">{"Sector Exposure" if not _hi else "सेक्टर एक्सपोज़र"}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-sub">{"Diversified across 8 key sectors" if not _hi else "8 प्रमुख क्षेत्रों में विविधीकरण"}</div>', unsafe_allow_html=True)

        sectors   = ["Banking", "IT", "FMCG", "Pharma", "Auto", "Infra", "Energy", "Others"]
        exposure  = [22, 18, 14, 12, 11, 9, 8, 6]
        bar_colors = ["#C9A84C" if v == max(exposure) else "#2D3748" for v in exposure]

        fig_sector = go.Figure(go.Bar(
            x=exposure, y=sectors, orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=[f"{v}%" for v in exposure],
            textposition="outside", textfont=dict(size=9, color="#9A9080"),
        ))
        fig_sector.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#9A9080", size=10),
            margin=dict(l=0, r=40, t=10, b=0),
            height=240,
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                       zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
            bargap=0.4,
        )
        st.plotly_chart(fig_sector, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with _chart2_r:
        st.markdown('<div class="hp-chart-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-title">{"₹5,000/mo SIP Growth" if not _hi else "₹5,000/माह SIP वृद्धि"}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hp-chart-sub">{"10-year corpus projection vs fixed deposit" if not _hi else "10 साल का कॉर्पस बनाम FD"}</div>', unsafe_allow_html=True)

        sip_years   = list(range(1, 11))
        sip_invested= [v * 60000 for v in sip_years]
        sip_corpus  = [64000, 131000, 204000, 283000, 370000, 465000, 569000, 683000, 808000, 945000]
        fd_corpus   = [62400, 127300, 195000, 266000, 341000, 419000, 502000, 589000, 681000, 778000]

        fig_sip = go.Figure()
        fig_sip.add_trace(go.Bar(
            x=sip_years, y=sip_corpus, name="SIP Return",
            marker_color="rgba(201,168,76,0.75)",
        ))
        fig_sip.add_trace(go.Bar(
            x=sip_years, y=fd_corpus, name="FD Return",
            marker_color="rgba(75,85,99,0.6)",
        ))
        fig_sip.add_trace(go.Scatter(
            x=sip_years, y=sip_invested, name="Amount Invested",
            line=dict(color="#6B6358", width=1.5, dash="dot"), mode="lines",
        ))
        fig_sip.update_layout(
            barmode="overlay",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#9A9080", size=10),
            margin=dict(l=0, r=0, t=10, b=0),
            height=240,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=9, color="#9A9080")),
            xaxis=dict(showgrid=False, zeroline=False, title="Year",
                       title_font=dict(size=9), tickfont=dict(size=9)),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                       zeroline=False, tickfont=dict(size=9),
                       tickformat=",.0f", tickprefix="₹"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_sip, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Services Section ───────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hp-section">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:16px;">
        <div>
          <div class="hp-section-tag">{"Advisory Services" if not _hi else "सलाहकार सेवाएँ"}</div>
          <div class="hp-section-title">{"What Can We Help You With?" if not _hi else "हम आपकी किसमें सहायता कर सकते हैं?"}</div>
        </div>
        <div class="hp-section-sub" style="max-width:300px;">
          {"Schedule a 15-min call for any of these topics — our AI agent finds the perfect slot instantly."
           if not _hi else
           "इनमें से किसी भी विषय के लिए 15 मिनट की कॉल शेड्यूल करें।"}
        </div>
      </div>

      <div class="hp-services-grid">
        <div class="hp-service-card">
          <div class="hp-svc-icon">🪪</div>
          <div class="hp-svc-title">{"KYC & Onboarding" if not _hi else "KYC और ऑनबोर्डिंग"}</div>
          <div class="hp-svc-desc">{"Identity verification, new account opening, PAN linking, and fund transfer setup." if not _hi else "पहचान सत्यापन, नए खाते की शुरुआत, PAN लिंकिंग।"}</div>
        </div>
        <div class="hp-service-card">
          <div class="hp-svc-icon">📅</div>
          <div class="hp-svc-title">{"SIP & Mandates" if not _hi else "SIP और मैंडेट"}</div>
          <div class="hp-svc-desc">{"Set up or modify systematic investment plans, auto-debit mandates and frequencies." if not _hi else "SIP शुरू करना, बदलाव करना, और ऑटो-डेबिट मैंडेट।"}</div>
        </div>
        <div class="hp-service-card">
          <div class="hp-svc-icon">📄</div>
          <div class="hp-svc-title">{"Statements & Tax" if not _hi else "स्टेटमेंट और टैक्स"}</div>
          <div class="hp-svc-desc">{"Capital gains, Form 26AS, ELSS certificates, CAS reports, visa letters." if not _hi else "कैपिटल गेन, टैक्स दस्तावेज़, CAS रिपोर्ट।"}</div>
        </div>
        <div class="hp-service-card">
          <div class="hp-svc-icon">💸</div>
          <div class="hp-svc-title">{"Withdrawals" if not _hi else "निकासी"}</div>
          <div class="hp-svc-desc">{"Redemption guidance, payout timelines, partial/full exits, and NRI withdrawals." if not _hi else "रिडेम्पशन, पेआउट टाइमलाइन, आंशिक/पूर्ण निकासी।"}</div>
        </div>
        <div class="hp-service-card">
          <div class="hp-svc-icon">🔄</div>
          <div class="hp-svc-title">{"Account Changes" if not _hi else "खाता बदलाव"}</div>
          <div class="hp-svc-desc">{"Nominee updates, address/bank changes, joint account additions, NRI status." if not _hi else "नॉमिनी, पता/बैंक बदलाव, संयुक्त खाता।"}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── How It Works ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:var(--bg-card);border-top:1px solid var(--border);border-bottom:1px solid var(--border);">
    <div class="hp-section">
      <div class="hp-section-tag">{"How It Works" if not _hi else "यह कैसे काम करता है"}</div>
      <div class="hp-section-title">{"Book in 60 Seconds" if not _hi else "60 सेकंड में बुक करें"}</div>
      <div class="hp-steps">
        <div class="hp-step">
          <div class="hp-step-num">1</div>
          <div class="hp-step-title">{"Start the Call" if not _hi else "कॉल शुरू करें"}</div>
          <div class="hp-step-desc">{"Click 'Start Advisor Call' — our AI agent greets you instantly." if not _hi else "कॉल शुरू करें — हमारा AI एजेंट तुरंत उत्तर देता है।"}</div>
        </div>
        <div class="hp-step">
          <div class="hp-step-num">2</div>
          <div class="hp-step-title">{"Say Your Topic" if not _hi else "विषय बताएं"}</div>
          <div class="hp-step-desc">{"Just speak — KYC, SIP, tax docs, or any topic. We understand naturally." if not _hi else "बस बोलें — KYC, SIP, टैक्स। हम समझते हैं।"}</div>
        </div>
        <div class="hp-step">
          <div class="hp-step-num">3</div>
          <div class="hp-step-title">{"Pick a Slot" if not _hi else "स्लॉट चुनें"}</div>
          <div class="hp-step-desc">{"We offer real-time slots from our advisor calendar. Pick what suits you." if not _hi else "हम रियल-टाइम स्लॉट प्रदान करते हैं। अपनी सुविधा अनुसार चुनें।"}</div>
        </div>
        <div class="hp-step">
          <div class="hp-step-num">4</div>
          <div class="hp-step-title">{"Confirmed!" if not _hi else "पुष्टि!"}</div>
          <div class="hp-step-desc">{"Get your booking code instantly. Calendar hold created. Advisor will reach out." if not _hi else "तुरंत बुकिंग कोड मिलता है। सलाहकार संपर्क करेंगे।"}</div>
        </div>
      </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Testimonials ───────────────────────────────────────────────────────
    _t1 = ('AI शेड्यूलिंग बेहतरीन है — एक मिनट में SIP परामर्श बुक हो गई। सलाहकार तैयार थे।'
           if _hi else
           'The AI scheduling is brilliant — booked my SIP consultation in under a minute. The advisor was well-prepared and solved my mandate issue on the same call.')
    _t2 = ('पहली बार किसी ने बिना शब्दजाल के समझाया। KYC के लिए वॉइस एजेंट का उपयोग किया — बेहतरीन अनुभव!'
           if _hi else
           'Finally an advisor who explains things without jargon. Used the voice agent for KYC — seamless, private, and fast. Impressed!')
    _t3 = ('8 साल बाद सलाहकार बदला — सबसे अच्छा निर्णय। कैपिटल गेन कॉल ने ₹2.1 लाख की टैक्स बचत की।'
           if _hi else
           'Switched advisors after 8 years — best decision. The capital gains call saved me ₹2.1 lakh in taxes. Zero PII on the call, very secure.')
    _r1 = 'वरिष्ठ इंजीनियर, पुणे' if _hi else 'Senior Engineer, Pune'
    _r2 = 'उद्यमी, चेन्नई'       if _hi else 'Entrepreneur, Chennai'
    _r3 = 'CFO, मुंबई'            if _hi else 'CFO, Mumbai'
    _testi_tag   = 'ग्राहक अनुभव'         if _hi else 'Client Stories'
    _testi_title = '14,000+ निवेशकों का भरोसा' if _hi else 'Trusted by 14,000+ Investors'

    st.markdown(f"""
    <div class="hp-section">
      <div class="hp-section-tag">{_testi_tag}</div>
      <div class="hp-section-title">{_testi_title}</div>
      <div class="hp-testimonials">
        <div class="hp-testi-card">
          <div class="hp-testi-stars">★★★★★</div>
          <div class="hp-testi-text">&ldquo;{_t1}&rdquo;</div>
          <div class="hp-testi-author">Rahul Mehta</div>
          <div class="hp-testi-role">{_r1}</div>
        </div>
        <div class="hp-testi-card">
          <div class="hp-testi-stars">★★★★★</div>
          <div class="hp-testi-text">&ldquo;{_t2}&rdquo;</div>
          <div class="hp-testi-author">Priya Nair</div>
          <div class="hp-testi-role">{_r2}</div>
        </div>
        <div class="hp-testi-card">
          <div class="hp-testi-stars">★★★★★</div>
          <div class="hp-testi-text">&ldquo;{_t3}&rdquo;</div>
          <div class="hp-testi-author">Aditya Kapoor</div>
          <div class="hp-testi-role">{_r3}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Book Now CTA Section ────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hp-section-sm">
    <div class="hp-cta-section" id="book-now">
      <div style="font-size:2.5rem;margin-bottom:16px;">🎙</div>
      <div class="hp-cta-title">{"Ready to Talk to an Advisor?" if not _hi else "सलाहकार से बात करने के लिए तैयार हैं?"}</div>
      <div class="hp-cta-sub">
        {"Speak with our AI scheduling agent — 24/7 available, zero PII collected on call. Just say what you need."
         if not _hi else
         "हमारे AI शेड्यूलिंग एजेंट से बात करें — 24/7 उपलब्ध, कॉल पर कोई व्यक्तिगत जानकारी नहीं।"}
      </div>
      <div class="disclaimer-box" style="display:inline-block;margin-bottom:28px;">
        <strong>{"SEBI Disclaimer:" if not _hi else "SEBI अस्वीकरण:"}</strong>
        {" Our advisors provide informational guidance only — not investment advice under SEBI (IA) Regulations, 2013. No PII is collected on this call."
         if not _hi else
         " हमारे सलाहकार केवल जानकारी देते हैं — SEBI नियमों के तहत निवेश सलाह नहीं।"}
      </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    _cta_l, _cta_c, _cta_r = st.columns([3, 2, 3])
    with _cta_c:
        _btn_lbl2 = ("🎙  Start Advisor Call" if not _hi else "🎙  कॉल शुरू करें")
        if st.button(_btn_lbl2, type="primary", use_container_width=True, key="cta_book"):
            from src.dialogue.fsm import DialogueFSM
            fsm = DialogueFSM()
            ctx, greeting = fsm.start()
            st.session_state.p5_fsm          = fsm
            st.session_state.p5_ctx          = ctx
            st.session_state.p5_started      = True
            st.session_state.p5_agent_speech = greeting
            st.session_state["_tts_hash"]    = ""
            st.session_state["_tts_played"]  = ""
            st.rerun()

    # ── Footer ─────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="dsa-footer">
      <div class="dsa-footer-grid">
        <div class="dsa-footer-brand">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <div class="dsa-logo-icon" style="width:30px;height:30px;font-size:16px;">📈</div>
            <div style="font-size:0.95rem;font-weight:800;color:var(--text-1);">Dalal Street Advisors</div>
          </div>
          <p>{"SEBI Registered Investment Advisor (IA-0000347). Providing expert financial guidance since 2015. Your trusted partner for informed investment decisions." if not _hi else "SEBI पंजीकृत निवेश सलाहकार (IA-0000347)। 2015 से विशेषज्ञ वित्तीय मार्गदर्शन।"}</p>
          <div style="display:flex;gap:12px;margin-top:16px;">
            <a href="#" style="color:var(--text-3);text-decoration:none;font-size:1.1rem;">𝕏</a>
            <a href="#" style="color:var(--text-3);text-decoration:none;font-size:1.1rem;">in</a>
            <a href="#" style="color:var(--text-3);text-decoration:none;font-size:1.1rem;">📘</a>
          </div>
        </div>
        <div class="dsa-footer-col">
          <h4>{"Services" if not _hi else "सेवाएँ"}</h4>
          <a href="#">{"KYC & Onboarding" if not _hi else "KYC और ऑनबोर्डिंग"}</a>
          <a href="#">{"SIP & Mandates" if not _hi else "SIP और मैंडेट"}</a>
          <a href="#">{"Tax Documents" if not _hi else "टैक्स दस्तावेज़"}</a>
          <a href="#">{"Withdrawals" if not _hi else "निकासी"}</a>
          <a href="#">{"Account Changes" if not _hi else "खाता बदलाव"}</a>
        </div>
        <div class="dsa-footer-col">
          <h4>{"Company" if not _hi else "कंपनी"}</h4>
          <a href="#">{"About Us" if not _hi else "हमारे बारे में"}</a>
          <a href="#">{"Our Advisors" if not _hi else "हमारे सलाहकार"}</a>
          <a href="#">{"Research Reports" if not _hi else "रिसर्च रिपोर्ट"}</a>
          <a href="#">{"Media" if not _hi else "मीडिया"}</a>
          <a href="#">{"Careers" if not _hi else "करियर"}</a>
        </div>
        <div class="dsa-footer-col">
          <h4>{"Support" if not _hi else "सहायता"}</h4>
          <a href="#">{"Book a Call" if not _hi else "कॉल बुक करें"}</a>
          <a href="#">{"FAQs" if not _hi else "सामान्य प्रश्न"}</a>
          <a href="#">{"Grievance" if not _hi else "शिकायत"}</a>
          <a href="#">{"Privacy Policy" if not _hi else "गोपनीयता नीति"}</a>
          <a href="#">{"SEBI Disclosure" if not _hi else "SEBI प्रकटीकरण"}</a>
        </div>
      </div>
      <div class="dsa-footer-bottom">
        <div class="dsa-footer-copy">
          {"© 2025 Dalal Street Advisors Pvt. Ltd. · CIN: U67190MH2015PTC267890 · SEBI IA Reg. No. IA-0000347 · Registered Office: 14th Floor, One BKC, Bandra Kurla Complex, Mumbai 400051. Investment advisory services are subject to market risks. Past performance does not guarantee future results."
           if not _hi else
           "© 2025 Dalal Street Advisors Pvt. Ltd. · SEBI IA पंज. सं. IA-0000347 · पंजीकृत कार्यालय: 14वीं मंज़िल, वन BKC, मुंबई 400051। निवेश सलाह सेवाएं बाज़ार जोखिमों के अधीन हैं।"}
        </div>
        <div class="dsa-footer-sebi">
          <span>SEBI</span> Registered IA · IA-0000347<br>
          <span>NSE</span> · <span>BSE</span> · <span>AMFI</span> ARN-122847
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.stop()


# ── ACTIVE CALL ────────────────────────────────────────────────────────────

# Site header during call
st.markdown(f"""
<div class="dsa-header">
  <div class="dsa-logo-wrap">
    <div class="dsa-logo-icon">📈</div>
    <div>
      <div class="dsa-logo-text">Dalal Street Advisors</div>
      <div class="dsa-logo-sub">SEBI Registered · IA-0000347</div>
    </div>
  </div>
  <div style="font-size:0.82rem;color:var(--gold-dim);letter-spacing:0.04em;">
    {"● Live Call in Progress" if _lang == "en-IN" else "● कॉल जारी है"}
  </div>
</div>
<div class="call-page-wrap">
""", unsafe_allow_html=True)

ctx     = st.session_state.p5_ctx
speech  = st.session_state.p5_agent_speech

# Determine visual state
_is_terminal     = ctx and ctx.current_state.is_terminal()
_is_complete     = ctx and ctx.current_state.name == "BOOKING_COMPLETE"
_is_waitlisted   = ctx and ctx.current_state.name == "WAITLIST_CONFIRMED"
_agent_turn      = bool(speech) and not _is_terminal and not _is_complete and not _is_waitlisted
_ring_class     = "idle"  # overridden in the status block below

# ── Booking Complete ────────────────────────────────────────────────────────
if _is_complete:
    _secure_url  = ctx.secure_url or ""
    _bc_code     = ctx.booking_code or ""
    _link_html   = ""
    if _secure_url:
        _link_html = (
            '<div class="booking-link">'
            '📎 Provide your contact details to receive a confirmation email:<br>'
            f'<a href="{_secure_url}" target="_blank">{_secure_url}</a>'
            '</div>'
        )

    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;padding:48px 20px 20px;">
      <div class="booking-success">
        <div class="booking-success-icon">✅</div>
        <div class="booking-success-title">Booking Confirmed!</div>
        <div style="color:#a7f3d0;font-size:0.9rem;margin-bottom:8px;">Your booking code is</div>
        <div class="booking-code-badge">{_bc_code}</div>
        <div style="color:#6ee7b7;font-size:0.88rem;margin-bottom:4px;">
          A tentative calendar hold has been created.<br>
          An advisor will reach out to confirm.
        </div>
        {_link_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

    mcp = st.session_state.p5_mcp
    if mcp:
        mc1, mc2, mc3 = st.columns(3)
        with mc1: st.metric("📅 Calendar", "✅" if mcp.calendar_success else "❌", f"{mcp.calendar.duration_ms:.0f}ms")
        with mc2: st.metric("📊 Sheets",   "✅" if mcp.sheets_success   else "❌", f"{mcp.sheets.duration_ms:.0f}ms")
        with mc3: st.metric("📧 Email",    "✅" if mcp.email_success    else "❌", f"{mcp.email.duration_ms:.0f}ms")

    # Play final agent audio (no download — JS Audio API)
    text_hash = hashlib.md5(speech.encode()).hexdigest()
    if st.session_state["_tts_hash"] != text_hash:
        audio_bytes = _tts(speech, language=_lang)
        st.session_state["_tts_hash"]  = text_hash
        st.session_state["_tts_audio"] = audio_bytes
    else:
        audio_bytes = st.session_state["_tts_audio"]

    if audio_bytes and st.session_state["_tts_played"] != text_hash:
        st.session_state["_tts_played"] = text_hash
        # Play only — no VAD after booking complete
        import base64 as _b64
        _b64str = _b64.b64encode(audio_bytes).decode()
        _fmt    = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
        components.html(f"""<script>
        (function(){{
            var raw=atob('{_b64str}'),buf=new Uint8Array(raw.length);
            for(var i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
            var url=URL.createObjectURL(new Blob([buf],{{type:'{_fmt}'}}));
            var a=new Audio(url); a.play().catch(function(){{}});
            a.addEventListener('ended',function(){{URL.revokeObjectURL(url);}},{{once:true}});
        }})();
        </script>""", height=0)

    _, _nb, _ = st.columns([2, 3, 2])
    with _nb:
        if st.button("📞  New Call", type="primary", use_container_width=True):
            for k in ["p5_started", "p5_ctx", "p5_fsm", "p5_mcp",
                      "p5_agent_speech", "_tts_hash", "_tts_audio",
                      "_tts_played", "_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()

# ── Waitlist Confirmed ──────────────────────────────────────────────────────
if _is_waitlisted:
    _wl_code    = ctx.waitlist_code or ""
    _wl_url     = ctx.secure_url or ""
    _wl_link_html = ""
    if _wl_url:
        _wl_link_html = (
            '<div class="booking-link">'
            '📎 Submit your email to get notified when your slot opens:<br>'
            f'<a href="{_wl_url}" target="_blank">{_wl_url}</a>'
            '</div>'
        )

    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;padding:48px 20px 20px;">
      <div class="booking-success" style="border-color:rgba(34,197,94,0.30);">
        <div class="booking-success-icon">🔔</div>
        <div class="booking-success-title" style="color:#4ade80;">Added to Waitlist!</div>
        <div style="color:#a7f3d0;font-size:0.9rem;margin-bottom:8px;">Your waitlist code is</div>
        <div class="booking-code-badge" style="color:#4ade80;">{_wl_code}</div>
        <div style="color:#6ee7b7;font-size:0.88rem;margin-bottom:4px;">
          We'll email you the moment a matching slot opens.<br>
          Submit your contact details at the link below.
        </div>
        {_wl_link_html}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Play waitlist confirmed audio
    if speech:
        text_hash = hashlib.md5(speech.encode()).hexdigest()
        if st.session_state["_tts_hash"] != text_hash:
            audio_bytes = _tts(speech, language=_lang)
            st.session_state["_tts_hash"]  = text_hash
            st.session_state["_tts_audio"] = audio_bytes
        else:
            audio_bytes = st.session_state["_tts_audio"]
        if audio_bytes and st.session_state["_tts_played"] != text_hash:
            st.session_state["_tts_played"] = text_hash
            import base64 as _b64
            _b64str = _b64.b64encode(audio_bytes).decode()
            _fmt    = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
            components.html(f"""<script>
            (function(){{
                var raw=atob('{_b64str}'),buf=new Uint8Array(raw.length);
                for(var i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
                var url=URL.createObjectURL(new Blob([buf],{{type:'{_fmt}'}}));
                var a=new Audio(url); a.play().catch(function(){{}});
                a.addEventListener('ended',function(){{URL.revokeObjectURL(url);}},{{once:true}});
            }})();
            </script>""", height=0)

    _, _nb, _ = st.columns([2, 3, 2])
    with _nb:
        if st.button("📞  New Call", type="primary", use_container_width=True):
            for k in ["p5_started", "p5_ctx", "p5_fsm", "p5_mcp",
                      "p5_agent_speech", "_tts_hash", "_tts_audio",
                      "_tts_played", "_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()

# ── Call ended ──────────────────────────────────────────────────────────────
if _is_terminal:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;padding:60px 20px;">
      <div style="font-size:3.5rem;margin-bottom:16px;">📵</div>
      <div style="font-size:1.3rem;font-weight:700;color:#f3f0ff;margin-bottom:8px;">Call Ended</div>
      <div style="color:#a78bfa;font-size:0.9rem;">Thank you for using the Advisor Scheduling Agent.</div>
    </div>
    """, unsafe_allow_html=True)

    # Play farewell audio (no download — JS Audio API)
    if speech:
        text_hash = hashlib.md5(speech.encode()).hexdigest()
        if st.session_state["_tts_hash"] != text_hash:
            audio_bytes = _tts(speech, language=_lang)
            st.session_state["_tts_hash"]  = text_hash
            st.session_state["_tts_audio"] = audio_bytes
        else:
            audio_bytes = st.session_state["_tts_audio"]
        if audio_bytes and st.session_state["_tts_played"] != text_hash:
            st.session_state["_tts_played"] = text_hash
            import base64 as _b64
            _b64str = _b64.b64encode(audio_bytes).decode()
            _fmt    = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
            components.html(f"""<script>
            (function(){{
                var raw=atob('{_b64str}'),buf=new Uint8Array(raw.length);
                for(var i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
                var url=URL.createObjectURL(new Blob([buf],{{type:'{_fmt}'}}));
                var a=new Audio(url); a.play().catch(function(){{}});
                a.addEventListener('ended',function(){{URL.revokeObjectURL(url);}},{{once:true}});
            }})();
            </script>""", height=0)

    _, _nb, _ = st.columns([2, 3, 2])
    with _nb:
        if st.button("📞  New Call", type="primary", use_container_width=True):
            for k in ["p5_started", "p5_ctx", "p5_fsm", "p5_mcp",
                      "p5_agent_speech", "_tts_hash", "_tts_audio",
                      "_tts_played", "_last_audio_hash"]:
                st.session_state.pop(k, None)
            _init_state()
            st.rerun()
    st.stop()


# ── Live call screen ────────────────────────────────────────────────────────

# Determine visual state: speaking → listening → (processing happens instantly)
_tts_ready = (speech and
              st.session_state["_tts_hash"] == hashlib.md5(speech.encode()).hexdigest())

if _agent_turn and _tts_ready:
    _dot_cls    = "gold"
    _ring_class = "speaking"
    _status     = "Speaking…" if _lang == "en-IN" else "बोल रहे हैं…"
elif _agent_turn and not _tts_ready:
    _dot_cls    = "dim"
    _ring_class = "idle"
    _status     = "One moment…" if _lang == "en-IN" else "एक पल…"
else:
    _dot_cls    = "green"
    _ring_class = "listening"
    _status     = "Listening…" if _lang == "en-IN" else "सुन रहे हैं…"

# Caption: last agent utterance, truncated for readability
_caption = speech[:200] + ("…" if len(speech) > 200 else "") if speech else ""

st.markdown(f"""
<div class="call-wrap">

  <div class="ring-outer {_ring_class}">
    <div class="caller-avatar">🤖</div>
  </div>

  <div class="caller-name">Advisor Agent</div>
  <div class="caller-firm">{"Dalal Street Advisors · AI Scheduling" if _lang == "en-IN" else "Dalal Street Advisors · AI शेड्यूलिंग"}</div>

  <div class="status-pill">
    <span class="s-dot {_dot_cls}"></span>
    {_status}
  </div>

  <div class="agent-caption">{_caption if _caption else "&nbsp;"}</div>

  <div class="vad-live-wrap">
    <div id="vad-live-status" class="vad-live-status">&nbsp;</div>
  </div>

  <div class="backend-status">{st.session_state.get("_backend_status", "") or "&nbsp;"}</div>

</div>
""", unsafe_allow_html=True)

# ── TTS playback + VAD (no st.audio → no downloads) ────────────────────────
if speech:
    text_hash = hashlib.md5(speech.encode()).hexdigest()
    _turn_count = ctx.turn_count if ctx else 0
    turn_key    = hashlib.md5(f"{_turn_count}:{text_hash}".encode()).hexdigest()[:16]

    if st.session_state["_tts_hash"] != text_hash:
        st.session_state["_backend_status"] = "Preparing audio…"
        with st.spinner(""):
            audio_bytes = _tts(speech, language=_lang)
        st.session_state["_backend_status"] = ""
        st.session_state["_tts_hash"]  = text_hash
        st.session_state["_tts_audio"] = audio_bytes
    else:
        audio_bytes = st.session_state["_tts_audio"]

    if st.session_state["_tts_played"] != turn_key:
        st.session_state["_tts_played"] = turn_key
        if audio_bytes:
            # Play audio + start VAD after
            _play_and_listen_js(audio_bytes, turn_id=turn_key)
        else:
            # TTS failed — skip audio, start mic immediately so call isn't dead
            _start_listen_js(turn_id=turn_key)

# ── Microphone input (off-screen, controlled by VAD JS) ─────────────────────
_mic_lbl = "mic" if _lang == "en-IN" else "mic-hi"
audio_input = st.audio_input(_mic_lbl, key="p5_audio_input",
                             label_visibility="hidden")
if audio_input is not None:
    _ab    = audio_input.read()
    _ahash = hashlib.md5(_ab).hexdigest()
    if st.session_state.get("_last_audio_hash") != _ahash:
        st.session_state["_last_audio_hash"] = _ahash

        # Short audio (< 8 KB ≈ < 0.5 s) → silence / no speech → re-prompt
        if len(_ab) < 8_000:
            _process("")
        else:
            st.session_state["_backend_status"] = "Transcribing speech…"
            with st.spinner(""):
                transcript = _stt(_ab, language=_lang)
            if not transcript:
                _process("")   # STT got nothing → no-input
            else:
                # ── "repeat" intercept ──────────────────────────────────────
                # If user asks to repeat, just replay last agent speech without
                # advancing the FSM state.
                _repeat_words = [
                    "repeat", "again", "say that again", "what did you say",
                    "pardon", "come again", "didn't hear", "can't hear",
                    "what", "huh", "sorry", "excuse me", "once more",
                    "kya", "dobara", "phir se", "samjha nahi", "suna nahi",
                ]
                _t_lower = transcript.lower().strip()
                _is_repeat = any(w in _t_lower for w in _repeat_words) and len(_t_lower) < 40
                if _is_repeat:
                    # Force re-play current speech by resetting turn key
                    st.session_state["_tts_played"] = ""
                else:
                    _process(transcript)

        st.rerun()

# ── End call button ───────────────────────────────────────────────────────────
st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
_, _ec, _ = st.columns([3, 2, 3])
with _ec:
    if st.button("End Call", type="secondary", use_container_width=True):
        for k in ["p5_started", "p5_ctx", "p5_fsm", "p5_mcp",
                  "p5_agent_speech", "_tts_hash", "_tts_audio",
                  "_tts_played", "_last_audio_hash"]:
            st.session_state.pop(k, None)
        _init_state()
        st.rerun()

# Close call-page-wrap + compact footer
st.markdown("""
</div>
<div style="background:#07080F;border-top:1px solid rgba(255,255,255,0.06);
     padding:20px 48px;text-align:center;margin-top:32px;">
  <div style="font-size:0.75rem;color:#4A4540;line-height:1.7;">
    © 2025 <span style="color:#6B6358;">Dalal Street Advisors Pvt. Ltd.</span> ·
    SEBI IA Reg. No. IA-0000347 ·
    Investment advisory services are subject to market risks.
    No personal information is collected on this call.
  </div>
</div>
""", unsafe_allow_html=True)
