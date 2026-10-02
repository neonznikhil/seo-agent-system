/**
 * RankForge Open API Client & Fetch Wrapper.
 */

const API_TIMEOUT = 120000;

export function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  let cleanPath = path.startsWith("/") ? path : `/${path}`;

  // In the browser, always call the same-origin Next.js proxy. The proxy owns
  // the backend URL (BACKEND_URL) and forwards identity headers, so the browser
  // never makes a cross-origin request and CORS can never break connectors.
  // Previously this fell back to a direct http://127.0.0.1:8000 call whenever
  // NEXT_PUBLIC_API_URL was unset, which failed CORS as soon as a website was
  // connected and generation started.
  if (typeof window !== "undefined") {
    if (!cleanPath.startsWith("/api/") && cleanPath !== "/api") {
      cleanPath = `/api${cleanPath}`;
    }
    return cleanPath;
  }

  // Server-side: resolve the backend base directly (same env the proxy uses).
  const rawBase = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "";
  const base = rawBase.replace(/\/+$/, "");

  if (!base) {
    if (!cleanPath.startsWith("/api/") && cleanPath !== "/api") {
      cleanPath = `/api${cleanPath}`;
    }
    return cleanPath;
  }

  if (base.endsWith("/api") && cleanPath.startsWith("/api/")) {
    cleanPath = cleanPath.substring(4);
  }
  return `${base}${cleanPath}`;
}

export async function authFetch(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {},
  retryCount: number = 0
): Promise<Response> {
  const isGenerationRequest = path.includes("generate") || path.includes("crew") || path.includes("crawl") || path.includes("writer");
  const defaultTimeout = isGenerationRequest ? 300000 : API_TIMEOUT;
  const timeoutMs = options.timeoutMs || defaultTimeout;

  let targetUrl = buildUrl(path);
  // If retry and failed with localhost, try 127.0.0.1
  if (retryCount > 0 && targetUrl.includes("localhost:8000")) {
    targetUrl = targetUrl.replace("localhost:8000", "127.0.0.1:8000");
  } else if (retryCount > 0 && targetUrl.includes("127.0.0.1:8000")) {
    targetUrl = targetUrl.replace("127.0.0.1:8000", "localhost:8000");
  }

  const controller = new AbortController();
  const TIMEOUT_REASON = "Request timed out";
  const timeout = setTimeout(() => {
    // Abort with a DOMException so fetch rejects with something whose .name we
    // can test. Aborting with a bare string made fetch reject with THAT STRING,
    // so error.name was undefined and every clause of isAborted below was false —
    // the intended "still generating in the background" message was unreachable
    // and every timeout read as a generic offline error.
    try {
      controller.abort(new DOMException(TIMEOUT_REASON, "TimeoutError"));
    } catch {
      controller.abort();
    }
  }, timeoutMs);

  const wid = typeof window !== "undefined"
    ? (localStorage.getItem("current-website-id") || localStorage.getItem("active_website_id") || "")
    : "";
  const uid = typeof window !== "undefined"
    ? (localStorage.getItem("user-id") || localStorage.getItem("account-id") || "a0000000-0000-0000-0000-000000000001")
    : "a0000000-0000-0000-0000-000000000001";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-Id": uid,
    ...(wid && wid !== "default-website-id" && wid !== "null" && wid !== "undefined" && wid !== "default" ? { "X-Website-Id": wid } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  try {
    const res = await fetch(targetUrl, {
      ...options,
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    // Retry only idempotent methods on 5xx. Replaying a POST (e.g. creating a
    // website) after an ambiguous failure would create duplicate resources.
    const method = (options.method || "GET").toUpperCase();
    const isIdempotent = method === "GET" || method === "HEAD" || method === "PUT" || method === "DELETE";
    if (!res.ok && res.status >= 500 && isIdempotent && retryCount < 2) {
      await new Promise((r) => setTimeout(r, 600 * (retryCount + 1)));
      return authFetch(path, options, retryCount + 1);
    }

    return res;
  } catch (error: any) {
    clearTimeout(timeout);
    const errName = error?.name;
    const errText = String(error?.message || error || "");
    const isTimeout =
      errName === "TimeoutError" ||
      errName === "AbortError" ||
      errText.includes(TIMEOUT_REASON) ||
      errText.toLowerCase().includes("abort");
    const isNetwork = errName === "TypeError" || errText.includes("Failed to fetch");

    const method = (options.method || "GET").toUpperCase();
    const isIdempotent = method === "GET" || method === "HEAD" || method === "PUT" || method === "DELETE";
    // Only retry genuine network failures, never an abort/timeout.
    if (isNetwork && !isTimeout && isIdempotent && retryCount < 2) {
      await new Promise((r) => setTimeout(r, 500));
      return authFetch(path, options, retryCount + 1);
    }

    const message = isTimeout
      ? "The request timed out. If this was a generation job it is still processing in the background — check /approvals in a few moments."
      : (error.message || "Failed to communicate with RankForge API");
    const err = new Error(message);
    (err as any).isTimeout = isTimeout;
    (err as any).targetUrl = targetUrl;
    throw err;
  }
}

function readableErrorDetail(errorText: string, statusText: string): string {
  // The backend returns JSON like {"error":"...","detail":"..."}; showing that
  // raw to the user (e.g. `API 502: {"error":"Backend unreachable",...}`) is
  // unreadable. Extract the human sentence, falling back to raw text.
  const raw = (errorText || "").trim();
  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw);
      const detail = parsed.detail ?? parsed.error ?? parsed.message;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return String(parsed.detail[0].msg);
    } catch {
      /* not JSON — fall through to raw */
    }
  }
  return raw || statusText;
}

