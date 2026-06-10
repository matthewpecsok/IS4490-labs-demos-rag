# Chunk Lab

A single-page Django teaching application for exploring how chunk size, overlap,
and Top K affect semantic retrieval over a fictional resume.

The backend uses the Hugging Face
`sentence-transformers/all-MiniLM-L6-v2` embedding model. The first search
downloads the model into `.cache/huggingface`; later searches run locally.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## Test

```bash
python manage.py test
```
