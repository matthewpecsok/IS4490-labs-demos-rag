import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import gemini_classifier, vector_store
from .candidate_data import CANDIDATE_DOCUMENTS, JOB_POSTING_TEXT, JOB_POSTING_TITLE
from .classification_data import CLASSIFICATION_QUESTIONS
from .help_center_data import ASSIGNMENT_QUESTIONS, HELP_CENTER_DOCUMENTS
from .models import ResumeClassification, question_key_for
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


@require_GET
def vectordb(request):
    return render(
        request,
        "explorer/vectordb.html",
        {
            "candidates": CANDIDATE_DOCUMENTS,
            "job_posting_title": JOB_POSTING_TITLE,
            "job_posting": JOB_POSTING_TEXT,
            "model_name": MODEL_NAME,
            "index_status": vector_store.get_index_status(),
        },
    )


@require_POST
def build_vector_index(request):
    try:
        payload = json.loads(request.body)
        chunk_size = int(payload.get("chunk_size", 80))
        overlap = int(payload.get("overlap", 20))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Index parameters are invalid."}, status=400)

    if not 20 <= chunk_size <= 200:
        return JsonResponse(
            {"error": "Chunk size must be between 20 and 200 words."}, status=400
        )
    if not 0 <= overlap < chunk_size:
        return JsonResponse(
            {"error": "Overlap must be zero or more and smaller than chunk size."},
            status=400,
        )

    try:
        stats = vector_store.build_index(CANDIDATE_DOCUMENTS, chunk_size, overlap)
    except Exception:
        return JsonResponse(
            {
                "error": (
                    "The embedding model could not be loaded. Check the server "
                    "connection and try again; the first build downloads the model."
                )
            },
            status=503,
        )

    return JsonResponse(stats)


@require_POST
def vectordb_search(request):
    try:
        payload = json.loads(request.body)
        query = str(payload.get("query", "")).strip()
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Search parameters are invalid."}, status=400)

    if not query:
        return JsonResponse({"error": "Enter a search term or question."}, status=400)
    if not 1 <= top_k <= 10:
        return JsonResponse({"error": "Top K must be between 1 and 10."}, status=400)

    try:
        results = vector_store.search_index(query, top_k)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except Exception:
        return JsonResponse(
            {
                "error": (
                    "The embedding model could not be loaded. Check the server "
                    "connection and try again."
                )
            },
            status=503,
        )

    return JsonResponse(
        {
            "query": query,
            "results": results,
            "index": vector_store.get_index_status(),
        }
    )


@require_GET
def classify(request):
    return render(
        request,
        "explorer/classify.html",
        {
            "candidates": CANDIDATE_DOCUMENTS,
            "questions": CLASSIFICATION_QUESTIONS,
            "model_name": MODEL_NAME,
            "gemini_model": gemini_classifier.GEMINI_MODEL,
            "gemini_configured": gemini_classifier.is_configured(),
        },
    )


@require_POST
def classify_candidate(request):
    try:
        payload = json.loads(request.body)
        candidate_id = str(payload.get("candidate_id", "")).strip()
        question_key = str(payload.get("question_key", "")).strip()
        question_text = str(payload.get("question_text", "")).strip()
        chunk_size = int(payload.get("chunk_size", 100))
        overlap = int(payload.get("overlap", 20))
        top_k = int(payload.get("top_k", 4))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Classification parameters are invalid."}, status=400)

    if candidate_id not in CANDIDATE_DOCUMENTS:
        return JsonResponse({"error": "Choose a known candidate."}, status=400)
    if question_key != "custom" and question_key not in CLASSIFICATION_QUESTIONS:
        return JsonResponse(
            {"error": "Choose one of the rubric questions or supply a custom one."},
            status=400,
        )
    if question_key == "custom" and not question_text:
        return JsonResponse({"error": "Enter a custom yes/no question."}, status=400)
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

    question = (
        question_text
        if question_key == "custom"
        else CLASSIFICATION_QUESTIONS[question_key]["question"]
    )
    candidate = CANDIDATE_DOCUMENTS[candidate_id]

    try:
        chunks = search_chunks(
            query=question,
            text=candidate["content"],
            chunk_size=chunk_size,
            overlap=overlap,
            top_k=top_k,
        )
    except Exception:
        return JsonResponse(
            {
                "error": (
                    "The embedding model could not be loaded. Check the server "
                    "connection and try again."
                )
            },
            status=503,
        )

    classification = gemini_classifier.classify_chunks(
        candidate["candidate_name"], question, chunks
    )

    stored = None
    if classification["available"]:
        stored_key = question_key_for(question_key, question)
        record, _ = ResumeClassification.objects.update_or_create(
            candidate_id=candidate_id,
            question_key=stored_key,
            defaults={
                "candidate_name": candidate["candidate_name"],
                "question_text": question,
                "answer": classification["answer"],
                "evidence": classification["evidence"],
                "chunk_size": chunk_size,
                "overlap": overlap,
                "top_k": top_k,
                "model_name": classification["model"],
            },
        )
        stored = {"question_key": record.question_key, "updated_at": record.updated_at.isoformat()}

    return JsonResponse(
        {
            "candidate_id": candidate_id,
            "candidate_name": candidate["candidate_name"],
            "question": question,
            "chunks": chunks,
            "classification": classification,
            "stored": stored,
        }
    )


@require_POST
def query_classifications(request):
    try:
        payload = json.loads(request.body)
        question_key = str(payload.get("question_key", "")).strip()
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Query parameters are invalid."}, status=400)

    if question_key not in CLASSIFICATION_QUESTIONS:
        return JsonResponse({"error": "Choose one of the rubric questions."}, status=400)

    records = list(
        ResumeClassification.objects.filter(question_key=question_key).order_by(
            "-answer", "candidate_name"
        )
    )

    return JsonResponse(
        {
            "question_key": question_key,
            "question_text": CLASSIFICATION_QUESTIONS[question_key]["question"],
            "total_classified": len(records),
            "matched_count": sum(1 for record in records if record.answer),
            "results": [
                {
                    "candidate_id": record.candidate_id,
                    "candidate_name": record.candidate_name,
                    "answer": record.answer,
                    "evidence": record.evidence,
                    "updated_at": record.updated_at.isoformat(),
                }
                for record in records
            ],
        }
    )
