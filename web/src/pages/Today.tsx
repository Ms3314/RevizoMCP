import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import type { ProblemSuggestion, StudyPlan } from "@/api/types";
import { StreakHeatmap } from "@/components/StreakHeatmap";

const DIFFICULTY_STYLE: Record<string, string> = {
  easy: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  hard: "bg-rose-500/15 text-rose-300",
};

function Progress({ label, done, target }: { label: string; done: number; target: number }) {
  const pct = target > 0 ? Math.min(100, Math.round((done / target) * 100)) : 0;
  const complete = done >= target && target > 0;
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-zinc-400">{label}</span>
        <span className={`text-sm ${complete ? "text-emerald-300" : "text-zinc-200"}`}>
          {done}/{target}
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${complete ? "bg-emerald-500" : "bg-blue-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SuggestionRow({ p, onSolve }: { p: ProblemSuggestion; onSolve: (id: string) => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="min-w-0">
        <a
          href={p.problem_link || "#"}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-zinc-100 hover:text-blue-300"
        >
          {p.problem_id}
        </a>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <span className={`rounded-full px-2 py-0.5 ${DIFFICULTY_STYLE[p.difficulty] ?? ""}`}>
            {p.difficulty}
          </span>
          {p.topics.map((t) => (
            <span key={t} className="rounded-full bg-zinc-800 px-2 py-0.5">
              {t}
            </span>
          ))}
        </div>
      </div>
      <button
        onClick={() => onSolve(p.problem_id)}
        className="shrink-0 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
      >
        Mark solved
      </button>
    </div>
  );
}

export function Today() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rev, setRev] = useState(1);
  const [back, setBack] = useState(2);
  const [notice, setNotice] = useState<string | null>(null);

  function refresh() {
    api
      .getStudyPlan()
      .then((p) => {
        setPlan(p);
        setRev(p.settings.revisions_per_session);
        setBack(p.settings.backlog_per_session);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load plan"));
  }

  useEffect(refresh, []);

  async function solve(id: string) {
    setBusyId(id);
    try {
      const updated = await api.solveProblem(id, { solved: true });
      setPlan(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to record solve");
    } finally {
      setBusyId(null);
    }
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    setNotice(null);
    try {
      await api.saveStudyPlanSettings({
        revisions_per_session: Number(rev),
        backlog_per_session: Number(back),
      });
      setNotice("Plan saved.");
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
    }
  }

  if (error) {
    return <div className="rounded-lg border border-rose-800 bg-rose-950/30 p-4 text-rose-200">{error}</div>;
  }
  if (!plan) {
    return <div className="text-sm text-zinc-500">Loading your plan…</div>;
  }

  const { old_target, old_solved_today, new_target, new_solved_today, old_suggestions, new_suggestions } = plan;

  return (
    <div className="space-y-10">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-zinc-100">Today</h1>
        <span className="text-sm text-zinc-500">Solve a little, every day.</span>
      </div>

      {/* Progress */}
      <section className="grid gap-3 sm:grid-cols-2">
        <Progress label="Review (old problems)" done={old_solved_today} target={old_target} />
        <Progress label="New problems" done={new_solved_today} target={new_target} />
      </section>

      {/* Review suggestions */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Review these
        </h2>
        {old_suggestions.length === 0 ? (
          <p className="text-sm text-zinc-500">Nothing left to review today. 🎉</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {old_suggestions.map((p) => (
              <SuggestionRow key={p.problem_id} p={p} onSolve={solve} />
            ))}
          </div>
        )}
      </section>

      {/* New suggestions */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">New problems</h2>
        {new_suggestions.length === 0 ? (
          <p className="text-sm text-zinc-500">
            All done — or add some in <Link to="/app/problems/new" className="text-blue-400 hover:text-blue-300">Add problem</Link>. 🎉
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {new_suggestions.map((p) => (
              <SuggestionRow key={p.problem_id} p={p} onSolve={solve} />
            ))}
          </div>
        )}
      </section>

      {/* Plan settings */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Daily plan</h2>
        <form onSubmit={saveSettings} className="flex flex-wrap items-end gap-4">
          <label className="block">
            <span className="mb-1 block text-sm text-zinc-400">Reviews / day</span>
            <input
              type="number"
              min={0}
              value={rev}
              onChange={(e) => setRev(Number(e.target.value))}
              className="input w-28"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-zinc-400">New / day</span>
            <input
              type="number"
              min={0}
              value={back}
              onChange={(e) => setBack(Number(e.target.value))}
              className="input w-28"
            />
          </label>
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Save
          </button>
          {notice && <span className="text-sm text-blue-300">{notice}</span>}
        </form>
      </section>

      {/* Streak */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Streak</h2>
        <StreakHeatmap streak={plan.streak} />
      </section>
    </div>
  );
}
