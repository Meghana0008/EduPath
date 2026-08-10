import type {
  AgentRun,
  AnalysisResult,
  Application,
  CalendarEvent,
  CareerRoadmap,
  ChatResponse,
  DashboardStats,
  DiscoverResponse,
  Document,
  Match,
  Notification,
  Opportunity,
  Profile,
  TokenResponse,
  User,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClientError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.data = data;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("edupath_token");
}

export function setToken(token: string) {
  localStorage.setItem("edupath_token", token);
}

export function clearToken() {
  localStorage.removeItem("edupath_token");
  localStorage.removeItem("edupath_demo_mode");
}

export function setDemoMode(demo: boolean) {
  localStorage.setItem("edupath_demo_mode", demo ? "true" : "false");
}

export function getDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("edupath_demo_mode") === "true";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}/api${path}`, {
    ...options,
    headers,
  });

  if (res.status === 204) return undefined as T;

  let data: unknown;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? (data as { detail: unknown }).detail
        : text;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail && "confirmation_prompt" in detail
          ? String((detail as { confirmation_prompt: string }).confirmation_prompt)
          : `Request failed (${res.status})`;
    throw new ApiClientError(message, res.status, data);
  }

  return data as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, false),

  register: (name: string, email: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    }, false),

  me: () => request<User>("/auth/me"),

  dashboard: () => request<DashboardStats>("/dashboard"),

  getProfile: () => request<Profile>("/profile"),

  updateProfile: (data: Partial<Profile>) =>
    request<Profile>("/profile", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  opportunities: () => request<Opportunity[]>("/opportunities"),

  opportunity: (id: string) => request<Opportunity>(`/opportunities/${id}`),

  evaluateOpportunity: (id: string) =>
    request<Match>(`/opportunities/${id}/evaluate`, { method: "POST" }),

  matches: () => request<Match[]>("/matches"),

  applications: () => request<Application[]>("/applications"),

  application: (id: string) => request<Application>(`/applications/${id}`),

  createApplication: (opportunity_id: string, confirm = false, notes?: string) =>
    request<Application>("/applications", {
      method: "POST",
      body: JSON.stringify({ opportunity_id, confirm, notes }),
    }),

  updateApplication: (
    id: string,
    data: { status?: string; notes?: string; confirm?: boolean }
  ) =>
    request<Application>(`/applications/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  documents: () => request<Document[]>("/documents"),

  uploadDocument: (document_type: string, file: File) => {
    const form = new FormData();
    form.append("document_type", document_type);
    form.append("file", file);
    return request<Document>("/documents", { method: "POST", body: form });
  },

  deleteDocument: (id: string, confirm = true) =>
    request<{ ok: boolean }>(`/documents/${id}?confirm=${confirm}`, {
      method: "DELETE",
    }),

  calendar: () => request<CalendarEvent[]>("/calendar"),

  notifications: () => request<Notification[]>("/notifications"),

  markNotificationRead: (id: string) =>
    request<Notification>(`/notifications/${id}/read`, { method: "PATCH" }),

  discover: (simulate_new = false) =>
    request<DiscoverResponse>(`/agent/discover?simulate_new=${simulate_new}`, {
      method: "POST",
    }),

  agentRuns: () => request<AgentRun[]>("/agent/runs"),

  activateAgent: () =>
    request<{ agent_active: boolean }>("/agent/activate", { method: "POST" }),

  onboardingStatus: () =>
    request<{
      profile_complete: boolean;
      documents_uploaded: boolean;
      discovery_run: boolean;
      onboarding_completed: boolean;
      missing_profile_fields: string[];
      documents_count: number;
      recommended_document_types: string[];
    }>("/onboarding/status"),

  completeOnboarding: () =>
    request<{ ok: boolean; onboarding_completed: boolean }>("/onboarding/complete", {
      method: "POST",
    }),

  analyzeResume: (data: {
    opportunity_id: string;
    resume_text?: string;
    document_id?: string;
  }) =>
    request<AnalysisResult>("/resume/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  analyzeSop: (data: {
    opportunity_id: string;
    sop_text: string;
    generate_improved_draft?: boolean;
  }) =>
    request<AnalysisResult>("/sop/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  careerRoadmap: () => request<CareerRoadmap>("/career-roadmap"),

  chat: (message: string, opportunity_id?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, opportunity_id }),
    }),
};
