import { Link } from "react-router-dom";
import { connectMeta, useMeta } from "./meta";

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[12px] text-zinc-300">
      {children}
    </code>
  );
}

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  return (
    <button
      onClick={() => navigator.clipboard.writeText(text)}
      className="rounded-md border border-white/[0.08] bg-[#161618] px-2.5 py-1.5 text-[12px] text-zinc-400 transition hover:text-zinc-100"
    >
      {label}
    </button>
  );
}

function ServerUrlBox({ url }: { url: string }) {
  return (
    <div className="relative mt-6 flex items-center justify-between gap-3 rounded-lg border border-white/[0.07] bg-[#0c0c0e] px-4 py-3">
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-600">Server URL</div>
        <div className="mt-0.5 truncate font-mono text-[13px] text-zinc-200">{url}</div>
      </div>
      <CopyButton text={url} label="Copy URL" />
    </div>
  );
}

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="mt-8 rounded-lg border border-white/[0.07] bg-[#0c0c0e] px-5 py-10 text-center">
      <div className="font-mono text-[13px] text-zinc-300">{name} guide — coming soon</div>
      <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-zinc-500">
        We're writing this guide right now. In the meantime, {name} follows the standard MCP connector flow —
        the overview page has the general steps.
      </p>
      <Link
        to="/docs/connect"
        className="mt-5 inline-flex h-8 items-center rounded-md border border-white/[0.08] px-3 text-[12.5px] text-zinc-300 transition hover:bg-white/[0.04]"
      >
        Connection overview
      </Link>
    </div>
  );
}

function Introduction() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">About Revizo</h1>
      <p className="doc-p">
        Revizo is a <span className="doc-strong">spaced-repetition revision coach for DSA interview prep</span>,
        living inside your LLM. Sign in once with Google, add it to any MCP client, and your editor's LLM becomes a
        coach that remembers every mistake you made — and resurfaces each problem exactly when forgetting starts winning.
      </p>

      <h2 className="doc-h2">The problem</h2>
      <p className="doc-p">
        You solved Two Sum four months ago. You failed it in one spot — a subtle off-by-one in your loop bounds. Since
        then you crammed fifty new problems, and nothing — not LeetCode history, not your notes app — will bring that
        mistake back to you.
      </p>
      <p className="doc-p">
        <span className="doc-strong">Solving isn't revision.</span> Interview prep culture is built around "grind 500
        problems," while burn-out-by-forgetting quietly defeats most of it. Revizo exists for that gap.
      </p>

      <h2 className="doc-h2">The loop</h2>
      <p className="doc-p">
        No streak counters, no gamification. The loop is:{" "}
        <span className="font-mono text-[12.5px] text-zinc-300">
          attempt → honest record → resurface at the right moment
        </span>
        . The coach sits next to your editor where you already grind — no separate app to babysit.
      </p>

      <h2 className="doc-h2">How scheduling works</h2>
      <p className="doc-p">One glance at the ladders (success intervals, in days):</p>
      <div className="mt-4 overflow-hidden rounded-lg border border-white/[0.07]">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-white/[0.07] bg-[#0c0c0e] text-left text-[11px] uppercase tracking-wider text-zinc-600">
              <th className="px-4 py-2.5 font-medium">Difficulty</th>
              <th className="px-4 py-2.5 font-medium">Success ladder (days)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.06] text-zinc-400">
            <tr>
              <td className="px-4 py-2.5 font-mono text-emerald-400/90">easy</td>
              <td className="px-4 py-2.5 font-mono text-zinc-300">1 → 3 → 7 → 14 → 30 → 60 → 120</td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-mono text-amber-400/90">medium</td>
              <td className="px-4 py-2.5 font-mono text-zinc-300">1 → 2 → 4 → 8 → 16 → 35 → 70</td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-mono text-rose-400/90">hard</td>
              <td className="px-4 py-2.5 font-mono text-zinc-300">1 → 2 → 3 → 6 → 12 → 25 → 50</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="doc-p">
        <span className="doc-strong">Solved</span> → the problem climbs one rung and comes back later.{" "}
        <span className="doc-strong">Failed</span> → snapped back to ~1 day, mistakes recorded, and it shows up tomorrow
        carrying them forward. That's the whole trick.
      </p>

      <h2 className="doc-h2">Privacy</h2>
      <p className="doc-p">
        Every problem, attempt, and mistake is scoped to your signed-in account — nothing shared, nothing public.
      </p>
    </article>
  );
}

