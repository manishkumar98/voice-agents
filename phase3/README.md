# Phase 3 — Voice I/O (STT / TTS / VAD) ⏳ Pending

**Goal:** Connect real speech input and output — turn the text-based FSM into a live voice agent.

## Planned folder structure

```
phase3/
├── src/voice/
│   ├── stt_engine.py          # Speech-to-Text (Google Cloud STT v2 primary, Deepgram fallback)
│   ├── tts_engine.py          # Text-to-Speech (Google Neural2 en-IN-Neural2-A)
│   ├── vad.py                 # Voice Activity Detection (Silero VAD v4, local ONNX)
│   ├── audio_pipeline.py      # WebRTC / PSTN audio stream handler
│   └── voice_logger.py        # Append-only JSONL voice audit logger
├── data/
│   └── tts_cache/             # Cached TTS audio (disclaimer, topic prompt, etc.)
└── tests/
    └── test_phase3_voice.py
```

## Components to build

| Component | Description |
|---|---|
| `STTEngine` | Streaming STT with confidence scoring; re-prompt if < 0.7 |
| `TTSEngine` | TTS with audio caching for repeated prompts (disclaimer, etc.) |
| `VAD` | Silence detection — 3s timeout triggers no-input counter |
| `AudioPipeline` | PCM stream handler; feeds STT → PII scrubber → FSM |
| `VoiceLogger` | Per-turn JSONL log: transcript, intent, slots, pii_blocked |

## Key integration points

- STT output → `pii_scrubber.scrub_pii()` → `IntentRouter.route()` → `DialogueFSM.process_turn()`
- FSM speech output → `ComplianceGuard.check_and_gate()` → `TTSEngine.speak()`
- Barge-in: VAD detects user speech during TTS → interrupt + re-process

## Acceptance criteria

- End-to-end voice test completes `book_new` happy path via spoken interaction.
- STT confidence < 0.7 → re-prompt (max 3×).
- 3s silence → no-input counter increments; 3 silences → S14 ERROR.
- Voice audit log produces correct JSONL after each turn.
- Disclaimer audio served from TTS cache (no re-synthesis cost).
