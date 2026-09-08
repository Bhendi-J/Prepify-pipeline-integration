import { FormEvent, useEffect, useRef, useState } from "react";
import { BookOpen, LogOut, Plus, RefreshCw, Upload, FileText, FolderOpen, Sparkles, Layers, CheckCircle2, Clock } from "lucide-react";
import { api, ApiError, DocumentItem, DueTopic, Mastery, Topic } from "./api";
import DocumentReader from "./components/DocumentReader";
import PracticePanel from "./components/PracticePanel";

type View = "notes" | "practice" | "history";
type Notice = { type: "ok" | "error"; message: string } | null;

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("prepify_token"));
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [dueTopics, setDueTopics] = useState<DueTopic[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [progress, setProgress] = useState<Mastery | null>(null);
  const [view, setView] = useState<View>("practice");
  const [readerId, setReaderId] = useState<number | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [newTopic, setNewTopic] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [notesFilter, setNotesFilter] = useState("");
  const [notesPage, setNotesPage] = useState(1);
  const [notice, setNotice] = useState<Notice>(null);
  const [operation, setOperation] = useState<string | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [practiceBusy, setPracticeBusy] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const epoch = useRef(0);
  const busy = useRef(false);
  const loading = workspaceLoading || operation !== null || practiceBusy;
  const topic = topics.find((row) => row.id === topicId);
  const topicDocuments = documents.filter((doc) => doc.topic_id === topicId);
  const reader = topicDocuments.find((doc) => doc.id === readerId);
  const filteredNotes = topicDocuments.filter((doc) => doc.title.toLowerCase().includes(notesFilter.toLowerCase()));
  const notePages = Math.max(1, Math.ceil(filteredNotes.length / 6));
  const displayedNotesPage = Math.min(notesPage, notePages);
  const activeUploads = documents.some((doc) => ["pending", "processing"].includes(doc.status));

  function logout() {
    epoch.current += 1;
    busy.current = false;
    localStorage.removeItem("prepify_token");
    setToken(null); setTopics([]); setDocuments([]); setDueTopics([]); setTopicId(null);
    setReaderId(null); setSelectedDocumentId(null); setProgress(null); setNewTopic("");
    setUploadTitle(""); setUploadFile(null); setPassword(""); setNotice(null);
    setOperation(null); setWorkspaceLoading(false); setPracticeBusy(false);
    setNotesFilter(""); setNotesPage(1); setView("practice");
  }
  function showError(error: unknown) {
    if (token && error instanceof ApiError && error.status === 401) {
      logout(); setNotice({ type: "error", message: "Your session expired. Please log in again." }); return;
    }
    setNotice({ type: "error", message: error instanceof Error ? error.message : "Something went wrong" });
  }

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const version = epoch.current;
    const current = () => !cancelled && version === epoch.current;
    setWorkspaceLoading(true);
    void Promise.all([api.listTopics(token), api.listDocuments(token), api.getDue(token)])
      .then(([topicRows, documentRows, dueRows]) => {
        if (!current()) return;
        setTopics(topicRows); setDocuments(documentRows); setDueTopics(dueRows);
        setTopicId((id) => topicRows.some((row) => row.id === id) ? id : topicRows[0]?.id ?? null);
      }).catch((error) => { if (current()) showError(error); })
      .finally(() => { if (current()) setWorkspaceLoading(false); });
    return () => { cancelled = true; };
  }, [token, refreshVersion]);

  useEffect(() => {
    if (!token || topicId === null) return;
    let cancelled = false;
    const version = epoch.current;
    setProgress(null);
    void api.getProgress(token, topicId).then((row) => { if (!cancelled && version === epoch.current) setProgress(row); })
      .catch((error) => { if (!cancelled && version === epoch.current) showError(error); });
    return () => { cancelled = true; };
  }, [token, topicId, refreshVersion]);

  useEffect(() => {
    if (!token || !activeUploads) return;
    let cancelled = false;
    let timer: number;
    const version = epoch.current;
    const current = () => !cancelled && version === epoch.current;
    async function poll() {
      try { const rows = await api.listDocuments(token!); if (current()) setDocuments(rows); }
      catch (error) { if (current()) showError(error); }
      finally { if (current()) timer = window.setTimeout(poll, 2500); }
    }
    timer = window.setTimeout(poll, 2500);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [token, activeUploads]);

  async function run(name: string, action: (current: () => boolean) => Promise<void>) {
    if (busy.current || workspaceLoading || practiceBusy) return;
    busy.current = true;
    const version = epoch.current;
    const current = () => version === epoch.current;
    setOperation(name); setNotice(null);
    try { await action(current); }
    catch (error) { if (current()) showError(error); }
    finally { if (current()) { busy.current = false; setOperation(null); } }
  }
  async function handleAuth(event: FormEvent) {
    event.preventDefault();
    await run("auth", async (current) => {
      if (authMode === "register") { await api.register(email.trim(), password); if (!current()) return; setAuthMode("login"); }
      const result = await api.login(email.trim(), password);
      if (!current()) return;
      localStorage.setItem("prepify_token", result.access_token); setToken(result.access_token); setPassword("");
    });
  }
  function selectTopic(id: number) {
    if (loading || id === topicId) return;
    setTopicId(id); setReaderId(null); setSelectedDocumentId(null); setView("practice");
    setNotesFilter(""); setNotesPage(1); setUploadTitle(""); setUploadFile(null); setNotice(null);
    if (fileInput.current) fileInput.current.value = "";
  }
  async function createTopic(event: FormEvent) {
    event.preventDefault();
    if (!token || !newTopic.trim()) return;
    await run("topic", async (current) => {
      const row = await api.createTopic(token, newTopic.trim());
      if (!current()) return;
      setTopics((rows) => [...rows, row]); setTopicId(row.id); setNewTopic("");
      setReaderId(null); setSelectedDocumentId(null); setView("notes"); setNotesFilter(""); setNotesPage(1);
    });
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!token || topicId === null || !uploadFile) return;
    if (!uploadFile.name.toLowerCase().endsWith(".txt") || uploadFile.size === 0) { showError(new Error("Choose a non-empty .txt file.")); return; }
    await run("upload", async (current) => {
      try {
        const row = await api.uploadDocument(token, { title: uploadTitle.trim() || uploadFile.name, topic_id: topicId, file: uploadFile });
        if (!current()) return;
        setDocuments((rows) => [row, ...rows]); setUploadTitle(""); setUploadFile(null); setNotesPage(1); setNotesFilter("");
        if (fileInput.current) fileInput.current.value = "";
        setNotice({ type: "ok", message: "Upload queued. You can read the notes now; practice and summaries become available after processing." });
      } catch (error) { if (current()) setRefreshVersion((value) => value + 1); throw error; }
    });
  }
  async function refreshProgress() {
    if (!token || topicId === null) return;
    const version = epoch.current;
    const [row, due] = await Promise.all([api.getProgress(token, topicId), api.getDue(token)]);
    if (version === epoch.current) { setProgress(row); setDueTopics(due); }
  }
  function practiceDocument(id: number) { setSelectedDocumentId(id); setReaderId(null); setView("practice"); setNotice(null); }

  if (!token) return <main className="auth-page"><section className="auth-panel">
    <div className="auth-intro"><span className="auth-icon"><BookOpen size={36} aria-hidden="true" /></span><p className="eyebrow">YOUR PERSONAL STUDY SPACE</p><h1>Small sessions.<br />Lasting knowledge.</h1><p className="muted">Read summaries, practice in focused sessions, and revisit your progress.</p></div>
    <form className="stack" onSubmit={handleAuth}>
      <div className="segmented"><button type="button" className={authMode === "login" ? "active" : ""} disabled={loading} onClick={() => setAuthMode("login")}>Login</button><button type="button" className={authMode === "register" ? "active" : ""} disabled={loading} onClick={() => setAuthMode("register")}>Register</button></div>
      <label>Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" required minLength={authMode === "register" ? 8 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="primary" disabled={loading}>{loading ? "Signing in…" : authMode === "login" ? "Login" : "Create Account"}</button>
      {notice && <p className={`notice ${notice.type}`}>{notice.message}</p>}
    </form>
  </section></main>;

  return <main className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark"><BookOpen size={22} aria-hidden="true" /></span><span>prepify<span className="brand-dot">.</span></span></div><div className="workspace-label"><span className="workspace-avatar">P</span><div>Personal workspace<small>Your learning, organized</small></div></div><p className="sidebar-label">YOUR TOPICS <span>{topics.length}</span></p>
      <form className="topic-form" onSubmit={createTopic}><input placeholder="New topic" value={newTopic} onChange={(event) => setNewTopic(event.target.value)} /><button title="Create topic" disabled={loading || !newTopic.trim()}><Plus size={18} /></button></form>
      <nav className="topic-list" aria-label="Topics">{topics.map((row) => <button key={row.id} className={topicId === row.id ? "selected" : ""} disabled={loading} onClick={() => selectTopic(row.id)}><FolderOpen size={17} aria-hidden="true" /><span>{row.name}</span></button>)}</nav>
      <div className="sidebar-tip"><Sparkles size={18} aria-hidden="true" /><strong>A little practice, every day.</strong><p>Your notes are the starting point. Understanding is the goal.</p></div><button className="ghost full" onClick={logout}><LogOut size={18} />Logout</button>
    </aside>
    <section className="workspace">
      <header className="topbar"><div><p className="eyebrow">Workspace / {reader ? "Notes reader" : view === "history" ? "Study sessions" : view === "notes" ? "Your library" : "Practice"}</p><h1>{topic?.name ?? "Create a topic"}</h1><p className="page-description">{view === "notes" ? "Everything you need to learn, in one place." : view === "history" ? "Pick up where you left off. See how far you’ve come." : "Build understanding. One focused session at a time."}</p></div><button className="ghost" disabled={loading} onClick={() => setRefreshVersion((value) => value + 1)}><RefreshCw size={18} />Refresh</button></header>
      {notice && <div role="alert" className={`notice ${notice.type}`}>{notice.message}<button title="Dismiss" onClick={() => setNotice(null)}>×</button></div>}
      {(operation || workspaceLoading) && <p role="status" className="muted">{operation === "upload" ? "Uploading notes…" : "Loading…"}</p>}
      {!reader && <div className="overview-strip">
        <div><FileText size={18} aria-hidden="true" /><span>Topic notes</span><strong>{topicDocuments.length}</strong></div>
        <div><CheckCircle2 size={18} aria-hidden="true" /><span>Ready to study</span><strong>{topicDocuments.filter(doc => doc.status === "ready").length}</strong></div>
        <div><Clock size={18} aria-hidden="true" /><span>Reviews due</span><strong>{dueTopics.length}</strong></div>
      </div>}
      <div className="workspace-tabs" role="tablist" aria-label="Topic workspace">{([['notes', 'Notes'], ['practice', 'Practice'], ['history', 'Study sessions']] as const).map(([id, title]) => <button key={id} role="tab" aria-selected={view === id && !reader} disabled={loading} onClick={() => { setReaderId(null); setView(id); setNotice(null); }}>{id === "notes" ? <FileText size={17} aria-hidden="true" /> : id === "practice" ? <Sparkles size={17} aria-hidden="true" /> : <Layers size={17} aria-hidden="true" />}{title}</button>)}</div>
      {reader ? <DocumentReader key={`${token}:${reader.id}`} token={token} document={reader} onBack={() => setReaderId(null)} onPractice={() => practiceDocument(reader.id)} onError={showError} /> : <>
        {view === "notes" && <section className="panel">
          <div><h2>Your notes</h2><p className="muted">Open a document for its summary and paginated original, or practice just those notes.</p></div>
          <form className="upload-form" onSubmit={upload}><input aria-label="Document title" placeholder="Document title" value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} /><input ref={fileInput} type="file" accept=".txt" disabled={loading || !topicId} onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} /><button className="primary" disabled={loading || !topicId || !uploadFile}><Upload size={18} />Upload</button></form>
          <input placeholder="Filter notes by title" aria-label="Filter notes by title" value={notesFilter} onChange={(event) => { setNotesFilter(event.target.value); setNotesPage(1); }} />
          <div className="session-grid">{filteredNotes.slice((displayedNotesPage - 1) * 6, displayedNotesPage * 6).map((doc) => <article className="session-card" key={doc.id}><div className="card-top"><span className="card-icon"><FileText size={22} aria-hidden="true" /></span><span className={`status-pill status-${doc.status}`}>{doc.status}</span></div><h3>{doc.title}</h3><p className="muted">{doc.status === "failed" ? "Processing failed. Please re-upload the notes." : doc.status}</p><div className="actions"><button onClick={() => setReaderId(doc.id)}>Read notes</button><button disabled={doc.status !== "ready"} onClick={() => practiceDocument(doc.id)}>Practice these notes</button></div></article>)}</div>
          {filteredNotes.length === 0 && <p className="empty-state">{notesFilter ? "No notes match this title." : "Upload a .txt file to get started."}</p>}
          {notePages > 1 && <div className="pagination"><button disabled={displayedNotesPage === 1} onClick={() => setNotesPage(displayedNotesPage - 1)}>Previous notes</button><span>Page {displayedNotesPage} of {notePages}</span><button disabled={displayedNotesPage === notePages} onClick={() => setNotesPage(displayedNotesPage + 1)}>Next notes</button></div>}
        </section>}
      </>}
      {topicId !== null && <div hidden={!!reader}><PracticePanel key={`${token}:${topicId}`} token={token} topicId={topicId} documents={topicDocuments} view={reader ? "notes" : view} selectedDocumentId={selectedDocumentId} onDocument={setSelectedDocumentId} onView={setView} onBusy={setPracticeBusy} onError={showError} onRecorded={refreshProgress} /></div>}
      {!topicId && <p className="empty-state">Create a topic using the sidebar, then upload your notes.</p>}
      {!reader && view === "practice" && <section className="panel due-panel"><div className="topbar"><h2>Due Reviews</h2><span className="muted">{dueTopics.length} due · Current topic streak {progress?.streak ?? 0}</span></div>{dueTopics.length === 0 ? <p className="muted">No scheduled reviews are due.</p> : <div className="session-grid">{dueTopics.map((row) => <button className="due-item" key={row.topic_id} disabled={loading} onClick={() => { selectTopic(row.topic_id); setView("history"); }}><strong>{row.name}</strong><span>Open sessions to review</span></button>)}</div>}</section>}
    </section>
  </main>;
}