function Features() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Features</h1>
      <p className="doc-p">
        Revizo's MCP server is the main product — the coach lives inside the LLM you already use. The web dashboard is
        just a quiet companion view of the same data.
      </p>

      <h2 className="doc-h2">What to revise today</h2>
      <p className="doc-p">
        Your due list, ranked by how overdue it is, how hard it hit you, and whether you last failed it. Ask{" "}
        <Code>{"what should I revise today?"}</Code> and start.
      </p>

      <h2 className="doc-h2">Your own mistakes, reminded</h2>
      <p className="doc-p">
        Before every revisit the coach replays your notes in your own words —{" "}
        <em>"you did an off-by-one here last time — check your loop bounds"</em> — so you re-fight the exact spot you
        lost, not a generic version of the problem.
      </p>

      <h2 className="doc-h2">Weak patterns across everything</h2>
      <p className="doc-p">
        The coach aggregates your most common failure patterns and warns you before new problems, not just old ones. Your
        vocabulary:
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {[
          "complexity_tle",
          "edge_cases",
          "off_by_one",
          "overflow",
          "misread_constraints",
          "wrong_ds",
          "math_error",
          "implementation_bug",
        ].map((tag) => (
          <span
            key={tag}
            className="rounded border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[11.5px] text-zinc-400"
          >
            {tag}
          </span>
        ))}
      </div>

      <h2 className="doc-h2">Rescheduled on truth</h2>
      <p className="doc-p">
        Success moves a problem further out on its difficulty ladder; failure brings it back tomorrow carrying the
        mistakes forward. Honest records make the schedule honest.
      </p>

      <h2 className="doc-h2">Real LeetCode sync</h2>
      <p className="doc-p">
        Sync recent activity with your public LeetCode profile, or connect once to import your full solved history. Later
        full imports only add newly solved problems. For code diagnosis, paste your code in chat.
      </p>
      <p className="doc-p">
        <Link to="/docs/leetcode-import" className="text-blue-400 transition hover:text-blue-300">
          Set up a full-history import →
        </Link>
      </p>

      <h2 className="doc-h2">Works where you work</h2>
      <p className="doc-p">
        Cursor, Claude Desktop, Claude Code, ChatGPT — anything that speaks MCP. See the{" "}
        <Link to="/docs/connect" className="text-blue-400 transition hover:text-blue-300">
          connect guides
        </Link>
        .
      </p>
    </article>
  );
}

function LeetCodeImport() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Import your full LeetCode history</h1>
      <p className="doc-p">
        The regular LeetCode sync uses public profile data and imports recent activity. To import all solved problems,
        connect your LeetCode account once with its <Code>LEETCODE_SESSION</Code> cookie.
      </p>

      <h2 className="doc-h2">1. Find your session cookie</h2>
      <ol className="mt-2 space-y-2 text-[13.5px] leading-relaxed text-zinc-400">
        <li>1. Sign in to <a href="https://leetcode.com" target="_blank" rel="noopener" className="text-blue-400">leetcode.com</a> in your browser.</li>
        <li>2. Open Developer Tools (usually <Code>F12</Code> or right-click → <span className="text-zinc-300">Inspect</span>).</li>
        <li>3. Open the <span className="text-zinc-300">Application</span> tab in Chrome/Edge (or <span className="text-zinc-300">Storage</span> in Firefox), then open <span className="text-zinc-300">Cookies → https://leetcode.com</span>.</li>
        <li>4. Find <Code>LEETCODE_SESSION</Code> and copy its <span className="text-zinc-300">Value</span>. Copy only the value, not the cookie name or other cookie fields.</li>
      </ol>
      <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-[12.5px] leading-relaxed text-amber-200/80">
        This cookie is a private sign-in credential. Never paste it into an AI chat, share it with anyone, or include it
        in a screenshot.
      </div>

      <h2 className="doc-h2">2. Save it in Revizo</h2>
      <ol className="mt-2 space-y-2 text-[13.5px] leading-relaxed text-zinc-400">
        <li>1. Sign in to Revizo and open <Link to="/app/leetcode" className="text-blue-400">LeetCode import settings</Link>.</li>
        <li>2. Enter your LeetCode username and paste the cookie value into the session-cookie field.</li>
        <li>3. Select <span className="text-zinc-300">Save connection</span>, then choose <span className="text-zinc-300">Import all problems</span>.</li>
      </ol>
      <p className="doc-p">
        Revizo encrypts the cookie before saving it. You add it once; it is reused for future imports and is not sent
        through your MCP chat. If LeetCode expires the cookie, replace it in the same settings page. You can remove it
        there at any time.
      </p>
      <p className="doc-p">
        The first import checks your solved-problem list. Later imports compare your solved count and only add slugs that
        are new since the last import. Existing tracker history is preserved.
      </p>
      <p className="doc-p">
        LeetCode's solved-problem list does not include each problem's original solve date or older attempt history.
        Imported problems start their revision schedule on the import date; use the regular recent sync to bring in recent
        attempts.
      </p>
    </article>
  );
}

