"""
Compliance Evaluator

Tests that the ComplianceGuard + IntentRouter correctly:
- Flags refuse_advice for investment advice requests
- Flags refuse_pii for personal info sharing
- Flags out_of_scope for unrelated queries
- Returns null flag for clean, in-scope booking requests

Computes precision, recall, F1 per flag type.
"""

from __future__ import annotations

import json
import sys
from datetime import timezone, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "phase2"))

from src.dialogue.states import DialogueContext, DialogueState
from src.dialogue.intent_router import IntentRouter, _rule_based_parse

IST = timezone(timedelta(hours=5, minutes=30))

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "compliance.json"

FLAG_TYPES = ["refuse_advice", "refuse_pii", "out_of_scope", None]


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def run_compliance_eval(use_llm: bool = True) -> dict[str, Any]:
    """
    For each compliance test case, route the input and check:
    1. Was the compliance_flag correctly set?
    2. Was the intent correctly classified (compliance intents map to flags)?
    """
    dataset = load_dataset()
    router = IntentRouter()

    # Intent → compliance_flag mapping
    intent_to_flag = {
        "refuse_advice": "refuse_advice",
        "refuse_pii": "refuse_pii",
        "out_of_scope": "out_of_scope",
    }

    results = []
    correct = 0

    by_flag: dict[str, dict] = {}

    for case in dataset:
        from datetime import datetime
        ctx = DialogueContext(
            call_id="EVAL-COMP",
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.DISCLAIMER_CONFIRMED,
        )

        expected_flag = case.get("expected_flag")  # None or string

        try:
            if use_llm:
                response = router.route(case["input"], ctx)
            else:
                response = _rule_based_parse(case["input"], ctx)

            predicted_flag = response.compliance_flag or intent_to_flag.get(response.intent)
            predicted_should_proceed = predicted_flag is None

        except Exception as exc:
            predicted_flag = "ERROR"
            predicted_should_proceed = False

        is_correct = predicted_flag == expected_flag

        if is_correct:
            correct += 1

        flag_key = str(expected_flag)
        if flag_key not in by_flag:
            by_flag[flag_key] = {"tp": 0, "fp": 0, "fn": 0, "total": 0}

        by_flag[flag_key]["total"] += 1
        if is_correct:
            by_flag[flag_key]["tp"] += 1
        else:
            by_flag[flag_key]["fn"] += 1
            # false positive for the predicted flag
            pred_key = str(predicted_flag)
            if pred_key not in by_flag:
                by_flag[pred_key] = {"tp": 0, "fp": 0, "fn": 0, "total": 0}
            by_flag[pred_key]["fp"] += 1

        results.append({
            "id": case["id"],
            "input": case["input"],
            "expected_flag": expected_flag,
            "predicted_flag": predicted_flag,
            "expected_should_proceed": case.get("should_proceed"),
            "predicted_should_proceed": predicted_should_proceed,
            "correct": is_correct,
            "category": case.get("category", "unknown"),
        })

    # Per-flag metrics
    flag_metrics = {}
    for flag, counts in by_flag.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        flag_metrics[flag] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn,
        }

    # Safety metrics: false negative on refuse_advice/refuse_pii is most dangerous
    safety_flags = ["refuse_advice", "refuse_pii"]
    safety_fn_total = sum(
        by_flag.get(f, {}).get("fn", 0) for f in safety_flags
    )
    safety_recall = {
        f: flag_metrics.get(f, {}).get("recall", 1.0) for f in safety_flags
    }

    failures = [r for r in results if not r["correct"]]

    return {
        "eval": "compliance",
        "total": len(results),
        "correct": correct,
        "accuracy": round(correct / len(results), 3) if results else 0.0,
        "flag_metrics": flag_metrics,
        "safety_false_negatives": safety_fn_total,
        "safety_recall": safety_recall,
        "failures": failures,
        "results": results,
    }
