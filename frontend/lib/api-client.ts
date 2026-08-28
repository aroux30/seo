const API_URL = process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? "/api/v1" : "http://localhost:8000/api/v1");

export class ApiError extends Error {
  status: number;
  data?: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

/**
 * Single-flight refresh.
 *
 * Previously every concurrent 401 fired its own POST /auth/refresh. Because the
 * backend rotates the refresh token, only the first call could succeed — the
 * rest presented a token that had just been revoked, got 401 back, and dropped
 * into the logout branch. A dashboard that fires five parallel requests on
 * mount would therefore bounce the user to /login instead of refreshing. The
 * new /auth/refresh rate limit (30/60s) makes the burst worse still.
 *
 * Now the first 401 owns the refresh and everyone else awaits the same promise.
 */
let refreshInFlight: Promise<boolean> | null = null;

function clearSessionAndRedirect() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  clearCache();
  // Guard against redirect loops when the 401 happened on /login itself.
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;
      const body = await res.json();
      const data = body?.data;
      if (!data?.access_token || !data?.refresh_token) return false;
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      // Release the slot so a later expiry can refresh again. Cleared in a
      // microtask so waiters still resolve against this same promise.
      Promise.resolve().then(() => {
        refreshInFlight = null;
      });
    }
  })();

  return refreshInFlight;
}

// ============================================================================
// GET cache — stale-while-revalidate (TTL) + in-flight dedup.
//
// Tab-to-tab navigation used to remount the target page, which refetched
// everything behind a full spinner even though the same data was on screen
// seconds ago. With this cache a revisit inside the TTL renders instantly from
// memory; mutations invalidate their resource prefix so post-action refetches
// stay correct. The cache key carries the org id — switching organizations can
// never serve the previous org's data.
// ============================================================================
const GET_TTL_MS = 60_000;
const getCache = new Map<string, { data: any; ts: number }>();
const inFlightGets = new Map<string, Promise<any>>();

// Endpoints whose response must always be fresh (polled counters, auth).
const NO_CACHE_PATTERNS = ["/auth/", "/notifications/unread-count"];

function cacheKey(url: string): string {
  const orgId = typeof window !== "undefined" ? localStorage.getItem("current_org_id") : null;
  return `${orgId ?? "no-org"}::${url}`;
}

function isCacheable(url: string): boolean {
  if (typeof window === "undefined") return false;
  return !NO_CACHE_PATTERNS.some((p) => url.includes(p));
}

/** Drop cached GETs under the mutated resource's first path segment. */
function invalidatePrefix(url: string): void {
  const seg = "/" + url.replace(/^\//, "").split("?")[0].split("/")[0];
  for (const key of [...getCache.keys()]) {
    const pathPart = key.split("::")[1] ?? "";
    if (pathPart.startsWith(seg)) getCache.delete(key);
  }
}

export function clearCache(): void {
  getCache.clear();
  inFlightGets.clear();
}

async function request<T = any>(
  endpoint: string,
  options: RequestInit = {},
  customHeaders: Record<string, string> = {},
  isRetry = false
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();

  // ---- GET cache fast paths (never entered on the 401-retry replay) ----
  if (method === "GET" && isCacheable(endpoint) && !isRetry) {
    const key = cacheKey(endpoint);
    const hit = getCache.get(key);
    if (hit && Date.now() - hit.ts < GET_TTL_MS) {
      return hit.data as T;
    }
    const pending = inFlightGets.get(key);
    if (pending) {
      return pending as Promise<T>;
    }
    const promise = doRequest<T>(endpoint, options, customHeaders, false)
      .then((data) => {
        getCache.set(key, { data, ts: Date.now() });
        return data;
      })
      .finally(() => {
        inFlightGets.delete(key);
      });
    inFlightGets.set(key, promise as Promise<any>);
    return promise;
  }

  return doRequest<T>(endpoint, options, customHeaders, isRetry);
}

async function doRequest<T = any>(
  endpoint: string,
  options: RequestInit = {},
  customHeaders: Record<string, string> = {},
  isRetry = false
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const orgId = typeof window !== "undefined" ? localStorage.getItem("current_org_id") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...customHeaders,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (orgId) {
    headers["X-Organization-Id"] = orgId;
  }

  const fetchOptions: RequestInit = {
    ...options,
    cache: "no-store",
    headers: {
      ...headers,
      ...options.headers,
    },
  };

  const res = await fetch(`${API_URL}${endpoint}`, fetchOptions);

  if (res.status === 204) {
    return null as T;
  }

  const json = await res.json().catch(() => ({}));

  if (!res.ok) {
    if (res.status >= 500) {
      // Server-side failures are worth keeping in the console for diagnosis;
      // per-request chatter (success logs with full payloads) is not — it
      // measurably slowed every call down.
      console.error(`[API] ${method} ${endpoint} -> ${res.status}`, json);
    }

    // 401: the access token is probably expired. Refresh once, then replay.
    const isAuthEndpoint =
      endpoint === "/auth/refresh" ||
      endpoint === "/auth/login" ||
      endpoint === "/auth/register";

    if (res.status === 401 && typeof window !== "undefined" && !isAuthEndpoint && !isRetry) {
      if (localStorage.getItem("refresh_token")) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          // isRetry=true: if the replay 401s too, surface it instead of looping.
          return doRequest<T>(endpoint, options, customHeaders, true);
        }
        clearSessionAndRedirect();
      }
    }

    let errorMessage = "خطای ارتباط با سرور";
    if (typeof json.detail === "string") {
      errorMessage = json.detail;
    } else if (Array.isArray(json.detail) && json.detail.length > 0 && json.detail[0].msg) {
      errorMessage = json.detail[0].msg;
    } else if (json.detail && typeof json.detail === "object") {
      errorMessage = JSON.stringify(json.detail);
    }

    throw new ApiError(res.status, errorMessage, json);
  }

  // A successful mutation changes server state — cached GETs for that resource
  // must not be served again. Content mutations also produce versions, and a
  // version rollback rewrites the live article — keep both caches in sync.
  if (method !== "GET") {
    invalidatePrefix(endpoint);
    if (endpoint.startsWith("/content")) {
      for (const key of [...getCache.keys()]) {
        if ((key.split("::")[1] ?? "").startsWith("/versions")) getCache.delete(key);
      }
    }
    if (endpoint.startsWith("/versions")) {
      for (const key of [...getCache.keys()]) {
        if ((key.split("::")[1] ?? "").startsWith("/content")) getCache.delete(key);
      }
    }
  }

  return json.data !== undefined ? json.data : json;
}

export const api = {
  get: <T = any>(url: string, headers?: Record<string, string>) =>
    request<T>(url, { method: "GET" }, headers),
  post: <T = any>(url: string, body?: any, headers?: Record<string, string>) =>
    request<T>(url, { method: "POST", body: body ? JSON.stringify(body) : undefined }, headers),
  put: <T = any>(url: string, body?: any, headers?: Record<string, string>) =>
    request<T>(url, { method: "PUT", body: body ? JSON.stringify(body) : undefined }, headers),
  patch: <T = any>(url: string, body?: any, headers?: Record<string, string>) =>
    request<T>(url, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }, headers),
  delete: <T = any>(url: string, headers?: Record<string, string>) =>
    request<T>(url, { method: "DELETE" }, headers),
  /** Force the next GET for these URL prefixes to hit the network. */
  invalidate: invalidatePrefix,
  clearCache,
};
