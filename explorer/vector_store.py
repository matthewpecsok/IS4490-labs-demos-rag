import sqlite3
import time
from pathlib import Path

import numpy as np

from .services import MODEL_NAME, chunk_text, get_embedding_model

DB_PATH = Path(__file__).resolve().parent.parent / "vector_store_data" / "candidates.sqlite3"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def build_index(documents, chunk_size, overlap, model=None):
    """Chunk, embed, and persist every document into the single-file SQLite vector store."""
    rows = [
        (document_id, document, local_chunk)
        for document_id, document in documents.items()
        for local_chunk in chunk_text(document["content"], chunk_size, overlap)
    ]
    if not rows:
        raise ValueError("No chunks were produced from the candidate documents.")

    embedding_model = model or get_embedding_model()
    embeddings = embedding_model.encode(
        [local_chunk["text"] for _, _, local_chunk in rows],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype("float32")

    connection = _connect()
    try:
        connection.execute("DROP TABLE IF EXISTS chunks")
        connection.execute("DROP TABLE IF EXISTS index_meta")
        connection.execute(
            """
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY,
                document_id TEXT NOT NULL,
                document_title TEXT NOT NULL,
                candidate_name TEXT NOT NULL,
                headline TEXT NOT NULL,
                location TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_word INTEGER NOT NULL,
                end_word INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL
            )
            """
        )
        connection.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

        connection.executemany(
            """
            INSERT INTO chunks (
                document_id, document_title, candidate_name, headline, location,
                chunk_index, start_word, end_word, word_count, text, embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document_id,
                    document["title"],
                    document["candidate_name"],
                    document["headline"],
                    document["location"],
                    local_chunk["id"],
                    local_chunk["start_word"],
                    local_chunk["end_word"],
                    local_chunk["word_count"],
                    local_chunk["text"],
                    embedding.tobytes(),
                )
                for (document_id, document, local_chunk), embedding in zip(rows, embeddings)
            ],
        )

        per_document_counts = {}
        for document_id, _, _ in rows:
            per_document_counts[document_id] = per_document_counts.get(document_id, 0) + 1

        meta = {
            "chunk_size": chunk_size,
            "overlap": overlap,
            "model_name": MODEL_NAME,
            "dimensions": int(embeddings.shape[1]),
            "chunk_count": len(rows),
            "document_count": len(documents),
            "built_at": time.time(),
        }
        connection.executemany(
            "INSERT INTO index_meta (key, value) VALUES (?, ?)",
            [(key, str(value)) for key, value in meta.items()],
        )
        connection.commit()
    finally:
        connection.close()

    return {
        **meta,
        "file_path": str(DB_PATH),
        "file_size_bytes": DB_PATH.stat().st_size,
        "chunks_per_document": [
            {
                "document_id": document_id,
                "candidate_name": documents[document_id]["candidate_name"],
                "chunk_count": count,
            }
            for document_id, count in per_document_counts.items()
        ],
    }


def get_index_status():
    if not DB_PATH.exists():
        return None

    connection = _connect()
    try:
        try:
            meta_rows = connection.execute("SELECT key, value FROM index_meta").fetchall()
        except sqlite3.OperationalError:
            return None
    finally:
        connection.close()

    if not meta_rows:
        return None

    meta = dict(meta_rows)
    return {
        "chunk_size": int(meta["chunk_size"]),
        "overlap": int(meta["overlap"]),
        "model_name": meta["model_name"],
        "dimensions": int(meta["dimensions"]),
        "chunk_count": int(meta["chunk_count"]),
        "document_count": int(meta["document_count"]),
        "built_at": float(meta["built_at"]),
        "file_path": str(DB_PATH),
        "file_size_bytes": DB_PATH.stat().st_size,
    }


def search_index(query, top_k, model=None):
    """Load every stored embedding from the SQLite file and rank by cosine similarity."""
    if get_index_status() is None:
        raise LookupError("The vector database has not been built yet.")

    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT document_id, document_title, candidate_name, headline, location,
                   chunk_index, start_word, end_word, word_count, text, embedding
            FROM chunks
            """
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return []

    embedding_matrix = np.vstack([np.frombuffer(row[-1], dtype="float32") for row in rows])

    embedding_model = model or get_embedding_model()
    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0].astype("float32")

    scores = np.dot(embedding_matrix, query_embedding)
    ranked_indices = np.argsort(scores)[::-1][: min(top_k, len(rows))]

    results = []
    for rank, index in enumerate(ranked_indices, start=1):
        row = rows[int(index)]
        results.append(
            {
                "document_id": row[0],
                "document_title": row[1],
                "candidate_name": row[2],
                "headline": row[3],
                "location": row[4],
                "chunk_index": row[5],
                "start_word": row[6],
                "end_word": row[7],
                "word_count": row[8],
                "text": row[9],
                "rank": rank,
                "score": round(float(scores[int(index)]), 4),
            }
        )

    return results
