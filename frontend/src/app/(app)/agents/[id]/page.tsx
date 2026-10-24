"use client";

import { useRouter } from "next/navigation";
import { use } from "react";
import { RunLauncher } from "@/components/RunLauncher";
import { RunsTable } from "@/components/RunsTable";
import { Button, ButtonLink, Card, CardTitle, ErrorBanner, Loading, PageHeader, Pill } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, humanize, isActive } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Agent, Run } from "@/lib/types";

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const agent = useApi<Agent>(`/agents/${id}`);
  const runs = useApi<Run[]>(`/runs?agent_id=${id}&limit=20`, (d) => (d?.some((r) => isActive(r.status)) ? 2000 : null));

  async function archive() {
    if (!window.confirm("Archive this agent? Its run history will be hidden.")) return;
    await api(`/agents/${id}`, { method: "DELETE" });
    router.push("/agents");
  }

  if (agent.error) return <ErrorBanner message={agent.error} />;
  if (!agent.data) return <Loading />;
  const a = agent.data;
  const running = runs.data?.some((r) => isActive(r.status));
  const notAllowed = a.tools.filter((t) => !a.allowed_tools.includes(t));

  return (
    <>
      <PageHeader
        title={a.name}
        subtitle={a.description || undefined}
        actions={
          <>
            <ButtonLink href={`/agents/${id}/edit`} variant="secondary">Edit</ButtonLink>
            <Button variant="danger" onClick={archive}>Archive</Button>
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardTitle>Run tests</CardTitle>
          <p className="mb-4 text-sm text-ink-2">
            Scenarios run in an isolated sandbox with simulated tools. No real refunds, emails or account changes happen.
          </p>
          {running ? <p className="mb-3 text-sm text-ink-2">A run is in progress for this agent.</p> : null}
          <RunLauncher agentId={id} disabled={running} />
        </Card>
        <Card>
          <CardTitle>Configuration</CardTitle>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs text-ink-3">Connection</dt>
              <dd className="break-all text-ink">
                {a.provider === "http" ? a.provider_config.endpoint_url : `Reference agent · ${humanize(a.provider_config.profile ?? "")}`}
              </dd>
              {a.provider === "http" && (
                <dd className="mt-1 text-xs text-ink-2">{a.has_auth_token ? "Bearer token stored (encrypted)" : "No auth token"}</dd>
              )}
            </div>
            <div>
              <dt className="text-xs text-ink-3">Refund limit</dt>
              <dd className="tabular text-ink">${a.policy.max_refund_amount.toFixed(2)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">Identity verification</dt>
              <dd className="text-ink">{a.policy.require_identity_verification ? "Required" : "Not required"}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">Tool budget</dt>
              <dd className="tabular text-ink">
                {a.policy.max_tool_calls_per_session} calls · {a.policy.max_identical_tool_calls} identical max
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs text-ink-3">Allowed tools ({a.allowed_tools.length})</dt>
              <dd className="flex flex-wrap gap-1">
                {a.allowed_tools.map((t) => (
                  <span key={t} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-ink">{t}</span>
                ))}
              </dd>
            </div>
            {notAllowed.length > 0 && (
              <div>
                <dt className="mb-1 text-xs text-ink-3">Wired in but not allowed</dt>
                <dd className="flex flex-wrap gap-1">
                  {notAllowed.map((t) => (
                    <Pill key={t} tone="serious">{t}</Pill>
                  ))}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-ink-3">Updated</dt>
              <dd className="text-ink">{formatDate(a.updated_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>
      <Card className="mt-4">
        <CardTitle>Run history</CardTitle>
        <ErrorBanner message={runs.error} />
        {runs.data ? <RunsTable runs={runs.data} showAgent={false} /> : <Loading />}
      </Card>
    </>
  );
}
