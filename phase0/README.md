# Phase 0 — Foundation & RAG Pipeline ✅ Done

**Goal:** Lay the groundwork. No product features yet — just data ingestion, config, and the FAQ search pipeline.

## What's in this folder

```
phase0/
├── src/agent/
│   └── rag_injector.py        # ChromaDB FAQ lookup (used by what_to_prepare intent)
├── scripts/
│   ├── build_index.py         # Builds ChromaDB vector index from raw_docs/
│   └── scrape_faq.py          # Scrapes public help-centre pages → raw_docs/
├── data/
│   ├── raw_docs/              # Source FAQ text files (per topic)
│   └── chroma_db/             # Persistent ChromaDB index (SQLite)
├── tests/
│   └── test_phase0_rag.py
├── config/
│   ├── settings.py            # Pydantic BaseSettings — all env vars
│   └── service_account.json   # Google Cloud service account (dev dummy)
├── app.py                     # Main Streamlit demo UI (integrates all phases)
├── console.py                 # CLI text-mode runner
├── internal_dashboard.py      # Phase build-tracker dashboard
└── path_setup.py              # Adds phase0/1/2 to sys.path (used by entry points)
```

## What was built

| Component | Status |
|---|---|
| Pydantic `Settings` config | ✅ |
| Mock calendar JSON | ✅ (moved to `phase1/data/`) |
| FAQ scraper (5 topics) | ✅ |
| ChromaDB embedding pipeline (`all-MiniLM-L6-v2`) | ✅ |
| `get_rag_context(query, topic)` | ✅ |

## How to run

```bash
cd voice-agents/phase0

# Build the FAQ index (first time only)
python scripts/build_index.py

# Run the Streamlit dashboard
streamlit run internal_dashboard.py --server.port 8502

# Run tests
pytest tests/test_phase0_rag.py
```
