"""
Phase 4 — Append-only JSONL operations log for MCP tool results.
Written to data/logs/mcp_ops_log.jsonl (configurable via MCP_OPS_LOG_PATH).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytz

from .models import MCPPayload, MCPResults

IST = pytz.timezone("Asia/Kolkata")


def _resolve_log_path(raw: str) -> str:
    if os.path.isabs(raw):
        return raw
    # Resolve relative to phase0/ directory
    _here = Path(__file__).resolve()
    for parent in _here.parents:
        candidate = parent / "phase0" / raw
        if candidate.parent.exists():
            return str(candidate)
    return raw


class MCPLogger:
    """Writes one JSONL record per dispatch_mcp call."""

    def log(self, payload: MCPPayload, results: MCPResults) -> None:
        raw_path = os.environ.get("MCP_OPS_LOG_PATH", "data/logs/mcp_ops_log.jsonl")
        log_path = _resolve_log_path(raw_path)
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts":           datetime.now(IST).isoformat(),
            "booking_code": payload.booking_code,
            "call_id":      payload.call_id,
            "topic_key":    payload.topic_key,
            "slot_ist":     payload.slot_start_ist,
            "total_ms":     round(results.total_duration_ms, 1),
            "calendar": {
                "ok":       results.calendar.success,
                "event_id": results.calendar_event_id,
                "ms":       round(results.calendar.duration_ms, 1),
                "error":    results.calendar.error,
            },
            "sheets": {
                "ok":        results.sheets.success,
                "row_index": results.sheet_row_index,
                "ms":        round(results.sheets.duration_ms, 1),
                "error":     results.sheets.error,
            },
            "email": {
                "ok":       results.email.success,
                "draft_id": results.email_draft_id,
                "ms":       round(results.email.duration_ms, 1),
                "error":    results.email.error,
            },
        }

        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
