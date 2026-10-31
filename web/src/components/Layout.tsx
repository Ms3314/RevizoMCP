import { NavLink, Link } from "react-router-dom";
import type { ReactNode } from "react";

const navItems = [
  { to: "/app", label: "Dashboard" },
  { to: "/app/today", label: "Today" },
  { to: "/app/problems/new", label: "Add problem" },
  { to: "/app/import", label: "Import" },
  { to: "/app/leetcode", label: "LeetCode" },
];

const navIdle = "rounded-md px-3 py-1.5 transition text-zinc-400 hover:text-zinc-200";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-200">
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-[#09090b]/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-zinc-100">
            <img src="/mark.svg" alt="" className="h-6 w-6" />
            Revizo
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive ? "rounded-md px-3 py-1.5 transition bg-zinc-800 text-zinc-100" : navIdle
                }
              >
                {item.label}
              </NavLink>
            ))}
            {/* Docs are still server-rendered (Jinja) — a full page load, not a client route. */}
            <a href="/docs" className={navIdle}>
              Docs
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {/* Full page load: /logout is a server route that clears the session cookie. */}
            <a className="text-zinc-400 hover:text-zinc-200" href="/logout">
              Sign out
            </a>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
