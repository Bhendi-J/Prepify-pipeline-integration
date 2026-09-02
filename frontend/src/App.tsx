import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  FileText,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Send,
  Upload,
  XCircle,
} from "lucide-react";
import {
  api,
  AttemptResult,
  DocumentItem,
  DueTopic,
  Mastery,
  Question,
  SearchResult,
  Topic,
} from "./api";

type AuthMode = "login" | "register";
type Notice = { type: "ok" | "error"; message: string } | null;

const storedToken = localStorage.getItem("prepify_token");

export default function App() {
  const [token, setToken] = useState<string | null>(storedToken);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [dueTopics, setDueTopics] = useState<DueTopic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [newTopicName, setNewTopicName] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [questionQuery, setQuestionQuery] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [question, setQuestion] = useState<Question | null>(null);
  const [attempt, setAttempt] = useState<AttemptResult | null>(null);
  const [progress, setProgress] = useState<Mastery | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const selectedTopic = useMemo(
    () => topics.find((topic) => topic.id === selectedTopicId) ?? null,
    [topics, selectedTopicId],
  );

  useEffect(() => {
    if (token) {
      void refreshWorkspace(token);
    }
  }, [token]);

  useEffect(() => {
    if (!token || documents.length === 0) {
      return;
    }

    const hasActiveDocument = documents.some((doc) => doc.status === "pending" || doc.status === "processing");
    if (!hasActiveDocument) {
      return;
    }

    const interval = window.setInterval(() => {
      void api.listDocuments(token).then(setDocuments).catch(showError);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [documents, token]);

  async function refreshWorkspace(authToken = token) {
    if (!authToken) {
      return;
    }
    setLoading(true);
    try {
      const [topicRows, documentRows, dueRows] = await Promise.all([
        api.listTopics(authToken),
        api.listDocuments(authToken),
        api.getDue(authToken),
      ]);
      setTopics(topicRows);
      setDocuments(documentRows);
      setDueTopics(dueRows);
      setSelectedTopicId((current) => current ?? topicRows[0]?.id ?? null);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAuth(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      if (authMode === "register") {
        await api.register(email, password);
      }
      const result = await api.login(email, password);
      localStorage.setItem("prepify_token", result.access_token);
      setToken(result.access_token);
      setNotice({ type: "ok", message: "Signed in" });
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTopic(event: FormEvent) {
    event.preventDefault();
    if (!token || !newTopicName.trim()) {
      return;
    }
    try {
      const topic = await api.createTopic(token, newTopicName.trim());
      setTopics((current) => [...current, topic].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedTopicId(topic.id);
      setNewTopicName("");
      setNotice({ type: "ok", message: "Topic created" });
    } catch (error) {
      showError(error);
    }
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!token || !uploadFile) {
      return;
    }
    try {
      const document = await api.uploadDocument(token, {
        title: uploadTitle.trim() || uploadFile.name,
        topic_id: selectedTopicId,
        file: uploadFile,
      });
      setDocuments((current) => [document, ...current]);
      setUploadTitle("");
      setUploadFile(null);
      setNotice({ type: "ok", message: "Upload queued" });
    } catch (error) {
      showError(error);
    }
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedTopicId || !searchQuery.trim()) {
      return;
    }
    setLoading(true);
    try {
      setSearchResults(await api.searchTopic(token, selectedTopicId, searchQuery.trim()));
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateQuestion(forceNew = false) {
    if (!token || !selectedTopicId) {
      return;
    }
    setLoading(true);
    try {
      const nextQuestion = await api.createQuestion(token, selectedTopicId, {
        query: questionQuery.trim() || undefined,
        difficulty,
        force_new: forceNew,
      });
      setQuestion(nextQuestion);
      setAttempt(null);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAttempt(is_correct: boolean) {
    if (!token || !question) {
      return;
    }
    setLoading(true);
    try {
      const result = await api.submitAttempt(token, question.id, { is_correct });
      setAttempt(result);
      if (selectedTopicId) {
        setProgress(await api.getProgress(token, selectedTopicId));
      }
      setDueTopics(await api.getDue(token));
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("prepify_token");
    setToken(null);
    setTopics([]);
    setDocuments([]);
    setDueTopics([]);
    setQuestion(null);
    setAttempt(null);
    setProgress(null);
  }

  function showError(error: unknown) {
    setNotice({ type: "error", message: error instanceof Error ? error.message : "Something went wrong" });
  }

  if (!token) {
    return (
      <main className="auth-page">
        <section className="auth-panel">
          <div>
            <p className="eyebrow">Prepify</p>
            <h1>Study from your own notes.</h1>
            <p className="muted">Upload notes, generate questions, and keep review timing on track.</p>
          </div>

          <form className="stack" onSubmit={handleAuth}>
            <div className="segmented">
              <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>
                Login
              </button>
              <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>
                Register
              </button>
            </div>
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
            </label>
            <label>
              Password
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" minLength={8} required />
            </label>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              {authMode === "login" ? "Login" : "Create Account"}
            </button>
            {notice && <p className={`notice ${notice.type}`}>{notice.message}</p>}
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <BookOpen size={24} />
          <span>Prepify</span>
        </div>
        <form className="topic-form" onSubmit={handleCreateTopic}>
          <input value={newTopicName} onChange={(event) => setNewTopicName(event.target.value)} placeholder="New topic" />
          <button type="submit" title="Create topic">
            <Plus size={18} />
          </button>
        </form>
        <nav className="topic-list">
          {topics.map((topic) => (
            <button
              key={topic.id}
              className={selectedTopicId === topic.id ? "selected" : ""}
              onClick={() => {
                setSelectedTopicId(topic.id);
                setQuestion(null);
                setAttempt(null);
                if (token) void api.getProgress(token, topic.id).then(setProgress).catch(showError);
              }}
            >
              {topic.name}
            </button>
          ))}
        </nav>
        <button className="ghost full" onClick={logout}>
          <LogOut size={18} />
          Logout
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Workspace</p>
            <h1>{selectedTopic?.name ?? "Create a topic"}</h1>
          </div>
          <button className="ghost" onClick={() => void refreshWorkspace()} disabled={loading}>
            <RefreshCw size={18} />
            Refresh
          </button>
        </header>

        {notice && (
          <div className={`notice ${notice.type}`}>
            {notice.message}
            <button onClick={() => setNotice(null)} title="Dismiss">
              <XCircle size={16} />
            </button>
          </div>
        )}

        <section className="metrics">
          <Metric label="Topics" value={topics.length} />
          <Metric label="Documents" value={documents.length} />
          <Metric label="Due now" value={dueTopics.length} />
          <Metric label="Streak" value={progress?.streak ?? 0} />
        </section>

        <section className="grid">
          <div className="panel">
            <div className="panel-title">
              <Upload size={18} />
              <h2>Documents</h2>
            </div>
            <form className="stack" onSubmit={handleUpload}>
              <input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="Document title" />
              <input type="file" accept=".txt" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
              <button className="primary" type="submit" disabled={!uploadFile || !selectedTopicId}>
                <Upload size={18} />
                Upload
              </button>
            </form>
            <div className="list">
              {documents.map((doc) => (
                <article className="row" key={doc.id}>
                  <FileText size={18} />
                  <div>
                    <strong>{doc.title}</strong>
                    <span>{doc.status} - topic {doc.topic_id ?? "none"}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">
              <Search size={18} />
              <h2>Search</h2>
            </div>
            <form className="search-row" onSubmit={handleSearch}>
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search your notes" />
              <button type="submit" title="Search">
                <Search size={18} />
              </button>
            </form>
            <div className="list">
              {searchResults.map((result) => (
                <article className="result" key={result.chunk_id}>
                  <strong>Chunk {result.chunk_id}</strong>
                  <p>{result.content}</p>
                  <span>distance {result.distance.toFixed(4)}</span>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="practice">
          <div className="panel">
            <div className="panel-title">
              <CheckCircle2 size={18} />
              <h2>Practice</h2>
            </div>
            <div className="practice-controls">
              <input value={questionQuery} onChange={(event) => setQuestionQuery(event.target.value)} placeholder="Optional focus query" />
              <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
              <button className="primary" onClick={() => void handleGenerateQuestion(false)} disabled={!selectedTopicId || loading}>
                {loading ? <Loader2 className="spin" size={18} /> : <BookOpen size={18} />}
                Question
              </button>
              <button className="ghost" onClick={() => void handleGenerateQuestion(true)} disabled={!selectedTopicId || loading}>
                <RefreshCw size={18} />
                Fresh
              </button>
            </div>

            {question && (
              <article className="question-box">
                <span>{question.difficulty}</span>
                <h3>{question.question_text}</h3>
                <div className="actions">
                  <button onClick={() => void handleAttempt(true)} disabled={loading}>
                    <CheckCircle2 size={18} />
                    Correct
                  </button>
                  <button onClick={() => void handleAttempt(false)} disabled={loading}>
                    <XCircle size={18} />
                    Missed
                  </button>
                </div>
              </article>
            )}

            {attempt && (
              <article className="answer-box">
                <strong>Answer</strong>
                <p>{attempt.answer_text}</p>
                <span>Next review {formatDate(attempt.next_review_at)}</span>
              </article>
            )}
          </div>

          <div className="panel due-panel">
            <h2>Due Reviews</h2>
            {dueTopics.length === 0 ? (
              <p className="muted">Nothing due right now.</p>
            ) : (
              dueTopics.map((topic) => (
                <button className="due-item" key={topic.topic_id} onClick={() => setSelectedTopicId(topic.topic_id)}>
                  <strong>{topic.name}</strong>
                  <span>{formatDate(topic.next_review_at)}</span>
                </button>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
