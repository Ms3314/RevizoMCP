import { createBrowserRouter } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { Today } from "./pages/Today";
import { NewProblem } from "./pages/NewProblem";
import { ImportProblems } from "./pages/ImportProblems";
import { LeetCodeSettings } from "./pages/LeetCodeSettings";
import { NotFound } from "./pages/NotFound";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <Layout>
        <Landing />
      </Layout>
    ),
  },
  {
    path: "/app",
    element: (
      <RequireAuth>
        <Layout>
          <Dashboard />
        </Layout>
      </RequireAuth>
    ),
  },
  {
    path: "/app/today",
    element: (
      <RequireAuth>
        <Layout>
          <Today />
        </Layout>
      </RequireAuth>
    ),
  },
  {
    path: "/app/problems/new",
    element: (
      <RequireAuth>
        <Layout>
          <NewProblem />
        </Layout>
      </RequireAuth>
    ),
  },
  {
    path: "/app/import",
    element: (
      <RequireAuth>
        <Layout>
          <ImportProblems />
        </Layout>
      </RequireAuth>
    ),
  },
  {
    path: "/app/leetcode",
    element: (
      <RequireAuth>
        <Layout>
          <LeetCodeSettings />
        </Layout>
      </RequireAuth>
    ),
  },
  // /docs is intentionally absent: the docs are still the server-rendered
  // Jinja pages until the docs/content.tsx port is wired in (Phase 3).
  {
    path: "*",
    element: <NotFound />,
  },
]);
