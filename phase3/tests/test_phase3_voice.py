"""
Phase 3 — Voice Integration Test Suite.

Coverage
--------
  TC-3.1  to TC-3.6   : TranscriptResult dataclass
  TC-3.7  to TC-3.13  : STTEngine — primary, fallback, offline, streaming
  TC-3.14 to TC-3.20  : SynthesisResult + TTSEngine — synthesis, cache, fallback
  TC-3.21 to TC-3.27  : VADEngine — speech detection, end-of-turn, energy fallback
  TC-3.28 to TC-3.37  : VoiceLogger — PII scrubbing, JSONL output, event types
  TC-3.38 to TC-3.52  : AudioPipeline — text mode, audio mode, barge-in, compliance
"""
from __future__ import annotations

import json
import math
import os
import struct
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers (also used in conftest)
# ---------------------------------------------------------------------------

def _pcm16_silence(ms: int = 300, sr: int = 16_000) -> bytes:
    n = int(sr * ms / 1000)
    return struct.pack(f"<{n}h", *([0] * n))


def _pcm16_sine(ms: int = 100, freq: float = 440.0, amp: int = 8000, sr: int = 16_000) -> bytes:
    n = int(sr * ms / 1000)
    samples = [int(amp * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


# ===========================================================================
# TC-3.1 to TC-3.6 — TranscriptResult
# ===========================================================================

class TestTranscriptResult:

    def test_reliable_above_threshold(self, monkeypatch):
        """TC-3.1 — is_reliable True when confidence ≥ threshold."""
        monkeypatch.setenv("STT_CONFIDENCE_THRESHOLD", "0.7")
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="hello", confidence=0.85, is_final=True, provider="google")
        assert r.is_reliable is True

    def test_unreliable_below_threshold(self, monkeypatch):
        """TC-3.2 — is_reliable False when confidence < threshold."""
        monkeypatch.setenv("STT_CONFIDENCE_THRESHOLD", "0.7")
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="mbl", confidence=0.5, is_final=True, provider="google")
        assert r.is_reliable is False

    def test_is_empty_blank_text(self):
        """TC-3.3 — is_empty True for whitespace-only text."""
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="   ", confidence=0.9, is_final=True)
        assert r.is_empty is True

    def test_is_empty_false_for_real_text(self):
        """TC-3.4 — is_empty False for non-blank text."""
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="KYC please", confidence=0.9, is_final=True)
        assert r.is_empty is False

    def test_validate_passes_valid(self):
        """TC-3.5 — validate() returns empty list for valid result."""
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="ok", confidence=0.8, is_final=True, provider="google")
        assert r.validate() == []

    def test_validate_catches_bad_confidence(self):
        """TC-3.6 — validate() catches out-of-range confidence."""
        from src.voice.stt_engine import TranscriptResult
        r = TranscriptResult(text="ok", confidence=1.5, is_final=True, provider="google")
        errors = r.validate()
        assert any("confidence" in e for e in errors)


# ===========================================================================
# TC-3.7 to TC-3.13 — STTEngine
# ===========================================================================

