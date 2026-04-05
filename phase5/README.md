# Phase 5 — Deploy & Polish ⏳ Pending

**Goal:** Production-ready packaging, hardening, monitoring, and deployment.

## Planned folder structure

```
phase5/
├── docker/
│   ├── Dockerfile             # Multi-stage build (Python 3.11 slim)
│   └── docker-compose.yml     # App + Redis + ChromaDB volumes
├── infra/
│   ├── nginx.conf             # Reverse proxy + SSL termination
│   └── supervisord.conf       # Process supervision (FastAPI + Streamlit)
├── scripts/
│   ├── health_check.py        # Liveness + readiness probes
│   └── seed_calendar.py       # Seed production calendar with initial slots
└── tests/
    └── test_phase5_e2e.py     # Full end-to-end integration tests
```

## What to build

### Deployment
| Item | Details |
|---|---|
| Dockerfile | Python 3.11-slim, non-root user, health check endpoint |
| docker-compose | FastAPI (port 8000) + Streamlit UI (8501) + Redis (6379) |
| Redis session store | Replace in-memory `SessionManager` with Redis 7 TTL keys |
| ENV secrets | `.env` → Docker secrets / GCP Secret Manager in prod |

### Hardening
| Item | Details |
|---|---|
| Rate limiting | Max 10 concurrent calls; queue overflow → busy tone |
| Async retry queue | Celery + Redis for failed MCP tool retries |
| Structured logging | `structlog` → JSON logs → Cloud Logging |
| Alerting | Compliance block rate > 5/10min → PagerDuty alert |
| STT fallback | Groq STT down → Deepgram → text-only mode |

### Observability
| Dashboard | Tool |
|---|---|
| Call volume + duration | Grafana |
| Intent distribution | Grafana |
| MCP success rate | Grafana |
| Compliance block rate | Grafana + PagerDuty alert |
| Audit log search | Cloud Logging |

### UI Polish
- Production Streamlit UI with authentication
- Live call transcript display
- Booking confirmation email preview panel

## Acceptance criteria

- Docker image builds and starts in < 30s.
- 10 concurrent simulated calls complete without errors.
- Redis session store replaces in-memory store with no behaviour change.
- Grafana dashboard shows call volume, intent mix, MCP success rate.
- `pytest tests/test_phase5_e2e.py` passes with all 12 training flows.
