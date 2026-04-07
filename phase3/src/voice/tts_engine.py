"""
TTS Engine — Text-to-Speech abstraction.

Primary:  Google Cloud Text-to-Speech Neural2  (en-IN-Neural2-A, Indian English)
Fallback: pyttsx3  (local, zero-cost, no network)

Features
--------
- Hash-based disk cache: repeated phrases (disclaimers, greetings) are
  synthesised once and served from disk on subsequent calls.
- Cache TTL configurable via TTS_CACHE_TTL_DAYS  (default 7).
- Graceful degradation: if both providers fail, returns empty bytes and
  logs an error — callers must handle empty audio.
- Injectable ``tts_callable`` for unit-testing without any audio SDK.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SynthesisResult:
    """Result from a single TTS call."""

    audio_bytes: bytes
    provider: str = "unknown"   # "google" | "pyttsx3" | "offline" | "mock"
    cached: bool = False
    duration_ms: float = 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.audio_bytes) == 0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not isinstance(self.audio_bytes, bytes):
            errors.append("audio_bytes must be bytes")
        if self.provider not in {"google", "pyttsx3", "offline", "mock", "unknown"}:
            errors.append(f"unknown provider {self.provider!r}")
        return errors


# ---------------------------------------------------------------------------
# TTSCallable type alias
# ---------------------------------------------------------------------------

# Signature: (text: str) -> bytes
TTSCallable = Callable[[str], bytes]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(text: str, voice: str) -> str:
    """Return a deterministic filename for the given text+voice combo."""
    digest = hashlib.md5(f"{voice}|{text}".encode("utf-8")).hexdigest()
    return f"{digest}.wav"


def _cache_dir() -> Path:
    raw = os.environ.get("TTS_CACHE_DIR", "data/tts_cache")
    if os.path.isabs(raw):
        p = Path(raw)
    else:
        # Resolve relative to repo root (two levels above this file)
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / raw
            if candidate.parent.exists() or parent.name in ("phase3", "voice-agent"):
                p = candidate
                break
        else:
            p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_ttl_seconds() -> float:
    days = float(os.environ.get("TTS_CACHE_TTL_DAYS", "7"))
    return days * 86_400


def _read_cache(key: str) -> bytes | None:
    """Return cached bytes if file exists and is not expired, else None."""
    path = _cache_dir() / key
    if not path.is_file():
        return None
    age = time.time() - path.stat().st_mtime
    if age > _cache_ttl_seconds():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return path.read_bytes()


def _write_cache(key: str, audio_bytes: bytes) -> None:
    try:
        (_cache_dir() / key).write_bytes(audio_bytes)
    except OSError as exc:
        logger.warning("TTS cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _google_synthesise(text: str) -> bytes:
    """
    Synthesise text using Google Cloud Text-to-Speech Neural2 (en-IN-Neural2-A).
    Requires: GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON
    """
    try:
        from google.cloud import texttospeech  # type: ignore[import]
        from google.oauth2 import service_account  # type: ignore[import]

        voice_name = os.environ.get("TTS_VOICE_NAME", "en-IN-Neural2-A")
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

        client = texttospeech.TextToSpeechClient(credentials=creds)
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-IN",
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=0.95,    # slightly slower for voice UX clarity
            pitch=0.0,
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return response.audio_content

    except ImportError:
        logger.warning("google-cloud-texttospeech not installed; skipping Google TTS")
        raise
    except Exception as exc:
        logger.error("Google TTS failed: %s", exc)
        raise


def _pyttsx3_synthesise(text: str) -> bytes:
    """
    Synthesise text locally using pyttsx3 (zero-cost, offline fallback).
    Saves to a temp WAV file and returns the bytes.
    """
    try:
        import io
        import tempfile

        import pyttsx3  # type: ignore[import]

        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.setProperty("volume", 1.0)

        # pyttsx3 can save to file; read back as bytes
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as fh:
                audio_bytes = fh.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not audio_bytes:
            raise RuntimeError("pyttsx3 produced empty audio")
        return audio_bytes

    except ImportError:
        logger.warning("pyttsx3 not installed; skipping local TTS")
        raise
    except Exception as exc:
        logger.error("pyttsx3 TTS failed: %s", exc)
        raise


def _offline_synthesise(_text: str) -> bytes:
    """Last-resort stub — returns empty bytes."""
    logger.warning("TTS: both Google and pyttsx3 unavailable; returning empty audio")
    return b""


# ---------------------------------------------------------------------------
# TTSEngine
# ---------------------------------------------------------------------------

class TTSEngine:
    """
    Text-to-Speech engine with disk caching and automatic provider fallback.

    Usage::

        engine = TTSEngine()
        result = engine.synthesise("Your booking code is NL-A742.")

    Inject a callable for testing::

        engine = TTSEngine(primary=lambda t: b"\\xFF\\xFB" * 100)
    """

    def __init__(
        self,
        primary: TTSCallable | None = None,
        fallback: TTSCallable | None = None,
        use_cache: bool = True,
    ) -> None:
        self._primary: TTSCallable = primary or _google_synthesise
        self._fallback: TTSCallable = fallback or _pyttsx3_synthesise
        self._use_cache = use_cache
        self._voice = os.environ.get("TTS_VOICE_NAME", "en-IN-Neural2-A")

    # ------------------------------------------------------------------
    def synthesise(self, text: str) -> SynthesisResult:
        """
        Convert text to audio bytes.

        Checks disk cache first. On miss, tries primary provider then
        fallback. Successful primary results are cached to disk.
        Never raises — returns empty SynthesisResult on total failure.
        """
        if not text or not text.strip():
            return SynthesisResult(audio_bytes=b"", provider="offline", cached=False)

        text = text.strip()
        cache_key = _cache_key(text, self._voice)

        # --- Cache hit ---
        if self._use_cache:
            cached = _read_cache(cache_key)
            if cached is not None:
                logger.debug("TTS cache hit for %r", text[:40])
                return SynthesisResult(
                    audio_bytes=cached, provider="google", cached=True
                )

        # --- Try primary then fallback ---
        for provider_fn, label in [
            (self._primary, "google"),
            (self._fallback, "pyttsx3"),
        ]:
            t0 = time.monotonic()
            try:
                audio_bytes = provider_fn(text)
                if not audio_bytes:
                    continue
                duration_ms = (time.monotonic() - t0) * 1000
                if label == "google" and self._use_cache:
                    _write_cache(cache_key, audio_bytes)
                logger.debug(
                    "TTS [%s]: %.0f ms | %d bytes | %r",
                    label, duration_ms, len(audio_bytes), text[:40],
                )
                return SynthesisResult(
                    audio_bytes=audio_bytes,
                    provider=label,
                    cached=False,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.warning("TTS %s provider failed; trying fallback", label)

        # --- Both failed ---
        return SynthesisResult(audio_bytes=b"", provider="offline", cached=False)

    # ------------------------------------------------------------------
    def clear_cache(self) -> int:
        """Delete all cached TTS files. Returns count of files removed."""
        removed = 0
        try:
            for f in _cache_dir().glob("*.wav"):
                f.unlink(missing_ok=True)
                removed += 1
        except OSError as exc:
            logger.warning("TTS cache clear error: %s", exc)
        return removed


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_engine: TTSEngine | None = None


def get_default_engine() -> TTSEngine:
    """Return the module-level singleton TTSEngine (lazy init)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = TTSEngine()
    return _default_engine


def synthesise(text: str) -> SynthesisResult:
    """Convenience wrapper using the default engine."""
    return get_default_engine().synthesise(text)