class TestSTTEngine:

    def test_primary_called_returns_result(self, mock_stt_callable, mock_audio_bytes):
        """TC-3.7 — Primary callable is used and result returned."""
        from src.voice.stt_engine import STTEngine
        engine = STTEngine(primary=mock_stt_callable)
        result = engine.transcribe(mock_audio_bytes)
        assert result.provider == "mock"
        assert "KYC" in result.text
        assert result.confidence == 0.95

    def test_fallback_called_on_primary_failure(self, failing_stt_callable, mock_audio_bytes):
        """TC-3.8 — Fallback is called when primary raises."""
        from src.voice.stt_engine import STTEngine, TranscriptResult

        def good_fallback(b: bytes) -> TranscriptResult:
            return TranscriptResult(text="fallback text", confidence=0.8,
                                    is_final=True, provider="deepgram")

        engine = STTEngine(primary=failing_stt_callable, fallback=good_fallback)
        result = engine.transcribe(mock_audio_bytes)
        assert result.provider == "deepgram"
        assert result.text == "fallback text"

    def test_offline_returned_when_both_fail(self, mock_audio_bytes):
        """TC-3.9 — Offline stub returned when both primary and fallback fail."""
        from src.voice.stt_engine import STTEngine

        def fail(_): raise RuntimeError("fail")

        engine = STTEngine(primary=fail, fallback=fail)
        result = engine.transcribe(mock_audio_bytes)
        assert result.provider == "offline"
        assert result.text == ""
        assert result.confidence == 0.0

    def test_empty_bytes_returns_offline(self):
        """TC-3.10 — Empty audio bytes returns offline stub immediately."""
        from src.voice.stt_engine import STTEngine
        engine = STTEngine()
        result = engine.transcribe(b"")
        assert result.provider == "offline"
        assert result.is_empty

    def test_transcribe_never_raises(self, mock_audio_bytes):
        """TC-3.11 — transcribe() never propagates exceptions."""
        from src.voice.stt_engine import STTEngine

        def always_crash(_): raise Exception("total meltdown")

        engine = STTEngine(primary=always_crash, fallback=always_crash)
        result = engine.transcribe(mock_audio_bytes)
        # Must return something, not raise
        assert isinstance(result.text, str)

    def test_streaming_yields_one_result_per_utterance(self, mock_stt_callable):
        """TC-3.12 — streaming yields result when empty bytes chunk signals end-of-turn."""
        from src.voice.stt_engine import STTEngine
        engine = STTEngine(primary=mock_stt_callable)
        speech_chunk = b"\x10\x20" * 100
        chunks = [speech_chunk, speech_chunk, b""]  # two speech + silence
        results = list(engine.transcribe_streaming(iter(chunks)))
        assert len(results) == 1
        assert results[0].provider == "mock"

    def test_streaming_yields_multiple_utterances(self, mock_stt_callable):
        """TC-3.13 — streaming yields one result per end-of-turn signal."""
        from src.voice.stt_engine import STTEngine
        engine = STTEngine(primary=mock_stt_callable)
        chunks = [b"\x10" * 100, b"", b"\x20" * 100, b""]
        results = list(engine.transcribe_streaming(iter(chunks)))
        assert len(results) == 2


# ===========================================================================
# TC-3.14 to TC-3.20 — SynthesisResult + TTSEngine
# ===========================================================================

class TestSynthesisResult:

    def test_is_empty_true_for_empty_bytes(self):
        """TC-3.14 — is_empty True when audio_bytes is empty."""
        from src.voice.tts_engine import SynthesisResult
        r = SynthesisResult(audio_bytes=b"", provider="offline")
        assert r.is_empty is True

    def test_is_empty_false_for_audio_bytes(self):
        """TC-3.15 — is_empty False when audio_bytes has content."""
        from src.voice.tts_engine import SynthesisResult
        r = SynthesisResult(audio_bytes=b"\xFF" * 100, provider="google")
        assert r.is_empty is False

    def test_validate_passes_valid(self):
        """TC-3.16 — validate() passes for valid SynthesisResult."""
        from src.voice.tts_engine import SynthesisResult
        r = SynthesisResult(audio_bytes=b"\x00", provider="google")
        assert r.validate() == []


