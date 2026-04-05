"""
console.py

Text-mode conversation loop for testing the full Phase 2 dialogue pipeline
without voice or a browser.

Usage:
    python console.py                  # uses LLM if API keys present
    python console.py --offline        # forces rule-based mode

Type 'quit' or 'exit' to end the session.
"""

from __future__ import annotations

import argparse
import os
import sys

# ── Cross-phase sys.path setup ─────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_VOICE_AGENTS_ROOT = os.path.dirname(_HERE)
for _phase in ("phase0", "phase1", "phase2"):
    _p = os.path.join(_VOICE_AGENTS_ROOT, _phase)
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    os.path.join(_VOICE_AGENTS_ROOT, "phase1", "data", "mock_calendar.json"),
)
# ───────────────────────────────────────────────────────────────────────────────

from src.dialogue import DialogueFSM, IntentRouter, ComplianceGuard, SessionManager

from src.booking.pii_scrubber import scrub_pii  # noqa: E402


def run_console(offline: bool = False) -> None:
    fsm = DialogueFSM()
    guard = ComplianceGuard()
    sessions = SessionManager()

    # Force offline if requested
    router = IntentRouter(llm_callable=None if not offline else _offline_stub)
    if offline:
        print("[INFO] Running in offline (rule-based) mode.\n")
    elif router.is_online:
        print("[INFO] LLM connected.\n")
    else:
        print("[INFO] No API keys found — using rule-based mode.\n")

    # Start session
    ctx, greeting = fsm.start()
    session_id = sessions.create_session(ctx)

    print("=" * 60)
    print("  Advisor Scheduling Voice Agent — Text Console")
    print("  Type 'quit' or 'exit' to end")
    print("=" * 60)
    print(f"\nAgent: {greeting}\n")

    while True:
        # Get user input
        try:
            raw_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAgent: Thank you for calling. Goodbye!")
            break

        if raw_input.lower() in ("quit", "exit", "bye"):
            print("Agent: Thank you for calling. Have a great day!")
            break

        # Fetch session
        ctx = sessions.get_session(session_id)
        if ctx is None:
            print("[ERROR] Session expired.")
            break

        # PII scrub
        scrub = scrub_pii(raw_input)
        if scrub.pii_found:
            cats = ", ".join(scrub.categories)
            print(f"  [PII scrubbed: {cats}]")
        clean_input = scrub.cleaned_text

        # Route intent
        llm_response = router.route(clean_input, ctx)

        # Compliance check on LLM's proposed speech
        checked_speech = guard.check_and_gate(llm_response.speech)
        if checked_speech != llm_response.speech:
            print("  [Compliance guard triggered]")
            llm_response.speech = checked_speech

        # FSM transition
        ctx, speech = fsm.process_turn(ctx, clean_input, llm_response)
        sessions.update_session(session_id, ctx)

        print(f"\nAgent: {speech}")
        print(f"  [State: {ctx.current_state.label()} | Turn: {ctx.turn_count}]\n")

        # End of conversation
        if ctx.current_state.is_terminal():
            sessions.close_session(session_id)
            break


def _offline_stub(*_args: str) -> str:
    """Never called — placeholder to satisfy type hint when offline=True."""
    raise RuntimeError("Should not be called in offline mode")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Agent text console")
    parser.add_argument(
        "--offline", action="store_true",
        help="Force rule-based mode (no LLM API calls)"
    )
    args = parser.parse_args()
    run_console(offline=args.offline)
