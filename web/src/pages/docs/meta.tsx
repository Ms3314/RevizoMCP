import { createContext, useContext, useEffect, useState } from "react";

interface Meta {
  oauth_configured: boolean;
  provider: string;
}

const MetaContext = createContext<Meta>({ oauth_configured: false, provider: "Google" });

export function MetaProvider({ children }: { children: React.ReactNode }) {
  const [meta, setMeta] = useState<Meta>({ oauth_configured: false, provider: "Google" });

  useEffect(() => {
    fetch("/api/meta", { credentials: "include" })
      .then((r) => r.json())
      .then((m: Meta) => setMeta(m))
      .catch(() => {
        /* public endpoint; failure → assume not configured */
      });
  }, []);

  return <MetaContext.Provider value={meta}>{children}</MetaContext.Provider>;
}

export function useMeta() {
  return useContext(MetaContext);
}

// The MCP endpoint + client-specific install links are derived from the browser
// origin, so they're always correct on localhost / 127.0.0.1 / a deploy domain.
export function connectMeta() {
  const origin = window.location.origin;
  const mcp_url = `${origin}/mcp`;
  const manual_json = JSON.stringify({ mcpServers: { revizo: { url: mcp_url } } }, null, 2);
  const config = btoa(JSON.stringify({ type: "http", url: mcp_url }));
  const cursor_link = `cursor://anysphere.cursor-deeplink/mcp/install?name=Revizo&config=${encodeURIComponent(config)}`;
  return { origin, mcp_url, manual_json, cursor_link };
}
