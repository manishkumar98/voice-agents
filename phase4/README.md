# Phase 4 — Google Workspace Integration (MCP) ⏳ Pending

**Goal:** Replace mock MCP dispatch with real Google Calendar, Sheets, and Gmail calls triggered in parallel after booking confirmation.

## Planned folder structure

```
phase4/
├── src/mcp/
│   ├── calendar_tool.py       # create_calendar_hold() → Google Calendar API
│   ├── sheets_tool.py         # append_booking_notes() → Google Sheets (gspread)
│   ├── email_tool.py          # draft_approval_email() → Gmail SMTP (draft only)
│   ├── mcp_orchestrator.py    # asyncio.gather() parallel dispatch + retry logic
│   └── mcp_logger.py          # mcp_ops_log.jsonl per-tool result logging
└── tests/
    └── test_phase4_mcp.py
```

## Components to build

| Tool | API | Auth | Output |
|---|---|---|---|
| `create_calendar_hold()` | Google Calendar v3 | Service Account + domain delegation | TENTATIVE event, returns `event_id` |
| `append_booking_notes()` | Google Sheets (gspread) | Service Account | Row in "Advisor Pre-Bookings", returns `row_index` |
| `draft_approval_email()` | Gmail SMTP / smtplib | Gmail App Password | DRAFT (not sent), returns `draft_id` |

## Orchestration pattern

```python
async def dispatch_mcp(payload: MCPPayload) -> MCPResults:
    # Step 1: Calendar first (email + notes need event_id)
    calendar_result = await create_calendar_hold(payload)
    event_id = calendar_result.get("event_id")

    # Step 2: Notes + Email in parallel
    notes_result, email_result = await asyncio.gather(
        append_booking_notes(payload, event_id),
        draft_approval_email(payload, event_id),
        return_exceptions=True,
    )
    return MCPResults(calendar=calendar_result, notes=notes_result, email=email_result)
```

## Failure handling

- Any single tool failure does **not** block booking code issuance.
- Partial failures logged to `data/logs/mcp_ops_log.jsonl` for async retry.
- All 3 tools must complete within 3s combined (parallel execution).

## Acceptance criteria

- Calendar hold created as TENTATIVE with correct title and slot time in IST.
- Sheet row appended with all required columns.
- Email saved as DRAFT (not sent); advisor must click Send manually.
- Partial failure does not prevent booking code from being spoken.
