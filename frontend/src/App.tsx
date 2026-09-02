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
  const [questionType, setQuestionType] = useState("short_answer");
  const [questionCount, setQuestionCount] = useState(3);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [answerDraft, setAnswerDraft] = useState("");
  const [questionStartedAt, setQuestionStartedAt] = useState<number | null>(null);
  const [attempt, setAttempt] = useState<AttemptResult | null>(null);
  const [progress, setProgress] = useState<Mastery | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const selectedTopic = useMemo(
    () => topics.find((topic) => topic.id === selectedTopicId) ?? null,
    [topics, selectedTopicId],
  );
  const selectedDocuments = useMemo(
    () => documents.filter((document) => document.topic_id === selectedTopicId),
    [documents, selectedTopicId],
  );
  const selectedDueTopic = useMemo(
    () => dueTopics.find((topic) => topic.topic_id === selectedTopicId) ?? null,
    [dueTopics, selectedTopicId],
  );
  const activeQuestion = questions[activeQuestionIndex] ?? null;

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
      const currentTopicStillExists = topicRows.some((topic) => topic.id === selectedTopicId);
      const nextSelectedTopicId = currentTopicStillExists
        ? selectedTopicId
        : topicRows[0]?.id ?? null;
      if (nextSelectedTopicId) {
        setSelectedTopicId(nextSelectedTopicId);
        await loadTopicState(authToken, nextSelectedTopicId);
      } else {
        clearTopicState();
      }
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
      clearTopicState();
      setSelectedTopicId(null);
      setTopics([]);
      setDocuments([]);
      setDueTopics([]);
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
      selectTopic(topic.id);
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

  async function handleGenerateQuestions(forceNew = false) {
    if (!token || !selectedTopicId) {
      return;
    }
    setLoading(true);
    try {
      const count = Number.isFinite(questionCount)
        ? Math.max(1, Math.min(questionCount, 5))
        : 1;
      const generated: Question[] = [];
      for (let index = 0; index < count; index += 1) {
        generated.push(
          await api.createQuestion(token, selectedTopicId, {
            query: questionQuery.trim() || undefined,
            difficulty,
            question_type: questionType,
            force_new: forceNew || index > 0,
          }),
        );
      }
      setQuestions((current) => mergeQuestions(generated, current));
      setActiveQuestionIndex(0);
      setQuestionStartedAt(Date.now());
      setAnswerDraft("");
      setAttempt(null);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAttempt(is_correct: boolean) {
    if (!token || !activeQuestion) {
      return;
    }
    setLoading(true);
    try {
      const response_time_ms = questionStartedAt ? Date.now() - questionStartedAt : undefined;
      const result = await api.submitAttempt(token, activeQuestion.id, {
        is_correct,
        response_time_ms,
      });
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
    setQuestions([]);
    setAttempt(null);
    setProgress(null);
  }

  function showError(error: unknown) {
    setNotice({ type: "error", message: error instanceof Error ? error.message : "Something went wrong" });
  }

  function selectTopic(topicId: number) {
    setSelectedTopicId(topicId);
    clearTopicState();
    if (token) {
      void loadTopicState(token, topicId);
    }
  }

  async function loadTopicState(authToken: string, topicId: number) {
    const [topicProgress, savedQuestions] = await Promise.all([
      api.getProgress(authToken, topicId),
      api.listQuestions(authToken, topicId),
    ]);
    setProgress(topicProgress);
    setQuestions(savedQuestions);
    setActiveQuestionIndex(0);
    setQuestionStartedAt(savedQuestions.length > 0 ? Date.now() : null);
  }

  function clearTopicState() {
    setSearchResults([]);
    setSearchQuery("");
    setQuestions([]);
    setActiveQuestionIndex(0);
    setAnswerDraft("");
    setAttempt(null);
    setProgress(null);
    setQuestionStartedAt(null);
  }

  function moveQuestion(direction: -1 | 1) {
    const nextIndex = activeQuestionIndex + direction;
    if (nextIndex < 0 || nextIndex >= questions.length) {
      return;
    }
    setActiveQuestionIndex(nextIndex);
    setAnswerDraft("");
    setAttempt(null);
    setQuestionStartedAt(Date.now());
  }

  function selectQuestion(index: number) {
    setActiveQuestionIndex(index);
    setAnswerDraft("");
    setAttempt(null);
    setQuestionStartedAt(Date.now());
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
              onClick={() => selectTopic(topic.id)}
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
          <Metric label="Topic docs" value={selectedDocuments.length} />
          <Metric label="Due now" value={selectedDueTopic ? 1 : 0} />
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
              {selectedDocuments.map((doc) => (
                <article className="row" key={doc.id}>
                  <FileText size={18} />
                  <div>
                    <strong>{doc.title}</strong>
                    <span>{doc.status}</span>
                  </div>
                </article>
              ))}
              {selectedDocuments.length === 0 && (
                <p className="muted">No notes uploaded for this topic yet.</p>
              )}
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
              <select value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
                <option value="short_answer">Short answer</option>
                <option value="multiple_choice">Multiple choice</option>
                <option value="true_false">True/false</option>
                <option value="conceptual">Conceptual</option>
              </select>
              <input
                aria-label="Question count"
                type="number"
                min={1}
                max={5}
                value={questionCount}
                onChange={(event) => setQuestionCount(Number(event.target.value) || 1)}
              />
              <button className="primary" onClick={() => void handleGenerateQuestions(false)} disabled={!selectedTopicId || loading}>
                {loading ? <Loader2 className="spin" size={18} /> : <BookOpen size={18} />}
                Generate
              </button>
              <button className="ghost" onClick={() => void handleGenerateQuestions(true)} disabled={!selectedTopicId || loading}>
                <RefreshCw size={18} />
                Fresh
              </button>
            </div>

            {activeQuestion && (
              <article className="question-box">
                <span>
                  {activeQuestion.difficulty} - {activeQuestion.question_type.replace("_", " ")} - {activeQuestionIndex + 1} of {questions.length}
                </span>
                <h3>{activeQuestion.question_text}</h3>
                <textarea
                  value={answerDraft}
                  onChange={(event) => setAnswerDraft(event.target.value)}
                  placeholder="Type your answer before revealing the stored answer"
                  rows={4}
                />
                <div className="actions">
                  <button onClick={() => moveQuestion(-1)} disabled={activeQuestionIndex === 0}>
                    Previous
                  </button>
                  <button onClick={() => moveQuestion(1)} disabled={activeQuestionIndex >= questions.length - 1}>
                    Next
                  </button>
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
                {answerDraft && (
                  <>
                    <strong>Your answer</strong>
                    <p>{answerDraft}</p>
                  </>
                )}
                <span>Next review {formatDate(attempt.next_review_at)}</span>
              </article>
            )}

            {questions.length > 0 && (
              <div className="question-list">
                {questions.map((savedQuestion, index) => (
                  <button
                    key={savedQuestion.id}
                    className={index === activeQuestionIndex ? "selected" : ""}
                    onClick={() => selectQuestion(index)}
                  >
                    <span>{index + 1}</span>
                    <strong>{savedQuestion.question_text}</strong>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="panel due-panel">
            <h2>Due Reviews</h2>
            {!selectedDueTopic ? (
              <p className="muted">This topic is not due right now.</p>
            ) : (
              <article className="due-item">
                <strong>{selectedDueTopic.name}</strong>
                <span>{formatDate(selectedDueTopic.next_review_at)}</span>
              </article>
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

function mergeQuestions(newQuestions: Question[], savedQuestions: Question[]) {
  const byId = new Map<number, Question>();
  for (const question of [...newQuestions, ...savedQuestions]) {
    byId.set(question.id, question);
  }
  return [...byId.values()];
}