function Importing() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Importing problems</h1>
      <p className="doc-p">
        Bulk-add problems by uploading a CSV on the{" "}
        <Link to="/app/import" className="text-blue-400 transition hover:text-blue-300">
          import page
        </Link>
        . Your file can have any columns in any order — Revizo picks out only the fields it tracks and ignores everything
        else.
      </p>

      <h2 className="doc-h2">The default template</h2>
      <p className="doc-p">
        The simplest starting point is the sample CSV — grab it here:{" "}
        <a href="/api/import/sample.csv" className="text-blue-400 transition hover:text-blue-300">
          download sample CSV
        </a>
        . It looks like this:
      </p>
      <pre className="mt-3 overflow-x-auto rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 font-mono text-[12px] leading-relaxed text-zinc-400">
        Problem,Link,Difficulty,Topics,Description{"\n"}
        Two Sum,https://leetcode.com/problems/two-sum/,easy,"arrays, hashing",Find two numbers that add up to the target.{"\n"}
        Coin Change,https://leetcode.com/problems/coin-change/,medium,dp,Fewest coins to make up an amount.
      </pre>
      <p className="doc-p mt-3">
        Only <Code>Problem</Code> and <Code>Link</Code> are required — everything else is optional. You can add, remove,
        or reorder columns freely; Revizo will match by header name.
      </p>

      <h2 className="doc-h2">Recognized columns</h2>
      <p className="doc-p">Header names are matched case-insensitively; any of these synonyms work:</p>
      <div className="mt-3 overflow-x-auto rounded-lg border border-white/[0.07]">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-white/[0.07] text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Field</th>
              <th className="px-4 py-2.5 font-medium">Accepted headers</th>
              <th className="px-4 py-2.5 font-medium">Required</th>
              <th className="px-4 py-2.5 font-medium">What it's for</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05] text-zinc-400">
            <tr>
              <td className="px-4 py-2.5 text-zinc-200">Problem</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">problem, title, problem name, name</td>
              <td className="px-4 py-2.5 text-rose-400">required</td>
              <td className="px-4 py-2.5">
                The problem's name — used as the unique ID in your tracker. If you import the same title twice, the
                second is counted as a duplicate and skipped.
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 text-zinc-200">Link</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">link, problem link, url, problem url</td>
              <td className="px-4 py-2.5 text-rose-400">required</td>
              <td className="px-4 py-2.5">
                Where to find the problem — LeetCode, Codeforces, a PDF, whatever. Clicked from the dashboard.
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 text-zinc-200">Difficulty</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">difficulty, level</td>
              <td className="px-4 py-2.5">optional · defaults to medium</td>
              <td className="px-4 py-2.5">
                Drives the spaced-repetition ladder: easy problems get longer intervals, hard ones get shorter. Accepts{" "}
                <Code>easy</Code>, <Code>medium</Code>, <Code>hard</Code>.
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 text-zinc-200">Topics</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">topics, topic, subtopic, tags</td>
              <td className="px-4 py-2.5">optional</td>
              <td className="px-4 py-2.5">
                Comma-separated tags like <Code>arrays, dp, greedy</Code>. Used to filter the dashboard and to surface
                weak spots ("you keep failing on <em>greedy</em>").
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 text-zinc-200">Description</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">description, problem statement, notes, approach</td>
              <td className="px-4 py-2.5">optional</td>
              <td className="px-4 py-2.5">
                What the problem asks, constraints worth remembering, or your approach. Shown by the coach when the
                problem comes up for revision.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="doc-h2">The rules</h2>
      <ul className="doc-p list-disc space-y-1.5 pl-5 text-zinc-400">
        <li>
          A row without <Code>both</Code> a problem and a link is skipped — you'll get a summary telling you exactly
          which rows and why.
        </li>
        <li>Problems already in your tracker are counted as duplicates and left untouched (no overwriting).</li>
        <li>Extra columns — Step, Starred, Notes, whatever — are simply ignored.</li>
        <li>Files up to 1 MB / 5,000 rows per upload; split bigger lists.</li>
      </ul>

      <h2 className="doc-h2">Real-world example: importing a Notion export</h2>
      <p className="doc-p">
        If you've been tracking problems in Notion (like the Striver A2Z sheet), your export probably has columns like{" "}
        <Code>
          Problem, Approach, Description, Difficulty, Key insight, Last revised, Link, Mistakes, Notes, Problem ID,
          Solved, Starred, Step, Step no, Sub-step, Sub-step progress, Subtopic, Topic
        </Code>
        . Revizo will automatically pick out <Code>Problem</Code>, <Code>Link</Code>, <Code>Difficulty</Code>,{" "}
        <Code>Topic</Code> / <Code>Subtopic</Code>, and <Code>Description</Code> — everything else is ignored.
      </p>

      <h2 className="doc-h2">What happens after import</h2>
      <p className="doc-p">
        Imported problems start as unsolved backlog items. They'll appear in your dashboard immediately, and you can
        record attempts against them via the MCP tools (or ask your coach "mark Two Sum as solved"). The
        spaced-repetition schedule kicks in once you record your first attempt.
      </p>
    </article>
  );
}

