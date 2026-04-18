const AUTH_KEY = "wb_auth";

export interface StoredAuth {
  token: string;
  role: import("./types").UserRole;
  userId: number;
}

export function readStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as StoredAuth;
    if (!v?.token || !v?.role || typeof v.userId !== "number") return null;
    return v;
  } catch {
    return null;
  }
}

export function writeStoredAuth(auth: StoredAuth | null) {
  if (typeof window === "undefined") return;
  if (!auth) localStorage.removeItem(AUTH_KEY);
  else localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

/** Browser: relative `/api` uses Vite proxy. SSR: full backend URL. */
export function apiOrigin(): string {
  if (typeof window !== "undefined") return "";
  return (
    (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
    "http://127.0.0.1:8000"
  );
}

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const o = apiOrigin();
  return `${o}${p}`;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function flattenDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === "object" && e && "msg" in e ? String((e as { msg: unknown }).msg) : JSON.stringify(e)))
      .join("; ");
  }
  if (detail && typeof detail === "object" && "detail" in detail) {
    return flattenDetail((detail as { detail: unknown }).detail);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return "Request failed";
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { token?: string | null; skipAuth?: boolean } = {}
): Promise<T> {
  const { token, skipAuth, headers: hdr, ...rest } = init;
  const headers = new Headers(hdr);
  if (!headers.has("Content-Type") && rest.body && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const authToken = skipAuth ? null : token ?? readStoredAuth()?.token;
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);

  const res = await fetch(apiUrl(path), { ...rest, headers });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const detail = body && typeof body === "object" && body !== null && "detail" in body ? (body as { detail: unknown }).detail : body;
    throw new ApiError(flattenDetail(detail) || res.statusText, res.status, detail);
  }
  return body as T;
}
