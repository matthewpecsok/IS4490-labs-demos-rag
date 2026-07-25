import os

from pydantic import BaseModel, Field

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


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
    """Ask Gemini (via LangChain) to answer a boolean question from retrieved chunks."""
    if not chunks:
        return {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": GEMINI_MODEL,
            "message": "No resume chunks were retrieved for this question.",
        }

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, timeout=timeout)
        classifier = llm.with_structured_output(ResumeQualification)
        result = classifier.invoke(_build_prompt(candidate_name, question, chunks))
    except Exception as exc:
        return {
            "available": False,
            "answer": None,
            "evidence": "",
            "model": GEMINI_MODEL,
            "message": (
                "Gemini is not available. Set GOOGLE_API_KEY (or GEMINI_API_KEY) "
                "and make sure langchain-google-genai is installed."
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
