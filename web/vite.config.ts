import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));

// Dev server proxies all backend traffic to the FastAPI app (cookie auth and
// same-origin are preserved, so no CORS needed). Default FastAPI port is 8000.
const API_TARGET = process.env.API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(root, "src") },
  },
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/oauth": { target: API_TARGET, changeOrigin: true },
      "/login": { target: API_TARGET, changeOrigin: true },
      "/logout": { target: API_TARGET, changeOrigin: true },
      "/docs": { target: API_TARGET, changeOrigin: true },
      "/connect": { target: API_TARGET, changeOrigin: true },
      "/auth": { target: API_TARGET, changeOrigin: true },
      "/mcp": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
      "/mark.svg": { target: API_TARGET, changeOrigin: true },
      "/logo": { target: API_TARGET, changeOrigin: true },
      "/app.css": { target: API_TARGET, changeOrigin: true },
    },
  },
});
