import { useEffect, useRef, useState } from "react";
import MarkdownContent from "./MarkdownContent";
import { api, DocumentContent, DocumentItem, DocumentSummary } from "../api";

type Props = { token: string; document: DocumentItem; onBack: () => void; onPractice: () => void; onError: (error: unknown) => void };

export default function DocumentReader({ token, document, onBack, onPractice, onError }: Props) {
  const [mode, setMode] = useState<"summary" | "original">("summary");
  const [page, setPage] = useState(1);
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [checkingSummary, setCheckingSummary] = useState(false);
  const [loading, setLoading] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [version, setVersion] = useState(0);
  const alive = useRef(true);
  const submitting = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: number;
    async function poll() {
      setCheckingSummary(true);
      try {
        const result = await api.getSummary(token, document.id);
        if (cancelled) return;
        setSummary(result);
        setSummaryError(false);
        if (["pending", "processing"].includes(result.status)) timer = window.setTimeout(poll, 2500);
      } catch (error) { if (!cancelled) { setSummaryError(true); onError(error); } }
      finally { if (!cancelled) setCheckingSummary(false); }
    }
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [token, document.id, version]);

  useEffect(() => {
    if (mode !== "original") return;
    let cancelled = false;
    setLoading(true);
    setContent(null);
    void api.getDocumentContent(token, document.id, page)
      .then((result) => { if (!cancelled) setContent(result); })
      .catch((error) => { if (!cancelled) onError(error); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, document.id, page, mode, version]);

  async function summarize() {
    if (submitting.current) return;
    submitting.current = true;
    setRequesting(true);
    try {
      const result = await api.summarizeDocument(token, document.id);
      if (!alive.current) return;
      setSummary(result);
      setVersion((value) => value + 1);
    } catch (error) { if (alive.current) onError(error); }
    finally { submitting.current = false; if (alive.current) setRequesting(false); }
  }

  return <section className="panel reader">
    <div className="topbar"><button onClick={onBack}>← Back to notes</button>
      <button className="primary" onClick={onPractice} disabled={document.status !== "ready"}>Practice these notes</button></div>
    <div><p className="eyebrow">Notes reader</p><h2>{document.title}</h2></div>
    <div className="actions reader-tabs">
      <button className={mode === "summary" ? "primary" : "ghost"} onClick={() => setMode("summary")}>Summary</button>
      <button className={mode === "original" ? "primary" : "ghost"} onClick={() => setMode("original")}>View original notes</button>
    </div>
    {mode === "summary" ? <>
      {summary?.status === "ready" && <><p className="muted">AI summary · Check the original notes for full detail.</p><MarkdownContent>{summary.summary ?? ""}</MarkdownContent></>}
      {summary && ["none", "failed"].includes(summary.status) && <div className="empty-state">
        <p>{summary.status === "failed" ? "The summary could not be completed. You can retry or read the original notes." : "Create a concise summary of these notes. It will be saved here for future visits."}</p>
        <button className="primary" onClick={() => void summarize()} disabled={requesting || document.status !== "ready"}>{requesting ? "Starting…" : summary.status === "failed" ? "Retry summary" : "Summarize notes"}</button>
        {document.status !== "ready" && <p className="muted">Summaries become available when these notes finish processing.</p>}
      </div>}
      {summaryError && <p role="status">Could not refresh the summary status. Retry or read the original notes.</p>}
      {(summaryError || (summary && ["pending", "processing"].includes(summary.status))) && <button disabled={checkingSummary} onClick={() => setVersion((value) => value + 1)}>{checkingSummary ? "Checking…" : "Retry"}</button>}
      {!summaryError && (!summary || ["pending", "processing"].includes(summary.status)) && <p role="status">{summary ? "Summarizing your notes… You can read the original while this runs." : "Loading summary…"}</p>}
    </> : <>
      {loading && <p role="status">Loading notes…</p>}
      {!loading && !content && <button onClick={() => setVersion((value) => value + 1)}>Retry loading notes</button>}
      {content && <>
        <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous page</button>
          <span>Page {content.page} of {content.total_pages}</span><button disabled={page >= content.total_pages} onClick={() => setPage(page + 1)}>Next page</button></div>
        <div className="notes-text">{content.content || "These notes are empty."}</div>
      </>}
    </>}
  </section>;
}
