import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import type { DashboardData, DashboardRow, Difficulty, StudyPlan } from "@/api/types";
import { StreakHeatmap } from "@/components/StreakHeatmap";

const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  easy: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  hard: "bg-rose-500/15 text-rose-300",
};

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
      <div className="mt-1 text-xs uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({ difficulty: "", status: "", topic: "" });

  useEffect(() => {
    api
      .get<DashboardData>("/api/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dashboard"));
    api
      .getStudyPlan()
      .then(setPlan)
      .catch(() => {
        /* streak widget is non-critical */
      });
  }, []);

  // Filter client-side for instant UX (the API returns the full problem set).
  const visibleRows = useMemo<DashboardRow[]>(() => {
    if (!data) return [];
    const topic = filters.topic.trim().toLowerCase();
    return data.rows.filter((row) => {
      const { p } = row;
      if (filters.difficulty && p.difficulty !== filters.difficulty) return false;
      if (topic && !p.topics.some((t) => t.toLowerCase() === topic)) return false;
      if (filters.status === "solved" && !p.solved) return false;
      if (filters.status === "backlog" && p.solved) return false;
      if (filters.status === "due" && !row.due) return false;
      return true;
    });
  }, [data, filters]);

  if (error) {
    return <div className="rounded-lg border border-rose-800 bg-rose-950/30 p-4 text-rose-200">{error}</div>;
  }
  if (!data) {
    return <div className="text-sm text-zinc-500">Loading your dashboard…</div>;
  }

  const { stats, due, weak_points, today_long } = data;

  return (
    <div className="space-y-10">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-zinc-100">Dashboard</h1>
        <span className="text-sm text-zinc-500">{today_long}</span>
      </div>

      {/* Today + streak summary */}
      {plan && (
        <section className="grid gap-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 lg:grid-cols-[1fr_auto]">
          <div>
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              Today's plan
              <Link to="/app/today" className="text-blue-400 hover:text-blue-300">
                open →
              </Link>
            </div>
            <div className="mt-2 flex gap-6 text-sm">
              <span className="text-zinc-200">
                Review <span className="font-semibold text-zinc-100">{plan.old_solved_today}/{plan.old_target}</span>
              </span>
              <span className="text-zinc-200">
                New <span className="font-semibold text-zinc-100">{plan.new_solved_today}/{plan.new_target}</span>
              </span>
            </div>
          </div>
          <div className="min-w-[260px]">
            <StreakHeatmap streak={plan.streak} />
          </div>
        </section>
      )}

      {/* Stats */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Total" value={stats.total} />
        <Stat label="Solved" value={stats.solved} />
        <Stat label="Backlog" value={stats.backlog} />
        <Stat label="Due today" value={stats.due_today} />
        <Stat
          label="By difficulty"
          value={`${stats.by_difficulty.easy}/${stats.by_difficulty.medium}/${stats.by_difficulty.hard}`}
        />
      </section>

      {/* Due for revision */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Due for revision
        </h2>
        {due.length === 0 ? (
          <p className="text-sm text-zinc-500">Nothing due. Add problems or enjoy the streak.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {due.map(({ p, when, watch_out }) => (
              <div key={p.problem_id} className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <div className="flex items-center justify-between gap-2">
                  <a
                    href={p.problem_link || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-zinc-100 hover:text-blue-300"
                  >
                    {p.problem_id}
                  </a>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${DIFFICULTY_STYLE[p.difficulty as Difficulty]}`}>
                    {p.difficulty}
                  </span>
                </div>
                <div className="mt-1 text-xs text-zinc-500">{when}</div>
                {watch_out && (
                  <p className="mt-2 rounded-md bg-zinc-900 p-2 text-xs text-amber-200/80">{watch_out}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Weak points */}
      {weak_points.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Weak points</h2>
          <div className="space-y-2">
            {weak_points.map((w) => (
              <div key={w.tag} className="flex items-center gap-3">
                <span className="w-40 shrink-0 truncate text-sm text-zinc-300">{w.tag}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
                  <div className="h-full rounded-full bg-blue-500" style={{ width: `${w.pct}%` }} />
                </div>
                <span className="w-10 text-right text-xs text-zinc-500">{w.count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Problem table */}
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-sm font-semibold uppercase tracking-wide text-zinc-400">Problems</h2>
          <select
            value={filters.difficulty}
            onChange={(e) => setFilters((f) => ({ ...f, difficulty: e.target.value }))}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200"
          >
            <option value="">Any difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200"
          >
            <option value="">Any status</option>
            <option value="solved">Solved</option>
            <option value="backlog">Backlog</option>
            <option value="due">Due</option>
          </select>
          <input
            value={filters.topic}
            onChange={(e) => setFilters((f) => ({ ...f, topic: e.target.value }))}
            placeholder="Filter by topic…"
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200 placeholder:text-zinc-600"
          />
        </div>

        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-2">Problem</th>
                <th className="px-4 py-2">Difficulty</th>
                <th className="px-4 py-2">Topics</th>
                <th className="px-4 py-2">Solved</th>
                <th className="px-4 py-2">Interval</th>
                <th className="px-4 py-2">Due</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map(({ p, due: isDue }) => (
                <tr key={p.problem_id} className="border-t border-zinc-800">
                  <td className="px-4 py-2">
                    <a
                      href={p.problem_link || "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="text-zinc-100 hover:text-blue-300"
                    >
                      {p.problem_id}
                    </a>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${DIFFICULTY_STYLE[p.difficulty as Difficulty]}`}>
                      {p.difficulty}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-zinc-400">{p.topics.join(", ")}</td>
                  <td className="px-4 py-2 text-zinc-300">{p.solved ? "✓" : "—"}</td>
                  <td className="px-4 py-2 text-zinc-400">{p.interval_days}d</td>
                  <td className="px-4 py-2">
                    {isDue ? <span className="text-amber-300">due</span> : <span className="text-zinc-600">—</span>}
                  </td>
                </tr>
              ))}
              {visibleRows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-zinc-500">
                    No problems match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
