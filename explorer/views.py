import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .resume_data import RESUME_TEXT
from .services import MODEL_NAME, search_chunks


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