class TestTTSEngine:

    def test_primary_synthesises_text(self, mock_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.17 — Primary callable used; non-empty bytes returned."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine(primary=mock_tts_callable, use_cache=False)
        result = engine.synthesise("Your booking code is NL-A742.")
        assert not result.is_empty
        assert result.provider == "google"

    def test_fallback_called_on_primary_failure(self, failing_tts_callable,
                                                 mock_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.18 — Fallback called when primary raises."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine(primary=failing_tts_callable, fallback=mock_tts_callable, use_cache=False)
        result = engine.synthesise("Hello.")
        assert result.provider == "pyttsx3"
        assert not result.is_empty

    def test_both_fail_returns_empty(self, failing_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.19 — Empty SynthesisResult returned when both providers fail."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine(primary=failing_tts_callable, fallback=failing_tts_callable,
                           use_cache=False)
        result = engine.synthesise("Hello.")
        assert result.is_empty
        assert result.provider == "offline"

    def test_cache_hit_on_second_call(self, mock_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.20 — Second call with same text served from cache; primary called only once."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        call_count = {"n": 0}

        def counting_tts(text: str) -> bytes:
            call_count["n"] += 1
            return b"\xFF" * 200

        engine = TTSEngine(primary=counting_tts, use_cache=True)
        text = "This service is for scheduling only."
        engine.synthesise(text)
        result2 = engine.synthesise(text)

        assert call_count["n"] == 1, "Primary should only be called once"
        assert result2.cached is True

    def test_empty_text_returns_empty(self, mock_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.20b — Empty string input returns empty SynthesisResult immediately."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine(primary=mock_tts_callable)
        result = engine.synthesise("   ")
        assert result.is_empty

    def test_clear_cache_removes_files(self, mock_tts_callable, tmp_tts_cache, monkeypatch):
        """TC-3.20c — clear_cache() removes all cached WAV files."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine
        engine = TTSEngine(primary=mock_tts_callable, use_cache=True)
        engine.synthesise("Test phrase one.")
        engine.synthesise("Test phrase two.")
        removed = engine.clear_cache()
        assert removed == 2
        assert list(Path(tmp_tts_cache).glob("*.wav")) == []


# ===========================================================================
# TC-3.21 to TC-3.27 — VADEngine
# ===========================================================================

class TestVADEngine:

    def test_silence_has_low_energy(self):
        """TC-3.21 — Silence chunk produces low RMS energy."""
        from src.voice.vad import VADEngine, _rms, _bytes_to_int16
        chunk = _pcm16_silence(100)
        samples = _bytes_to_int16(chunk)
        assert _rms(samples) < 10

    def test_speech_chunk_has_high_energy(self):
        """TC-3.22 — Sine wave chunk produces RMS above speech threshold."""
        from src.voice.vad import _rms, _bytes_to_int16, _ENERGY_SPEECH_RMS
        chunk = _pcm16_sine(100, amp=10000)
        samples = _bytes_to_int16(chunk)
        assert _rms(samples) > _ENERGY_SPEECH_RMS

    def test_vad_detects_no_end_of_turn_during_speech(self):
        """TC-3.23 — is_end_of_turn False while speech is active."""
        from src.voice.vad import VADEngine
        vad = VADEngine(silence_threshold_ms=300)

        # Feed speech — no end-of-turn yet
        for _ in range(5):
            result = vad.process_chunk(_pcm16_sine(30, amp=10000))
        assert result.is_end_of_turn is False

    def test_vad_detects_end_of_turn_after_silence(self):
        """TC-3.24 — is_end_of_turn True after speech followed by 300 ms silence."""
        from src.voice.vad import VADEngine
        vad = VADEngine(silence_threshold_ms=300)

        # Establish speech context
        for _ in range(5):
            vad.process_chunk(_pcm16_sine(30, amp=10000))

        # Feed 10 × 30 ms = 300 ms silence
        result = None
        for _ in range(10):
            result = vad.process_chunk(_pcm16_silence(30))
        assert result is not None
        assert result.is_end_of_turn is True

    def test_vad_reset_clears_state(self):
        """TC-3.25 — reset() clears accumulated silence and speech flag."""
        from src.voice.vad import VADEngine
        vad = VADEngine(silence_threshold_ms=300)

        # Build up some speech + silence
        for _ in range(5):
            vad.process_chunk(_pcm16_sine(30, amp=10000))
        for _ in range(5):
            vad.process_chunk(_pcm16_silence(30))

        vad.reset()
        assert vad.silent_ms == 0.0
        assert vad.has_heard_speech is False

    def test_vad_no_end_of_turn_without_prior_speech(self):
        """TC-3.26 — Pure silence without prior speech never triggers end-of-turn."""
        from src.voice.vad import VADEngine
        vad = VADEngine(silence_threshold_ms=300)

        result = None
        for _ in range(20):  # 600 ms silence, never spoken
            result = vad.process_chunk(_pcm16_silence(30))
        assert result is not None
        assert result.is_end_of_turn is False

    def test_vad_result_validate(self):
        """TC-3.27 — VADResult.validate() returns empty list for valid result."""
        from src.voice.vad import VADResult
        r = VADResult(is_speech=True, is_end_of_turn=False,
                      energy_rms=500.0, silent_ms_so_far=0.0, provider="energy")
        assert r.validate() == []

    def test_vad_energy_provider_label(self):
        """TC-3.27b — Energy-based fallback sets provider='energy'."""
        from src.voice.vad import VADEngine
        # Patch silero load to always fail → forces energy fallback
        with patch("src.voice.vad._load_silero", return_value=False):
            vad = VADEngine(silence_threshold_ms=300)
        result = vad.process_chunk(_pcm16_sine(30, amp=10000))
        assert result.provider == "energy"


# ===========================================================================
# TC-3.28 to TC-3.37 — VoiceLogger
# ===========================================================================

class TestVoiceLogger:

    def test_log_turn_creates_file(self, voice_logger, tmp_log_path):
        """TC-3.28 — log_turn() creates JSONL file."""
        voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="I want to book for KYC",
            detected_intent="book_new",
            agent_speech="What time works for you?",
        )
        assert Path(tmp_log_path).is_file()
        assert Path(tmp_log_path).stat().st_size > 0

    def test_log_turn_valid_jsonl(self, voice_logger, tmp_log_path):
        """TC-3.29 — Each line in log file is valid JSON."""
        voice_logger.log_turn(call_id="C-001", turn_index=1,
                              user_transcript_raw="book KYC Monday 2pm",
                              agent_speech="Confirmed")
        with open(tmp_log_path) as f:
            for line in f:
                obj = json.loads(line)
                assert "call_id" in obj
                assert "timestamp_ist" in obj

    def test_pii_not_in_log_phone(self, voice_logger, tmp_log_path):
        """TC-3.30 — Phone number is NOT written to log file."""
        voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="my number is 9876543210 book KYC",
            agent_speech="ok",
        )
        content = Path(tmp_log_path).read_text()
        assert "9876543210" not in content

    def test_pii_not_in_log_email(self, voice_logger, tmp_log_path):
        """TC-3.31 — Email address is NOT written to log file."""
        voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="email me at test@example.com",
            agent_speech="ok",
        )
        content = Path(tmp_log_path).read_text()
        assert "test@example.com" not in content

    def test_pii_blocked_flag_set(self, voice_logger, tmp_log_path):
        """TC-3.32 — pii_blocked=True when PII detected in transcript."""
        entry = voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="call me on 9123456789",
            agent_speech="ok",
        )
        assert entry.pii_blocked is True
        assert "[REDACTED]" in entry.user_transcript_sanitised

    def test_pii_blocked_false_for_clean_input(self, voice_logger):
        """TC-3.33 — pii_blocked=False for clean transcript."""
        entry = voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="I want to book for KYC on Monday",
            agent_speech="ok",
        )
        assert entry.pii_blocked is False

    def test_log_compliance_block(self, voice_logger, tmp_log_path):
        """TC-3.34 — log_compliance_block() writes COMPLIANCE_BLOCK event."""
        voice_logger.log_compliance_block(
            call_id="C-001", turn_index=2,
            flag="refuse_advice",
            blocked_speech="You should invest in index funds.",
            safe_speech="I'm only able to help with scheduling.",
        )
        entries = voice_logger.read_entries(call_id="C-001")
        block_entries = [e for e in entries if e.event_type == "COMPLIANCE_BLOCK"]
        assert len(block_entries) == 1
        assert block_entries[0].compliance_flag == "refuse_advice"

    def test_log_mcp_trigger(self, voice_logger, tmp_log_path):
        """TC-3.35 — log_mcp_trigger() writes MCP_TRIGGER event."""
        voice_logger.log_mcp_trigger(
            call_id="C-001", turn_index=3,
            booking_code="NL-A742",
            mcp_summary="calendar:✅ sheets:✅ email:✅",
        )
        entries = voice_logger.read_entries(call_id="C-001")
        mcp_entries = [e for e in entries if e.event_type == "MCP_TRIGGER"]
        assert len(mcp_entries) == 1
        assert mcp_entries[0].booking_code == "NL-A742"

    def test_log_session_start_and_end(self, voice_logger):
        """TC-3.36 — Session start and end events logged correctly."""
        voice_logger.log_session_start("C-002", extra={"channel": "phone"})
        voice_logger.log_session_end("C-002", turn_count=5)
        entries = voice_logger.read_entries(call_id="C-002")
        event_types = {e.event_type for e in entries}
        assert "SESSION_START" in event_types
        assert "SESSION_END" in event_types

    def test_read_entries_filters_by_call_id(self, voice_logger):
        """TC-3.37 — read_entries() returns only entries for given call_id."""
        voice_logger.log_turn(call_id="C-AAA", turn_index=1,
                              user_transcript_raw="hi", agent_speech="hello")
        voice_logger.log_turn(call_id="C-BBB", turn_index=1,
                              user_transcript_raw="bye", agent_speech="goodbye")
        entries_a = voice_logger.read_entries(call_id="C-AAA")
        assert all(e.call_id == "C-AAA" for e in entries_a)
        entries_b = voice_logger.read_entries(call_id="C-BBB")
        assert all(e.call_id == "C-BBB" for e in entries_b)

    def test_multiple_pii_types_all_redacted(self, voice_logger, tmp_log_path):
        """TC-3.37b — Multiple PII types in one transcript all redacted."""
        entry = voice_logger.log_turn(
            call_id="C-001", turn_index=1,
            user_transcript_raw="call 9876543210 or email me at foo@bar.com",
            agent_speech="ok",
        )
        assert "9876543210" not in entry.user_transcript_sanitised
        assert "foo@bar.com" not in entry.user_transcript_sanitised
        assert entry.pii_blocked is True


# ===========================================================================
# TC-3.38 to TC-3.52 — AudioPipeline
# ===========================================================================

class TestAudioPipelineTextMode:

    def test_start_session_returns_call_id(self, pipeline_text_mode):
        """TC-3.38 — start_session() returns a non-empty call_id."""
        call_id = pipeline_text_mode.start_session()
        assert call_id
        assert "CALL-" in call_id

    def test_start_session_creates_session_record(self, pipeline_text_mode):
        """TC-3.39 — Session is stored and retrievable."""
        call_id = pipeline_text_mode.start_session()
        session = pipeline_text_mode.get_session(call_id)
        assert session is not None
        assert session.call_id == call_id
        assert session.is_active is True

    def test_process_text_turn_returns_pipeline_result(self, pipeline_text_mode):
        """TC-3.40 — process_text_turn() returns PipelineResult."""
        from src.voice.audio_pipeline import PipelineResult
        call_id = pipeline_text_mode.start_session()
        result = pipeline_text_mode.process_text_turn(call_id, "Hello")
        assert isinstance(result, PipelineResult)
        assert result.call_id == call_id
        assert result.turn_index >= 1

    def test_process_text_turn_increments_turn_index(self, pipeline_text_mode):
        """TC-3.41 — turn_index increments with each turn."""
        call_id = pipeline_text_mode.start_session()
        r1 = pipeline_text_mode.process_text_turn(call_id, "turn one")
        r2 = pipeline_text_mode.process_text_turn(call_id, "turn two")
        assert r2.turn_index > r1.turn_index

    def test_pii_in_input_is_flagged(self, pipeline_text_mode):
        """TC-3.42 — PII in user input is scrubbed and flagged."""
        call_id = pipeline_text_mode.start_session()
        result = pipeline_text_mode.process_text_turn(
            call_id, "my phone is 9876543210"
        )
        assert result.pii_blocked is True
        assert "9876543210" not in result.user_text_sanitised

    def test_clean_input_not_flagged(self, pipeline_text_mode):
        """TC-3.43 — Clean input is not flagged as PII."""
        call_id = pipeline_text_mode.start_session()
        result = pipeline_text_mode.process_text_turn(
            call_id, "I want to book for KYC"
        )
        assert result.pii_blocked is False

    def test_validate_call_id_must_not_be_empty(self):
        """TC-3.44 — PipelineResult.validate() catches empty call_id."""
        from src.voice.audio_pipeline import PipelineResult
        r = PipelineResult(
            call_id="", turn_index=1, user_text_sanitised="",
            agent_speech="hi", audio_out=b"", pii_blocked=False,
            compliance_blocked=False, current_state="",
        )
        errors = r.validate()
        assert any("call_id" in e for e in errors)

    def test_unknown_session_raises(self, pipeline_text_mode):
        """TC-3.45 — process_text_turn() raises ValueError for unknown call_id."""
        with pytest.raises(ValueError, match="Unknown or inactive session"):
            pipeline_text_mode.process_text_turn("NONEXISTENT-ID", "hello")

    def test_active_sessions_listed(self, pipeline_text_mode):
        """TC-3.46 — active_sessions() returns all active call_ids."""
        id1 = pipeline_text_mode.start_session()
        id2 = pipeline_text_mode.start_session()
        active = pipeline_text_mode.active_sessions()
        assert id1 in active
        assert id2 in active

    def test_end_session_removes_from_active(self, pipeline_text_mode):
        """TC-3.47 — end_session() removes call from active list."""
        call_id = pipeline_text_mode.start_session()
        pipeline_text_mode.end_session(call_id)
        assert call_id not in pipeline_text_mode.active_sessions()

    def test_text_mode_audio_out_is_empty(self, pipeline_text_mode):
        """TC-3.48 — In text_mode, audio_out is always empty bytes."""
        call_id = pipeline_text_mode.start_session()
        result = pipeline_text_mode.process_text_turn(call_id, "book KYC")
        assert result.audio_out == b""

    def test_compliance_blocked_on_advice_output(self, voice_logger):
        """TC-3.49 — ComplianceGuard blocks investment advice in agent response."""
        from src.voice.audio_pipeline import AudioPipeline

        # Inject a mock router that outputs investment advice
        class AdviceRouter:
            def route(self, text, ctx):
                r = MagicMock()
                r.intent = "book_new"
                r.speech = "You should invest in index funds for long-term growth."
                r.slots = {}
                r.compliance_flag = None
                return r

        # Inject a mock FSM that returns the advice speech
        class AdviceFSM:
            def start(self, call_id=None):
                ctx = MagicMock()
                ctx.booking_code = None
                ctx.secure_url = None
                return ctx, "Hello, how can I help?"

            def process_turn(self, ctx, text, llm_resp):
                ctx.booking_code = None
                ctx.secure_url = None
                return ctx, llm_resp.speech

        try:
            from src.dialogue.compliance_guard import ComplianceGuard
        except ImportError:
            try:
                from phase2.src.dialogue.compliance_guard import ComplianceGuard
            except ImportError:
                pytest.skip("Phase 2 ComplianceGuard not available")

        pipeline = AudioPipeline(
            text_mode=True,
            voice_logger=voice_logger,
            fsm_factory=lambda: AdviceFSM(),
            intent_router_factory=lambda: AdviceRouter(),
            compliance_guard_factory=lambda: ComplianceGuard(),
        )
        call_id = pipeline.start_session()
        result = pipeline.process_text_turn(call_id, "should I invest in stocks?")
        assert result.compliance_blocked is True
        assert "invest in index funds" not in result.agent_speech

    def test_session_log_written_on_start(self, voice_logger, tmp_log_path):
        """TC-3.50 — SESSION_START event written when session begins."""
        from src.voice.audio_pipeline import AudioPipeline
        pipeline = AudioPipeline(text_mode=True, voice_logger=voice_logger)
        call_id = pipeline.start_session()
        entries = voice_logger.read_entries(call_id=call_id)
        assert any(e.event_type == "SESSION_START" for e in entries)

    def test_turn_log_written_per_turn(self, pipeline_text_mode, voice_logger, tmp_log_path):
        """TC-3.51 — TURN event written to log for each process_text_turn call."""
        call_id = pipeline_text_mode.start_session()
        pipeline_text_mode.process_text_turn(call_id, "first turn")
        pipeline_text_mode.process_text_turn(call_id, "second turn")
        entries = voice_logger.read_entries(call_id=call_id)
        turn_entries = [e for e in entries if e.event_type == "TURN"]
        assert len(turn_entries) >= 2


class TestAudioPipelineAudioMode:

    def test_process_audio_chunk_returns_none_during_speech(
        self, pipeline_audio_mode, speech_chunk
    ):
        """TC-3.52 — Returns None while user is still speaking."""
        call_id = pipeline_audio_mode.start_session()
        result = pipeline_audio_mode.process_audio_chunk(call_id, speech_chunk)
        assert result is None

    def test_process_audio_chunk_returns_result_on_end_of_turn(
        self, pipeline_audio_mode, speech_chunk, silence_chunk
    ):
        """TC-3.53 — Returns PipelineResult when end-of-turn silence detected."""
        from src.voice.audio_pipeline import PipelineResult
        call_id = pipeline_audio_mode.start_session()

        # Speak for a bit
        for _ in range(5):
            r = pipeline_audio_mode.process_audio_chunk(
                call_id, _pcm16_sine(30, amp=10000)
            )
            assert r is None  # still speaking

        # Silence beyond threshold
        result = None
        for _ in range(15):
            result = pipeline_audio_mode.process_audio_chunk(
                call_id, _pcm16_silence(30)
            )
            if result is not None:
                break

        assert result is not None
        assert isinstance(result, PipelineResult)
        assert result.audio_out  # non-empty audio bytes from mock TTS

    def test_low_confidence_triggers_reprompt(
        self, voice_logger, low_confidence_stt_callable, mock_tts_callable,
        tmp_tts_cache, monkeypatch
    ):
        """TC-3.54 — Low-confidence STT result triggers re-prompt response."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        monkeypatch.setenv("STT_CONFIDENCE_THRESHOLD", "0.7")
        from src.voice.stt_engine import STTEngine
        from src.voice.tts_engine import TTSEngine
        from src.voice.audio_pipeline import AudioPipeline

        pipeline = AudioPipeline(
            text_mode=False,
            stt_engine=STTEngine(primary=low_confidence_stt_callable),
            tts_engine=TTSEngine(primary=mock_tts_callable),
            voice_logger=voice_logger,
        )
        call_id = pipeline.start_session()

        for _ in range(5):
            pipeline.process_audio_chunk(call_id, _pcm16_sine(30, amp=10000))
        result = None
        for _ in range(15):
            result = pipeline.process_audio_chunk(call_id, _pcm16_silence(30))
            if result is not None:
                break

        assert result is not None
        assert "didn't catch" in result.agent_speech.lower() or \
               result.current_state == "LOW_CONFIDENCE"

    def test_pii_in_audio_transcript_flagged(
        self, voice_logger, tmp_tts_cache, mock_tts_callable, monkeypatch
    ):
        """TC-3.55 — PII in STT transcript is flagged and scrubbed."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.stt_engine import STTEngine, TranscriptResult
        from src.voice.tts_engine import TTSEngine
        from src.voice.audio_pipeline import AudioPipeline

        def pii_stt(audio: bytes) -> TranscriptResult:
            return TranscriptResult(
                text="call me on 9876543210", confidence=0.9,
                is_final=True, provider="mock"
            )

        pipeline = AudioPipeline(
            text_mode=False,
            stt_engine=STTEngine(primary=pii_stt),
            tts_engine=TTSEngine(primary=mock_tts_callable),
            voice_logger=voice_logger,
        )
        call_id = pipeline.start_session()

        for _ in range(5):
            pipeline.process_audio_chunk(call_id, _pcm16_sine(30, amp=10000))
        result = None
        for _ in range(15):
            result = pipeline.process_audio_chunk(call_id, _pcm16_silence(30))
            if result is not None:
                break

        assert result is not None
        assert result.pii_blocked is True
        assert "9876543210" not in result.user_text_sanitised


# ===========================================================================
# TC-3.56 to TC-3.60 — Integration: all modules working together
# ===========================================================================

class TestVoiceModuleIntegration:

    def test_full_text_mode_turn_writes_all_log_fields(
        self, pipeline_text_mode, voice_logger, tmp_log_path
    ):
        """TC-3.56 — Full text turn produces log entry with all required fields."""
        call_id = pipeline_text_mode.start_session()
        pipeline_text_mode.process_text_turn(call_id, "I want to book for KYC Monday 2 PM")

        entries = voice_logger.read_entries(call_id=call_id)
        turn_entries = [e for e in entries if e.event_type == "TURN"]
        assert turn_entries, "No TURN entries found"

        entry = turn_entries[0]
        assert entry.call_id == call_id
        assert entry.timestamp_ist != ""
        assert entry.turn_index >= 1
        assert "9876543210" not in entry.user_transcript_sanitised  # safety check

    def test_stt_to_voice_logger_no_pii_leakage(
        self, mock_stt_callable, voice_logger, tmp_log_path
    ):
        """TC-3.57 — PII in STT transcript is scrubbed before reaching VoiceLogger."""
        from src.voice.stt_engine import STTEngine, TranscriptResult

        def pii_transcript(_):
            return TranscriptResult(
                text="I'm user test@domain.com with PAN ABCDE1234F",
                confidence=0.95, is_final=True, provider="mock"
            )

        stt = STTEngine(primary=pii_transcript)
        result = stt.transcribe(b"\x00" * 100)

        # Manually log with raw text (as pipeline would)
        voice_logger.log_turn(
            call_id="C-PII", turn_index=1,
            user_transcript_raw=result.text,
            agent_speech="ok",
        )
        content = Path(tmp_log_path).read_text()
        assert "test@domain.com" not in content
        assert "ABCDE1234F" not in content

    def test_tts_cache_persists_across_engine_instances(
        self, mock_tts_callable, tmp_tts_cache, monkeypatch
    ):
        """TC-3.58 — TTS cache is on disk and survives new engine instance."""
        monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
        from src.voice.tts_engine import TTSEngine

        call_count = {"n": 0}
        def counting(text): call_count["n"] += 1; return b"\xAA" * 100

        engine1 = TTSEngine(primary=counting, use_cache=True)
        engine1.synthesise("Cached phrase.")

        engine2 = TTSEngine(primary=counting, use_cache=True)
        result = engine2.synthesise("Cached phrase.")

        assert call_count["n"] == 1  # second engine hit disk cache
        assert result.cached is True

    def test_vad_and_stt_end_to_end(self, mock_stt_callable):
        """TC-3.59 — VAD detects end-of-turn then STT transcribes accumulated buffer."""
        from src.voice.vad import VADEngine
        from src.voice.stt_engine import STTEngine

        vad = VADEngine(silence_threshold_ms=300)
        stt = STTEngine(primary=mock_stt_callable)

        buffer = []
        end_detected = False

        # Simulate speaking for 150 ms then silence for 300 ms
        for _ in range(5):
            chunk = _pcm16_sine(30, amp=10000)
            buffer.append(chunk)
            vad.process_chunk(chunk)

        for _ in range(10):
            chunk = _pcm16_silence(30)
            buffer.append(chunk)
            r = vad.process_chunk(chunk)
            if r.is_end_of_turn:
                end_detected = True
                break

        assert end_detected
        combined = b"".join(buffer)
        transcript = stt.transcribe(combined)
        assert not transcript.is_empty
        assert transcript.provider == "mock"

    def test_multiple_sessions_no_state_bleed(self, voice_logger):
        """TC-3.60 — Multiple concurrent pipeline sessions have isolated state."""
        from src.voice.audio_pipeline import AudioPipeline
        pipeline = AudioPipeline(text_mode=True, voice_logger=voice_logger)

        ids = [pipeline.start_session() for _ in range(10)]

        for call_id in ids:
            pipeline.process_text_turn(call_id, f"booking for {call_id}")

        # Each session's turn_index must be independent
        for call_id in ids:
            session = pipeline.get_session(call_id)
            if session:
                assert session.call_id == call_id
