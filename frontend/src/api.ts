const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type User = {
  id: number;
  email: string;
  created_at: string;
};

export type Topic = {
  id: number;
  user_id: number;
  name: string;
  parent_id: number | null;
};

export type DocumentItem = {
  id: number;
  user_id: number;
  topic_id: number | null;
  title: string;
  source_type: string;
  file_path: string;
  status: "pending" | "processing" | "ready" | "failed" | string;
  uploaded_at: string;
};

export type SearchResult = {
  chunk_id: number;
  document_id: number;
  topic_id: number | null;
  content: string;
  token_count: number;
  distance: number;
};

export type Question = {
  id: number;
  topic_id: number;
  chunk_id: number | null;
  source_chunk_ids: number[];
  question_text: string;
  difficulty: string;
};

export type AttemptResult = {
  id: number;
  user_id: number;
  question_id: number;
  is_correct: boolean;
  response_time_ms: number | null;
  created_at: string;
  answer_text: string;
  next_review_at: string;
};

export type Mastery = {
  user_id: number;
  topic_id: number;
  ease_factor: number;
  interval_days: number;
  next_review_at: string;
  streak: number;
};

export type DueTopic = {
  topic_id: number;
  name: string;
  parent_id: number | null;
  ease_factor: number;
  interval_days: number;
  next_review_at: string;
  streak: number;
};

type RequestOptions = RequestInit & {
  token?: string | null;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data?.detail ?? response.statusText;
    throw new Error(Array.isArray(detail) ? detail[0]?.msg ?? response.statusText : detail);
  }

  return data as T;
}

export const api = {
  register(email: string, password: string) {
    return request<User>("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },
  login(email: string, password: string) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    return request<{ access_token: string; token_type: string }>("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
  },
  listTopics(token: string) {
    return request<Topic[]>("/api/v1/topics/", { token });
  },
  createTopic(token: string, name: string, parent_id: number | null = null) {
    return request<Topic>("/api/v1/topics/", {
      token,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_id }),
    });
  },
  listDocuments(token: string) {
    return request<DocumentItem[]>("/api/v1/documents/", { token });
  },
  getDocument(token: string, id: number) {
    return request<DocumentItem>(`/api/v1/documents/${id}`, { token });
  },
  uploadDocument(token: string, input: { title: string; topic_id: number | null; file: File }) {
    const form = new FormData();
    form.set("title", input.title);
    form.set("source_type", ".txt");
    if (input.topic_id !== null) {
      form.set("topic_id", String(input.topic_id));
    }
    form.set("file", input.file);
    return request<DocumentItem>("/api/v1/documents/", {
      token,
      method: "POST",
      body: form,
    });
  },
  searchTopic(token: string, topicId: number, query: string, k = 5) {
    return request<SearchResult[]>(`/api/v1/topics/${topicId}/search`, {
      token,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k }),
    });
  },
  createQuestion(token: string, topicId: number, input: { query?: string; difficulty: string; force_new: boolean }) {
    return request<Question>(`/api/v1/practice/${topicId}/question`, {
      token,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  submitAttempt(token: string, questionId: number, input: { is_correct: boolean; response_time_ms?: number }) {
    return request<AttemptResult>(`/api/v1/practice/${questionId}/attempt`, {
      token,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  getDue(token: string) {
    return request<DueTopic[]>("/api/v1/progress/due", { token });
  },
  getProgress(token: string, topicId: number) {
    return request<Mastery>(`/api/v1/progress/${topicId}`, { token });
  },
};
