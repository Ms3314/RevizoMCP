import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="mx-auto max-w-2xl py-24 text-center">
      <h1 className="text-3xl font-semibold text-zinc-100">404</h1>
      <p className="mt-3 text-zinc-500">That page doesn’t exist.</p>
      <Link to="/" className="mt-6 inline-block text-blue-400 hover:text-blue-300">
        Go home
      </Link>
    </div>
  );
}
