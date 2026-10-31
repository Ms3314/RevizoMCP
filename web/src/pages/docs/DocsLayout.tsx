import { Outlet } from "react-router-dom";

// Placeholder docs shell — the full docs tree (Introduction, Features, LeetCode
// import, Importing, Connect/*) is ported from the Jinja templates in Phase 3.
export function DocsLayout() {
  return (
    <div className="doc-p">
      <h1 className="text-2xl font-semibold text-zinc-100">Docs</h1>
      <p className="mt-3 text-zinc-500">
        The full documentation is ported from the server-rendered templates in Phase 3.
      </p>
      <Outlet />
    </div>
  );
}
