import { api } from "@/lib/api";
import type {
  Answer, ChatMessage, ChatSummary, KnowledgeTree, Quiz, StudentProfile, Tokens, User,
} from "@/types";

// -- auth ------------------------------------------------------------------ //
export const authApi = {
  register: (email: string, password: string, name: string) =>
    api.post<Tokens>("/auth/register", { email, password, name }).then((r) => r.data),
  login: (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    return api.post<Tokens>("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }).then((r) => r.data);
  },
  me: () => api.get<User>("/auth/me").then((r) => r.data),
};

// -- chat ------------------------------------------------------------------ //
export const chatApi = {
  send: (message: string, chatId?: number | null) =>
    api.post<Answer>("/chat", { message, chat_id: chatId ?? null }).then((r) => r.data),
  list: () => api.get<ChatSummary[]>("/chats").then((r) => r.data),
  messages: (id: number) => api.get<ChatMessage[]>(`/chats/${id}`).then((r) => r.data),
  remove: (id: number) => api.delete(`/chats/${id}`).then((r) => r.data),
};

// -- knowledge ------------------------------------------------------------- //
export const knowledgeApi = {
  tree: () => api.get<KnowledgeTree>("/knowledge/tree").then((r) => r.data),
  resource: (id: string) => api.get(`/knowledge/resource/${id}`).then((r) => r.data),
  summarize: (id: string) => api.post(`/knowledge/resource/${id}/summarize`).then((r) => r.data),
  related: (id: string) => api.get(`/knowledge/resource/${id}/related`).then((r) => r.data),
  quiz: (id: string) => api.post(`/knowledge/resource/${id}/quiz`).then((r) => r.data),
  citations: (id: string) => api.get(`/knowledge/resource/${id}/citations`).then((r) => r.data),
};

export const uploadApi = {
  upload: (file: File, course = "uploads", module = "misc") => {
    const form = new FormData();
    form.append("file", file);
    form.append("course", course);
    form.append("module", module);
    return api.post("/upload", form, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  list: () => api.get("/uploads").then((r) => r.data),
};

// -- other capabilities ---------------------------------------------------- //
export const searchApi = { query: (q: string) => api.get("/search", { params: { q } }).then((r) => r.data) };
export const researchApi = {
  ask: (question: string, save = false) => api.post("/research", { question, save }).then((r) => r.data),
};
export const studentApi = {
  profile: () => api.get<StudentProfile>("/student").then((r) => r.data),
  preferences: (p: Record<string, unknown>) => api.put("/student/preferences", p).then((r) => r.data),
};
export const dashboardApi = { get: () => api.get("/dashboard").then((r) => r.data) };
export const plannerApi = {
  plan: (goal: string, days: number, minutes: number) =>
    api.post("/planner", { goal, days, minutes }).then((r) => r.data),
  calendarUrl: "/api/planner/calendar",
};
export const graphApi = {
  concept: (id: string) => api.get(`/graph/concept/${id}`).then((r) => r.data),
  stats: () => api.get("/graph/stats").then((r) => r.data),
};
export const quizApi = {
  // Quiz generation is LLM-backed (~30-45s); the Next dev proxy times out at ~30s
  // ("socket hang up"), so — like streaming and agent calls — go DIRECT to the backend.
  generate: async (resourceId: string, n = 4, difficulty = "medium"): Promise<Quiz> => {
    const { authStore } = await import("@/store/auth");
    const token = authStore.getState().accessToken;
    const res = await fetch(`${directBase()}/api/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ resource_id: resourceId, n, difficulty }),
    });
    if (!res.ok) throw new Error(`quiz generation failed: ${res.status}`);
    return res.json();
  },
};

export const llmApi = { status: () => api.get("/llm").then((r) => r.data) };

// Slow LLM-backed JSON calls go DIRECT to the backend (the Next dev proxy times out at ~30s).
function directBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "";
}

export const agentsApi = {
  roster: () => api.get("/agents").then((r) => r.data),
  ask: async (text: string, concept?: string) => {
    const { authStore } = await import("@/store/auth");
    const token = authStore.getState().accessToken;
    const res = await fetch(`${directBase()}/api/agents/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text, concept: concept ?? null }),
    });
    if (!res.ok) throw new Error(`agent ask failed: ${res.status}`);
    return res.json();
  },
};

export const rlApi = {
  status: (concept?: string) =>
    api.get("/rl/status", { params: concept ? { concept } : {} }).then((r) => r.data),
};

// -- admin (role: admin) --------------------------------------------------- //
export const adminApi = {
  users: () => api.get("/admin/users").then((r) => r.data),
  setRole: (id: number, role: string) => api.patch(`/admin/users/${id}`, { role }).then((r) => r.data),
  remove: (id: number) => api.delete(`/admin/users/${id}`).then((r) => r.data),
  stats: () => api.get("/admin/stats").then((r) => r.data),
  health: () => api.get("/admin/health").then((r) => r.data),
};

// -- instructor (role: instructor|admin) ----------------------------------- //
export const instructorApi = {
  students: () => api.get("/instructor/students").then((r) => r.data),
  student: (id: string) => api.get(`/instructor/student/${id}`).then((r) => r.data),
  overview: () => api.get("/instructor/overview").then((r) => r.data),
  content: () => api.get("/instructor/content").then((r) => r.data),
};
