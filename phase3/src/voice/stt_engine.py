"""
STT Engine — Speech-to-Text abstraction.

Primary:  Google Cloud Speech-to-Text v2 (streaming, en-IN)
Fallback: Deepgram Nova-2 (lower latency, good Hindi-English code-switch)
Offline:  Returns empty TranscriptResult with confidence=0.0

Designed to be fully injectable for testing — pass a custom
``stt_callable`` to bypass real API calls.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TranscriptResult:
    """Immutable result from a single STT call."""

    text: str
    confidence: float          # 0.0–1.0
    is_final: bool
    provider: str = "unknown"  # "google" | "deepgram" | "offline" | "mock"
    duration_ms: float = 0.0

    # ------------------------------------------------------------------
    @property
    def is_reliable(self) -> bool:
        """True when confidence meets or exceeds the configured threshold."""
        threshold = float(os.environ.get("STT_CONFIDENCE_THRESHOLD", "0.7"))
        return self.confidence >= threshold

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not isinstance(self.text, str):
            errors.append("text must be str")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence {self.confidence!r} out of [0, 1]")
        if self.provider not in {"google", "deepgram", "offline", "mock", "unknown"}:
            errors.append(f"unknown provider {self.provider!r}")
        return errors


# ---------------------------------------------------------------------------
# STTCallable type alias
# ---------------------------------------------------------------------------

# Signature: (audio_bytes: bytes) -> TranscriptResult
STTCallable = Callable[[bytes], TranscriptResult]


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _google_transcribe(audio_bytes: bytes) -> TranscriptResult:
    """
    Call Google Cloud Speech-to-Text v2 REST / gRPC.
    Requires: GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON
    Language:  en-IN (Indian English)
    """
    t0 = time.monotonic()
    try:
        from google.cloud import speech  # type: ignore[import]
        from google.oauth2 import service_account  # type: ignore[import]

        sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "")
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

        if sa_json:
            import json as _json
            info = _json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        elif sa_path and os.path.isfile(sa_path):
            creds = service_account.Credentials.from_service_account_file(
                sa_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            raise RuntimeError("No Google credentials configured")

        client = speech.SpeechClient(credentials=creds)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-IN",
            enable_automatic_punctuation=True,
            model="latest_long",
        )
        response = client.recognize(config=config, audio=audio)

        if not response.results:
            return TranscriptResult(
                text="", confidence=0.0, is_final=True,
                provider="google",
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        best = response.results[0].alternatives[0]
        return TranscriptResult(
            text=best.transcript.strip(),
            confidence=best.confidence,
            is_final=True,
            provider="google",
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    except ImportError:
        logger.warning("google-cloud-speech not installed; skipping Google STT")
        raise
    except Exception as exc:
        logger.error("Google STT failed: %s", exc)
        raise


def _deepgram_transcribe(audio_bytes: bytes) -> TranscriptResult:
    """
    Call Deepgram Nova-2 REST API.
    Requires: DEEPGRAM_API_KEY
    """
    t0 = time.monotonic()
    try:
        from deepgram import DeepgramClient, PrerecordedOptions  # type: ignore[import]

        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPGRAM_API_KEY not set")

        client = DeepgramClient(api_key)
        options = PrerecordedOptions(
            model="nova-2",
            language="en-IN",
            punctuate=True,
            smart_format=True,
        )
        response = client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_bytes, "mimetype": "audio/wav"}, options
        )
        channel = response["results"]["channels"][0]
        alt = channel["alternatives"][0]
        return TranscriptResult(
            text=alt.get("transcript", "").strip(),
            confidence=alt.get("confidence", 0.0),
            is_final=True,
            provider="deepgram",
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    except ImportError:
        logger.warning("deepgram-sdk not installed; skipping Deepgram STT")
        raise
    except Exception as exc:
        logger.error("Deepgram STT failed: %s", exc)
        raise


def _offline_transcribe(_audio_bytes: bytes) -> TranscriptResult:
    """Last-resort offline stub — returns empty with zero confidence."""
    logger.warning(
        "STT: both Google and Deepgram unavailable; returning empty transcript"
    )
    return TranscriptResult(
        text="", confidence=0.0, is_final=True, provider="offline"
    )


# ---------------------------------------------------------------------------
# STTEngine
# ---------------------------------------------------------------------------

class STTEngine:
    """
    Speech-to-Text engine with automatic provider fallback.

    Usage::

        engine = STTEngine()
        result = engine.transcribe(audio_bytes)

    Inject a custom callable for testing::

        engine = STTEngine(primary=my_mock_fn)
    """

    def __init__(
        self,
        primary: STTCallable | None = None,
        fallback: STTCallable | None = None,
    ) -> None:
        self._primary: STTCallable = primary or _google_transcribe
        self._fallback: STTCallable = fallback or _deepgram_transcribe
        self._timeout_s = float(os.environ.get("STT_SILENCE_TIMEOUT_SECONDS", "3"))

    # ------------------------------------------------------------------
    def transcribe(self, audio_bytes: bytes) -> TranscriptResult:
        """
        Transcribe audio bytes to text.

        Tries primary provider, then fallback, then offline stub.
        Never raises — always returns a TranscriptResult.
        """
        if not audio_bytes:
            return TranscriptResult(
                text="", confidence=0.0, is_final=True, provider="offline"
            )

        for provider_fn, label in [
            (self._primary, "primary"),
            (self._fallback, "fallback"),
            (_offline_transcribe, "offline"),
        ]:
            try:
                result = provider_fn(audio_bytes)
                if label != "offline":
                    logger.debug(
                        "STT [%s]: %.0f ms | conf=%.2f | %r",
                        result.provider, result.duration_ms,
                        result.confidence, result.text[:60],
                    )
                return result
            except Exception:
                if label == "offline":
                    # offline stub itself failed — return a safe default
                    return TranscriptResult(
                        text="", confidence=0.0, is_final=True, provider="offline"
                    )
                logger.warning("STT %s provider failed; trying next", label)

        # Should never reach here
        return TranscriptResult(text="", confidence=0.0, is_final=True, provider="offline")

    # ------------------------------------------------------------------
    def transcribe_streaming(
        self, audio_chunks: Iterator[bytes]
    ) -> Iterator[TranscriptResult]:
        """
        Yield TranscriptResult for each audio chunk.

        This is a simplified streaming interface — collects chunks until
        silence (empty bytes chunk signals end-of-turn) then transcribes.
        """
        buffer: list[bytes] = []
        for chunk in audio_chunks:
            if chunk:
                buffer.append(chunk)
            else:
                # Empty chunk = end-of-turn signal
                if buffer:
                    combined = b"".join(buffer)
                    yield self.transcribe(combined)
                    buffer = []

        # Flush remaining
        if buffer:
            yield self.transcribe(b"".join(buffer))


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_engine: STTEngine | None = None


def get_default_engine() -> STTEngine:
    """Return the module-level singleton STTEngine (lazy init)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = STTEngine()
    return _default_engine


def transcribe(audio_bytes: bytes) -> TranscriptResult:
    """Convenience wrapper using the default engine."""
    return get_default_engine().transcribe(audio_bytes)