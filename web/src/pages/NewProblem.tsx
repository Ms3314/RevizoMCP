import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";

const DIFFICULTIES = ["easy", "medium", "hard"] as const;

export function NewProblem() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    link: "",
    difficulty: "medium",
    topics: "",
    description: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.post("/api/problems", form);
      navigate("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add problem");
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-zinc-100">Add problem</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Track a new problem. Leave the link blank for non-LeetCode material and we’ll keep it.
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        <Field label="Title">
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
            placeholder="Two Sum"
            className="input"
          />
        </Field>
        <Field label="Link">
          <input
            value={form.link}
            onChange={(e) => setForm({ ...form, link: e.target.value })}
            placeholder="https://leetcode.com/problems/two-sum/"
            className="input"
          />
        </Field>
        <Field label="Difficulty">
          <select
            value={form.difficulty}
            onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
            className="input"
          >
            {DIFFICULTIES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Topics (comma-separated)">
          <input
            value={form.topics}
            onChange={(e) => setForm({ ...form, topics: e.target.value })}
            placeholder="arrays, hashing"
            className="input"
          />
        </Field>
        <Field label="Description">
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={4}
            placeholder="What’s the problem asking? Notes for later."
            className="input"
          />
        </Field>

        {error && (
          <div className="rounded-lg border border-rose-800 bg-rose-950/30 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {saving ? "Saving…" : "Add problem"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/app")}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm text-zinc-400">{label}</span>
      {children}
    </label>
  );
}
