// Thin fetch wrapper for the Revizo JSON API. Cookie session auth is used
// (credentials: "include"), so no explicit token handling on the client.

import type { ImportEvent, SolveIn, StudyPlan, StudyPlanSettings } from "./types";

const BASE = ""; // same-origin; dev proxies /api to the FastAPI app.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (res.status === 401) {
    // Not signed in — let the caller redirect to /login.
    throw new ApiError(401, "Not authenticated");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return (await res.text()) as unknown as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
  getStudyPlan: () => api.get<StudyPlan>("/api/study-plan"),
  saveStudyPlanSettings: (s: StudyPlanSettings) =>
    api.post<StudyPlanSettings & { notice?: string }>("/api/study-plan/settings", s),
  solveProblem: (id: string, body: SolveIn) =>
    api.post<StudyPlan>(`/api/problems/${encodeURIComponent(id)}/solve`, body),
};

// Streams the CSV import endpoint (Server-Sent Events) and invokes `onEvent`
// for each parsed event. Resolves when the stream closes, rejects on HTTP error.
export async function streamImport(
  file: File,
  onEvent: (e: ImportEvent) => void,
): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/import", { method: "POST", body: form, credentials: "include" });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON */
    }
    throw new ApiError(res.status, detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          onEvent(JSON.parse(line.slice(6)) as ImportEvent);
        }
      }
    }
  }
}
