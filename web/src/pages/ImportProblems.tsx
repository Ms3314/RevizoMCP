import { useRef, useState } from "react";
import { streamImport } from "@/api/client";
import type { ImportDone, ImportEvent } from "@/api/types";

export function ImportProblems() {
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<{ processed: number; total: number; imported: number; duplicates: number } | null>(null);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState<ImportDone | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function start() {
    if (!file) return;
    setError(null);
    setDone(null);
    setProgress(null);
    setStarted(false);
    setBusy(true);
    try {
      await streamImport(file, (e: ImportEvent) => {
        if (e.type === "progress") {
          setStarted(true);
          setProgress(e);
        }
        if (e.type === "done") setDone(e);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  const pct = progress && progress.total ? Math.round((progress.processed / progress.total) * 100) : 0;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-zinc-100">Import problems</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Upload a CSV (Problem, Link, Difficulty, Topics, Description). We stream progress as it imports.
      </p>

      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-zinc-400 file:mr-3 file:rounded-md file:border-0 file:bg-zinc-800 file:px-3 file:py-1.5 file:text-zinc-200 hover:file:bg-zinc-700"
        />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={start}
            disabled={busy || !file}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {busy ? "Importing…" : "Import"}
          </button>
          <a
            href="/api/import/sample.csv"
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            Download template
          </a>
        </div>

        {busy && !started && (
          <div className="mt-5">
            <div className="mb-1 text-xs text-zinc-500">Reading & parsing your file…</div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-500" />
            </div>
          </div>
        )}

        {progress && (
          <div className="mt-5">
            <div className="mb-1 flex justify-between text-xs text-zinc-500">
              <span>
                {progress.processed}/{progress.total} rows · {progress.imported} imported · {progress.duplicates} duplicates
              </span>
              <span>{pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
              <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-rose-800 bg-rose-950/30 p-3 text-sm text-rose-200">{error}</div>
      )}

      {done && (
        <div className="mt-4 rounded-lg border border-emerald-800 bg-emerald-950/30 p-4 text-sm text-emerald-200">
          <div>
            Imported <span className="font-medium">{done.imported}</span>, {done.duplicates} duplicates,{" "}
            {done.skipped.length} skipped.
          </div>
          {done.skipped.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-emerald-300">
                {done.skipped.length} row(s) skipped
              </summary>
              <ul className="mt-1 list-disc pl-5">
                {done.skipped.map((s) => (
                  <li key={s.row_number}>
                    Row {s.row_number}: {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {done.failed.length > 0 && (
            <div className="mt-2 text-rose-200">Failed: {done.failed.join(", ")}</div>
          )}
        </div>
      )}
    </div>
  );
}