function apiError(status: number, errorText: string, statusText: string): Error {
  const detail = readableErrorDetail(errorText, statusText);
  const msg =
    status === 429
      ? "Too many requests (429) — backend waking or busy. Wait 30 seconds, then retry once."
      : status === 502 || status === 504
      ? `Cannot reach the RankForge backend (${status}). ${detail}`
      : `API ${status}: ${detail}`;
  const error = new Error(msg);
  (error as any).status = status;
  return error;
}

async function retryOnceAfter429(
  res: Response,
  path: string,
  options: RequestInit,
  retried: boolean
): Promise<Response | null> {
  if (res.status !== 429 || retried) return null;
  const waitSecs = Math.min(parseInt(res.headers.get("Retry-After") || "5", 10) || 5, 30);
  await new Promise((r) => setTimeout(r, waitSecs * 1000));
  return authFetch(path, options);
}

export async function get(path: string, headers: Record<string, string> = {}) {
  const res = await authFetch(path, { method: "GET", headers });
  if (!res.ok) {
    if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
      const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
      const altRes = await authFetch(altPath, { method: "GET", headers });
      if (altRes.ok) return await altRes.json();
    }
    if (res.status === 429) {
      const retry = await retryOnceAfter429(res, path, { method: "GET", headers }, false);
      if (retry?.ok) return await retry.json();
    }
    const errorText = await res.text().catch(() => "");
    throw apiError(res.status, errorText, res.statusText);
  }
  return await res.json();
}

export async function post(path: string, body: any = {}, headers: Record<string, string> = {}) {
  const payload = typeof body === "string" ? body : JSON.stringify(body);
  const res = await authFetch(path, { method: "POST", headers, body: payload });
  if (!res.ok) {
    if (res.status === 404 && !path.startsWith("/api") && !path.startsWith("api")) {
      const altPath = `/api${path.startsWith("/") ? path : `/${path}`}`;
      const altRes = await authFetch(altPath, { method: "POST", headers, body: payload });
      if (altRes.ok) return await altRes.json();
    }
    if (res.status === 429) {
      const retry = await retryOnceAfter429(res, path, { method: "POST", headers, body: payload }, false);
      if (retry?.ok) return await retry.json();
    }
    const errorText = await res.text().catch(() => "");
    throw apiError(res.status, errorText, res.statusText);
  }
  return await res.json();
}

export async function put(path: string, body: any = {}, headers: Record<string, string> = {}) {
  const payload = typeof body === "string" ? body : JSON.stringify(body);
  const res = await authFetch(path, { method: "PUT", headers, body: payload });
  if (!res.ok) {
    if (res.status === 429) {
      const retry = await retryOnceAfter429(res, path, { method: "PUT", headers, body: payload }, false);
      if (retry?.ok) return await retry.json();
    }
    const errorText = await res.text().catch(() => "");
    throw apiError(res.status, errorText, res.statusText);
  }
  return await res.json();
}

export async function del(path: string, headers: Record<string, string> = {}) {
  const res = await authFetch(path, { method: "DELETE", headers });
  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw apiError(res.status, errorText, res.statusText);
  }
  return await res.json();
}

/**
 * Build an EventSource URL that authenticates.
 *
 * The native EventSource API cannot attach custom headers, so the backend never
 * saw X-User-Id and answered 401 in production — every live view was permanently
 * dead. Identity travels in the query string and the Next proxy promotes it back
 * to the header server-side.
 */
export function buildSSEUrl(path: string): string {
  const base = buildUrl(path);
  if (typeof window === "undefined") return base;
  const uid =
    localStorage.getItem("user-id") ||
    localStorage.getItem("account-id") ||
    "a0000000-0000-0000-0000-000000000001";
  const wid = localStorage.getItem("current-website-id") || localStorage.getItem("active_website_id") || "";
  const joiner = base.includes("?") ? "&" : "?";
  return `${base}${joiner}user_id=${encodeURIComponent(uid)}${
    wid && wid !== "default" ? `&website_id=${encodeURIComponent(wid)}` : ""
  }`;
}

export function createSSE(path: string, onMessage: (event: MessageEvent) => void): EventSource | null {
  if (typeof window === "undefined") return null;
  try {
    const source = new EventSource(buildSSEUrl(path));
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