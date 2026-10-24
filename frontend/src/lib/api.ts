// Thin client for the AgentGuard API. Requests go to the same origin (/api/*) and are
// proxied to the backend; authentication rides on an HttpOnly cookie the browser
// manages, so this file never touches credentials.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc.filter((p: unknown) => p !== "body").join(".") : "";
          const msg = String(d?.msg ?? "Invalid value").replace(/^Value error, /, "");
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join("; ");
    }
  }
  return `Request failed (${status})`;
}

export async function api<T>(path: string, options: { method?: Method; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-Requested-With"] = "AgentGuard"; // CSRF guard
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status));
  return body as T;
}
