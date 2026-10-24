"use client";

import Link from "next/link";
import { ButtonLink, Card, Empty, ErrorBanner, Loading, PageHeader, ScoreBadge, StatusBadge } from "@/components/ui";
import { humanize, relativeTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Agent } from "@/lib/types";

export default function AgentsPage() {
  const { data, error, loading } = useApi<Agent[]>("/agents");
  return (
    <>
      <PageHeader title="Agent registry" subtitle="The agents you test, with their tools, permissions and policies." actions={<ButtonLink href="/agents/new">Register agent</ButtonLink>} />
      <ErrorBanner message={error} />
      {loading && !data ? (
        <Loading />
      ) : data?.length === 0 ? (
        <Empty title="No agents yet">Register your first agent to start testing.</Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data?.map((a) => (
            <Link key={a.id} href={`/agents/${a.id}`} className="block">
              <Card className="h-full transition hover:border-accent">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold text-ink">{a.name}</h2>
                    <p className="mt-0.5 line-clamp-2 text-sm text-ink-2">{a.description || "No description"}</p>
                  </div>
                  {a.latest_run && <StatusBadge status={a.latest_run.status} />}
                </div>
                <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-ink-3">Connection</dt>
                    <dd className="truncate text-ink">{a.provider === "http" ? "HTTP endpoint" : humanize(a.provider_config.profile ?? "")}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-3">Allowed tools</dt>
                    <dd className="tabular text-ink">
                      {a.allowed_tools.length}/{a.tools.length}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-ink-3">Last tested</dt>
                    <dd className="text-ink">{a.latest_run ? relativeTime(a.latest_run.created_at) : "Never"}</dd>
                  </div>
                </dl>
                <div className="mt-4 border-t border-border pt-3">
                  <ScoreBadge score={a.latest_run?.reliability_score} />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
