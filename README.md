# <span>**Revizo**</span> <em>— your problems remember what you got wrong.</em>

<p align="left">
  <img src="revizo.png" alt="Revizo" width="620"/>
</p>

<p align="left">
  <em>A spaced-repetition revision coach for DSA interview prep, living inside your LLM.</em>
</p>

---

## The problem

You solved Two Sum four months ago. You failed it in one spot — a subtle off-by-one in your loop bounds. In that time you crammed through fifty new problems, and nobody — not LeetCode history, not your notes app, not your Notion tracker — is going to bring that mistake back to you.

**Solving isn't revision.** Interview prep culture is built around "grind 500 problems," while burn-out-by-forgetting quietly defeats most of it: the problems you *almost* understood, the *exact* mistake you made each time, and *when* you were supposed to face it again.

Revizo exists for that gap.

## What Revizo is

Revizo is an **MCP server that acts as your private DSA revision coach**. Sign in once (Google), add it to Cursor (or Claude, ChatGPT connectors — anything that speaks MCP), and your editor's LLM becomes a coach that:

- tells you **what to revise today** — your due list, ranked by how overdue it is, how hard it hit you, and whether you last failed it
- **reminds you of your own mistakes** before every revisit, in your own words ("you did an off-by-one here last time — check your loop bounds")
- **tracks your weak patterns** across everything — "you keep falling for edge case bugs: empty inputs, boundaries, overflow" — and warns you *before* new problems, not just old ones
- **reschedules on truth**: success moves a problem further out on its ladder, failure brings it back tomorrow *carrying the mistakes forward* — that's the whole trick
- **syncs your real LeetCode solves — and your recent failed attempts** — so the coach knows exactly what you're stuck on (public API only; for code diagnosis, paste your code in chat)

No separate app. No dashboard to babysit. The coach sits next to your editor where you already grind.

## What a session looks like

```text
You:   what should I revise today?
Coach: You're due 5. Priority: "Count Inversions" — you last failed it with
       [complexity_tle]; brute force won't cut it this time — think merge sort.
You:   ok, got it this time
Coach: recorded ✅ — solved → next visit in 7 days. Watch out for complexity_tle;
       it's your #2 pattern overall.
You:   give me something fresh
Coach: Backlog pick: "Longest Consecutive Sequence" (arrays, medium).
       Heads-up — edge_cases is your recurring weak spot; probe empties first.
```

No streak-management UI. No "streak +1" gamification. The loop is: **attempt → honest record → resurface at the right moment**.

## How the scheduling works

One glance at the ladders:

| difficulty | success ladder (days) |
| :--- | :--- |
| easy | 1 → 3 → 7 → 14 → 30 → 60 → 120 |
| medium | 1 → 2 → 4 → 8 → 16 → 35 → 70 |
| hard | 1 → 2 → 3 → 6 → 12 → 25 → 50 |

- **Solved** → the problem climbs one rung and comes back later.
- **Failed** → snapped back to ~1 day, mistakes recorded, and it shows up tomorrow with `watch_out` reminders attached.

Your most common failure patterns (`complexity_tle`, `off_by_one`, `edge_cases`, `wrong_ds`, `misread_constraints`, `implementation_bug`, `math_error`, `overflow`) get aggregated into your **weak-points profile** — the thing no notes app ever builds for you.

## Why it fits inside your LLM

Generic "explain DSA" assistants give everyone the same tutorial. Revizo's coach reads **your data** before every attempt: past mistakes, retry patterns, weak-topic pools, your own real LeetCode code. Revision, which is 80% of interview success, finally gets a dedicated system of record — and the LLM is the mechanism, not another chatbot bolted onto one.

## Setup

Everything local or your choice of hosting. Honest quickstart:

```bash
git clone <repo> && cd learnersMcp
uv sync
cp .env.example .env         # fill in DATABASE_URL + Supabase values
uv run fastapi dev main.py
```

Then:
1. **Supabase** project (free tier works) → Auth → enable a provider (Google), set redirect URLs → paste URL + anon key in `.env`
2. Open `http://localhost:8000/connect` → **Add to Cursor** (one click — no settings editing)
3. Sign in with Google. First chat: "what should I revise today?" or "sync my leetcode, user <your-id>"

Everything else (SRS state, mistakes, weak points) is yours woven privately per signed-in account — no shared bucket.

## Roadmap

- [x] **Public-API sync of failed attempts** — last ~20 submissions of any status; per-submission dedup, zero cookies
- [ ] **Vercel-ready deploy guide** (stateless mode flag already implemented)
- [ ] **GitHub OAuth provider** alongside Google
- [ ] **Auto-sync on first use** (24h cooldown)
- [ ] Rotation model ("every 7th solved problem revisited") as an alternate cadence

## Stack (for the curious)

Python 3.12 · FastAPI · MCP (sdk Streamable HTTP) · SQLAlchemy 2 · Supabase for auth & Postgres · MCP-spec OAuth (RFC 8414 + DCR + PKCE) with JWT minting · pytest unit-tested SRS core

## Why this niche exists

Every serious DSA grinder tracks what they solved. Almost nobody tracks what they got wrong when, and surfaces it again at the right time. Learning platforms measure input; RetainMe-style apps measure streaks. Revizo measures **the actual thing**: your mistakes, resurfacing exactly when forgetting starts winning.

---

*Built as one person's interview-prep tool, powered as an MCP server for anyone's. PRs welcome — especially around more mistake vocabularies and problem sources.*

## License

MIT — do the thing.
