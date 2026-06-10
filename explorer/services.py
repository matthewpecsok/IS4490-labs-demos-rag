from functools import lru_cache

import numpy as np


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def chunk_text(text, chunk_size, overlap):
    """Split text into fixed word windows and retain source word positions."""
    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")
    if overlap < 0:
        raise ValueError("Overlap cannot be negative.")
    if overlap >= chunk_size:
        raise ValueError("Overlap must be smaller than chunk size.")

    words = text.split()
    step = chunk_size - overlap
    chunks = []

    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break

        chunks.append(
            {
                "id": len(chunks),
                "text": " ".join(chunk_words),
                "start_word": start + 1,
                "end_word": start + len(chunk_words),
                "word_count": len(chunk_words),
                "overlap_count": min(overlap, len(chunk_words))
                if chunks
                else 0,
            }
        )

        if start + chunk_size >= len(words):
            break

    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def search_chunks(query, text, chunk_size, overlap, top_k, model=None):
    chunks = chunk_text(text, chunk_size, overlap)
    if not query.strip() or not chunks:
        return []

    embedding_model = model or get_embedding_model()
    passages = [chunk["text"] for chunk in chunks]
    embeddings = embedding_model.encode(
        [query] + passages,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    query_embedding = embeddings[0]
    chunk_embeddings = embeddings[1:]
    scores = np.dot(chunk_embeddings, query_embedding)
    ranked_indices = np.argsort(scores)[::-1][: min(top_k, len(chunks))]

    results = []
    for rank, index in enumerate(ranked_indices, start=1):
        result = dict(chunks[int(index)])
        result["rank"] = rank
        result["score"] = round(float(scores[int(index)]), 4)
        results.append(result)

    return results
