#!/usr/bin/env python3
"""
Phase 5 — Liveness & Readiness Health Check

Usage:
    python health_check.py                   # check all (default host/port)
    python health_check.py --host 0.0.0.0 --port 8501
    python health_check.py --json            # output JSON

Exit codes:
    0 — all checks pass
    1 — one or more checks failed
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# ── Optional Redis check ───────────────────────────────────────────────────────
try:
    import redis as _redis_lib
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

# ── Path setup ─────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[2]   # voice-agents/
sys.path.insert(0, str(_root / "phase1"))
sys.path.insert(0, str(_root / "phase2"))
sys.path.insert(0, str(_root / "phase3"))


# ── Individual checks ──────────────────────────────────────────────────────────

def check_streamlit(host: str, port: int, timeout: int = 5) -> dict[str, Any]:
    url = f"http://{host}:{port}/_stcore/health"
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode()
            ok = resp.status == 200
    except urllib.error.URLError as exc:
        return {"name": "streamlit", "ok": False, "error": str(exc),
                "duration_ms": (time.monotonic() - t0) * 1000}
    return {
        "name": "streamlit",
        "ok": ok,
        "status_code": resp.status,
        "body": body[:120],
        "duration_ms": (time.monotonic() - t0) * 1000,
    }


def check_redis(host: str = "localhost", port: int = 6379, timeout: int = 3) -> dict[str, Any]:
    if not _HAS_REDIS:
        return {"name": "redis", "ok": True, "note": "redis-py not installed — skipped"}
    import os
    redis_url = os.environ.get("REDIS_URL", f"redis://{host}:{port}/0")
    t0 = time.monotonic()
    try:
        client = _redis_lib.from_url(redis_url, socket_connect_timeout=timeout)
        pong = client.ping()
    except Exception as exc:
        return {"name": "redis", "ok": False, "error": str(exc),
                "duration_ms": (time.monotonic() - t0) * 1000}
    return {
        "name": "redis",
        "ok": pong,
        "duration_ms": (time.monotonic() - t0) * 1000,
    }


def check_calendar_file() -> dict[str, Any]:
    """Verify the mock calendar data file is present and readable."""
    import os
    cal_path = os.environ.get(
        "MOCK_CALENDAR_PATH",
        str(_root / "phase1" / "data" / "mock_calendar.json"),
    )
    t0 = time.monotonic()
    try:
        import json as _json
        with open(cal_path) as f:
            data = _json.load(f)
        count = len(data.get("slots", data) if isinstance(data, dict) else data)
    except Exception as exc:
        return {"name": "calendar_file", "ok": False, "error": str(exc),
                "duration_ms": (time.monotonic() - t0) * 1000}
    return {
        "name": "calendar_file",
        "ok": True,
        "slot_count": count,
        "path": cal_path,
        "duration_ms": (time.monotonic() - t0) * 1000,
    }


def check_fsm_import() -> dict[str, Any]:
    """Verify core FSM is importable (detects import errors early)."""
    t0 = time.monotonic()
    try:
        from src.dialogue.fsm import DialogueFSM
        fsm = DialogueFSM()
        ctx, speech = fsm.start(call_id="HEALTH-CHECK")
        assert speech
    except Exception as exc:
        return {"name": "fsm_import", "ok": False, "error": str(exc),
                "duration_ms": (time.monotonic() - t0) * 1000}
    return {
        "name": "fsm_import",
        "ok": True,
        "duration_ms": (time.monotonic() - t0) * 1000,
    }


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks(host: str, port: int) -> list[dict[str, Any]]:
    return [
        check_streamlit(host, port),
        check_redis(),
        check_calendar_file(),
        check_fsm_import(),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisor Scheduling Agent health check")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    results = run_checks(args.host, args.port)
    all_ok = all(r["ok"] for r in results)

    if args.as_json:
        print(json.dumps({"ok": all_ok, "checks": results}, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"  Health Check — {'✅ PASS' if all_ok else '❌ FAIL'}")
        print(f"{'='*50}")
        for r in results:
            status = "✅" if r["ok"] else "❌"
            ms = f"{r.get('duration_ms', 0):.1f}ms"
            note = r.get("error") or r.get("note") or ""
            print(f"  {status} {r['name']:<20} {ms:>10}  {note}")
        print(f"{'='*50}\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
