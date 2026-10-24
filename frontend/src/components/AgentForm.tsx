"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Agent, AgentPolicy, Profile, Tool } from "@/lib/types";
import { Button, Card, CardTitle, ErrorBanner, Field, inputClass, Loading, Pill } from "./ui";

const DEFAULT_POLICY: AgentPolicy = {
  max_refund_amount: 100,
  require_identity_verification: true,
  max_tool_calls_per_session: 12,
  max_identical_tool_calls: 3,
};

const RISKY = new Set(["financial", "destructive", "communication", "pii"]);

export interface ToolPermission {
  wired: boolean;
  allowed: boolean;
}

/** Derive the API's `tools` / `allowed_tools` lists; allowed tools must be wired. */
export function toToolLists(perms: Record<string, ToolPermission>, order: string[]) {
  const tools = order.filter((t) => perms[t]?.wired);
  const allowed_tools = tools.filter((t) => perms[t]?.allowed);
  return { tools, allowed_tools };
}

export function AgentForm({ agent }: { agent?: Agent }) {
  const router = useRouter();
  const tools = useApi<Tool[]>("/tools");
  const profiles = useApi<Profile[]>("/profiles");
  const [provider, setProvider] = useState<"simulated" | "http">(agent?.provider ?? "simulated");
  const [policy, setPolicy] = useState<AgentPolicy>({ ...DEFAULT_POLICY, ...agent?.policy });
  const [perms, setPerms] = useState<Record<string, ToolPermission> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toolOrder = useMemo(() => tools.data?.map((t) => t.name) ?? [], [tools.data]);
  const permissions: Record<string, ToolPermission> =
    perms ??
    Object.fromEntries(
      toolOrder.map((name) => [
        name,
        agent
          ? { wired: agent.tools.includes(name), allowed: agent.allowed_tools.includes(name) }
          : { wired: true, allowed: name !== "delete_account" },
      ]),
    );

  function setPerm(name: string, change: Partial<ToolPermission>) {
    const next = { ...permissions, [name]: { ...permissions[name], ...change } };
    if (change.wired === false) next[name].allowed = false;
    setPerms(next);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const providerConfig =
      provider === "simulated"
        ? { profile: f.get("profile") }
        : { endpoint_url: f.get("endpoint_url"), timeout_seconds: Number(f.get("timeout_seconds")) || 20 };
    const token = String(f.get("auth_token") ?? "");
    const body: Record<string, unknown> = {
      name: f.get("name"),
      description: f.get("description"),
      system_prompt: f.get("system_prompt"),
      provider_config: providerConfig,
      policy,
      ...toToolLists(permissions, toolOrder),
    };
    if (token) body.auth_token = token;
    setBusy(true);
    setError(null);
    try {
      if (agent) {
        if (f.get("clear_auth_token") === "on") body.clear_auth_token = true;
        await api<Agent>(`/agents/${agent.id}`, { method: "PATCH", body });
        router.push(`/agents/${agent.id}`);
        router.refresh();
      } else {
        const created = await api<Agent>("/agents", { method: "POST", body: { ...body, provider } });
        router.push(`/agents/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the agent.");
      setBusy(false);
    }
  }

  if (tools.loading || profiles.loading) return <Loading />;

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <ErrorBanner message={error ?? tools.error ?? profiles.error} />
      <Card>
        <CardTitle>Basics</CardTitle>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Name" htmlFor="name">
            <input id="name" name="name" required maxLength={120} defaultValue={agent?.name} className={inputClass} />
          </Field>
          <Field label="Description" htmlFor="description">
            <input id="description" name="description" maxLength={2000} defaultValue={agent?.description} className={inputClass} />
          </Field>
        </div>
        <div className="mt-4">
          <Field label="System prompt" htmlFor="system_prompt" hint="Sent to HTTP agents with every step. Reference agents ignore it except when a scenario probes for leaks.">
            <textarea id="system_prompt" name="system_prompt" rows={4} maxLength={20000} defaultValue={agent?.system_prompt} className={inputClass} />
          </Field>
        </div>
      </Card>

      <Card>
        <CardTitle>Agent connection</CardTitle>
        {!agent && (
          <fieldset className="mb-4 grid gap-3 sm:grid-cols-2">
            <legend className="sr-only">Provider</legend>
            {(
              [
                ["simulated", "Reference agent", "Built-in deterministic agent for demos and evaluating AgentGuard. No API keys."],
                ["http", "HTTP endpoint", "Your agent, called via the AgentGuard step protocol. Tool calls run in our sandbox."],
              ] as const
            ).map(([value, title, text]) => (
              <label key={value} className={`cursor-pointer rounded-lg border p-3 ${provider === value ? "border-accent bg-surface-2" : "border-border"}`}>
                <input type="radio" name="provider" value={value} checked={provider === value} onChange={() => setProvider(value)} className="mr-2" />
                <span className="text-sm font-medium text-ink">{title}</span>
                <p className="mt-1 text-xs text-ink-2">{text}</p>
              </label>
            ))}
          </fieldset>
        )}
        {provider === "simulated" ? (
          <Field label="Behaviour profile" htmlFor="profile">
            <select id="profile" name="profile" defaultValue={agent?.provider_config.profile ?? "guarded"} className={inputClass}>
              {profiles.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} — {p.description}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <div className="grid gap-4 md:grid-cols-[1fr_160px]">
            <Field label="Endpoint URL" htmlFor="endpoint_url" hint="Must be a public HTTPS endpoint in production.">
              <input id="endpoint_url" name="endpoint_url" type="url" required defaultValue={agent?.provider_config.endpoint_url} placeholder="https://agent.example.com/agentguard/step" className={inputClass} />
            </Field>
            <Field label="Timeout (s)" htmlFor="timeout_seconds">
              <input id="timeout_seconds" name="timeout_seconds" type="number" min={1} max={120} defaultValue={agent?.provider_config.timeout_seconds ?? 20} className={inputClass} />
            </Field>
            <div className="md:col-span-2">
              <Field
                label="Bearer token (optional)"
                htmlFor="auth_token"
                hint="Encrypted at rest and never shown again. Leave blank to keep the current token."
              >
                <input id="auth_token" name="auth_token" type="password" autoComplete="off" maxLength={4096} placeholder={agent?.has_auth_token ? "•••••••• (stored)" : ""} className={inputClass} />
              </Field>
              {agent?.has_auth_token && (
                <label className="mt-2 flex items-center gap-2 text-sm text-ink-2">
                  <input type="checkbox" name="clear_auth_token" /> Remove stored token
                </label>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Tools and permissions</CardTitle>
        <p className="mb-4 text-sm text-ink-2">
          <strong className="text-ink">Wired in</strong> tools are exposed to the agent in the sandbox. <strong className="text-ink">Allowed</strong> tools are
          ones it is authorized to use; calling a wired-in tool that is not allowed is flagged as a violation.
        </p>
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-ink-3">
              <tr>
                <th className="px-5 pb-2 font-medium">Tool</th>
                <th className="px-3 pb-2 text-center font-medium">Wired in</th>
                <th className="px-5 pb-2 text-center font-medium">Allowed</th>
              </tr>
            </thead>
            <tbody>
              {tools.data?.map((t) => (
                <tr key={t.name} className="border-t border-border">
                  <td className="px-5 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-ink">{t.name}</span>
                      <Pill tone={RISKY.has(t.category) ? "serious" : "neutral"}>{t.category}</Pill>
                    </div>
                    <div className="mt-0.5 text-xs text-ink-3">{t.description}</div>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <input type="checkbox" aria-label={`${t.name} wired in`} checked={permissions[t.name]?.wired ?? false} onChange={(e) => setPerm(t.name, { wired: e.target.checked })} />
                  </td>
                  <td className="px-5 py-2.5 text-center">
                    <input
                      type="checkbox"
                      aria-label={`${t.name} allowed`}
                      disabled={!permissions[t.name]?.wired}
                      checked={permissions[t.name]?.allowed ?? false}
                      onChange={(e) => setPerm(t.name, { allowed: e.target.checked })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardTitle>Policy</CardTitle>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Max refund amount ($)" htmlFor="max_refund_amount">
            <input id="max_refund_amount" type="number" min={0} step="0.01" value={policy.max_refund_amount} onChange={(e) => setPolicy({ ...policy, max_refund_amount: Number(e.target.value) })} className={inputClass} />
          </Field>
          <Field label="Max tool calls per conversation" htmlFor="max_tool_calls">
            <input id="max_tool_calls" type="number" min={1} max={100} value={policy.max_tool_calls_per_session} onChange={(e) => setPolicy({ ...policy, max_tool_calls_per_session: Number(e.target.value) })} className={inputClass} />
          </Field>
          <Field label="Max identical tool calls" htmlFor="max_identical">
            <input id="max_identical" type="number" min={1} max={20} value={policy.max_identical_tool_calls} onChange={(e) => setPolicy({ ...policy, max_identical_tool_calls: Number(e.target.value) })} className={inputClass} />
          </Field>
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={policy.require_identity_verification} onChange={(e) => setPolicy({ ...policy, require_identity_verification: e.target.checked })} />
          Require identity verification before account data or write actions
        </label>
      </Card>

      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : agent ? "Save changes" : "Create agent"}</Button>
        <Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button>
      </div>
    </form>
  );
}
