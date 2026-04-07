"""
STT Engine — Speech-to-Text abstraction.

Provider priority (first available wins):
  1. Groq Whisper (whisper-large-v3) — fast, accurate, supports Hindi + Indian English
     Set GROQ_API_KEY. Language auto-detected or overridden by STT_LANGUAGE.
  2. Google Cloud Speech-to-Text v2 — Indian English (en-IN) / Hindi (hi-IN)
     Set GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON
  3. Deepgram Nova-2 — good Hindi-English code-switching fallback
     Set DEEPGRAM_API_KEY
  4. Offline stub — returns empty transcript

Language env vars:
  STT_LANGUAGE = "en-IN" | "hi-IN" | "" (auto-detect, default)
  When "hi-IN", Groq Whisper uses language="hi" for best accuracy.

Designed to be fully injectable for testing — pass a custom
``stt_callable`` to bypass real API calls.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
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
        if self.provider not in {"groq", "google", "deepgram", "offline", "mock", "unknown"}:
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

def _groq_transcribe(audio_bytes: bytes) -> TranscriptResult:
    """
    Transcribe via Groq Whisper (whisper-large-v3).
    Requires: GROQ_API_KEY

    Supports Indian English and Hindi natively.
    STT_LANGUAGE="hi-IN" forces Hindi decoding for best accuracy.
    Leave blank for automatic language detection.
    """
    t0 = time.monotonic()
    try:
        from groq import Groq  # type: ignore[import]
        import tempfile

        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set")

        # Map STT_LANGUAGE to Whisper language code
        _lang_map = {"en-IN": "en", "hi-IN": "hi", "en": "en", "hi": "hi"}
        stt_lang = os.environ.get("STT_LANGUAGE", "").strip()
        whisper_lang = _lang_map.get(stt_lang) or None  # None = auto-detect

        client = Groq(api_key=api_key)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as af:
                kwargs: dict = dict(
                    model="whisper-large-v3",
                    file=("audio.wav", af, "audio/wav"),
                    response_format="verbose_json",
                )
                if whisper_lang:
                    kwargs["language"] = whisper_lang
                result = client.audio.transcriptions.create(**kwargs)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        text = getattr(result, "text", "") or ""
        # Groq verbose_json includes avg_logprob as a proxy for confidence
        avg_logprob = getattr(result, "avg_logprob", None)
        confidence = min(1.0, max(0.0, float(avg_logprob) + 1.0)) if avg_logprob is not None else 0.9

        return TranscriptResult(
            text=text.strip(),
            confidence=confidence,
            is_final=True,
            provider="groq",
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    except ImportError:
        logger.warning("groq package not installed; skipping Groq STT")
        raise
    except Exception as exc:
        logger.error("Groq STT failed: %s", exc)
        raise


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
        self._timeout_s = float(os.environ.get("STT_SILENCE_TIMEOUT_SECONDS", "3"))
        # Injectable primary for tests; otherwise build Groq → Google → Deepgram chain
        if primary is not None:
            self._providers: list[tuple[STTCallable, str]] = [
                (primary, "mock"),
                (fallback or _offline_transcribe, "fallback"),
            ]
        else:
            self._providers = [
                (_groq_transcribe, "groq"),
                (_google_transcribe, "google"),
                (_deepgram_transcribe, "deepgram"),
                (_offline_transcribe, "offline"),
            ]

    # ------------------------------------------------------------------
    def transcribe(self, audio_bytes: bytes) -> TranscriptResult:
        """
        Transcribe audio bytes to text.

        Tries Groq Whisper → Google STT → Deepgram → offline stub.
        Set STT_LANGUAGE="hi-IN" for Hindi, "en-IN" for Indian English (default auto).
        Never raises — always returns a TranscriptResult.
        """
        if not audio_bytes:
            return TranscriptResult(
                text="", confidence=0.0, is_final=True, provider="offline"
            )

        for provider_fn, label in self._providers:
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