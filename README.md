# RAG Teaching Labs

A Django teaching application with two interactive pages:

- `/` explores how chunk size, overlap, and Top K affect semantic retrieval over
  a fictional resume.
- `/assignment/` asks students to tune retrieval over a 20-document software help
  center and reports Precision@K and Recall@K before sending the retrieved chunks
  to a local LLM.

The backend uses the Hugging Face
`sentence-transformers/all-MiniLM-L6-v2` embedding model. The first search
downloads the model into `.cache/huggingface`; later searches run locally.

The assignment page sends retrieved context to
[Ollama](https://ollama.com/) at `http://127.0.0.1:11434/api/generate`. It uses
`llama3.2:3b` by default:

```bash
ollama pull llama3.2:3b
ollama serve
```

Override the defaults with `OLLAMA_URL` and `OLLAMA_MODEL`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open <http://127.0.0.1:8000> or
<http://127.0.0.1:8000/assignment/>.

## Test

```bash
python manage.py test
```
