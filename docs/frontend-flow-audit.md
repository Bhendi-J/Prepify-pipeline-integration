# Prepify Phase 6 verification — 2026-09-08

This report supersedes the earlier single-question/search-block flow. The implementation uses the existing PostgreSQL, Redis, Celery, and Hugging Face configuration. No grading or scheduling redesign was performed.

## Current behavior

- Notes, Practice, and Study sessions are separate workspace views.
- Notes cards are paginated and filterable by title. The reader shows an on-demand cached summary or the original text, paginated by characters.
- A new session generates 1–5 questions through one API request and one generation model call. An optional document filter is applied before vector ranking; an optional query guides ranking and generation.
- Validated batches are stored atomically. Normalized text/similarity checks reject identical and closely worded repeats. Request UUIDs make successful creation retry-safe.
- Practice displays only the opened session, one question at a time, with previous/next and direct question-number navigation. Session folders have their own pagination.
- Answer reveal is separate from self-rating. Attempt UUIDs protect retries, and recorded attempts are restored on reopening. Typed drafts and unrecorded reveals are not persisted across reloads or topic changes.
- Generation shares a per-user transaction lock for quota enforcement. Empty extracted notes fail ingestion instead of becoming ready.

## Endpoints and storage

- `POST /api/v1/study-sessions/`: `topic_id`, UUID `request_id`, optional `document_id`, `query`, `count` (1–5), difficulty/type.
- `GET /api/v1/study-sessions/?topic_id=…&page=…&page_size=6`: folder history.
- `GET /api/v1/study-sessions/{id}?page=…&page_size=1`: session question page and recorded attempts.
- `GET /api/v1/documents/{id}/content?page=…&page_size=4000`: original text.
- `GET /api/v1/documents/{id}/summary`: summary/status.
- `POST /api/v1/documents/{id}/summary`: enqueue/retry failed summary; reuse cached or in-flight work.
- Existing reveal, attempt, progress, and legacy single-question endpoints remain available. Legacy generation also saves into a session.

Migration `8d92f0a63b17` adds attempt submission IDs. Migration `9a36c20f7b41` adds study sessions, question links, and document summaries. It preserves old questions in one “Earlier questions” folder per topic; historical session boundaries cannot be recovered because they were not recorded.

Summaries use `HF_TOKEN`, `HUGGINGFACE_CHAT_PROVIDER`, and optional `HUGGINGFACE_SUMMARY_MODEL`, falling back to `HUGGINGFACE_QUESTION_MODEL`. Celery's `summarize_document` task processes the source in bounded sections and reduces summaries for long notes. Ready summaries are cached.

## Ordered verification results

1. **Live HF check completed; quality limitations found.** Three questions were returned in **2.02 seconds**. One claimed groundwater is the primary source of water for plants, which was not established by the supplied notes. Another was a true/false question despite requesting short answers. Summary generation took **2.35 seconds** and produced coherent water-cycle notes, but added minor elaborations such as water release through leaves. Availability passed; strict grounding/type adherence did not fully pass. Times are end-to-end service-call measurements from one synthetic sample.
2. **Worker restart passed.** Stopped the old worker (PID 23464), then ran the unchanged `zsh run_celery_worker.sh`. Registration confirmed:

   ```text
   -> celery@JatinN: OK
       * process_document
       * summarize_document
   1 node online.
   ```
3. **Read-only coverage passed.** Before creating walkthrough data: **16 total questions, 16 with session links, all 16 under Earlier questions, 0 unassigned, 0 owner/topic mismatches**. Nothing was deleted or regenerated in this check.
4. **Full live walkthrough passed.** Real browser and API, with no mocked responses: uploaded synthetic notes → real Celery/HF ingestion → selected that document → generated 3 questions → confirmed only that session's current question displayed → reopened Earlier questions → generated a real background summary → read original pages 1 and 2. No flow deviations. The labeled document `Phase 6 live walkthrough 1788862542546` and session **23** remain in the account for inspection. This adds three questions after the step-3 count.
5. **Manual summary status recovery passed.** Fetch failures now show a recovery message instead of permanent “Loading summary.” Retry is also available for pending/processing states. It starts a fresh GET and resumes polling rather than rereading cached React state. Three targeted browser tests passed (fetch failure, pending, processing), plus production build. Tests simulate server state changes; a real worker crash was not injected.
6. **Documentation updated.** README and this report describe the implemented session/reader flow, migration, configuration, and verification limits.

The earlier implementation run passed 13 browser tests and 22 backend tests. This pass ran only the three new recovery tests and the build, plus the requested live checks; it did not rerun the full suites.

## Remaining limits

- **Grounding and format quality:** prompt instructions and duplicate checks do not guarantee source-supported answers or question-type adherence. The live sample exposed both issues; a separate targeted change is needed if strict guarantees are required.
- **Stranded summary jobs:** status Retry refreshes the server state; it does not automatically requeue a lost job. If a crashed worker leaves the database permanently pending/processing, repeated GETs still return that state. Failed jobs can be re-enqueued with Retry summary. Orphan detection/recovery remains unimplemented.
- **Scheduling:** each correct attempt advances the topic's schedule. Multiple answers in one sitting can advance it quickly. This remains intentionally unchanged.
- **Grading:** ratings are self-assessed and trusted. Retry protection does not prevent deliberate fabricated ratings or enforce semantic answer correctness.
- Topic rename/delete/hierarchy and reassignment of unassigned notes are still absent from the UI. Failed document ingestion requires re-upload. Multiple-choice options are text, not automatically scored controls.

All implementation changes remain uncommitted. The pre-existing worker-script edit and Redis dump were not edited and should be excluded from an implementation commit. The synthetic walkthrough records are database data, not Git changes.
