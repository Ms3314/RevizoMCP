# <img src="public/mark.svg" width="34" align="top" alt="Revizo"/> <span>**Revizo**</span> <em>— your problems remember what you got wrong.</em>

<img width="3899" height="2140" alt="Revizo" src="https://github.com/user-attachments/assets/a8e8e681-06e1-4695-ba72-a24c9108ddab" />

<p align="left">
  <em>A spaced-repetition revision coach for DSA interview prep, living inside your LLM.</em>
</p>

---

## Monorepo layout

Revizo is a monorepo with two independent packages that talk only over HTTP:

- **`server/`** — the Python app (FastAPI + MCP). `uv`-managed. Serves the MCP
  endpoint at `/mcp`, the JSON API at `/api`, OAuth at `/oauth`, and the built
  React SPA from `server/static`. This is the primary application.

- **`web/`** — the React + TypeScript + Tailwind v4 dashboard. `npm`-managed
  (Vite). Builds to `web/dist`, which `make build` copies into `server/static`.

Neither package depends on the other at build time. One deployment serves
everything from the FastAPI process (same origin, cookie session auth, no CORS).

Common commands (root `Makefile`):


```bash

make install        # install both server (uv) and web (npm) deps

make dev            # FastAPI on :8000 (--reload) + Vite on :5173 (proxies /api)

make build          # build web/ and copy into server/

make serve          # production-style: FastAPI serves

make test-server    # pytest for the Python package

```

> The SPA owns `/app` and `/app/*` routes; the older Jinja page templates are

> being ported section by section (see migration phases). Until a section is

> ported, its server-rendered route still works.

## What is Revizo?

Revizo is an **MCP server for DSA revision**.

It keeps track of the problems you solve, the mistakes you make, and when you should revisit them. You can interact with it directly through an MCP-compatible LLM client like Cursor, Claude, or ChatGPT.

The idea is simple:

**solve → record → revisit → repeat**

### What it can do

-  Add problems from **LeetCode, CodeChef, GFG**, and other sources
-  Sync your **LeetCode activity**
-  Import your **full LeetCode solved history**, with incremental updates
-  Revise problems using **AI hints**
-  Schedule problems using **spaced repetition**
-  Remember the **mistakes you made** on previous attempts
-  Identify recurring **weak points** across problems
-  OAuth-enabled authentication with **Google**
-  Works directly through **MCP**

## Full LeetCode import setup

To enable full-history imports, configure `LEETCODE_SESSION_ENCRYPTION_KEY` with a

Fernet key (generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

Keep the key stable across restarts and deployments: saved LeetCode session cookies

are encrypted with it. Users connect once from `/app/leetcode`; see the

LeetCode import guide in the running app for how to find and save their cookie.