function ConnectOverview() {
  const { oauth_configured, provider } = useMeta();
  const { mcp_url } = connectMeta();
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Connect Revizo</h1>
      <p className="doc-p">
        Revizo is an MCP server. Any client that speaks MCP can connect — it signs in once with {provider} through your
        browser, and from then on your LLM is your revision coach.
      </p>

      {!oauth_configured && (
        <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3.5 py-3 text-[13px] text-amber-300/90">
          OAuth isn't configured on this server yet — connections will fail until <Code>SUPABASE_URL</Code> and{" "}
          <Code>SUPABASE_ANON_KEY</Code> are set and a sign-in provider is enabled in Supabase.
        </div>
      )}

      <ServerUrlBox url={mcp_url} />

      <h2 className="doc-h2">Pick your client</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Link to="/docs/connect/cursor" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">Cursor</div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">One-click deeplink install.</p>
        </Link>
        <Link to="/docs/connect/claude" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">Claude Desktop</div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">Custom connector.</p>
        </Link>
        <Link to="/docs/connect/claude-code" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">Claude Code</div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">One CLI command.</p>
        </Link>
        <Link to="/docs/connect/chatgpt" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">ChatGPT</div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">Apps &amp; Connectors.</p>
        </Link>
        <Link to="/docs/connect/codex" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="flex items-center gap-2 text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">
            Codex <span className="rounded border border-white/[0.08] px-1.5 py-px text-[10px] uppercase tracking-wide text-zinc-500">soon</span>
          </div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">Guide in progress.</p>
        </Link>
        <Link to="/docs/connect/hermes" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-4 transition hover:border-white/[0.16]">
          <div className="flex items-center gap-2 text-[13.5px] font-medium text-zinc-100 group-hover:text-blue-400">
            Hermes <span className="rounded border border-white/[0.08] px-1.5 py-px text-[10px] uppercase tracking-wide text-zinc-500">soon</span>
          </div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-500">Guide in progress.</p>
        </Link>
      </div>
      <p className="doc-p">
        Using something else?{" "}
        <Link to="/docs/connect/other" className="text-blue-400 transition hover:text-blue-300">
          Any MCP client works →
        </Link>
      </p>

      <h2 className="doc-h2">First steps once connected</h2>
      <p className="doc-p">Open your tool, sign in, and try:</p>
      <ul className="mt-1">
        <li className="doc-li">
          <span>
            <span className="doc-strong font-mono text-[12.5px]">"what should I revise today?"</span> — your due list,
            with your past mistakes attached.
          </span>
        </li>
        <li className="doc-li">
          <span>
            <span className="doc-strong font-mono text-[12.5px]">"sync my leetcode, user &lt;your-id&gt;"</span> — pull
            in your real solves and recent failed attempts.
          </span>
        </li>
        <li className="doc-li">
          <span>
            <span className="doc-strong font-mono text-[12.5px]">"import all my LeetCode problems"</span> — first
            connect LeetCode from your{" "}
            <Link to="/app/leetcode" className="text-blue-400">
              Revizo dashboard
            </Link>
            ; the saved session is reused on future imports.
          </span>
        </li>
        <li className="doc-li">
          <span>
            <span className="doc-strong font-mono text-[12.5px]">"record that as solved"</span> — honest record, the
            problem climbs its ladder.
          </span>
        </li>
      </ul>
    </article>
  );
}

