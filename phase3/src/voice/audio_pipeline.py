"""
Audio Pipeline — orchestrates the full voice interaction loop.

                    audio bytes (PCM16)
                          │
                   ┌──────▼──────┐
                   │  VADEngine  │  ← detect end-of-turn / barge-in
                   └──────┬──────┘
                          │ end-of-turn signal
                   ┌──────▼──────┐
                   │  STTEngine  │  ← transcribe audio → text
                   └──────┬──────┘
                          │ raw transcript
                   ┌──────▼──────┐
                   │ PII Scrubber│  ← sanitise before any processing
                   └──────┬──────┘
                          │ sanitised text
                   ┌──────▼──────┐      ┌──────────────┐
                   │IntentRouter │ ◄────►│ DialogueFSM  │
                   └──────┬──────┘      └──────────────┘
                          │ agent speech (raw)
                   ┌──────▼──────────┐
                   │ ComplianceGuard │  ← block PII / advice leakage
                   └──────┬──────────┘
                          │ safe speech text
                   ┌──────▼──────┐
                   │  TTSEngine  │  ← text → audio bytes
                   └──────┬──────┘
                          │
                     audio bytes out

The pipeline supports two modes:
  - ``text_mode=True``  — bypasses STT/TTS entirely (used for testing UI)
  - ``text_mode=False`` — full audio pipeline

All external dependencies (IntentRouter, FSM, etc.) are lazily imported
from Phase 2 to allow Phase 3 to be used standalone in text mode without
Phase 2 being installed.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pytz

from .stt_engine import STTEngine, TranscriptResult, transcribe as _default_transcribe
from .tts_engine import TTSEngine, SynthesisResult, synthesise as _default_synthesise
from .vad import VADEngine, VADResult
from .voice_logger import VoiceLogger, get_default_logger

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of one complete pipeline turn (audio-in → audio-out)."""

    call_id: str
    turn_index: int
    user_text_sanitised: str        # after PII scrub
    agent_speech: str               # text that was (or would be) spoken
    audio_out: bytes                # TTS audio bytes (empty in text_mode)
    pii_blocked: bool
    compliance_blocked: bool
    current_state: str
    intent: str | None = None
    booking_code: str | None = None
    secure_url: str | None = None
    stt_confidence: float = 1.0
    stt_provider: str = "text_mode"
    tts_provider: str = "text_mode"
    is_end_of_call: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.call_id:
            errors.append("call_id must not be empty")
        if self.turn_index < 0:
            errors.append("turn_index must be >= 0")
        return errors


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class PipelineSession:
    """Per-call state held by the pipeline."""

    call_id: str
    turn_index: int = 0
    is_active: bool = True
    # Lazy-loaded dialogue context (Phase 2 object, typed as Any to avoid hard dep)
    dialogue_ctx: object | None = None
    audio_buffer: list[bytes] = field(default_factory=list)
    created_at_ist: str = ""

    def __post_init__(self) -> None:
        if not self.created_at_ist:
            self.created_at_ist = datetime.now(IST).isoformat()


# ---------------------------------------------------------------------------
# Phase 2 lazy imports
# ---------------------------------------------------------------------------

def _load_phase2():
    """
    Lazy-load Phase 2 components (FSM, IntentRouter, ComplianceGuard).
    Returns (DialogueFSM, IntentRouter, ComplianceGuard) or (None, None, None).
    """
    try:
        from src.dialogue.fsm import DialogueFSM  # type: ignore[import]
        from src.dialogue.intent_router import IntentRouter  # type: ignore[import]
        from src.dialogue.compliance_guard import ComplianceGuard  # type: ignore[import]
        return DialogueFSM, IntentRouter, ComplianceGuard
    except ImportError:
        pass
    try:
        from phase2.src.dialogue.fsm import DialogueFSM  # type: ignore[import]
        from phase2.src.dialogue.intent_router import IntentRouter  # type: ignore[import]
        from phase2.src.dialogue.compliance_guard import ComplianceGuard  # type: ignore[import]
        return DialogueFSM, IntentRouter, ComplianceGuard
    except ImportError:
        logger.warning(
            "Phase 2 modules not importable. Pipeline will run in echo mode."
        )
        return None, None, None


