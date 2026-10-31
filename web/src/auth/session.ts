import { api } from "@/api/client";
import type { SessionUser } from "@/api/types";

// Lightweight session check used by the route guard. Returns null when the
// visitor is not signed in (the API returns 401 → we treat as null).
export async function getSession(): Promise<SessionUser | null> {
  try {
    return await api.get<SessionUser>("/api/me");
  } catch {
    return null;
  }
}
