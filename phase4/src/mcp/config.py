"""
Phase 4 — MCP configuration loader.
Reads from environment variables (dotenv loaded by caller or process env).
The GOOGLE_CALENDAR_ID may be base64-encoded — decoded transparently here.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path


def _decode_if_base64(raw: str) -> str:
    """Decode base64 string if it decodes to a valid calendar ID (contains '@'), else return raw."""
    if not raw:
        return raw
    try:
        decoded = base64.b64decode(raw + "==").decode("utf-8")
        if "@" in decoded and "." in decoded:
            return decoded
    except Exception:
        pass
    return raw


def _find_service_account_file(relative_path: str) -> str:
    """Resolve a relative service account path against known anchor dirs."""
    if os.path.isabs(relative_path) and os.path.exists(relative_path):
        return relative_path
    # Search relative to phase0/ (where it was placed) from any depth
    _here = Path(__file__).resolve()
    for parent in _here.parents:
        candidate = parent / "phase0" / relative_path
        if candidate.exists():
            return str(candidate)
        candidate2 = parent / relative_path
        if candidate2.exists():
            return str(candidate2)
    return relative_path  # fallback — let open() raise a useful error


def get_service_account_info() -> dict:
    """Load service account JSON from env var (inline JSON) or file path."""
    # Cloud deployment: full JSON inline
    inline = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if inline:
        return json.loads(inline)
    # Local development: path to JSON key file
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "config/service_account.json")
    resolved = _find_service_account_file(path)
    with open(resolved) as f:
        return json.load(f)


class MCPConfig:
    """Lazy property bag for all Phase 4 settings."""

    @property
    def service_account(self) -> dict:
        return get_service_account_info()

    @property
    def calendar_id(self) -> str:
        raw = os.environ.get("GOOGLE_CALENDAR_ID", "")
        return _decode_if_base64(raw)

    @property
    def slot_duration_minutes(self) -> int:
        return int(os.environ.get("CALENDAR_SLOT_DURATION_MINUTES", "30"))

    @property
    def hold_expiry_hours(self) -> int:
        return int(os.environ.get("CALENDAR_HOLD_EXPIRY_HOURS", "48"))

    @property
    def sheet_id(self) -> str:
        return os.environ.get("GOOGLE_SHEET_ID", "")

    @property
    def sheet_tab(self) -> str:
        return os.environ.get("GOOGLE_SHEET_TAB_NAME", "Advisor Pre-Bookings")

    @property
    def gmail_address(self) -> str:
        return os.environ.get("GMAIL_ADDRESS", "")

    @property
    def gmail_app_password(self) -> str:
        # App passwords may be stored with spaces (e.g. "thqi zgxl edlt kxrv") — strip them
        return os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

    @property
    def gmail_smtp_host(self) -> str:
        return os.environ.get("GMAIL_SMTP_HOST", "smtp.gmail.com")

    @property
    def gmail_smtp_port(self) -> int:
        return int(os.environ.get("GMAIL_SMTP_PORT", "587"))

    @property
    def advisor_email(self) -> str:
        return os.environ.get("ADVISOR_EMAIL", self.gmail_address)

    @property
    def advisor_name(self) -> str:
        return os.environ.get("ADVISOR_NAME", "Financial Advisor")

    @property
    def advisor_id(self) -> str:
        return os.environ.get("ADVISOR_ID", "ADV-001")

    @property
    def ops_log_path(self) -> str:
        return os.environ.get("MCP_OPS_LOG_PATH", "data/logs/mcp_ops_log.jsonl")


config = MCPConfig()
