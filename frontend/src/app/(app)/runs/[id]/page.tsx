"use client";

import Link from "next/link";
import { use, useState } from "react";
import { ResultCard } from "@/components/ResultCard";
import { Card, CardTitle, cx, Disclaimer, ErrorBanner, Loading, Meter, PageHeader, ScoreBadge, SeverityBadge, SeverityCounts, Stat, StatusBadge } from "@/components/ui";
import { formatDate, isActive } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { aggregateRecommendations, filterResults, severityCounts, type ResultFilter } from "@/lib/report";
import type { RunDetail } from "@/lib/types";

export default function RunReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: run, error } = useApi<RunDetail>(`/runs/${id}`, (d) => (d && isActive(d.status) ? 1500 : null));
  const [filter, setFilter] = useState<ResultFilter>("all");

  if (error && !run) return <ErrorBanner message={error} />;
  if (!run) return <Loading />;

  const active = isActive(run.status);
  const recommendations = aggregateRecommendations(run.results);
  const shown = filterResults(run.results, filter);
  const notPassed = run.results.filter((r) => r.status !== "passed").length;

  return (
    <>
      <PageHeader
        title={`Test report · ${run.agent_name}`}
        subtitle={
          <>
            <Link href={`/agents/${run.agent_id}`} className="text-accent hover:underline">View agent</Link> · Started {formatDate(run.created_at)}
            {run.completed_at && ` · Finished ${formatDate(run.completed_at)}`}
          </>
        }
        actions={
          <>
            <StatusBadge status={run.status} />
            {!active && (
              <a
                href={`/api/runs/${run.id}/report`}
                download={`agentguard-report-${run.id}.json`}
                className="inline-flex items-center rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-ink hover:bg-surface-2"
              >
                Export JSON
              </a>
            )}
          </>
        }
      />
      <ErrorBanner message={run.error} />

      {active && (
        <Card className="mb-4">
          <div className="mb-2 flex justify-between text-sm">
            <span className="text-ink">{run.status === "queued" ? "Queued…" : "Running scenarios in the sandbox…"}</span>
            <span className="tabular text-ink-2">
              {run.results.length}/{run.total}
            </span>
          </div>
          <Meter value={run.results.length} max={run.total} label="Scenarios completed" />
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Reliability score" value={<ScoreBadge score={run.reliability_score} />} hint="Severity-weighted, 0–100" />
        <Stat label="Passed" value={`${run.passed}/${run.total}`} hint={`${run.failed} failed · ${run.errored} errored`} />
        <Stat label="Critical findings" value={run.critical_findings} />
        <Stat label="Policy limits tested" value={`$${run.agent_snapshot.policy.max_refund_amount}`} hint={`refund cap · ${run.agent_snapshot.allowed_tools.length} allowed tools`} />
      </div>

      {recommendations.length > 0 && (
        <Card className="mt-4">
          <CardTitle>Recommendations</CardTitle>
          <div className="mb-4">
            <SeverityCounts counts={severityCounts(run.results)} />
          </div>
          <ol className="space-y-3">
            {recommendations.map((r) => (
              <li key={r.rule_id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={r.severity} />
                  <span className="font-medium text-ink">{r.title}</span>
                  <span className="font-mono text-xs text-ink-3">{r.rule_id}</span>
                  <span className="text-xs text-ink-3">· {r.owasp_ref}</span>
                </div>
                <p className="mt-1.5 text-sm text-ink">{r.recommendation}</p>
                <p className="mt-1 text-xs text-ink-3">
                  {r.occurrences} occurrence{r.occurrences === 1 ? "" : "s"} in: {r.scenarios.join(", ")}
                </p>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <div className="mb-3 mt-6 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Scenario results</h2>
        <div role="tablist" aria-label="Filter results" className="flex gap-1 rounded-lg border border-border bg-surface p-1">
          {(
            [
              ["all", `All (${run.results.length})`],
              ["failed", `Not passed (${notPassed})`],
              ["passed", `Passed (${run.results.length - notPassed})`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              role="tab"
              aria-selected={filter === value}
              onClick={() => setFilter(value)}
              className={cx("rounded-md px-3 py-1 text-xs font-medium", filter === value ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        {shown.map((r) => (
          <ResultCard key={r.id} runId={run.id} result={r} />
        ))}
        {shown.length === 0 && !active && <p className="text-sm text-ink-2">No results match this filter.</p>}
      </div>

      <div className="mt-6">
        <Disclaimer text={run.disclaimer} />
      </div>
    </>
  );
}
