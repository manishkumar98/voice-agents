"""
TTS Engine — Text-to-Speech abstraction.

Provider priority (first available wins):
  1. Sarvam AI Bulbul v1  — most natural Indian English + Hindi
     Set SARVAM_API_KEY. Voices: meera (F), pavithra (F), maitreyi (F),
     arvind (M), amol (M), amartya (M), diya (F), neel (M), misha (F),
     vian (M), arjun (M), maya (F)
  2. Google Cloud TTS Neural2 — Indian English en-IN / Hindi hi-IN
     Set GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON
     Voices (en-IN): en-IN-Neural2-A/B/C/D | Journey: en-IN-Journey-D/F
     Voices (hi-IN): hi-IN-Neural2-A/B/C/D
  3. pyttsx3 — local, zero-cost, offline fallback

Language selection (env var TTS_LANGUAGE):
  "en-IN"  → Indian English (default)
  "hi-IN"  → Hindi

Features
--------
- Hash-based disk cache: repeated phrases are synthesised once and served
  from disk. Cache TTL configurable via TTS_CACHE_TTL_DAYS (default 7).
- Graceful degradation: returns empty bytes on total failure.
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
        if self.provider not in {"sarvam", "google", "pyttsx3", "offline", "mock", "cached", "unknown"}:
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

# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def _detect_language(text: str) -> str:
    """
    Detect whether text is Hindi (Devanagari script) or Indian English.
    Returns "hi-IN" if Devanagari characters are found, else "en-IN".
    Overridden by TTS_LANGUAGE env var.
    """
    forced = os.environ.get("TTS_LANGUAGE", "").strip()
    if forced:
        return forced
    # Devanagari Unicode block: U+0900–U+097F
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "hi-IN"
    return "en-IN"


def _sarvam_speaker(language: str) -> str:
    """
    Return the Sarvam voice name for a given language.
    Configurable via TTS_SARVAM_SPEAKER_EN / TTS_SARVAM_SPEAKER_HI.
    """
    if language == "hi-IN":
        return os.environ.get("TTS_SARVAM_SPEAKER_HI", "manisha")  # natural Hindi female
    return os.environ.get("TTS_SARVAM_SPEAKER_EN", "anushka")       # natural Indian-English female


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

def _sarvam_synthesise(text: str, language: str = "en-IN") -> bytes:
    """
    Synthesise text via Sarvam AI Bulbul v1 — natural Indian English + Hindi.
    Requires: SARVAM_API_KEY  (get free key at https://dashboard.sarvam.ai)

    Sarvam Bulbul supports both "en-IN" (Indian English) and "hi-IN" (Hindi)
    in the same model, with multiple natural-sounding speakers.
    Returns WAV bytes decoded from base64 response.
    """
    import base64
    import json as _json
    try:
        import requests as _requests
    except ImportError:
        logger.warning("requests not installed; skipping Sarvam TTS")
        raise

    api_key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY not set")

    speaker = _sarvam_speaker(language)
    payload = {
        "inputs": [text[:500]],          # Sarvam max ~500 chars per call
        "target_language_code": language,
        "speaker": speaker,
        "pitch": 0,
        "pace": float(os.environ.get("TTS_PACE", "1.0")),
        "loudness": 1.5,
        "speech_sample_rate": 22050,
        "enable_preprocessing": True,
        "model": "bulbul:v2",
    }
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    resp = _requests.post(
        "https://api.sarvam.ai/text-to-speech",
        json=payload,
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Response: {"audios": ["<base64-encoded-wav>", ...]}
    audios = data.get("audios", [])
    if not audios:
        raise RuntimeError(f"Sarvam returned no audio: {data}")
    return base64.b64decode(audios[0])


def _google_synthesise(text: str, language: str = "en-IN") -> bytes:
    """
    Synthesise text using Google Cloud Text-to-Speech Neural2.
    Requires: GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON

    Language → default voice mapping:
      "en-IN"  → en-IN-Neural2-A  (Indian English, female)
      "hi-IN"  → hi-IN-Neural2-A  (Hindi, female)
    Override via TTS_VOICE_NAME (language-specific: TTS_VOICE_NAME_EN / TTS_VOICE_NAME_HI).
    """
    try:
        from google.cloud import texttospeech  # type: ignore[import]
        from google.oauth2 import service_account  # type: ignore[import]

        # Language-specific voice selection
        _voice_defaults = {
            "en-IN": "en-IN-Neural2-A",
            "hi-IN": "hi-IN-Neural2-A",
        }
        if language == "hi-IN":
            voice_name = os.environ.get("TTS_VOICE_NAME_HI",
                         os.environ.get("TTS_VOICE_NAME", _voice_defaults["hi-IN"]))
        else:
            voice_name = os.environ.get("TTS_VOICE_NAME_EN",
                         os.environ.get("TTS_VOICE_NAME", _voice_defaults["en-IN"]))

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
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=float(os.environ.get("TTS_PACE", "1.0")),
            pitch=0.0,
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
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
        engine.setProperty("rate", int(150 * float(os.environ.get("TTS_PACE", "1.0"))))
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

    Provider chain:
      1. Sarvam AI Bulbul v1 (natural Indian English + Hindi) if SARVAM_API_KEY set
      2. Google Cloud TTS Neural2 (Indian English / Hindi)
      3. pyttsx3 (offline fallback)

    Usage::

        engine = TTSEngine()
        result = engine.synthesise("Your booking code is NL-A742.")
        result = engine.synthesise("आपकी बुकिंग हो गई।", language="hi-IN")

    Language is auto-detected from Devanagari script if not passed explicitly.
    Override globally via TTS_LANGUAGE env var ("en-IN" or "hi-IN").

    Inject a callable for testing::

        engine = TTSEngine(primary=lambda t: b"\\xFF\\xFB" * 100)
    """

    def __init__(
        self,
        primary: TTSCallable | None = None,
        fallback: TTSCallable | None = None,
        use_cache: bool = True,
    ) -> None:
        self._use_cache = use_cache
        # If primary injectable is given (e.g. for tests), use it directly.
        # Otherwise build Sarvam → Google → pyttsx3 chain.
        if primary is not None:
            self._providers: list[tuple[TTSCallable, str]] = [
                (primary, "mock"),
                (fallback or _pyttsx3_synthesise, "pyttsx3"),
            ]
        else:
            self._providers = [
                (_sarvam_synthesise, "sarvam"),
                (_google_synthesise, "google"),
                (_pyttsx3_synthesise, "pyttsx3"),
            ]
        # Kept for cache-key compatibility when TTS_VOICE_NAME is set
        self._voice = os.environ.get("TTS_VOICE_NAME", "en-IN-Neural2-A")

    # ------------------------------------------------------------------
    def synthesise(self, text: str, language: str | None = None) -> SynthesisResult:
        """
        Convert text to audio bytes.

        Args:
            text:     The text to speak.
            language: "en-IN" (Indian English) or "hi-IN" (Hindi).
                      Auto-detected from Devanagari script if omitted.

        Checks disk cache first. On miss, tries providers in order.
        Successful results from named providers are cached to disk.
        Never raises — returns empty SynthesisResult on total failure.
        """
        if not text or not text.strip():
            return SynthesisResult(audio_bytes=b"", provider="offline", cached=False)

        text = text.strip()
        lang = language or _detect_language(text)
        cache_key = _cache_key(text, f"{self._voice}|{lang}")

        # --- Cache hit ---
        if self._use_cache:
            cached = _read_cache(cache_key)
            if cached is not None:
                logger.debug("TTS cache hit for %r [%s]", text[:40], lang)
                return SynthesisResult(
                    audio_bytes=cached, provider="cached", cached=True
                )

        # --- Try providers in order ---
        for provider_fn, label in self._providers:
            t0 = time.monotonic()
            try:
                # Language-aware providers accept a second `language` argument;
                # legacy injectables (tests) may only accept text.
                import inspect as _inspect
                sig = _inspect.signature(provider_fn)
                if len(sig.parameters) >= 2:
                    audio_bytes = provider_fn(text, lang)  # type: ignore[call-arg]
                else:
                    audio_bytes = provider_fn(text)
                if not audio_bytes:
                    continue
                duration_ms = (time.monotonic() - t0) * 1000
                if label in ("sarvam", "google") and self._use_cache:
                    _write_cache(cache_key, audio_bytes)
                logger.debug(
                    "TTS [%s]: %.0f ms | %d bytes | %r [%s]",
                    label, duration_ms, len(audio_bytes), text[:40], lang,
                )
                return SynthesisResult(
                    audio_bytes=audio_bytes,
                    provider=label,
                    cached=False,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.warning("TTS %s provider failed; trying next", label)

        # --- All failed ---
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