function ConnectCursor() {
  const { provider } = useMeta();
  const { mcp_url, cursor_link, manual_json } = connectMeta();
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Cursor</h1>
      <p className="doc-p">One click — no settings editing. On first connect, Cursor opens a browser sign-in ({provider}).</p>

      <ServerUrlBox url={mcp_url} />

      <h2 className="doc-h2">Add to Cursor</h2>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <a
          href={cursor_link}
          className="flex h-8 items-center rounded-md bg-white px-3 text-[13px] font-medium text-zinc-900 transition hover:bg-zinc-200"
        >
          Add to Cursor
        </a>
        <span className="text-[12px] text-zinc-600">opens Cursor's MCP installer with Revizo pre-filled</span>
      </div>

      <h2 className="doc-h2">Manual setup</h2>
      <p className="doc-p">Settings → MCP → Add custom MCP server, then paste:</p>
      <div className="relative mt-2">
        <pre className="overflow-x-auto rounded-lg border border-white/[0.07] bg-[#0c0c0e] px-4 py-3 font-mono text-[12.5px] leading-relaxed text-zinc-300">
          {manual_json}
        </pre>
        <div className="absolute right-2 top-2">
          <CopyButton text={manual_json} />
        </div>
      </div>
    </article>
  );
}

function ConnectClaude() {
  const { provider } = useMeta();
  const { mcp_url } = connectMeta();
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Claude Desktop</h1>
      <p className="doc-p">
        Connect Revizo as a custom connector — Claude opens the {provider} sign-in the first time you use it.
      </p>

      <ServerUrlBox url={mcp_url} />

      <h2 className="doc-h2">Steps</h2>
      <ol className="mt-1">
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">1.</span>
          <span>
            Open <span className="doc-strong">Settings → Connectors</span> and choose{" "}
            <span className="doc-strong">Add custom connector</span>.
          </span>
        </li>
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">2.</span>
          <span>
            Name it <span className="doc-strong">Revizo</span> and paste the server URL above.
          </span>
        </li>
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">3.</span>
          <span>Enable it in a chat — the sign-in opens on first use, then you're set.</span>
        </li>
      </ol>
    </article>
  );
}

function ConnectClaudeCode() {
  const { provider } = useMeta();
  const { mcp_url } = connectMeta();
  const cmd = `claude mcp add --transport http revizo ${mcp_url}`;
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Claude Code</h1>
      <p className="doc-p">One command, then authenticate in-session.</p>

      <ServerUrlBox url={mcp_url} />

      <h2 className="doc-h2">Add the server</h2>
      <div className="relative mt-3">
        <pre className="overflow-x-auto rounded-lg border border-white/[0.07] bg-[#0c0c0e] px-4 py-3 font-mono text-[12.5px] leading-relaxed text-zinc-300">
          {cmd}
        </pre>
        <div className="absolute right-2 top-2">
          <CopyButton text={cmd} />
        </div>
      </div>
      <p className="doc-p">
        Then run <Code>/mcp</Code> inside Claude Code and pick <span className="doc-strong">Revizo → authenticate</span>.
        The {provider} sign-in opens in your browser.
      </p>
    </article>
  );
}

function ConnectChatGpt() {
  const { provider } = useMeta();
  const { mcp_url } = connectMeta();
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">ChatGPT</h1>
      <p className="doc-p">
        Connect Revizo as an app — the {provider} sign-in opens on first use.
      </p>

      <ServerUrlBox url={mcp_url} />

      <h2 className="doc-h2">Steps</h2>
      <ol className="mt-1">
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">1.</span>
          <span>
            Go to <span className="doc-strong">Settings → Apps &amp; Connectors</span> and create a connector (developer
            mode).
          </span>
        </li>
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">2.</span>
          <span>
            Set authentication to <span className="doc-strong">OAuth</span> and paste the server URL above.
          </span>
        </li>
        <li className="doc-li">
          <span className="shrink-0 tabular-nums text-zinc-600">3.</span>
          <span>Enable the connector in a chat and start the session.</span>
        </li>
      </ol>
    </article>
  );
}

function ConnectCodex() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Codex</h1>
      <ComingSoon name="Codex" />
    </article>
  );
}

