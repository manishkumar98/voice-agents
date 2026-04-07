"""
Phase 3 test configuration.

Sets up sys.path so all phase modules are importable, loads .env,
and provides shared fixtures for audio data, mock engines, and tmp paths.
"""
from __future__ import annotations

import os
import struct
import sys
import math
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — mirrors phase4/tests/conftest.py pattern
# ---------------------------------------------------------------------------

_tests_dir  = Path(__file__).resolve().parent
_phase3_dir = _tests_dir.parent
_root_dir   = _phase3_dir.parent

for _entry in [
    str(_root_dir / "phase0"),
    str(_root_dir / "phase1"),
    str(_root_dir / "phase2"),
    str(_phase3_dir),
]:
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(str(_root_dir / ".env"))
except ImportError:
    pass

# Point mock calendar at phase1 fixture
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    str(_root_dir / "phase1" / "data" / "mock_calendar.json"),
)

# ---------------------------------------------------------------------------
# Audio generation helpers
# ---------------------------------------------------------------------------

def _pcm16_silence(duration_ms: int = 300, sample_rate: int = 16_000) -> bytes:
    """Return PCM16 silence chunk of given duration."""
    n_samples = int(sample_rate * duration_ms / 1000)
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def _pcm16_sine(
    duration_ms: int = 100,
    frequency: float = 440.0,
    amplitude: int = 8000,
    sample_rate: int = 16_000,
) -> bytes:
    """Return PCM16 sine-wave chunk (simulates speech energy)."""
    n_samples = int(sample_rate * duration_ms / 1000)
    samples = [
        int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        for i in range(n_samples)
    ]
    return struct.pack(f"<{n_samples}h", *samples)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def silence_chunk() -> bytes:
    """300 ms of PCM16 silence."""
    return _pcm16_silence(300)


@pytest.fixture
def speech_chunk() -> bytes:
    """200 ms of PCM16 sine wave (simulates speech energy above threshold)."""
    return _pcm16_sine(200, amplitude=10000)


@pytest.fixture
def long_speech_chunk() -> bytes:
    """1000 ms of PCM16 sine wave."""
    return _pcm16_sine(1000, amplitude=10000)


@pytest.fixture
def mock_audio_bytes() -> bytes:
    """Short non-empty byte sequence used as a stand-in for real audio."""
    return b"\x00\x01" * 512


@pytest.fixture
def tmp_log_path(tmp_path) -> str:
    """Path to a temp JSONL log file."""
    return str(tmp_path / "voice_audit.jsonl")


@pytest.fixture
def tmp_tts_cache(tmp_path) -> str:
    """Path to a temp TTS cache directory."""
    cache = tmp_path / "tts_cache"
    cache.mkdir()
    return str(cache)


@pytest.fixture
def mock_stt_callable():
    """
    Returns a STT callable that echoes a fixed transcript.
    Used to inject into STTEngine for deterministic tests.
    """
    from src.voice.stt_engine import TranscriptResult

    def _fn(audio_bytes: bytes) -> TranscriptResult:
        return TranscriptResult(
            text="I want to book for KYC on Monday at 2 PM",
            confidence=0.95,
            is_final=True,
            provider="mock",
        )
    return _fn


@pytest.fixture
def low_confidence_stt_callable():
    """STT callable that always returns low-confidence result."""
    from src.voice.stt_engine import TranscriptResult

    def _fn(audio_bytes: bytes) -> TranscriptResult:
        return TranscriptResult(
            text="mumble mumble",
            confidence=0.3,
            is_final=True,
            provider="mock",
        )
    return _fn


@pytest.fixture
def failing_stt_callable():
    """STT callable that always raises (simulates API failure)."""
    def _fn(audio_bytes: bytes):
        raise ConnectionError("Simulated STT API failure")
    return _fn


@pytest.fixture
def mock_tts_callable():
    """TTS callable that returns deterministic mock audio bytes."""
    def _fn(text: str) -> bytes:
        # Return bytes proportional to text length so tests can verify
        return (b"\xFF\xFB" * max(1, len(text) // 2))
    return _fn


@pytest.fixture
def failing_tts_callable():
    """TTS callable that always raises."""
    def _fn(text: str) -> bytes:
        raise ConnectionError("Simulated TTS API failure")
    return _fn


@pytest.fixture
def voice_logger(tmp_log_path):
    """VoiceLogger writing to a temp file."""
    from src.voice.voice_logger import VoiceLogger
    return VoiceLogger(log_path=tmp_log_path)


@pytest.fixture
def stt_engine(mock_stt_callable):
    """STTEngine with mocked primary (no real API calls)."""
    from src.voice.stt_engine import STTEngine
    return STTEngine(primary=mock_stt_callable)


@pytest.fixture
def tts_engine(mock_tts_callable, tmp_tts_cache, monkeypatch):
    """TTSEngine with mocked primary and temp cache dir."""
    monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
    from src.voice.tts_engine import TTSEngine
    return TTSEngine(primary=mock_tts_callable)


@pytest.fixture
def pipeline_text_mode(voice_logger):
    """AudioPipeline in text mode with a fresh VoiceLogger."""
    from src.voice.audio_pipeline import AudioPipeline
    return AudioPipeline(text_mode=True, voice_logger=voice_logger)


@pytest.fixture
def pipeline_audio_mode(mock_stt_callable, mock_tts_callable, voice_logger,
                        tmp_tts_cache, monkeypatch):
    """AudioPipeline in audio mode with mocked STT/TTS."""
    monkeypatch.setenv("TTS_CACHE_DIR", tmp_tts_cache)
    # Override .env value so 300 ms silence (10 × 30 ms chunks) triggers end-of-turn
    monkeypatch.setenv("STT_SILENCE_TIMEOUT_SECONDS", "0.3")
    from src.voice.stt_engine import STTEngine
    from src.voice.tts_engine import TTSEngine
    from src.voice.vad import VADEngine
    from src.voice.audio_pipeline import AudioPipeline
    return AudioPipeline(
        text_mode=False,
        stt_engine=STTEngine(primary=mock_stt_callable),
        tts_engine=TTSEngine(primary=mock_tts_callable),
        vad_factory=lambda: VADEngine(silence_threshold_ms=300),
        voice_logger=voice_logger,
    )
