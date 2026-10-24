import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("calls same-origin /api with credentials and no CSRF header on GET", async () => {
    const fetch = mockFetch(200, { ok: true });
    await expect(api("/agents")).resolves.toEqual({ ok: true });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/agents");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers["X-Requested-With"]).toBeUndefined();
  });

  it("adds the CSRF header and JSON body on mutations", async () => {
    const fetch = mockFetch(201, { id: "1" });
    await api("/agents", { method: "POST", body: { name: "x" } });
    const [, init] = fetch.mock.calls[0];
    expect(init.headers["X-Requested-With"]).toBe("AgentGuard");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"name":"x"}');
  });

  it("never sends an Authorization header (auth is an HttpOnly cookie)", async () => {
    const fetch = mockFetch(200, {});
    await api("/runs", { method: "POST", body: {} });
    expect(Object.keys(fetch.mock.calls[0][1].headers)).not.toContain("Authorization");
  });

  it("returns undefined for 204", async () => {
    mockFetch(204, undefined);
    await expect(api("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("raises ApiError with the backend detail", async () => {
    mockFetch(409, { detail: "A run for this agent is already in progress." });
    await expect(api("/runs", { method: "POST", body: {} })).rejects.toEqual(
      new ApiError(409, "A run for this agent is already in progress."),
    );
  });

  it("flattens FastAPI validation errors", async () => {
    mockFetch(422, { detail: [{ loc: ["body", "policy", "max_refund_amount"], msg: "Input should be greater than or equal to 0" }] });
    await expect(api("/agents", { method: "POST", body: {} })).rejects.toThrow(
      "policy.max_refund_amount: Input should be greater than or equal to 0",
    );
  });

  it("handles non-JSON error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })));
    await expect(api("/dashboard")).rejects.toThrow("Request failed (502)");
  });
});
