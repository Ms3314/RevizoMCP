import type { Streak } from "@/api/types";

export function StreakHeatmap({ streak }: { streak: Streak }) {
  // Oldest-first weeks as columns of 7 (matching LeetCode's contribution grid).
  const weeks: { date: string; count: number }[][] = [];
  for (let i = 0; i < streak.days.length; i += 7) {
    weeks.push(streak.days.slice(i, i + 7));
  }

  return (
    <div>
      <div className="flex items-end gap-6">
        <div>
          <div className="text-2xl font-semibold text-zinc-100">{streak.current}</div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">day streak</div>
        </div>
        <div>
          <div className="text-2xl font-semibold text-zinc-100">{streak.longest}</div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">longest</div>
        </div>
      </div>
      <div className="mt-4 flex gap-1 overflow-x-auto pb-2">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1">
            {week.map((d) => (
              <div
                key={d.date}
                title={`${d.date}: ${d.count} solved`}
                className={`h-3 w-3 rounded-sm ${d.count > 0 ? "bg-blue-500" : "bg-zinc-800"}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
