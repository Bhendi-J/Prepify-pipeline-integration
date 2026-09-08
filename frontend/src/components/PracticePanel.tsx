import { useEffect, useRef, useState } from "react";
import { FolderOpen, Sparkles, BookOpen } from "lucide-react";
import MarkdownContent from "./MarkdownContent";
import { api, ApiError, AttemptResult, DocumentItem, SessionPage, SessionQuestions } from "../api";

type View = "notes" | "practice" | "history";
type Choice = { label: string; text: string };
type Review = { draft: string; answer?: string; result?: AttemptResult; responseTimeMs?: number; submissionId?: string; rating?: boolean; selectedOption?: string };
type Props = { token: string; topicId: number; documents: DocumentItem[]; view: View; selectedDocumentId: number | null;
  onDocument: (id: number | null) => void; onView: (view: View) => void; onBusy: (busy: boolean) => void;
  onError: (error: unknown) => void; onRecorded: () => Promise<void> };

export default function PracticePanel({ token, topicId, documents, view, selectedDocumentId, onDocument, onView, onBusy, onError, onRecorded }: Props) {
  const [query, setQuery] = useState("");
  const [count, setCount] = useState(1);
  const [difficulty, setDifficulty] = useState("medium");
  const [questionType] = useState("multiple_choice");
  const [active, setActive] = useState<SessionQuestions | null>(null);
  const [history, setHistory] = useState<SessionPage | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [reviews, setReviews] = useState<Record<number, Review>>({});
  const [jump, setJump] = useState(1);
  const alive = useRef(true);
  const busy = useRef(false);
  const startedAt = useRef(Date.now());
  const generation = useRef<{ signature: string; id: string } | null>(null);
  const question = active?.items[0];
  const review = question ? reviews[question.id] : undefined;
  const choices = question ? parseChoices(question.question_text) : null;
  const ready = documents.some((doc) => doc.status === "ready" && (selectedDocumentId === null || doc.id === selectedDocumentId));

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (view !== "history") return;
    let cancelled = false;
    setHistoryLoading(true);
    void api.listSessions(token, topicId, historyPage)
      .then((result) => { if (!cancelled) setHistory(result); })
      .catch((error) => { if (!cancelled) onError(error); })
      .finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [token, topicId, historyPage, historyVersion, view]);

  async function run(name: string, action: () => Promise<void>) {
    if (busy.current) return;
    busy.current = true;
    setOperation(name);
    onBusy(true);
    try { await action(); }
    catch (error) { if (alive.current) onError(error); }
    finally { busy.current = false; if (alive.current) { setOperation(null); onBusy(false); } }
  }
  function updateReview(id: number, patch: Partial<Review>) {
    setReviews((rows) => ({ ...rows, [id]: { ...(rows[id] ?? { draft: "" }), ...patch } }));
  }
  function display(result: SessionQuestions) {
    setActive(result);
    setJump(result.page);
    startedAt.current = Date.now();
    for (const attempt of result.attempts ?? []) updateReview(attempt.question_id, { answer: attempt.answer_text, result: attempt });
    onView("practice");
  }
  async function generate() {
    if (!ready) return;
    await run("generate", async () => {
      const input = { topic_id: topicId, document_id: selectedDocumentId, query: query.trim() || undefined,
        count: Number.isFinite(count) ? Math.max(1, Math.min(5, Math.floor(count))) : 1, difficulty, question_type: questionType };
      const signature = JSON.stringify(input);
      if (generation.current?.signature !== signature) generation.current = { signature, id: crypto.randomUUID() };
      const result = await api.createSession(token, { ...input, request_id: generation.current!.id });
      if (!alive.current) return;
      generation.current = null;
      display(result);
      setHistoryPage(1);
      setHistoryVersion((value) => value + 1);
    });
  }
  async function openSession(id: number, page = 1) {
    await run("open", async () => {
      const result = await api.getSession(token, id, page);
      if (alive.current) display(result);
    });
  }
  async function reveal() {
    if (!question || review?.answer !== undefined) return;
    await run("reveal", async () => {
      const responseTimeMs = Math.max(0, Date.now() - startedAt.current);
      const result = await api.revealAnswer(token, question.id);
      if (alive.current) updateReview(question.id, { answer: result.answer_text, responseTimeMs });
    });
  }
  async function rate(isCorrect: boolean) {
    if (!question || review?.answer === undefined || review.result) return;
    await run("rate", async () => {
      const submissionId = review.submissionId ?? crypto.randomUUID();
      const rating = review.rating ?? isCorrect;
      updateReview(question.id, { submissionId, rating });
      const result = await api.submitAttempt(token, question.id, { is_correct: rating, response_time_ms: review.responseTimeMs, submission_id: submissionId });
      if (!alive.current) return;
      updateReview(question.id, { result });
      try { await onRecorded(); }
      catch (error) {
        if (error instanceof ApiError && error.status === 401) throw error;
        if (alive.current) onError(new Error("Rating saved. Refresh to update your review schedule."));
      }
    });
  }
  async function chooseOption(label: string) {
    if (!question || review?.result?.is_correct) return;
    await run("choice", async () => {
      const submissionId = review?.submissionId ?? crypto.randomUUID();
      const responseTimeMs = Math.max(0, Date.now() - startedAt.current);
      updateReview(question.id, { submissionId, selectedOption: label, responseTimeMs });
      const result = await api.submitChoice(token, question.id, { selected_option: label, response_time_ms: responseTimeMs, submission_id: submissionId });
      if (!alive.current) return;
      updateReview(question.id, { result, answer: result.answer_text });
      try { await onRecorded(); }
      catch (error) {
        if (error instanceof ApiError && error.status === 401) throw error;
        if (alive.current) onError(new Error("Answer saved. Refresh to update your review schedule."));
      }
    });
  }

  return <section hidden={view === "notes"} className="practice-area">
    {view === "history" ? <div className="panel">
      <div className="topbar"><div><h2>Study sessions</h2><p className="muted">Open a folder to revisit just that set of questions.</p></div>
        <button onClick={() => onView("practice")}>New practice</button></div>
      {historyLoading && <p role="status">Loading sessions…</p>}
      {!historyLoading && history?.total === 0 && <p className="empty-state">No sessions yet. Create your first question set in Practice.</p>}
      {!historyLoading && !history && <button onClick={() => setHistoryVersion((value) => value + 1)}>Retry loading sessions</button>}
      <div className="session-grid">{!historyLoading && history?.items.map((item) => <article className="session-card" key={item.id}>
        <div className="card-icon"><FolderOpen size={21} aria-hidden="true" /></div>
        <span className="eyebrow">{item.is_legacy ? "Earlier questions" : "Study session"}</span>
        <h3>{item.title}</h3><p className="muted">{new Date(item.created_at).toLocaleString()} · {item.question_count} questions</p>
        <p>{item.focus || (item.document_id ? documents.find((doc) => doc.id === item.document_id)?.title ?? "Selected notes" : "Topic notes")}</p>
        <button onClick={() => void openSession(item.id)} disabled={operation !== null}>Open session</button>
      </article>)}</div>
      {history && history.total > 0 && <div className="pagination">
        <button disabled={historyLoading || operation !== null || historyPage === 1} onClick={() => setHistoryPage(historyPage - 1)}>Previous sessions</button>
        <span>Page {history.page} of {Math.ceil(history.total / history.page_size)}</span>
        <button disabled={historyLoading || operation !== null || historyPage * history.page_size >= history.total} onClick={() => setHistoryPage(historyPage + 1)}>Next sessions</button>
      </div>}
    </div> : <>
      <div className="panel">
        <div className="section-heading"><span className="heading-icon"><Sparkles size={20} aria-hidden="true" /></span><div><p className="eyebrow">Make it a focused session</p><h2>Start a study session</h2></div></div>
        <p className="muted">Choose your notes, set a focus, and turn what you’ve learned into practice.</p>
        <div className="practice-controls">
          <label>Use notes<select aria-label="Use notes" value={selectedDocumentId ?? ""} onChange={(event) => onDocument(event.target.value ? Number(event.target.value) : null)} disabled={operation !== null}>
            <option value="">All notes in this topic</option>
            {documents.map((doc) => <option key={doc.id} value={doc.id} disabled={doc.status !== "ready"}>{doc.title}{doc.status !== "ready" ? ` (${doc.status})` : ""}</option>)}
          </select></label>
          <label>Focus<input placeholder="Optional focus query" value={query} maxLength={1000} onChange={(event) => setQuery(event.target.value)} disabled={operation !== null} /></label>
          <label>Difficulty<select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} disabled={operation !== null}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
          <label>Question type<input value="Multiple choice" disabled /></label>
          <label>Question count<input aria-label="Question count" type="number" min={1} max={5} step={1} value={count} onChange={(event) => setCount(Number(event.target.value))} disabled={operation !== null} /></label>
          <button className="primary" onClick={() => void generate()} disabled={!ready || operation !== null}>{operation === "generate" ? "Creating session…" : "Create session"}</button>
        </div>
        {!ready && <p className="muted">Upload notes and wait for processing to finish before creating a session.</p>}
        {operation && <p role="status">{operation === "generate" ? "Generating your question set. This can take a moment." : "Loading…"}</p>}
      </div>
      {!active && <div className="panel empty-state"><div className="empty-illustration"><BookOpen size={32} aria-hidden="true" /></div><h2>Your next session starts here</h2><p>Create a question set above, or open a saved session. Older questions stay out of the way.</p><button onClick={() => onView("history")}>Browse study sessions</button></div>}
      {active && question && <div className="panel">
        <div><p className="eyebrow">Current study session</p><h2>{active.session.title}</h2><p className="muted">{active.session.focus || "Practice from your notes"} · {new Date(active.session.created_at).toLocaleString()}</p></div>
        <div className="pagination"><button disabled={operation !== null || active.page <= 1} onClick={() => void openSession(active.session.id, active.page - 1)}>Previous question</button>
          <strong>Question {active.page} of {active.total}</strong><button disabled={operation !== null || active.page >= active.total} onClick={() => void openSession(active.session.id, active.page + 1)}>Next question</button></div>
        <article className="question-box"><p className="muted">{question.difficulty} · {question.question_type.replaceAll("_", " ")}</p>
          {choices ? <><h3 className="notes-text">{choices.stem}</h3><div className="choice-grid">{choices.options.map((choice) => {
            const selected = review?.selectedOption === choice.label;
            const correct = review?.answer?.trim().toUpperCase().startsWith(choice.label);
            return <button key={choice.label} className={review?.result ? correct ? "choice correct" : selected ? "choice missed" : "choice" : "choice"} disabled={operation !== null || review?.result?.is_correct} onClick={() => void chooseOption(choice.label)}><strong>{choice.label}</strong><span>{choice.text}</span></button>;
          })}</div></> : <>
            <h3 className="notes-text">{question.question_text}</h3>
            <textarea placeholder="Type your answer before revealing the stored answer" rows={4} value={review?.draft ?? ""} disabled={operation !== null || review?.answer !== undefined} onChange={(event) => updateReview(question.id, { draft: event.target.value })} />
            {review?.answer === undefined && <button disabled={operation !== null} onClick={() => void reveal()}>Reveal answer</button>}
          </>}
        </article>
        {review?.answer !== undefined && <article className="answer-box"><strong>Reference answer</strong><MarkdownContent>{review.answer}</MarkdownContent>
          {review.draft && <><strong>Your answer</strong><p className="notes-text">{review.draft}</p></>}
          {review.result ? <p>Recorded as {review.result.is_correct ? "correct" : "missed"}. {review.result.is_correct ? `Next review ${new Date(review.result.next_review_at).toLocaleString()}` : "Choose the correct option to clear it from Due Reviews."}</p> : <>
            <p className="muted">Compare with your answer and rate your recall. This is self-assessed; typed drafts are not saved after a page reload.</p>
            <div className="actions"><button disabled={operation !== null || review.rating === false} onClick={() => void rate(true)}>{review.rating === true ? "Retry correct rating" : "I got it right"}</button>
              <button disabled={operation !== null || review.rating === true} onClick={() => void rate(false)}>{review.rating === false ? "Retry missed rating" : "I missed it"}</button></div>
          </>}
        </article>}
        <form className="pagination" onSubmit={(event) => { event.preventDefault(); if (Number.isInteger(jump) && jump >= 1 && jump <= active.total) void openSession(active.session.id, jump); }}>
          <label>Go to question<input aria-label="Go to question" type="number" min={1} max={active.total} value={jump} onChange={(event) => setJump(Number(event.target.value))} /></label><button disabled={operation !== null} type="submit">Go</button>
        </form>
      </div>}
    </>}
  </section>;
}

function parseChoices(questionText: string): { stem: string; options: Choice[] } | null {
  const lines = questionText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const options: Choice[] = [];
  const stem: string[] = [];
  for (const line of lines) {
    const match = line.match(/^(?:[-*]\s*)?([A-D])[\).:-]\s+(.+)$/i);
    if (match) options.push({ label: match[1].toUpperCase(), text: match[2].trim() });
    else if (options.length === 0) stem.push(line);
  }
  if (options.length !== 4 || options.map((option) => option.label).join("") !== "ABCD") return null;
  return { stem: stem.join("\n") || "Choose the best answer.", options };
}
