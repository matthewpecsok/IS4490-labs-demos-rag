from functools import lru_cache
import json
import os
from urllib import error, request

import numpy as np


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_URL = os.environ.get(
    "OLLAMA_URL", "http://127.0.0.1:11434/api/generate"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


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


def chunk_documents(documents, chunk_size, overlap):
    chunks = []
    for document_id, document in documents.items():
        for local_chunk in chunk_text(document["content"], chunk_size, overlap):
            chunk = dict(local_chunk)
            chunk["id"] = f"{document_id}:{local_chunk['id']}"
            chunk["document_id"] = document_id
            chunk["document_title"] = document["title"]
            chunks.append(chunk)
    return chunks


def calculate_retrieval_metrics(results, gold_document_ids):
    if not results:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "relevant_chunks_retrieved": 0,
            "gold_documents_retrieved": 0,
            "gold_document_count": len(gold_document_ids),
        }

    relevant_results = [
        result
        for result in results
        if result["document_id"] in gold_document_ids
    ]
    retrieved_gold_documents = {
        result["document_id"] for result in relevant_results
    }
    return {
        "precision_at_k": round(len(relevant_results) / len(results), 4),
        "recall_at_k": round(
            len(retrieved_gold_documents) / len(gold_document_ids), 4
        )
        if gold_document_ids
        else 0.0,
        "relevant_chunks_retrieved": len(relevant_results),
        "gold_documents_retrieved": len(retrieved_gold_documents),
        "gold_document_count": len(gold_document_ids),
    }


def retrieve_help_center(
    question_key,
    question,
    documents,
    chunk_size,
    overlap,
    top_k,
    model=None,
):
    chunks = chunk_documents(documents, chunk_size, overlap)
    embedding_model = model or get_embedding_model()
    embeddings = embedding_model.encode(
        [question] + [chunk["text"] for chunk in chunks],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    scores = np.dot(embeddings[1:], embeddings[0])
    ranked_indices = np.argsort(scores)[::-1][: min(top_k, len(chunks))]
    gold_document_ids = {
        document_id
        for document_id, document in documents.items()
        if question_key in document["relevant_for"]
    }

    results = []
    for rank, index in enumerate(ranked_indices, start=1):
        result = dict(chunks[int(index)])
        result["rank"] = rank
        result["score"] = round(float(scores[int(index)]), 4)
        result["is_relevant"] = result["document_id"] in gold_document_ids
        results.append(result)

    return {
        "results": results,
        "metrics": calculate_retrieval_metrics(results, gold_document_ids),
        "gold_document_ids": sorted(gold_document_ids),
        "total_chunks": len(chunks),
    }


def generate_local_answer(question, results, timeout=60):
    context = "\n\n".join(
        (
            f"[{result['document_id']} | {result['document_title']} | "
            f"chunk {result['id']}]\n{result['text']}"
        )
        for result in results
    )
    prompt = f"""You are the Acme Cloud help center assistant.
Answer the customer's question using only the retrieved context below.
If the context does not contain enough information, say so directly.
Give concise, actionable steps and cite source document IDs in square brackets.

Customer question:
{question}

Retrieved context:
{context}

Answer:"""
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    http_request = request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "available": False,
            "answer": "",
            "model": OLLAMA_MODEL,
            "message": (
                "Ollama is not available. Start Ollama and make sure the configured "
                f"model ({OLLAMA_MODEL}) is installed."
            ),
            "detail": str(exc),
        }

    answer = str(data.get("response", "")).strip()
    return {
        "available": bool(answer),
        "answer": answer,
        "model": data.get("model", OLLAMA_MODEL),
        "message": "" if answer else "The local model returned an empty answer.",
    }
