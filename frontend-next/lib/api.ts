const API_ROOT = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const API_BASE = API_ROOT.endsWith("/api") ? API_ROOT : `${API_ROOT}/api`;

export { API_BASE };
const API_TIMEOUT = 30000;

function getXUserId(): string {
  if (typeof window === "undefined") return "anonymous";
  return localStorage.getItem("x-user-id") || "anonymous";
}

function getDefaultHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-User-Id": getXUserId(),
  };
}

function isOfflineError(error: any): boolean {
  return (
    error?.message?.includes("Backend not running") ||
    error?.message?.includes("offline") ||
    error?.message?.includes("Failed to fetch") ||
    error?.message?.includes("NetworkError") ||
    error?.message?.includes("ECONNREFUSED")
  );
}

export function createSSE(path: string, onMessage: (event: MessageEvent) => void): EventSource {
  const url = `${API_BASE}${path}`;
  const source = new EventSource(url);
  source.onmessage = onMessage;
  source.onerror = () => {
    source.close();
  };
  return source;
}

async function fetchWithTimeout(path: string, options: RequestInit = {}, retry: boolean = false): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...getDefaultHeaders(), ...(options.headers || {}) },
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok && res.status === 500 && !retry) {
      const retryRes = await fetchWithTimeout(path, options, true);
      return retryRes;
    }

    return res;
  } catch (error: any) {
    clearTimeout(timeout);
    if (error.name === "AbortError") {
      throw new Error("API request timeout - backend may be offline");
    }
    if (isOfflineError(error)) {
      throw new Error("Backend not running - start the FastAPI server");
    }
    throw error;
  }
}

async function parseOrThrow(res: Response) {
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      detail = res.statusText;
    }
    if (res.status === 403 && !detail) detail = "Forbidden - check permissions or login";
    const error = new Error(detail || `API ${res.status}: ${res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return await res.json();
}

export async function get(path: string, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { method: "GET", headers });
  return await parseOrThrow(res);
}

export async function del(path: string, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { method: "DELETE", headers });
  return await parseOrThrow(res);
}

export async function put(path: string, body: any, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { method: "PUT", headers, body: JSON.stringify(body) });
  return await parseOrThrow(res);
}

export async function post(path: string, body: any, headers: Record<string, string> = {}) {
  const res = await fetchWithTimeout(path, { method: "POST", headers, body: JSON.stringify(body) });
  return await parseOrThrow(res);
}