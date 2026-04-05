"""
tests/test_phase0_rag.py

Phase 0 test suite — Foundation & RAG Pipeline.
All tests except TC-0.6 run fully offline (no external APIs).

Test cases:
    TC-0.1  Config loads without error
    TC-0.2  mock_calendar.json is valid and parseable
    TC-0.3  ChromaDB collection exists and has >= 50 chunks
    TC-0.4  RAG query returns topic-relevant chunks (5 topics)
    TC-0.5  RAG returns graceful fallback when ChromaDB is empty
    TC-0.6  Scraping pipeline creates output files [INTEGRATION]
"""

import json
import os
import subprocess
import sys
from datetime import datetime

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# TC-0.1 — Config loads without error
# ---------------------------------------------------------------------------

def test_settings_load():
    """Settings object initialises without raising ValidationError."""
    from config.settings import settings

    # Required fields must be non-empty strings
    assert isinstance(settings.GROQ_API_KEY, str) and settings.GROQ_API_KEY != ""
    assert isinstance(settings.SECURE_URL_SECRET, str) and settings.SECURE_URL_SECRET != ""
    assert isinstance(settings.GOOGLE_CALENDAR_ID, str) and settings.GOOGLE_CALENDAR_ID != ""
    assert isinstance(settings.CHROMA_DB_PATH, str) and settings.CHROMA_DB_PATH != ""
    assert isinstance(settings.MOCK_CALENDAR_PATH, str) and settings.MOCK_CALENDAR_PATH != ""


def test_settings_types():
    """Settings fields have the correct types."""
    from config.settings import settings

    assert isinstance(settings.RAG_TOP_K, int) and settings.RAG_TOP_K > 0
    assert isinstance(settings.MAX_TURNS_PER_CALL, int) and settings.MAX_TURNS_PER_CALL > 0
    assert isinstance(settings.CALENDAR_SLOT_DURATION_MINUTES, int)
    assert isinstance(settings.STT_CONFIDENCE_THRESHOLD, float)
    assert 0.0 < settings.STT_CONFIDENCE_THRESHOLD <= 1.0


def test_settings_secure_url_secret_length():
    """SECURE_URL_SECRET must be at least 32 characters for HMAC safety."""
    from config.settings import settings

    assert len(settings.SECURE_URL_SECRET) >= 32, (
        f"SECURE_URL_SECRET is only {len(settings.SECURE_URL_SECRET)} chars — must be >= 32"
    )


# ---------------------------------------------------------------------------
# TC-0.2 — mock_calendar.json is valid and parseable
# ---------------------------------------------------------------------------

def test_mock_calendar_schema():
    """mock_calendar.json exists, has >= 15 slots, all with valid ISO 8601 datetimes."""
    cal_path = os.path.join(PROJECT_ROOT, "data", "mock_calendar.json")
    assert os.path.exists(cal_path), f"mock_calendar.json not found at {cal_path}"

    with open(cal_path) as f:
        cal = json.load(f)

    assert "slots" in cal, "Top-level key 'slots' missing"
    assert "advisor_id" in cal, "Top-level key 'advisor_id' missing"
    assert "timezone" in cal, "Top-level key 'timezone' missing"
    assert len(cal["slots"]) >= 15, f"Expected >= 15 slots, got {len(cal['slots'])}"

    for slot in cal["slots"]:
        assert "slot_id" in slot, f"slot missing 'slot_id': {slot}"
        assert "start" in slot, f"slot missing 'start': {slot}"
        assert "end" in slot, f"slot missing 'end': {slot}"
        assert "status" in slot, f"slot missing 'status': {slot}"
        assert "topic_affinity" in slot, f"slot missing 'topic_affinity': {slot}"

        # ISO 8601 datetimes must be parseable
        start_dt = datetime.fromisoformat(slot["start"])
        end_dt = datetime.fromisoformat(slot["end"])

        # End must be after start
        assert end_dt > start_dt, f"Slot end <= start: {slot['slot_id']}"

        # Status must be a known value
        assert slot["status"] in {"AVAILABLE", "TENTATIVE", "CONFIRMED", "CANCELLED"}, (
            f"Unknown status '{slot['status']}' in slot {slot['slot_id']}"
        )

        # topic_affinity must be a list
        assert isinstance(slot["topic_affinity"], list), (
            f"topic_affinity must be a list in slot {slot['slot_id']}"
        )


