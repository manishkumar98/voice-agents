"""
Slot Extraction Evaluator

Tests accuracy of slot extraction (topic, day_preference, time_preference, booking_code).
Uses the rule-based extractor functions from intent_router.py for offline testing.
Also tests booking code extraction robustness for transcription variants.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "phase2"))

from src.dialogue.states import DialogueContext, DialogueState
from src.dialogue.intent_router import IntentRouter, _rule_based_parse

IST = timezone(timedelta(hours=5, minutes=30))

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "slot_extraction.json"


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def _normalize(val: str | None) -> str:
    if not val:
        return ""
    return val.strip().lower()


def _slot_match(expected: str, predicted: str) -> bool:
    """Fuzzy match for slot values — checks if expected is a substring of predicted."""
    e = _normalize(expected)
    p = _normalize(predicted)
    if not e:
        return True  # no expectation = always pass
    return e in p or p in e


def run_slot_eval(use_llm: bool = True) -> dict[str, Any]:
    """
    Run slot extraction eval.

    For each test case, route the input and check which slots were extracted
    against the expected slots. Computes per-slot precision/recall.
    """
    dataset = load_dataset()
    router = IntentRouter()

    SLOT_KEYS = ["topic", "day_preference", "time_preference", "existing_booking_code"]

    per_slot_tp: dict[str, int] = {k: 0 for k in SLOT_KEYS}
    per_slot_expected: dict[str, int] = {k: 0 for k in SLOT_KEYS}
    per_slot_predicted: dict[str, int] = {k: 0 for k in SLOT_KEYS}

    results = []

    for case in dataset:
        ctx = DialogueContext(
            call_id="EVAL-SLOT",
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.DISCLAIMER_CONFIRMED,
        )

        try:
            if use_llm:
                response = router.route(case["input"], ctx)
            else:
                response = _rule_based_parse(case["input"], ctx)
        except Exception:
            response = None

        expected_slots = case.get("expected_slots", {})
        slot_results = {}

        for key in SLOT_KEYS:
            expected_val = expected_slots.get(key)
            predicted_val = (response.slots.get(key) if response else None) if response else None

            if expected_val is not None:
                per_slot_expected[key] += 1

            if predicted_val is not None:
                per_slot_predicted[key] += 1

            if expected_val is not None and predicted_val is not None:
                if _slot_match(expected_val, predicted_val):
                    per_slot_tp[key] += 1
                    slot_results[key] = {"expected": expected_val, "predicted": predicted_val, "match": True}
                else:
                    slot_results[key] = {"expected": expected_val, "predicted": predicted_val, "match": False}
            elif expected_val is not None and predicted_val is None:
                slot_results[key] = {"expected": expected_val, "predicted": None, "match": False}
            elif expected_val is None and predicted_val is not None:
                slot_results[key] = {"expected": None, "predicted": predicted_val, "match": None}  # extra (not penalized)

        all_expected_match = all(
            slot_results.get(k, {}).get("match", True)
            for k in expected_slots.keys()
        )

        results.append({
            "id": case["id"],
            "input": case["input"],
            "category": case.get("category", "unknown"),
            "slots": slot_results,
            "all_match": all_expected_match,
        })

    # Per-slot precision / recall / F1
    slot_metrics: dict[str, dict] = {}
    for key in SLOT_KEYS:
        tp = per_slot_tp[key]
        fn = per_slot_expected[key] - tp
        fp = per_slot_predicted[key] - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        slot_metrics[key] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    full_match_count = sum(1 for r in results if r["all_match"])
    failures = [r for r in results if not r["all_match"]]

    return {
        "eval": "slot_extraction",
        "total": len(results),
        "full_match_count": full_match_count,
        "full_match_rate": round(full_match_count / len(results), 3) if results else 0.0,
        "slot_metrics": slot_metrics,
        "failures": failures,
        "results": results,
    }
