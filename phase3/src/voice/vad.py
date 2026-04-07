"""
Voice Activity Detector (VAD).

Primary:  Silero VAD v4  (PyTorch, local — no API cost, <10 ms latency)
Fallback: Energy-based VAD  (numpy RMS threshold — zero deps beyond numpy)

The VAD answers two questions per audio chunk:
  1. is_speech   — does this chunk contain speech?
  2. is_end_of_turn — has the speaker stopped (silence_threshold_ms elapsed)?

``VADEngine`` is stateful per call session.  Create one instance per call and
feed it chunks sequentially.  Call ``reset()`` when a new turn begins.
"""
from __future__ import annotations

import array
import logging
import math
import os
import struct
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

_DEFAULT_SILENCE_MS   = 300    # ms of continuous silence → end-of-turn
_DEFAULT_SAMPLE_RATE  = 16_000 # Hz
_DEFAULT_CHUNK_MS     = 30     # ms per audio chunk (matches Silero expectation)
_ENERGY_SPEECH_RMS    = 300    # RMS threshold for energy-based VAD


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VADResult:
    """Result for a single audio chunk."""

    is_speech: bool
    is_end_of_turn: bool      # True when silence_threshold crossed after speech
    energy_rms: float         # Root-mean-square of chunk (useful for debugging)
    silent_ms_so_far: float   # Accumulated silence duration since last speech
    provider: str = "silero"  # "silero" | "energy"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.energy_rms < 0:
            errors.append("energy_rms must be >= 0")
        if self.silent_ms_so_far < 0:
            errors.append("silent_ms_so_far must be >= 0")
        if self.provider not in {"silero", "energy"}:
            errors.append(f"unknown provider {self.provider!r}")
        return errors


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _bytes_to_int16(audio_bytes: bytes) -> list[int]:
    """Convert raw PCM16 LE bytes to a list of int16 samples."""
    n_samples = len(audio_bytes) // 2
    samples = struct.unpack(f"<{n_samples}h", audio_bytes[:n_samples * 2])
    return list(samples)


def _rms(samples: list[int]) -> float:
    """Root-mean-square amplitude of a list of int16 samples."""
    if not samples:
        return 0.0
    mean_sq = sum(s * s for s in samples) / len(samples)
    return math.sqrt(mean_sq)


def _chunk_duration_ms(audio_bytes: bytes, sample_rate: int = _DEFAULT_SAMPLE_RATE) -> float:
    """Return duration of PCM16 audio bytes in milliseconds."""
    n_samples = len(audio_bytes) // 2
    return (n_samples / sample_rate) * 1000.0


# ---------------------------------------------------------------------------
# Silero VAD loader
# ---------------------------------------------------------------------------

_silero_model = None
_silero_utils = None


def _load_silero() -> bool:
    """Try to load the Silero VAD model. Returns True on success."""
    global _silero_model, _silero_utils
    if _silero_model is not None:
        return True
    try:
        import torch  # type: ignore[import]
        # silero-vad ships a torch.hub model
        _silero_model, _silero_utils = torch.hub.load(  # type: ignore[assignment]
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
        )
        logger.info("Silero VAD loaded successfully")
        return True
    except Exception as exc:
        logger.warning("Silero VAD unavailable (%s); using energy-based fallback", exc)
        return False


# ---------------------------------------------------------------------------
# VADEngine
# ---------------------------------------------------------------------------

class VADEngine:
    """
    Stateful VAD engine for a single call session.

    Create once per call, feed chunks in order, call ``reset()`` between turns.

    Example::

        vad = VADEngine()
        for chunk in audio_stream:
            result = vad.process_chunk(chunk)
            if result.is_end_of_turn:
                transcript = stt.transcribe(collected_audio)
                vad.reset()
    """

    def __init__(
        self,
        silence_threshold_ms: int | None = None,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        chunk_ms: int = _DEFAULT_CHUNK_MS,
        energy_threshold: float = _ENERGY_SPEECH_RMS,
    ) -> None:
        self._silence_threshold_ms = silence_threshold_ms or float(
            os.environ.get("STT_SILENCE_TIMEOUT_SECONDS", "0.3")
        ) * 1000

        self._sample_rate   = sample_rate
        self._chunk_ms      = chunk_ms
        self._energy_thresh = energy_threshold

        # State
        self._silent_ms: float = 0.0
        self._has_speech: bool = False  # has any speech been heard this turn?

        # Decide provider
        self._use_silero = _load_silero()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset silence counter between turns."""
        self._silent_ms  = 0.0
        self._has_speech = False

    # ------------------------------------------------------------------
    def process_chunk(self, audio_bytes: bytes) -> VADResult:
        """
        Analyse one PCM16 audio chunk.

        ``audio_bytes`` must be raw 16-bit little-endian PCM at
        ``sample_rate`` Hz (default 16 kHz).
        """
        samples    = _bytes_to_int16(audio_bytes)
        energy_rms = _rms(samples)
        chunk_dur  = _chunk_duration_ms(audio_bytes, self._sample_rate)

        if self._use_silero:
            is_speech = self._silero_is_speech(audio_bytes, energy_rms)
            provider  = "silero"
        else:
            is_speech = energy_rms >= self._energy_thresh
            provider  = "energy"

        if is_speech:
            self._has_speech = True
            self._silent_ms  = 0.0
        else:
            if self._has_speech:
                self._silent_ms += chunk_dur

        is_end_of_turn = (
            self._has_speech
            and self._silent_ms >= self._silence_threshold_ms
        )

        return VADResult(
            is_speech=is_speech,
            is_end_of_turn=is_end_of_turn,
            energy_rms=energy_rms,
            silent_ms_so_far=self._silent_ms,
            provider=provider,
        )

    # ------------------------------------------------------------------
    def _silero_is_speech(self, audio_bytes: bytes, energy_rms: float) -> bool:
        """
        Run the Silero model on the audio chunk.
        Falls back to energy threshold if Silero inference fails.
        """
        try:
            import torch  # type: ignore[import]
            samples = _bytes_to_int16(audio_bytes)
            tensor  = torch.FloatTensor(samples).unsqueeze(0) / 32768.0
            prob: float = _silero_model(tensor, self._sample_rate).item()  # type: ignore[union-attr]
            return prob >= 0.5
        except Exception as exc:
            logger.debug("Silero inference error, using energy fallback: %s", exc)
            return energy_rms >= self._energy_thresh

    # ------------------------------------------------------------------
    @property
    def silent_ms(self) -> float:
        """Accumulated silence duration since last speech (ms)."""
        return self._silent_ms

    @property
    def has_heard_speech(self) -> bool:
        """True if any speech was detected in the current turn."""
        return self._has_speech


# ---------------------------------------------------------------------------
# Convenience: simple end-of-turn check for a single chunk
# ---------------------------------------------------------------------------

def is_end_of_turn(
    audio_bytes: bytes,
    silence_threshold_ms: int = _DEFAULT_SILENCE_MS,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
) -> VADResult:
    """
    Stateless single-chunk helper.

    Creates a temporary VADEngine, processes one chunk, returns result.
    Note: ``is_end_of_turn`` will only be True if silence is detected
    immediately (no prior speech context).  Use ``VADEngine`` for
    accurate multi-chunk streaming.
    """
    engine = VADEngine(
        silence_threshold_ms=silence_threshold_ms,
        sample_rate=sample_rate,
    )
    return engine.process_chunk(audio_bytes)
