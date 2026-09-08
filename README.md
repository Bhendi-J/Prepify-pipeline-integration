# Prepify Pipeline Integration

Prepify is a FastAPI backend for uploading study notes, turning them into vector-searchable chunks, generating practice questions, and scheduling review by topic.

## Architecture

- FastAPI serves the API routes under `/api/v1`.
- PostgreSQL stores users, documents, chunks, topics, study sessions, generated questions, attempts, and topic mastery state.
- pgvector stores chunk embeddings and powers semantic retrieval.
- Redis is the Celery broker/result backend.
- Celery processes uploads and generates cached document summaries asynchronously.
- Hugging Face provides embeddings, batch question generation, and summaries in the current local setup.

## Current Flow

1. A user registers and logs in to get a JWT.
2. The user creates topics and uploads `.txt` documents.
3. Uploads are saved locally and queued for Celery.
4. The worker extracts text, chunks it, embeds each chunk, and marks the document `ready`.
5. In Notes, users open a document reader with a cached AI summary and paginated original text. The library filters document titles instead of rendering raw search chunks.
6. In Practice, users choose all topic notes or a specific document plus an optional focus. One request generates 1–5 questions in one model call. Selected-document filtering happens before vector ranking.
7. A validated question batch is saved atomically as a study session. Practice shows only the opened session, one question per page, with direct question navigation.
8. Study sessions lists saved folders, six per page. Existing questions are preserved under “Earlier questions.”
9. Users reveal answers and self-rate. Saved attempts are restored when reopening a session; typed drafts remain in browser memory only.
10. Progress shows topic-level mastery and due reviews. Grading and topic scheduling remain unchanged.

## API Map

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/documents/`
- `GET /api/v1/documents/`
- `GET /api/v1/documents/{document_id}`
- `PATCH /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/content?page=1&page_size=4000` — original text, paginated by characters
- `GET /api/v1/documents/{document_id}/summary` — cached summary/status
- `POST /api/v1/documents/{document_id}/summary` — enqueue summary, reuse ready/in-flight results, or retry failed jobs
- `POST /api/v1/study-sessions/` — create a batch; requires `topic_id` and UUID `request_id`, with optional `document_id`, `query`, `count`, `difficulty`, `question_type`
- `GET /api/v1/study-sessions/?topic_id=1&page=1&page_size=6` — session folders
- `GET /api/v1/study-sessions/{session_id}?page=1&page_size=1` — question page and existing attempts
- `POST /api/v1/topics/`
- `GET /api/v1/topics/`
- `GET /api/v1/topics/{topic_id}`
- `PATCH /api/v1/topics/{topic_id}`
- `DELETE /api/v1/topics/{topic_id}`
- `POST /api/v1/topics/{topic_id}/search`
- `POST /api/v1/practice/{topic_id}/question`
- `GET /api/v1/practice/{topic_id}/questions`
- `GET /api/v1/practice/{question_id}/answer`
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
zsh run_celery_worker.sh
```

Run the frontend:

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend calls the API at `http://127.0.0.1:8000` unless `VITE_API_BASE_URL` is set.

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
python -m unittest app.tests.test_routes app.tests.test_generation_and_summaries
```

The route tests use FastAPI `TestClient` and a real configured database, then clean up their own rows.

Frontend browser regressions use mocked API responses. From `frontend/`:

```bash
npx playwright install chromium
npm test
```

If Chrome is already installed, `PLAYWRIGHT_CHANNEL=chrome npm test` uses it instead.

## Hardening Already In Place

- Document, topic, question, attempt, and progress reads are scoped to the authenticated user.
- Uploads are limited to `.txt` and capped by `MAX_UPLOAD_BYTES`.
- Failed worker processing marks documents `failed`.
- Queue enqueue failure marks the document `failed` and returns `503`.
- Empty/unready topics return a clean `404` before embedding calls.
- Question responses use a public schema that excludes `answer_text`.
- Question source provenance tracks all retrieved chunks via `question_chunks`.
- Question generation has a daily per-user cap through `MAX_QUESTION_GENERATIONS_PER_DAY`.
- Generation uses a shared per-user transaction lock for quota enforcement; mastery updates use topic locks. Session request UUIDs prevent duplicate successful batches on retry.
- Batch validation rejects incomplete sets and identical/closely worded questions before saving. It does not verify factual grounding or semantic uniqueness.
- Practice submissions accept an optional `submission_id` UUID. Retrying the same question/rating with the same UUID returns the existing attempt without advancing mastery again. Apply migrations with `alembic upgrade head` before running the updated backend.

## Design Notes

- Mastery is currently topic-level, not question-level. That means one correct attempt advances the topic schedule.
- Free-text grading is not implemented yet. The client currently submits `is_correct`; a future phase can replace that with rubric/LLM grading.
- Revealing an answer does not record a rating. Saved ratings are restored through session reads. Unsubmitted drafts and unrecorded reveals are not persisted across reload/logout or topic changes.
- PDF/DOCX extraction is not implemented yet. Start with `.txt` uploads.

## Session migration and summaries

Run `alembic upgrade head` before starting the updated backend. Migration `8d92f0a63b17` adds retry-safe attempt IDs. Migration `9a36c20f7b41` adds sessions and cached summaries, placing existing questions into one “Earlier questions” folder per topic without deleting them. Previous session boundaries were never stored and cannot be reconstructed.

Summary configuration in `backend/.env`:

- `HF_TOKEN`: existing Hugging Face token.
- `HUGGINGFACE_CHAT_PROVIDER`: shared provider, default `auto`.
- `HUGGINGFACE_QUESTION_MODEL`: question model; also the summary fallback.
- `HUGGINGFACE_SUMMARY_MODEL`: optional summary model override; omit to reuse the question model.

Summary states are `none`, `pending`, `processing`, `ready`, and `failed`. Long notes are split into bounded sections and summarized hierarchically; successful summaries are cached. Restart the worker after code changes and confirm `summarize_document` with `venv/bin/celery -A app.workers.celery_app inspect registered`.

The reader's **Retry** makes a new status request after fetch failures or while a summary is pending/processing. It resumes polling and displays the actual server state. **Retry summary** re-enqueues a failed summary. Status Retry does not itself requeue jobs stranded by a worker crash; automatic orphan-job detection/recovery is not implemented.

## Latest live verification — 2026-09-08

- Real HF batch: three questions in 2.02 seconds. Availability passed, but one question had an unsupported answer and one did not follow the requested short-answer type.
- Real HF summary: 2.35 seconds; coherent, with minor details beyond the supplied source. These are single-run measurements, not performance guarantees.
- Before the walkthrough: 16/16 existing questions belonged to “Earlier questions”; no unassigned questions or owner/topic mismatches.
- Full real-browser walkthrough passed: upload, actual worker ingestion, selected-document batch, isolated Practice session, earlier-session reopening, actual summary task, and both original-text pages.
- Production build and three focused summary-recovery browser tests passed on this date. The prior session implementation passed 13 browser and 22 backend regressions; those complete suites were not rerun in this limited-credit pass.

See [the frontend flow audit](docs/frontend-flow-audit.md) for remaining limits and the verification record.
