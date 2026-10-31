import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/api/client";
import type { LeetCodeImportResult, LeetCodeStatus } from "@/api/types";

export function LeetCodeSettings() {
  const [status, setStatus] = useState<LeetCodeStatus | null>(null);
  const [username, setUsername] = useState("");
  const [sessionCookie, setSessionCookie] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importResult, setImportResult] = useState<LeetCodeImportResult | null>(null);

  useEffect(() => {
    api
      .get<LeetCodeStatus>("/api/leetcode")
      .then((s) => {
        setStatus(s);
        setUsername(s.username);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load status"));
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const s = await api.post<LeetCodeStatus>("/api/leetcode/settings", { username, session_cookie: sessionCookie });
      setStatus(s);
      setNotice(s.notice ?? "Saved.");
      setSessionCookie("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setError(null);
    setBusy(true);
    try {
      const s = await api.post<LeetCodeStatus>("/api/leetcode/disconnect", {});
      setStatus(s);
      setNotice(s.notice ?? "Disconnected.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect");
    } finally {
      setBusy(false);
    }
  }

  async function runImport() {
    setError(null);
    setImportResult(null);
    setBusy(true);
    try {
      const r = await api.post<{ connected: boolean; username: string; result: LeetCodeImportResult }>(
        "/api/leetcode/import",
        {},
      );
      setImportResult(r.result);
      setNotice("Import complete.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-zinc-100">LeetCode</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Connect once with your username + session cookie, then sync your solved history any time.
      </p>

      {status?.connected && (
        <div className="mt-4 rounded-lg border border-emerald-800 bg-emerald-950/30 p-3 text-sm text-emerald-200">
          Connected as <span className="font-medium">{status.username}</span>.
        </div>
      )}

      <form onSubmit={save} className="mt-6 space-y-4">
        <label className="block">
          <span className="mb-1 block text-sm text-zinc-400">LeetCode username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            placeholder="your-handle"
            className="input"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-zinc-400">Session cookie (leave blank to keep)</span>
          <input
            value={sessionCookie}
            onChange={(e) => setSessionCookie(e.target.value)}
            placeholder="LEETCODE_SESSION=…"
            className="input"
          />
        </label>

        {error && (
          <div className="rounded-lg border border-rose-800 bg-rose-950/30 p-3 text-sm text-rose-200">{error}</div>
        )}
        {notice && !error && (
          <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-3 text-sm text-blue-200">{notice}</div>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {busy ? "Working…" : "Save"}
          </button>
          <button
            type="button"
            onClick={disconnect}
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-60"
          >
            Disconnect
          </button>
          <button
            type="button"
            onClick={runImport}
            disabled={busy || !status?.connected}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-60"
          >
            Import all solved
          </button>
        </div>
      </form>

      {importResult && (
        <pre className="mt-4 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-xs text-zinc-300">
          {JSON.stringify(importResult, null, 2)}
        </pre>
      )}
    </div>
  );
}
