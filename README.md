# Prepify Pipeline Integration

Prepify is a FastAPI backend for uploading study notes, turning them into vector-searchable chunks, generating practice questions, and scheduling review by topic.

## Architecture

- FastAPI serves the API routes under `/api/v1`.
- PostgreSQL stores users, documents, chunks, topics, generated questions, attempts, and topic mastery state.
- pgvector stores chunk embeddings and powers semantic retrieval.
- Redis is the Celery broker/result backend.
- Celery processes uploaded documents asynchronously.
- Hugging Face provides embeddings and question generation in the current local setup.

## Current Flow

1. A user registers and logs in to get a JWT.
2. The user creates topics and uploads `.txt` documents.
3. Uploads are saved locally and queued for Celery.
4. The worker extracts text, chunks it, embeds each chunk, and marks the document `ready`.
5. Topic search retrieves relevant chunks with pgvector distance search.
6. Practice question generation uses the top chunks, stores the answer privately, and returns only the public question fields.
7. Attempts reveal the stored answer and update topic-level mastery scheduling.
8. Progress endpoints show topic mastery and due reviews.

## API Map

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/documents/`
- `GET /api/v1/documents/`
- `GET /api/v1/documents/{document_id}`
- `PATCH /api/v1/documents/{document_id}`
- `POST /api/v1/topics/`
- `GET /api/v1/topics/`
- `GET /api/v1/topics/{topic_id}`
- `PATCH /api/v1/topics/{topic_id}`
- `DELETE /api/v1/topics/{topic_id}`
- `POST /api/v1/topics/{topic_id}/search`
- `POST /api/v1/practice/{topic_id}/question`
- `POST /api/v1/practice/{question_id}/attempt`
- `GET /api/v1/progress/due`
- `GET /api/v1/progress/{topic_id}`

## Local Setup

From `backend/`:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Required environment:

```bash
DATABASE_URL=postgresql+psycopg://postgres@localhost:5433/mydb
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=
EMBEDDING_PROVIDER=huggingface
EMBEDDING_DIMENSIONS=384
HF_TOKEN=
```

Run the API:

```bash
python -m uvicorn app.main:app --reload
```

Run the worker:

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

## Docker Compose

From the repo root:

```bash
docker compose up --build
```

This starts:

- `api` on `http://localhost:8000`
- `worker`
- `postgres` with pgvector
- `redis`

Pass `HF_TOKEN` and `JWT_SECRET_KEY` in your shell or a local `.env` file before running compose.

## Tests

From `backend/`:

```bash
python -m unittest app.tests.test_adaptive_engine app.tests.test_ingestion
python -m unittest app.tests.test_routes
```

The route tests use FastAPI `TestClient` and a real configured database, then clean up their own rows.

## Hardening Already In Place

- Document, topic, question, attempt, and progress reads are scoped to the authenticated user.
- Uploads are limited to `.txt` and capped by `MAX_UPLOAD_BYTES`.
- Failed worker processing marks documents `failed`.
- Queue enqueue failure marks the document `failed` and returns `503`.
- Empty/unready topics return a clean `404` before embedding calls.
- Question responses use a public schema that excludes `answer_text`.
- Question source provenance tracks all retrieved chunks via `question_chunks`.
- Question generation has a daily per-user cap through `MAX_QUESTION_GENERATIONS_PER_DAY`.
- Practice question reuse and mastery updates use Postgres advisory locks to avoid common duplicate/race windows.

## Design Notes

- Mastery is currently topic-level, not question-level. That means one correct attempt advances the topic schedule.
- Free-text grading is not implemented yet. The client currently submits `is_correct`; a future phase can replace that with rubric/LLM grading.
- PDF/DOCX extraction is not implemented yet. Start with `.txt` uploads.
