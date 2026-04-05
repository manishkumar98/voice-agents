"""
src/agent/rag_injector.py

Queries ChromaDB for FAQ context relevant to the user's question and topic.
Used only for the `what_to_prepare` intent to inject grounded context into the LLM prompt.
"""

import os


def get_rag_context(query: str, topic: str, top_k: int | None = None) -> str:
    """
    Query ChromaDB and return a formatted context string.

    Args:
        query:  The user's natural language question.
        topic:  Canonical topic key (e.g. "kyc_onboarding") used as a metadata filter.
        top_k:  Number of chunks to retrieve. Reads from settings if not provided.

    Returns:
        A formatted string of relevant context passages, or "No relevant context found."
        if ChromaDB is empty or the query yields no results.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return "No relevant context found."

    # Read config at call-time so tests can monkeypatch env vars
    chroma_path = os.environ.get("CHROMA_DB_PATH", "data/chroma_db")
    collection_name = os.environ.get("CHROMA_COLLECTION_NAME", "advisor_faq")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    if top_k is None:
        try:
            top_k = int(os.environ.get("RAG_TOP_K", "3"))
        except ValueError:
            top_k = 3

    try:
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection(collection_name)
    except Exception:
        return "No relevant context found."

    if collection.count() == 0:
        return "No relevant context found."

    # Embed the query
    model = SentenceTransformer(embedding_model)
    query_embedding = model.encode([query])[0].tolist()

    # Query with topic filter
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where={"topic_key": topic},
            include=["documents", "metadatas"],
        )
    except Exception:
        # Fallback: query without topic filter if filter fails (e.g. no docs for topic)
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas"],
            )
        except Exception:
            return "No relevant context found."

    documents = results.get("documents", [[]])[0]
    if not documents:
        return "No relevant context found."

    # Format context passages
    context_parts = []
    for i, doc in enumerate(documents, start=1):
        context_parts.append(f"[{i}] {doc.strip()}")

    return "\n\n".join(context_parts)
