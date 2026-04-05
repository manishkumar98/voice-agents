"""
tests/conftest.py

Sets up the Python path and builds a shared ChromaDB test index
(session-scoped) so TC-0.3 and TC-0.4 work without needing to run
scripts/build_index.py manually first.
"""

import os
import sys

import pytest

# Make sure `config` and `src` are importable from tests
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Point all settings to test-friendly paths relative to project root
os.environ.setdefault("CHROMA_DB_PATH", os.path.join(PROJECT_ROOT, "data", "chroma_db"))
os.environ.setdefault("CHROMA_COLLECTION_NAME", "advisor_faq")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("RAG_TOP_K", "3")
os.environ.setdefault("MOCK_CALENDAR_PATH", os.path.join(PROJECT_ROOT, "data", "mock_calendar.json"))


@pytest.fixture(scope="session", autouse=True)
def build_chroma_index():
    """
    Ensures the ChromaDB test index is populated before any tests run.
    Runs scrape_faq (built-in data only) then build_index.
    Skips if the collection already has enough chunks.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer  # noqa: F401 — verify importable
    except ImportError:
        pytest.skip("chromadb or sentence-transformers not installed — skipping RAG tests")

    chroma_path = os.environ["CHROMA_DB_PATH"]
    collection_name = os.environ["CHROMA_COLLECTION_NAME"]

    # Check if index is already built
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        col = client.get_collection(collection_name)
        if col.count() >= 50:
            return  # Already good
    except Exception:
        pass

    # Run scrape (built-in data) then index
    from scripts.scrape_faq import TOPIC_KEYS, scrape_topic
    from scripts.build_index import build_index

    raw_docs_dir = os.path.join(PROJECT_ROOT, "data", "raw_docs")
    for topic in TOPIC_KEYS:
        scrape_topic(topic, raw_docs_dir)

    build_index(
        raw_docs_dir=raw_docs_dir,
        chroma_path=chroma_path,
        collection_name=collection_name,
    )
