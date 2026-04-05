# Phase 2 — FSM + LLM Core ✅ Done

**Goal:** Wire the booking brain to a 16-state dialogue state machine with LLM-powered intent routing, compliance guardrails, and session management.

## What's in this folder

```
phase2/
├── src/dialogue/
│   ├── states.py          # DialogueState (16 states), DialogueContext, LLMResponse
│   ├── fsm.py             # DialogueFSM — stateless 16-state controller
│   ├── intent_router.py   # LLM intent extraction (Groq → Claude → rule-based)
│   ├── compliance_guard.py # Post-LLM safety gate (advice, PII, scope)
│   └── session_manager.py # TTL-based in-memory session store
├── data/
│   └── training_set.py    # 12 executable dialogue flows (all paths covered)
└── tests/
    └── test_phase2_dialogue.py
```

## What was built

| Component | Status |
|---|---|
| 16-state `DialogueFSM` | ✅ |
| `_offer_slots()` — 4-step expansion, always returns 2 slots | ✅ |
| `_from_slots_offered()` — re-search, question detection, slot selection | ✅ |
| `IntentRouter` — Groq → Anthropic Claude → rule-based fallback chain | ✅ |
| `ComplianceGuard` — post-LLM advice/PII/scope blocking | ✅ |
| `SessionManager` — TTL-based, thread-safe session store | ✅ |
| Training set — 12 flows covering all dialogue paths | ✅ |

## How to import (from any entry point)

```python
from src.dialogue.fsm import DialogueFSM
from src.dialogue.states import DialogueContext, DialogueState, LLMResponse
from src.dialogue.intent_router import IntentRouter
from src.dialogue.compliance_guard import ComplianceGuard
from src.dialogue.session_manager import SessionManager
```

> **Note:** `path_setup.py` (in `phase0/`) must be run first so that `phase1/` and `phase2/` are on `sys.path`. `fsm.py` imports from `src.booking.*` (phase1).

## Run the training set

```bash
cd voice-agents
python phase2/data/training_set.py
```

## Run tests

```bash
cd voice-agents/phase0
pytest ../phase2/tests/
```