def test_mock_calendar_has_available_slots():
    """At least 10 slots must have status AVAILABLE."""
    cal_path = os.path.join(PROJECT_ROOT, "data", "mock_calendar.json")
    with open(cal_path) as f:
        cal = json.load(f)
    available = [s for s in cal["slots"] if s["status"] == "AVAILABLE"]
    assert len(available) >= 10, f"Expected >= 10 AVAILABLE slots, got {len(available)}"


def test_mock_calendar_has_topic_affinity_slots():
    """At least 3 slots must have non-empty topic_affinity restrictions."""
    cal_path = os.path.join(PROJECT_ROOT, "data", "mock_calendar.json")
    with open(cal_path) as f:
        cal = json.load(f)
    restricted = [s for s in cal["slots"] if s.get("topic_affinity")]
    assert len(restricted) >= 3, (
        f"Expected >= 3 slots with topic_affinity restrictions, got {len(restricted)}"
    )


# ---------------------------------------------------------------------------
# TC-0.3 — ChromaDB collection exists and has >= 50 chunks
# ---------------------------------------------------------------------------

def test_chroma_collection_populated():
    """
    ChromaDB collection 'advisor_faq' must exist and contain >= 50 chunks.
    The conftest.py session fixture builds this automatically if needed.
    """
    try:
        import chromadb
    except ImportError:
        pytest.skip("chromadb not installed")

    from config.settings import settings
    chroma_path = os.environ.get("CHROMA_DB_PATH", settings.CHROMA_DB_PATH)

    client = chromadb.PersistentClient(path=chroma_path)
    col = client.get_collection("advisor_faq")
    count = col.count()
    assert count >= 50, f"Expected >= 50 chunks in ChromaDB, got {count}"


def test_chroma_collection_has_all_topics():
    """Each of the 5 topic keys must be represented in the ChromaDB collection."""
    try:
        import chromadb
    except ImportError:
        pytest.skip("chromadb not installed")

    from config.settings import settings
    chroma_path = os.environ.get("CHROMA_DB_PATH", settings.CHROMA_DB_PATH)

    expected_topics = {
        "kyc_onboarding",
        "sip_mandates",
        "statements_tax",
        "withdrawals",
        "account_changes",
    }

    client = chromadb.PersistentClient(path=chroma_path)
    col = client.get_collection("advisor_faq")

    for topic in expected_topics:
        results = col.get(where={"topic_key": topic}, limit=1)
        docs = results.get("documents", [])
        assert len(docs) > 0, f"No chunks found for topic '{topic}' in ChromaDB"


# ---------------------------------------------------------------------------
# TC-0.4 — RAG query returns topic-relevant chunks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,expected_topic",
    [
        ("what documents do I need for KYC", "kyc_onboarding"),
        ("how to set up a SIP mandate", "sip_mandates"),
        ("how long does withdrawal take", "withdrawals"),
        ("how to add a nominee", "account_changes"),
        ("where can I get my tax statement", "statements_tax"),
    ],
)
def test_rag_query_topic_relevance(query, expected_topic):
    """RAG query returns a non-empty, relevant context string for each topic."""
    from src.agent.rag_injector import get_rag_context

    context = get_rag_context(query=query, topic=expected_topic)

    assert isinstance(context, str), "get_rag_context must return a string"
    assert len(context) > 0, f"Expected non-empty context for query: '{query}'"
    assert context != "No relevant context found.", (
        f"RAG returned fallback string for query '{query}' / topic '{expected_topic}'"
    )


