"""
Phase 4 — Data models for MCP tool inputs and outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MCPPayload:
    """All data needed to create calendar, sheet row, and email draft."""
    booking_code: str
    call_id: str
    topic_key: str          # e.g. "kyc_onboarding"
    topic_label: str        # e.g. "KYC and Onboarding"
    slot_start_iso: str     # ISO 8601 with tz offset, e.g. "2026-04-13T09:00:00+05:30"
    slot_start_ist: str     # Human-readable, e.g. "Monday, 13/04/2026 at 09:00 AM IST"
    slot_end_iso: str       # slot_start + slot_duration_minutes
    advisor_id: str
    created_at_ist: str     # "2026-04-05 14:32:00 IST"
    status: str = "booked"  # "booked" | "waitlisted" | "cancelled"


@dataclass
class ToolResult:
    """Result from a single MCP tool call."""
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class MCPResults:
    """Aggregated results from all three MCP tools."""
    calendar: ToolResult
    sheets: ToolResult
    email: ToolResult
    total_duration_ms: float = 0.0

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def calendar_event_id(self) -> str | None:
        return self.calendar.data.get("event_id")

    @property
    def sheet_row_index(self) -> int | None:
        return self.sheets.data.get("row_index")

    @property
    def email_draft_id(self) -> str | None:
        return self.email.data.get("draft_id")

    @property
    def calendar_success(self) -> bool:
        return self.calendar.success

    @property
    def sheets_success(self) -> bool:
        return self.sheets.success

    @property
    def email_success(self) -> bool:
        return self.email.success

    @property
    def all_succeeded(self) -> bool:
        return self.calendar_success and self.sheets_success and self.email_success

    @property
    def partial_success(self) -> bool:
        return self.calendar_success or self.sheets_success or self.email_success

    def summary(self) -> str:
        parts = []
        for name, result in [("calendar", self.calendar), ("sheets", self.sheets), ("email", self.email)]:
            status = "✅" if result.success else f"❌ {result.error}"
            parts.append(f"{name}: {status}")
        return " | ".join(parts)
