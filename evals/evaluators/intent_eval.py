"""
Intent Classification Evaluator

Tests accuracy of the IntentRouter LLM chain across 10 intent types.
Runs using actual Groq/Claude APIs if keys are available, else rule-based fallback.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import timezone, timedelta
from pathlib import Path
from typing import Any

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "phase2"))

from src.dialogue.states import DialogueContext, DialogueState
from src.dialogue.intent_router import IntentRouter, _rule_based_parse

IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "intent_classification.json"


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def _make_ctx() -> DialogueContext:
    from datetime import datetime
    return DialogueContext(
        call_id="EVAL-001",
        session_start_ist=datetime.now(IST),
        current_state=DialogueState.DISCLAIMER_CONFIRMED,
    )


def run_intent_eval(use_llm: bool = True) -> dict[str, Any]:
    """
    Run intent classification eval.

    Args:
        use_llm: If True, uses Groq/Claude. If False, forces rule-based only.

    Returns:
        Dict with overall accuracy, per-category breakdown, and per-case results.
    """
    dataset = load_dataset()
    router = IntentRouter()

    results = []
    correct = 0
    total = len(dataset)

    by_category: dict[str, dict] = {}

    for case in dataset:
        ctx = _make_ctx()
        start = time.monotonic()

        try:
            if use_llm:
                response = router.route(case["input"], ctx)
            else:
                response = _rule_based_parse(case["input"], ctx)

            predicted = response.intent
            elapsed_ms = (time.monotonic() - start) * 1000
            is_correct = predicted == case["expected_intent"]

        except Exception as exc:
            predicted = "ERROR"
            elapsed_ms = (time.monotonic() - start) * 1000
            is_correct = False
            logger.warning("Error on %s: %s", case["id"], exc)

        if is_correct:
            correct += 1

        cat = case.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = {"correct": 0, "total": 0}
        by_category[cat]["total"] += 1
        if is_correct:
            by_category[cat]["correct"] += 1

        results.append({
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected_intent"],
            "predicted": predicted,
            "correct": is_correct,
            "language": case.get("language", "en"),
            "category": cat,
            "elapsed_ms": round(elapsed_ms, 1),
        })

    # Per-category accuracy
    category_accuracy = {
        cat: {
            "accuracy": round(v["correct"] / v["total"], 3),
            "correct": v["correct"],
            "total": v["total"],
        }
        for cat, v in by_category.items()
    }

    overall_accuracy = round(correct / total, 3) if total else 0.0

    # Find failures
    failures = [r for r in results if not r["correct"]]

    return {
        "eval": "intent_classification",
        "total": total,
        "correct": correct,
        "accuracy": overall_accuracy,
        "category_accuracy": category_accuracy,
        "failures": failures,
        "results": results,
    }
