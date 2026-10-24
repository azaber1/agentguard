"use client";

import { useState } from "react";
import { riskLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Finding, ResultDetail, ResultSummary } from "@/lib/types";
import { TraceViewer } from "./TraceViewer";
import { Button, Card, ErrorBanner, Loading, Pill, SeverityBadge, StatusBadge } from "./ui";

function FindingItem({ f }: { f: Finding }) {
  const { step, excerpt } = f.evidence as { step?: number; excerpt?: string };
  return (
    <li className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={f.severity} />
        <span className="font-medium text-ink">{f.title}</span>
        <span className="font-mono text-xs text-ink-3">{f.rule_id}</span>
      </div>
      <div className="mt-1 text-xs text-ink-3">
        {riskLabel(f.category)} · {f.owasp_ref}
        {step !== undefined && ` · step ${step}`}
      </div>
      <p className="mt-2 text-sm text-ink">{f.explanation}</p>
      {excerpt && <p className="mt-1 rounded bg-surface-2 p-2 font-mono text-xs text-ink-2">{excerpt}</p>}
      <p className="mt-2 text-sm text-ink-2">
        <span className="font-medium text-ink">Recommendation: </span>
        {f.recommendation}
      </p>
    </li>
  );
}

function Trace({ runId, resultId, flagged }: { runId: string; resultId: string; flagged: number[] }) {
  const { data, error } = useApi<ResultDetail>(`/runs/${runId}/results/${resultId}`);
  if (error) return <ErrorBanner message={error} />;
  if (!data) return <Loading label="Loading trace…" />;
  const effects = Object.entries(data.sandbox_effects).filter(([, v]) => v.length > 0);
  return (
    <>
      {effects.length > 0 && (
        <div className="mb-3 rounded-lg border border-border bg-surface-2 p-3 text-xs text-ink-2">
          <span className="font-medium text-ink">Simulated side effects (nothing real happened): </span>
          {effects.map(([k, v]) => `${v.length} ${k.replace("_", " ")}`).join(", ")}
        </div>
      )}
      <TraceViewer trace={data.trace} flaggedSteps={flagged} />
    </>
  );
}

export function ResultCard({ runId, result }: { runId: string; result: ResultSummary }) {
  const [open, setOpen] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const flagged = result.findings.map((f) => (f.evidence as { step?: number }).step).filter((s): s is number => typeof s === "number");

  return (
    <Card className="p-4">
      <button className="flex w-full flex-wrap items-center justify-between gap-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <div className="min-w-0">
          <div className="font-medium text-ink">{result.scenario_name}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-3">
            <span className="font-mono">{result.scenario_id}</span>
            <span>· {result.metrics.tool_calls ?? 0} tool calls</span>
            {result.findings.length > 0 && <span>· {result.findings.length} findings</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity={result.severity} />
          <StatusBadge status={result.status} />
          <span className="tabular w-10 text-right text-sm font-semibold text-ink">{result.score}</span>
        </div>
      </button>
      {open && (
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          {result.error && (
            <div className="flex items-start gap-2 text-sm text-ink">
              <Pill tone="warning">Agent error</Pill>
              <span>{result.error} This scenario counts as not passed.</span>
            </div>
          )}
          {result.findings.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-3">Findings</h4>
              <ul className="space-y-2">
                {result.findings.map((f) => (
                  <FindingItem key={f.id} f={f} />
                ))}
              </ul>
            </div>
          )}
          {result.expectations.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-3">Expected vs actual</h4>
              <div className="-mx-4 overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead className="text-left text-xs text-ink-3">
                    <tr>
                      <th className="px-4 pb-1 font-medium">Check</th>
                      <th className="px-2 pb-1 font-medium">Expected</th>
                      <th className="px-2 pb-1 font-medium">Actual</th>
                      <th className="px-4 pb-1 font-medium" />
                    </tr>
                  </thead>
                  <tbody>
                    {result.expectations.map((c, i) => (
                      <tr key={i} className="border-t border-border align-top">
                        <td className="px-4 py-2 text-ink">{c.description}</td>
                        <td className="break-all px-2 py-2 font-mono text-xs text-ink-2">{c.expected}</td>
                        <td className="px-2 py-2 text-ink-2">{c.actual}</td>
                        <td className="px-4 py-2">
                          <Pill tone={c.passed ? "good" : "critical"}>{c.passed ? "Met" : "Not met"}</Pill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {result.status === "passed" && result.findings.length === 0 && (
            <p className="text-sm text-ink-2">No policy violations and all expectations met on this run.</p>
          )}
          <div>
            <Button variant="secondary" onClick={() => setShowTrace(!showTrace)}>
              {showTrace ? "Hide trace" : "Show full trace"}
            </Button>
            {showTrace && (
              <div className="mt-3">
                <Trace runId={runId} resultId={result.id} flagged={flagged} />
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
