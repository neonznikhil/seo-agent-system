const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");
const API_TIMEOUT = 30000;

function getXUserId(): string {
  if (typeof window === "undefined") return "default-user";
  return localStorage.getItem("x-user-id") || "default-user";
}

function getDefaultHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-User-Id": getXUserId(),
  };
}

export function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  let cleanPath = path.startsWith("/") ? path : `/${path}`;
  
  // Normalize double /api/api
  cleanPath = cleanPath.replace(/^\/api\/api\//, "/api/");
  
  return `${API_BASE}${cleanPath}`;
}

export function createSSE(path: string, onMessage: (event: MessageEvent) => void): EventSource | null {
  if (typeof window === "undefined") return null;
  try {
    const url = buildUrl(path);
    const source = new EventSource(url);
    source.onmessage = onMessage;
    source.onerror = () => {
      source.close();
    };
    return source;
  } catch {
    return null;
  }
}

async function fetchWithTimeout(path: string, options: RequestInit = {}, retryCount: number = 0): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT);
  const targetUrl = buildUrl(path);

  try {
    const res = await fetch(targetUrl, {
      ...options,
      headers: { ...getDefaultHeaders(), ...(options.headers || {}) },
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok && res.status >= 500 && retryCount < 2) {
      await new Promise(r => setTimeout(r, 600 * (retryCount + 1)));
      return fetchWithTimeout(path, options, retryCount + 1);
    }

    return res;
  } catch (error: any) {
    clearTimeout(timeout);
    if (retryCount < 1 && (error.name === "TypeError" || error.message?.includes("Failed to fetch"))) {
      await new Promise(r => setTimeout(r, 500));
      return fetchWithTimeout(path, options, retryCount + 1);
    }
    const err = new Error(error.message || "Failed to communicate with RankForge API");
    (err as any).isOffline = true;
    (err as any).targetUrl = targetUrl;
    throw err;
  }
}

export async function get(path: string, headers: Record<string, string> = {}) {
  try {
    const res = await fetchWithTimeout(path, { method: "GET", headers });
    if (!res.ok) {
      // If 404 on /something, try /api/something
      if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
        const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
        const altRes = await fetchWithTimeout(altPath, { method: "GET", headers });
        if (altRes.ok) return await altRes.json();
      }
      const error = new Error(`API ${res.status}: ${res.statusText}`);
      (error as any).status = res.status;
      throw error;
    }
    return await res.json();
  } catch (e: any) {
    throw e;
  }
}

export async function post(path: string, body: any = {}, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { 
    method: "POST", 
    headers, 
    body: typeof body === "string" ? body : JSON.stringify(body) 
  });
  if (!res.ok) {
    if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
      const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
      const altRes = await fetchWithTimeout(altPath, { 
        method: "POST", 
        headers, 
        body: typeof body === "string" ? body : JSON.stringify(body) 
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
  const res = await fetchWithTimeout(path, { 
    method: "PUT", 
    headers, 
    body: typeof body === "string" ? body : JSON.stringify(body) 
  });
  if (!res.ok) {
    const error = new Error(`API ${res.status}: ${res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function del(path: string, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { method: "DELETE", headers });
  if (!res.ok) {
    const error = new Error(`API ${res.status}: ${res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export const api = {
  get,
  post,
  put,
  del,
  buildUrl,
  createSSE,
};

export default api;