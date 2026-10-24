"use client";

import Link from "next/link";
import { RunsTable } from "@/components/RunsTable";
import { ButtonLink, Card, CardTitle, Disclaimer, Empty, ErrorBanner, Loading, Meter, PageHeader, ScoreBadge, SeverityCounts, Stat } from "@/components/ui";
import { percent, riskLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { data, error, loading } = useApi<Dashboard>("/dashboard", (d) =>
    d?.recent_runs.some((r) => r.status === "queued" || r.status === "running") ? 2000 : null,
  );

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBanner message={error} />;

  const { totals, security_violations: v } = data;
  const critical = v.by_severity.critical ?? 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Reliability and security posture across your agents."
        actions={<ButtonLink href="/agents">Run tests</ButtonLink>}
      />
      <ErrorBanner message={error} />

      {totals.tests_executed === 0 ? (
        <Empty title="No tests have run yet">
          <p>Register an agent, then run the scenario library against it.</p>
          <div className="mt-4">
            <ButtonLink href="/agents/new">Register an agent</ButtonLink>
          </div>
        </Empty>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Tests executed" value={totals.tests_executed} hint={`${totals.runs} runs across ${totals.agents} agents`} />
            <Stat
              label="Pass rate"
              value={totals.pass_rate === null ? "—" : `${totals.pass_rate}%`}
              hint={`${totals.passed} passed · ${totals.failed} failed · ${totals.errored} errored`}
            />
            <Stat label="Reliability score" value={<ScoreBadge score={data.reliability_score} />} hint="Mean of each agent's latest run, 0–100" />
            <Stat label="Security violations" value={v.total} hint={`${critical} critical`} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardTitle>Pass rate by scenario category</CardTitle>
              <ul className="space-y-3">
                {data.category_results.map((c) => (
                  <li key={c.category}>
                    <div className="mb-1 flex justify-between gap-2 text-sm">
                      <span className="text-ink">{c.label}</span>
                      <span className="tabular text-ink-2">
                        {c.passed}/{c.total} passed · {percent(c.passed, c.total)}%
                      </span>
                    </div>
                    <Meter value={c.passed} max={c.total} label={`${c.label} pass rate`} />
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <CardTitle>Policy violations</CardTitle>
              <SeverityCounts counts={v.by_severity} />
              <h3 className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-ink-3">By risk category</h3>
              <ul className="space-y-1 text-sm">
                {Object.entries(v.by_category)
                  .sort((a, b) => b[1] - a[1])
                  .map(([cat, n]) => (
                    <li key={cat} className="flex justify-between">
                      <span className="text-ink">{riskLabel(cat)}</span>
                      <span className="tabular text-ink-2">{n}</span>
                    </li>
                  ))}
              </ul>
              <h3 className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-ink-3">Most frequent rules</h3>
              <ul className="space-y-1 text-sm">
                {v.top_rules.map((r) => (
                  <li key={r.rule_id} className="flex justify-between gap-2">
                    <span className="truncate text-ink">
                      <span className="font-mono text-xs text-ink-3">{r.rule_id}</span> {r.title}
                    </span>
                    <span className="tabular text-ink-2">{r.count}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card>
            <CardTitle action={<Link href="/agents" className="text-sm text-accent hover:underline">All agents</Link>}>
              Agent reliability
            </CardTitle>
            <div className="-mx-5 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-ink-3">
                  <tr>
                    <th className="px-5 pb-2 font-medium">Agent</th>
                    <th className="px-3 pb-2 font-medium">Latest score</th>
                    <th className="px-3 pb-2 font-medium">Passed</th>
                    <th className="px-5 pb-2 text-right font-medium">Critical findings</th>
                  </tr>
                </thead>
                <tbody>
                  {data.agents.map((a) => (
                    <tr key={a.id} className="border-t border-border">
                      <td className="px-5 py-2.5">
                        <Link href={`/agents/${a.id}`} className="font-medium text-ink hover:text-accent">
                          {a.name}
                        </Link>
                        <div className="text-xs text-ink-3">{a.provider === "http" ? "HTTP endpoint" : "Simulated"}</div>
                      </td>
                      <td className="px-3 py-2.5">
                        {a.latest_run ? <ScoreBadge score={a.latest_run.reliability_score} /> : <span className="text-ink-3">Not tested</span>}
                      </td>
                      <td className="tabular px-3 py-2.5 text-ink-2">{a.latest_run ? `${a.latest_run.passed}/${a.latest_run.total}` : "—"}</td>
                      <td className="tabular px-5 py-2.5 text-right text-ink-2">{a.latest_run?.critical_findings ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardTitle action={<Link href="/runs" className="text-sm text-accent hover:underline">All runs</Link>}>Recent test runs</CardTitle>
            <RunsTable runs={data.recent_runs} />
          </Card>
        </div>
      )}
      <div className="mt-6">
        <Disclaimer text={data.disclaimer} />
      </div>
    </>
  );
}