def test_rag_query_returns_string_type():
    """get_rag_context always returns a str, never None or other type."""
    from src.agent.rag_injector import get_rag_context

    result = get_rag_context(query="test query", topic="kyc_onboarding")
    assert isinstance(result, str)


def test_rag_query_result_format():
    """Returned context is formatted with numbered passages [1], [2], ..."""
    from src.agent.rag_injector import get_rag_context

    context = get_rag_context(query="what is KYC", topic="kyc_onboarding")
    if context != "No relevant context found.":
        assert "[1]" in context, "Expected numbered passages starting with [1]"


# ---------------------------------------------------------------------------
# TC-0.5 — RAG returns graceful fallback when ChromaDB is empty
# ---------------------------------------------------------------------------

def test_rag_empty_db_fallback(tmp_path, monkeypatch):
    """
    When CHROMA_DB_PATH points to an empty directory, get_rag_context
    must return 'No relevant context found.' without raising an exception.
    """
    monkeypatch.setenv("CHROMA_DB_PATH", str(tmp_path))

    # Force re-import with new env var (rag_injector reads env at call time)
    from src.agent import rag_injector
    import importlib
    importlib.reload(rag_injector)

    result = rag_injector.get_rag_context(query="anything", topic="kyc_onboarding")
    assert result == "No relevant context found.", (
        f"Expected fallback string, got: '{result}'"
    )


def test_rag_nonexistent_topic_does_not_raise():
    """
    Querying for a topic that has no documents in ChromaDB must not raise —
    it should return a non-empty string (either results from other topics or fallback).
    """
    from src.agent.rag_injector import get_rag_context

    # Should not raise even if topic has no chunks
    result = get_rag_context(query="tell me about derivatives", topic="unknown_topic_xyz")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TC-0.6 — Scraping pipeline creates output files [INTEGRATION]
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_scrape_creates_output(tmp_path):
    """
    Running scrape_faq.py for a single topic creates at least one .txt file
    with more than 100 bytes of content.

    Marked [integration] — skipped unless RUN_INTEGRATION=true.
    """
    run_integration = os.environ.get("RUN_INTEGRATION", "false").lower() == "true"
    if not run_integration:
        pytest.skip("Set RUN_INTEGRATION=true to run integration tests")

    script = os.path.join(PROJECT_ROOT, "scripts", "scrape_faq.py")
    result = subprocess.run(
        [sys.executable, script, "--topic", "kyc_onboarding", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"scrape_faq.py failed:\n{result.stderr}"

    files = list(tmp_path.glob("**/*.txt"))
    assert len(files) >= 1, "Expected at least one .txt file to be created"
    assert files[0].stat().st_size > 100, (
        f"Output file too small: {files[0].stat().st_size} bytes"
    )


@pytest.mark.integration
def test_build_index_populates_chroma(tmp_path):
    """
    Running build_index.py against scraped data creates a ChromaDB collection
    with >= 50 chunks.

    Marked [integration] — skipped unless RUN_INTEGRATION=true.
    """
    run_integration = os.environ.get("RUN_INTEGRATION", "false").lower() == "true"
    if not run_integration:
        pytest.skip("Set RUN_INTEGRATION=true to run integration tests")

    try:
        import chromadb
    except ImportError:
        pytest.skip("chromadb not installed")

    from scripts.scrape_faq import TOPIC_KEYS, scrape_topic
    from scripts.build_index import build_index

    raw_docs = tmp_path / "raw_docs"
    chroma_dir = tmp_path / "chroma_db"

    for topic in TOPIC_KEYS:
        scrape_topic(topic, str(raw_docs))

    count = build_index(
        raw_docs_dir=str(raw_docs),
        chroma_path=str(chroma_dir),
        collection_name="test_advisor_faq",
    )
    assert count >= 50, f"Expected >= 50 chunks, got {count}"
