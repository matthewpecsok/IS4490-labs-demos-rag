import logging
import os

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# Vertex AI's "API key" surface: unlike the generativelanguage.googleapis.com
# Gemini Developer API, this endpoint accepts newer AQ.-prefixed API keys via
# the x-goog-api-key header and needs no GCP project/location in the URL.
GEMINI_API_URL = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "BOOLEAN"},
        "evidence": {"type": "STRING"},
    },
    "required": ["answer", "evidence"],
}


class ResumeQualification(BaseModel):
    """Structured yes/no verdict grounded in retrieved resume evidence."""

    answer: bool = Field(
        description=(
            "True only if the retrieved resume excerpts support a yes answer to "
            "the question. False if the evidence is missing or insufficient."
        )
    )
    evidence: str = Field(
        description=(
            "One or two sentences citing the specific evidence that justifies the "
            "answer. If the answer is false, explain what is missing."
        )
    )


def is_configured():
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def _api_key():
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def _build_prompt(candidate_name, question, chunks):
    context = "\n\n".join(
        f"[chunk {chunk['rank']} | similarity {chunk['score']}]\n{chunk['text']}"
        for chunk in chunks
    )
    return (
        f"You are screening the resume of {candidate_name} against a single "
        "qualification question. Base your answer strictly on the retrieved resume "
        "excerpts below - do not assume anything the excerpts do not state. If the "
        "excerpts do not support a yes, answer false.\n\n"
        f"Question: {question}\n\n"
        f"Retrieved resume excerpts:\n{context}\n"
    )


def classify_chunks(candidate_name, question, chunks, timeout=60):
    """Ask Gemini (via Vertex AI's generateContent REST endpoint) a yes/no question."""
    if not chunks:
        return {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": GEMINI_MODEL,
            "message": "No resume chunks were retrieved for this question.",
        }

    api_key = _api_key()
    try:
        if not api_key:
            raise RuntimeError("No API key in GOOGLE_API_KEY or GEMINI_API_KEY.")

        response = requests.post(
            GEMINI_API_URL.format(model=GEMINI_MODEL),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": _build_prompt(candidate_name, question, chunks)}
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                    "responseSchema": RESPONSE_SCHEMA,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        candidates = response.json()["candidates"]
        text = candidates[0]["content"]["parts"][0]["text"]
        result = ResumeQualification.model_validate_json(text)
    except Exception as exc:
        logger.exception(
            "Gemini classification failed (is_configured=%s, model=%s)",
            is_configured(),
            GEMINI_MODEL,
        )
        return {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": GEMINI_MODEL,
            "message": (
                "Gemini is not available. Set GOOGLE_API_KEY (or GEMINI_API_KEY) to "
                "a key valid for the Vertex AI generateContent endpoint."
            ),
            "detail": str(exc),
        }

    return {
        "available": True,
        "answer": bool(result.answer),
        "evidence": result.evidence,
        "model": GEMINI_MODEL,
        "message": "",
    }