# ---------------------------------------------------------------------------
# AudioPipeline
# ---------------------------------------------------------------------------

class AudioPipeline:
    """
    Full voice pipeline for a single call session.

    Usage (text mode — testing / demo)::

        pipeline = AudioPipeline(text_mode=True)
        call_id  = pipeline.start_session()
        result   = pipeline.process_text_turn(call_id, "I want to book for KYC")
        print(result.agent_speech)

    Usage (audio mode — production)::

        pipeline = AudioPipeline()
        call_id  = pipeline.start_session()
        for chunk in audio_stream:
            result = pipeline.process_audio_chunk(call_id, chunk)
            if result:                # None until end-of-turn
                play_audio(result.audio_out)

    All dependencies are injectable for testing.
    """

    def __init__(
        self,
        text_mode: bool = False,
        stt_engine: STTEngine | None = None,
        tts_engine: TTSEngine | None = None,
        vad_factory: Callable[[], VADEngine] | None = None,
        voice_logger: VoiceLogger | None = None,
        # injectable Phase-2 objects (set in tests)
        fsm_factory: Callable | None = None,
        intent_router_factory: Callable | None = None,
        compliance_guard_factory: Callable | None = None,
    ) -> None:
        self._text_mode   = text_mode
        self._stt         = stt_engine or STTEngine()
        self._tts         = tts_engine or TTSEngine()
        self._vad_factory = vad_factory or (lambda: VADEngine())
        self._vlog        = voice_logger or get_default_logger()

        # Phase 2 lazy load
        DialogueFSM, IntentRouter, ComplianceGuard = _load_phase2()

        self._fsm_cls     = fsm_factory or (DialogueFSM if DialogueFSM else None)
        self._router_cls  = intent_router_factory or (IntentRouter if IntentRouter else None)
        self._guard_cls   = compliance_guard_factory or (ComplianceGuard if ComplianceGuard else None)

        # Active sessions: call_id → PipelineSession
        self._sessions: dict[str, PipelineSession] = {}
        # Per-session Phase-2 objects
        self._fsm_instances:    dict[str, object] = {}
        self._router_instances: dict[str, object] = {}
        self._guard_instances:  dict[str, object] = {}
        # Per-session VAD engines
        self._vad_instances:    dict[str, VADEngine] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, call_id: str | None = None) -> str:
        """
        Initialise a new call session.
        Returns the call_id (generated if not provided).
        """
        call_id = call_id or f"CALL-{datetime.now(IST).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        session = PipelineSession(call_id=call_id)
        self._sessions[call_id] = session
        self._vad_instances[call_id] = self._vad_factory()

        # Initialise Phase-2 objects
        if self._fsm_cls:
            self._fsm_instances[call_id]    = self._fsm_cls()
        if self._router_cls:
            self._router_instances[call_id] = self._router_cls()
        if self._guard_cls:
            self._guard_instances[call_id]  = self._guard_cls()

        # Prime the FSM so that the first user turn calls process_turn (not start)
        fsm = self._fsm_instances.get(call_id)
        if fsm:
            try:
                ctx, _ = fsm.start(call_id=call_id)
                session.dialogue_ctx = ctx
            except Exception as exc:
                logger.warning("FSM start error: %s", exc)

        greeting = self._get_greeting()
        self._vlog.log_session_start(call_id, extra={"greeting": greeting})
        logger.info("Pipeline session started: %s", call_id)

        return call_id

    def end_session(self, call_id: str) -> None:
        """Cleanly terminate a session."""
        session = self._sessions.get(call_id)
        if session:
            session.is_active = False
            self._vlog.log_session_end(call_id, turn_count=session.turn_index)
        for store in [self._sessions, self._vad_instances,
                      self._fsm_instances, self._router_instances,
                      self._guard_instances]:
            store.pop(call_id, None)
        logger.info("Pipeline session ended: %s", call_id)

    # ------------------------------------------------------------------
    # Text-mode turn (bypasses STT / TTS)
    # ------------------------------------------------------------------

    def process_text_turn(self, call_id: str, user_text: str) -> PipelineResult:
        """
        Process one text turn (text_mode or test usage).
        Runs PII scrub → intent routing → FSM → compliance guard.
        Does NOT call STT or TTS.
        """
        session = self._sessions.get(call_id)
        if not session or not session.is_active:
            raise ValueError(f"Unknown or inactive session: {call_id!r}")

        session.turn_index += 1
        turn_idx = session.turn_index

        # PII scrub
        sanitised, pii_blocked, pii_cats = self._scrub(user_text)

        # Route through FSM
        agent_speech, intent, new_state, booking_code, secure_url = self._route(
            call_id, sanitised, session
        )

        # Compliance guard on agent output
        compliance_blocked = False
        safe_speech = agent_speech
        guard = self._guard_instances.get(call_id)
        if guard:
            try:
                result = guard.check(agent_speech)
                if not result.is_compliant:
                    compliance_blocked = True
                    safe_speech = result.safe_speech
                    self._vlog.log_compliance_block(
                        call_id=call_id,
                        turn_index=turn_idx,
                        flag=result.flag or "",
                        blocked_speech=agent_speech,
                        safe_speech=safe_speech,
                    )
            except Exception as exc:
                logger.warning("ComplianceGuard error: %s", exc)

        # Update session context
        if new_state:
            session.dialogue_ctx = new_state

        # Log turn
        self._vlog.log_turn(
            call_id=call_id,
            turn_index=turn_idx,
            user_transcript_raw=user_text,
            detected_intent=intent,
            slots_filled={},
            agent_speech=safe_speech,
            current_state=str(new_state) if new_state else "",
            booking_code=booking_code,
        )

        is_end = safe_speech.lower().startswith("thank you") or \
                 "have a great day" in safe_speech.lower()

        if is_end:
            self.end_session(call_id)

        return PipelineResult(
            call_id=call_id,
            turn_index=turn_idx,
            user_text_sanitised=sanitised,
            agent_speech=safe_speech,
            audio_out=b"",
            pii_blocked=pii_blocked,
            compliance_blocked=compliance_blocked,
            current_state=str(new_state) if new_state else "",
            intent=intent,
            booking_code=booking_code,
            secure_url=secure_url,
            stt_confidence=1.0,
            stt_provider="text_mode",
            tts_provider="text_mode",
            is_end_of_call=is_end,
        )

    # ------------------------------------------------------------------
    # Audio-mode chunk processing
    # ------------------------------------------------------------------

    def process_audio_chunk(
        self, call_id: str, audio_chunk: bytes
    ) -> PipelineResult | None:
        """
        Feed one PCM16 audio chunk into the pipeline.

        Returns ``None`` while the user is still speaking.
        Returns a ``PipelineResult`` when end-of-turn is detected,
        containing the synthesised audio response in ``audio_out``.
        """
        session = self._sessions.get(call_id)
        if not session or not session.is_active:
            raise ValueError(f"Unknown or inactive session: {call_id!r}")

        vad = self._vad_instances[call_id]
        vad_result = vad.process_chunk(audio_chunk)

        if audio_chunk:
            session.audio_buffer.append(audio_chunk)

        if not vad_result.is_end_of_turn:
            return None

        # End-of-turn: transcribe accumulated buffer
        combined = b"".join(session.audio_buffer)
        session.audio_buffer = []
        vad.reset()

        transcript = self._stt.transcribe(combined)
        session.turn_index += 1
        turn_idx = session.turn_index

        # Low-confidence — re-prompt
        if not transcript.is_reliable or transcript.is_empty:
            reprompt = "I'm sorry, I didn't catch that. Could you please repeat?"
            audio_out = self._tts.synthesise(reprompt).audio_bytes
            self._vlog.log_turn(
                call_id=call_id, turn_index=turn_idx,
                user_transcript_raw="", detected_intent=None,
                agent_speech=reprompt, current_state="LOW_CONFIDENCE",
            )
            return PipelineResult(
                call_id=call_id, turn_index=turn_idx,
                user_text_sanitised="",
                agent_speech=reprompt, audio_out=audio_out,
                pii_blocked=False, compliance_blocked=False,
                current_state="LOW_CONFIDENCE",
                stt_confidence=transcript.confidence,
                stt_provider=transcript.provider,
                tts_provider="unknown",
            )

        # PII scrub
        sanitised, pii_blocked, _ = self._scrub(transcript.text)

        # Route through FSM
        agent_speech, intent, new_state, booking_code, secure_url = self._route(
            call_id, sanitised, session
        )

        # Compliance guard
        compliance_blocked = False
        safe_speech = agent_speech
        guard = self._guard_instances.get(call_id)
        if guard:
            try:
                result = guard.check(agent_speech)
                if not result.is_compliant:
                    compliance_blocked = True
                    safe_speech = result.safe_speech
                    self._vlog.log_compliance_block(
                        call_id=call_id, turn_index=turn_idx,
                        flag=result.flag or "", blocked_speech=agent_speech,
                        safe_speech=safe_speech,
                    )
            except Exception as exc:
                logger.warning("ComplianceGuard check failed: %s", exc)

        # Synthesise
        tts_result = self._tts.synthesise(safe_speech)

        if new_state:
            session.dialogue_ctx = new_state

        self._vlog.log_turn(
            call_id=call_id, turn_index=turn_idx,
            user_transcript_raw=transcript.text,
            detected_intent=intent, slots_filled={},
            agent_speech=safe_speech,
            current_state=str(new_state) if new_state else "",
            booking_code=booking_code,
        )

        is_end = "have a great day" in safe_speech.lower() or \
                 safe_speech.lower().startswith("thank you")
        if is_end:
            self.end_session(call_id)

        return PipelineResult(
            call_id=call_id, turn_index=turn_idx,
            user_text_sanitised=sanitised,
            agent_speech=safe_speech, audio_out=tts_result.audio_bytes,
            pii_blocked=pii_blocked, compliance_blocked=compliance_blocked,
            current_state=str(new_state) if new_state else "",
            intent=intent, booking_code=booking_code, secure_url=secure_url,
            stt_confidence=transcript.confidence,
            stt_provider=transcript.provider,
            tts_provider=tts_result.provider,
            is_end_of_call=is_end,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _route(
        self,
        call_id: str,
        sanitised_text: str,
        session: PipelineSession,
    ) -> tuple[str, str | None, object | None, str | None, str | None]:
        """
        Route sanitised text through IntentRouter → FSM.

        Returns (agent_speech, intent, new_ctx, booking_code, secure_url).
        Falls back to echo mode if Phase 2 not available.
        """
        router = self._router_instances.get(call_id)
        fsm    = self._fsm_instances.get(call_id)

        if router is None or fsm is None:
            # Echo mode — no Phase 2
            return (
                f"Echo: {sanitised_text}" if sanitised_text
                else "Hello! How can I help you today?",
                None, None, None, None,
            )

        try:
            ctx = session.dialogue_ctx

            # Start the FSM if no context yet
            if ctx is None:
                ctx, speech = fsm.start(call_id=call_id)
                session.dialogue_ctx = ctx
                return speech, "session_start", ctx, None, None

            # Route intent
            llm_response = router.route(sanitised_text, ctx)
            intent = getattr(llm_response, "intent", None)

            # Advance FSM
            ctx, speech = fsm.process_turn(ctx, sanitised_text, llm_response)

            # Extract booking artefacts
            booking_code = getattr(ctx, "booking_code", None)
            secure_url   = getattr(ctx, "secure_url", None)

            return speech, intent, ctx, booking_code, secure_url

        except Exception as exc:
            logger.error("FSM/Router error: %s", exc)
            return (
                "I'm sorry, I'm having a technical issue. Please try again.",
                None, session.dialogue_ctx, None, None,
            )

    @staticmethod
    def _scrub(text: str) -> tuple[str, bool, list[str]]:
        """Delegate to voice_logger's scrub helper (single point of truth)."""
        from .voice_logger import _scrub as _vl_scrub
        return _vl_scrub(text)

    def _get_greeting(self) -> str:
        company = os.environ.get("COMPANY_NAME", "our company")
        return (
            f"Hello! I'm the Advisor Scheduling assistant for {company}. "
            "I'll help you book a consultation in about two minutes."
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_session(self, call_id: str) -> PipelineSession | None:
        return self._sessions.get(call_id)

    def active_sessions(self) -> list[str]:
        return [cid for cid, s in self._sessions.items() if s.is_active]
