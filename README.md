# RAG Teaching Labs

A Django teaching application with four interactive pages:

- `/` explores how chunk size, overlap, and Top K affect semantic retrieval over
  a fictional resume.
- `/assignment/` asks students to tune retrieval over a 20-document software help
  center and reports Precision@K and Recall@K before sending the retrieved chunks
  to a local LLM.
- `/vectordb/` embeds three fictional candidate resumes with configurable chunk
  size and overlap, writes the chunks and their embeddings into a single-file
  SQLite vector store (`vector_store_data/candidates.sqlite3`), and lets students
  query that store with a configurable Top K.
- `/classify/` demonstrates why semantic search alone doesn't scale to a large
  resume corpus: it retrieves the top chunks from **one resume at a time**, asks
  Gemini (via LangChain) a yes/no qualification question grounded in that
  evidence, and stores the boolean verdict in a real Django model
  (`ResumeClassification`, in `db.sqlite3`). A separate "query the database" step
  then answers "which candidates qualify?" with a plain ORM/SQL filter — no
  chunking, embeddings, or LLM calls involved.

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

The classify page sends retrieved chunks to Gemini via a direct REST call to
Vertex AI's `generateContent` endpoint (`aiplatform.googleapis.com`), using the
API key as an `x-goog-api-key` header. Set an API key before starting the
server:

```bash
export GOOGLE_API_KEY=your-key-here   # or GEMINI_API_KEY
```

Note: some Google accounts now issue `AQ.`-prefixed API keys instead of the
older `AIza...` format. `AQ.` keys are rejected by the classic Gemini
Developer API (`generativelanguage.googleapis.com`) but work against the
Vertex `aiplatform.googleapis.com` endpoint used here.

Override the model with `GEMINI_MODEL` (defaults to `gemini-3.5-flash`). Without
a key, the page still runs chunking, retrieval, and storage, and clearly reports
classification as unavailable.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000>, <http://127.0.0.1:8000/assignment/>,
<http://127.0.0.1:8000/vectordb/>, or <http://127.0.0.1:8000/classify/>.

## Test

```bash
python manage.py test
# or
pytest
```

## Logs

The `explorer` app logs to the console (see `LOGGING` in `rag_demo/settings.py`).
When a request fails — the embedding model can't load, or a Gemini call raises —
the view returns a generic error to the browser but logs the full exception
with `logger.exception(...)`, so check the `runserver` console output for the
real cause (e.g. a missing/invalid `GEMINI_API_KEY`) instead of guessing from
the user-facing message alone.
