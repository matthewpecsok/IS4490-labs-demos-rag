import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .help_center_data import ASSIGNMENT_QUESTIONS, HELP_CENTER_DOCUMENTS
from .resume_data import RESUME_TEXT
from .services import (
    MODEL_NAME,
    OLLAMA_MODEL,
    generate_local_answer,
    retrieve_help_center,
    search_chunks,
)


@require_GET
def index(request):
    return render(
        request,
        "explorer/index.html",
        {
            "resume": RESUME_TEXT,
            "resume_word_count": len(RESUME_TEXT.split()),
            "model_name": MODEL_NAME,
        },
    )


@require_POST
def search(request):
    try:
        payload = json.loads(request.body)
        query = str(payload.get("query", "")).strip()
        chunk_size = int(payload.get("chunk_size", 80))
        overlap = int(payload.get("overlap", 20))
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Search parameters are invalid."}, status=400)

    if not query:
        return JsonResponse({"error": "Enter a search term or question."}, status=400)
    if not 20 <= chunk_size <= 200:
        return JsonResponse(
            {"error": "Chunk size must be between 20 and 200 words."}, status=400
        )
    if not 0 <= overlap < chunk_size:
        return JsonResponse(
            {"error": "Overlap must be zero or more and smaller than chunk size."},
            status=400,
        )
    if not 1 <= top_k <= 10:
        return JsonResponse({"error": "Top K must be between 1 and 10."}, status=400)

    try:
        results = search_chunks(
            query=query,
            text=RESUME_TEXT,
            chunk_size=chunk_size,
            overlap=overlap,
            top_k=top_k,
        )
    except Exception:
        return JsonResponse(
            {
                "error": (
                    "The embedding model could not be loaded. Check the server "
                    "connection and try again; the first search downloads the model."
                )
            },
            status=503,
        )

    return JsonResponse(
        {
            "query": query,
            "results": results,
            "chunk_count": len(results),
            "model": MODEL_NAME,
        }
    )


@require_GET
def assignment(request):
    return render(
        request,
        "explorer/assignment.html",
        {
            "questions": ASSIGNMENT_QUESTIONS,
            "document_count": len(HELP_CENTER_DOCUMENTS),
            "embedding_model": MODEL_NAME,
            "llm_model": OLLAMA_MODEL,
        },
    )


@require_POST
def evaluate_assignment(request):
    try:
        payload = json.loads(request.body)
        question_key = str(payload.get("question_key", "")).strip()
        chunk_size = int(payload.get("chunk_size", 80))
        overlap = int(payload.get("overlap", 20))
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Evaluation parameters are invalid."}, status=400)

    if question_key not in ASSIGNMENT_QUESTIONS:
        return JsonResponse({"error": "Choose one of the assignment questions."}, status=400)
    if not 20 <= chunk_size <= 180:
        return JsonResponse(
            {"error": "Chunk size must be between 20 and 180 words."}, status=400
        )
    if not 0 <= overlap < chunk_size:
        return JsonResponse(
            {"error": "Overlap must be zero or more and smaller than chunk size."},
            status=400,
        )
    if not 1 <= top_k <= 10:
        return JsonResponse({"error": "Top K must be between 1 and 10."}, status=400)

    question = ASSIGNMENT_QUESTIONS[question_key]["question"]
    try:
        retrieval = retrieve_help_center(
            question_key=question_key,
            question=question,
            documents=HELP_CENTER_DOCUMENTS,
            chunk_size=chunk_size,
            overlap=overlap,
            top_k=top_k,
        )
    except Exception:
        return JsonResponse(
            {
                "error": (
                    "The embedding model could not be loaded. The first evaluation "
                    "requires access to the cached or downloadable model."
                )
            },
            status=503,
        )

    llm = generate_local_answer(question, retrieval["results"])
    return JsonResponse(
        {
            "question_key": question_key,
            "question": question,
            "parameters": {
                "chunk_size": chunk_size,
                "overlap": overlap,
                "top_k": top_k,
            },
            "embedding_model": MODEL_NAME,
            "retrieval": retrieval,
            "llm": llm,
        }
    )
