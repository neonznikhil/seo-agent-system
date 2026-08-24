/**
 * RankForge Open API Client & Fetch Wrapper.
 */

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");
const API_TIMEOUT = 30000;

export function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  let cleanPath = path.startsWith("/") ? path : `/${path}`;
  const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
  
  if (base.endsWith("/api") && cleanPath.startsWith("/api/")) {
    cleanPath = cleanPath.substring(4);
  }
  return `${base}${cleanPath}`;
}

export async function authFetch(
  path: string,
  options: RequestInit = {},
  retryCount: number = 0
): Promise<Response> {
  const targetUrl = buildUrl(path);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  try {
    const res = await fetch(targetUrl, {
      ...options,
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    // Retry on 500 errors
    if (!res.ok && res.status >= 500 && retryCount < 2) {
      await new Promise((r) => setTimeout(r, 600 * (retryCount + 1)));
      return authFetch(path, options, retryCount + 1);
    }

    return res;
  } catch (error: any) {
    clearTimeout(timeout);
    if (retryCount < 1 && (error.name === "TypeError" || error.message?.includes("Failed to fetch"))) {
      await new Promise((r) => setTimeout(r, 500));
      return authFetch(path, options, retryCount + 1);
    }
    const err = new Error(error.message || "Failed to communicate with RankForge API");
    (err as any).isOffline = true;
    (err as any).targetUrl = targetUrl;
    throw err;
  }
}

export async function get(path: string, headers: Record<string, string> = {}) {
  const res = await authFetch(path, { method: "GET", headers });
  if (!res.ok) {
    if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
      const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
      const altRes = await authFetch(altPath, { method: "GET", headers });
      if (altRes.ok) return await altRes.json();
    }
    const errorText = await res.text().catch(() => "");
    const error = new Error(`API ${res.status}: ${errorText || res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function post(path: string, body: any = {}, headers: Record<string, string> = {}) {
  const res = await authFetch(path, {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
      const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
      const altRes = await authFetch(altPath, {
        method: "POST",
        headers,
        body: typeof body === "string" ? body : JSON.stringify(body),
      });
      if (altRes.ok) return await altRes.json();
    }
    const errorText = await res.text().catch(() => "");
    const error = new Error(`API ${res.status}: ${errorText || res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function put(path: string, body: any = {}, headers: Record<string, string> = {}) {
  const res = await authFetch(path, {
    method: "PUT",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    const error = new Error(`API ${res.status}: ${errorText || res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function del(path: string, headers: Record<string, string> = {}) {
  const res = await authFetch(path, { method: "DELETE", headers });
  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    const error = new Error(`API ${res.status}: ${errorText || res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export function createSSE(path: string, onMessage: (event: MessageEvent) => void): EventSource | null {
  if (typeof window === "undefined") return null;
  try {
    const url = buildUrl(path);
    const source = new EventSource(url);
    source.onmessage = onMessage;
    source.onerror = () => source.close();
    return source;
  } catch {
    return null;
  }
}

export const api = {
  get,
  post,
  put,
  del,
  authFetch,
  fetchWithTimeout: authFetch,
  buildUrl,
  createSSE,
};

export default api;