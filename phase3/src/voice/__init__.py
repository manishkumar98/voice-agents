"""
Phase 3 — Voice Integration Layer.

Public API::

    from src.voice import (
        STTEngine, TranscriptResult,
        TTSEngine, SynthesisResult,
        VADEngine, VADResult,
        VoiceLogger, VoiceLogEntry,
        AudioPipeline, PipelineResult,
    )
"""
from __future__ import annotations

from .stt_engine import STTEngine, TranscriptResult
from .tts_engine import TTSEngine, SynthesisResult
from .vad import VADEngine, VADResult
from .voice_logger import VoiceLogger, VoiceLogEntry
from .audio_pipeline import AudioPipeline, PipelineResult, PipelineSession

__all__ = [
    # STT
    "STTEngine",
    "TranscriptResult",
    # TTS
    "TTSEngine",
    "SynthesisResult",
    # VAD
    "VADEngine",
    "VADResult",
    # Logger
    "VoiceLogger",
    "VoiceLogEntry",
    # Pipeline
    "AudioPipeline",
    "PipelineResult",
    "PipelineSession",
]
