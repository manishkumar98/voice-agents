"""
scripts/build_index.py

Reads all .txt files from data/raw_docs/, chunks them, embeds them
using all-MiniLM-L6-v2, and upserts to a ChromaDB collection.

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --raw-docs data/raw_docs --chroma-path data/chroma_db
"""

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def chunk_text(text: str, chunk_size: int = 256, chunk_overlap: int = 32) -> list[str]:
    """
    Simple recursive character splitter.
    Tries to split on double-newline first, then single newline, then space.
    """
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", " ", ""]
    for sep in separators:
        if sep and sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            for part in parts:
                candidate = (current + sep + part).lstrip() if current else part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    # If single part is already too long, recurse
                    if len(part) > chunk_size:
                        chunks.extend(chunk_text(part, chunk_size, chunk_overlap))
                        current = ""
                    else:
                        current = part
                        # Add overlap from last chunk
                        if chunks and chunk_overlap > 0:
                            overlap_text = chunks[-1][-chunk_overlap:]
                            current = overlap_text + sep + current
            if current:
                chunks.append(current)
            return [c for c in chunks if c.strip()]

    # No separator worked — hard split
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]


def load_documents(raw_docs_dir: str) -> list[dict]:
    """
    Walk raw_docs_dir and load all .txt files.
    Returns list of {text, topic_key, source_file}.
    """
    docs = []
    if not os.path.isdir(raw_docs_dir):
        print(f"Warning: raw_docs directory not found: {raw_docs_dir}")
        return docs

    for topic_key in os.listdir(raw_docs_dir):
        topic_dir = os.path.join(raw_docs_dir, topic_key)
        if not os.path.isdir(topic_dir):
            continue
        for fname in os.listdir(topic_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(topic_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                docs.append({"text": content, "topic_key": topic_key, "source_file": fpath})

    return docs


def build_index(
    raw_docs_dir: str,
    chroma_path: str,
    collection_name: str = "advisor_faq",
    chunk_size: int = 256,
    chunk_overlap: int = 32,
    embedding_model: str = "all-MiniLM-L6-v2",
) -> int:
    """
    Load docs → chunk → embed → upsert to ChromaDB.
    Returns the total number of chunks indexed.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"Missing dependency: {e}. Run: pip install chromadb sentence-transformers")
        sys.exit(1)

    print(f"Loading documents from: {raw_docs_dir}")
    docs = load_documents(raw_docs_dir)
    if not docs:
        print("No documents found. Run scrape_faq.py first.")
        sys.exit(1)
    print(f"Loaded {len(docs)} document(s).")

    # Chunk all documents
    all_chunks = []
    for doc in docs:
        chunks = chunk_text(doc["text"], chunk_size, chunk_overlap)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                all_chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": chunk.strip(),
                        "topic_key": doc["topic_key"],
                        "source_file": doc["source_file"],
                        "chunk_index": i,
                    }
                )

    print(f"Total chunks: {len(all_chunks)}")

    # Embed
    print(f"Loading embedding model: {embedding_model}")
    model = SentenceTransformer(embedding_model)
    texts = [c["text"] for c in all_chunks]
    print("Embedding chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    # Upsert to ChromaDB
    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)

    # Delete and recreate collection for a clean rebuild
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.get_or_create_collection(collection_name)

    print(f"Upserting {len(all_chunks)} chunks to ChromaDB collection '{collection_name}'...")
    batch_size = 100
    for start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[start : start + batch_size]
        collection.upsert(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=embeddings[start : start + batch_size].tolist(),
            metadatas=[
                {"topic_key": c["topic_key"], "source_file": c["source_file"], "chunk_index": c["chunk_index"]}
                for c in batch
            ],
        )

    final_count = collection.count()
    print(f"Done. ChromaDB collection '{collection_name}' now has {final_count} chunks.")
    return final_count


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(description="Build ChromaDB index from raw FAQ documents.")
    parser.add_argument("--raw-docs", default=os.path.join(project_root, "data", "raw_docs"))
    parser.add_argument("--chroma-path", default=os.path.join(project_root, "data", "chroma_db"))
    parser.add_argument("--collection", default="advisor_faq")
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--chunk-overlap", type=int, default=32)
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    args = parser.parse_args()

    count = build_index(
        raw_docs_dir=args.raw_docs,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embedding_model=args.model,
    )
    if count < 50:
        print(f"Warning: only {count} chunks indexed. Expected >= 50.")
        sys.exit(1)


if __name__ == "__main__":
    main()
