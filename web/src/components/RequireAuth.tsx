import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { getSession } from "@/auth/session";

// Redirects anonymous visitors to the server-side /login (which sets the
// session cookie and bounces back to /app). While the check is in flight we
// render nothing to avoid a flash.
export function RequireAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "ok" | "anon">("loading");

  useEffect(() => {
    let active = true;
    getSession().then((user) => {
      if (!active) return;
      setState(user ? "ok" : "anon");
    });
    return () => {
      active = false;
    };
  }, []);

  if (state === "loading") return null;
  if (state === "anon") return <Navigate to="/login" replace />;
  return <>{children}</>;
}