function ConnectHermes() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Hermes</h1>
      <ComingSoon name="Hermes" />
    </article>
  );
}

function ConnectOther() {
  const { provider } = useMeta();
  const { mcp_url } = connectMeta();
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Other MCP clients</h1>
      <p className="doc-p">Revizo works with anything that speaks MCP over <span className="doc-strong">Streamable HTTP</span>.</p>

      <ServerUrlBox url={mcp_url} />

      <p className="doc-p">
        The server advertises standard OAuth metadata, so auth-capable clients discover the sign-in flow automatically —
        register the URL, and the {provider} sign-in happens in your browser on first connect. No token setup, no config
        files.
      </p>
    </article>
  );
}

function DocsIndex() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold tracking-tight text-white">Documentation</h1>
      <p className="doc-p">Everything you need to wire Revizo into your tools and workflow.</p>

      <div className="mt-8 grid gap-3">
        <Link to="/docs/introduction" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-5 transition hover:border-white/[0.16]">
          <div className="text-[14px] font-medium text-zinc-100 group-hover:text-blue-400">Introduction</div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
            What Revizo is, why it exists, and how the spaced-repetition loop works.
          </p>
        </Link>
        <Link to="/docs/features" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-5 transition hover:border-white/[0.16]">
          <div className="text-[14px] font-medium text-zinc-100 group-hover:text-blue-400">Features</div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
            Due lists, mistake reminders, weak patterns, SRS ladders, LeetCode sync.
          </p>
        </Link>
        <Link to="/docs/importing" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-5 transition hover:border-white/[0.16]">
          <div className="text-[14px] font-medium text-zinc-100 group-hover:text-blue-400">Importing problems</div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
            Bulk-add problems from a CSV — whatever format your spreadsheet is in.
          </p>
        </Link>
        <Link to="/docs/leetcode-import" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-5 transition hover:border-white/[0.16]">
          <div className="text-[14px] font-medium text-zinc-100 group-hover:text-blue-400">LeetCode full-history import</div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
            Connect once with your LeetCode session cookie, then import new solves incrementally.
          </p>
        </Link>
        <Link to="/docs/connect" className="group rounded-lg border border-white/[0.07] bg-[#0c0c0e] p-5 transition hover:border-white/[0.16]">
          <div className="text-[14px] font-medium text-zinc-100 group-hover:text-blue-400">Connect Revizo to your tools</div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">
            Per-client guides: Cursor, Claude Desktop, Claude Code, ChatGPT, Codex, Hermes — or any MCP client.
          </p>
        </Link>
      </div>
    </div>
  );
}

export interface DocPage {
  title: string;
  element: () => React.ReactNode;
}

export const DOCS_ORDER: string[] = [
  "introduction",
  "features",
  "leetcode-import",
  "importing",
  "connect",
  "connect/cursor",
  "connect/claude",
  "connect/claude-code",
  "connect/chatgpt",
  "connect/codex",
  "connect/hermes",
  "connect/other",
];

export const DOCS_COMPONENTS: Record<string, () => React.ReactNode> = {
  "introduction": Introduction,
  "features": Features,
  "leetcode-import": LeetCodeImport,
  "importing": Importing,
  "connect": ConnectOverview,
  "connect/cursor": ConnectCursor,
  "connect/claude": ConnectClaude,
  "connect/claude-code": ConnectClaudeCode,
  "connect/chatgpt": ConnectChatGpt,
  "connect/codex": ConnectCodex,
  "connect/hermes": ConnectHermes,
  "connect/other": ConnectOther,
};

export const DOCS_GROUPS: { title: string; items: { slug: string; label: string }[] }[] = [
  {
    title: "Introduction",
    items: [
      { slug: "introduction", label: "About Revizo" },
      { slug: "features", label: "Features" },
    ],
  },
  {
    title: "Reference",
    items: [
      { slug: "importing", label: "Importing problems" },
      { slug: "leetcode-import", label: "LeetCode import" },
    ],
  },
  {
    title: "Connect",
    items: [
      { slug: "connect", label: "Overview" },
      { slug: "connect/cursor", label: "Cursor" },
      { slug: "connect/claude", label: "Claude Desktop" },
      { slug: "connect/claude-code", label: "Claude Code" },
      { slug: "connect/chatgpt", label: "ChatGPT" },
      { slug: "connect/codex", label: "Codex" },
      { slug: "connect/hermes", label: "Hermes" },
      { slug: "connect/other", label: "Other clients" },
    ],
  },
];

export { DocsIndex };
