"use client";

import { useState } from "react";
import { Card, ErrorBanner, Loading, PageHeader, Pill, SeverityBadge } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import type { ScenarioDetail, ScenarioSummary } from "@/lib/types";

interface Catalog {
  categories: { id: string; label: string }[];
  scenarios: ScenarioSummary[];
}

function ScenarioBody({ id }: { id: string }) {
  const { data, error } = useApi<ScenarioDetail>(`/scenarios/${id}`);
  if (error) return <ErrorBanner message={error} />;
  if (!data) return <Loading />;
  const e = data.expectations;
  const list = (label: string, items: string[]) =>
    items.length > 0 && (
      <div>
        <dt className="text-xs text-ink-3">{label}</dt>
        <dd className="mt-1 flex flex-wrap gap-1">
          {items.map((t) => (
            <span key={t} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-ink">{t}</span>
          ))}
        </dd>
      </div>
    );
  return (
    <div className="mt-4 grid gap-4 border-t border-border pt-4 md:grid-cols-2">
      <div>
        <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-3">Scripted customer</h4>
        <p className="mb-2 text-xs text-ink-2">{data.persona.description}</p>
        <ol className="space-y-2">
          {data.user_turns.map((t, i) => (
            <li key={i} className="rounded-lg bg-surface-2 p-2.5 text-sm text-ink">{t}</li>
          ))}
        </ol>
      </div>
      <dl className="space-y-3 text-sm">
        {list("Must call", e.required_tools)}
        {list("Must not call", e.forbidden_tools)}
        {e.max_tool_calls !== null && (
          <div>
            <dt className="text-xs text-ink-3">Tool-call allowance</dt>
            <dd className="text-ink">At most {e.max_tool_calls}</dd>
          </div>
        )}
        {list("Reply must match", e.response_must_match)}
        {list("Reply must not match", e.response_must_not_match)}
        {data.faults.length > 0 && (
          <div>
            <dt className="text-xs text-ink-3">Injected faults</dt>
            <dd className="text-ink">
              {data.faults.map((f) => `${f.tool}: ${f.mode}${f.times ? ` ×${f.times}` : " (every call)"}`).join(", ")}
            </dd>
          </div>
        )}
        {data.has_injection && <Pill tone="serious">Contains planted prompt injection</Pill>}
        <p className="text-xs text-ink-3">All global policy rules (AG-001 – AG-012) also apply.</p>
      </dl>
    </div>
  );
}

export default function ScenariosPage() {
  const { data, error, loading } = useApi<Catalog>("/scenarios");
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <PageHeader
        title="Scenario library"
        subtitle={data ? `${data.scenarios.length} predefined customer-support scenarios across ${data.categories.length} categories.` : undefined}
      />
      <ErrorBanner message={error} />
      {loading && !data && <Loading />}
      <div className="space-y-8">
        {data?.categories.map((c) => (
          <section key={c.id}>
            <h2 className="mb-3 text-sm font-semibold text-ink">{c.label}</h2>
            <div className="space-y-3">
              {data.scenarios
                .filter((s) => s.category === c.id)
                .map((s) => (
                  <Card key={s.id} className="p-4">
                    <button className="flex w-full items-start justify-between gap-3 text-left" onClick={() => setOpen(open === s.id ? null : s.id)} aria-expanded={open === s.id}>
                      <div className="min-w-0">
                        <div className="font-medium text-ink">{s.name}</div>
                        <p className="mt-0.5 text-sm text-ink-2">{s.description}</p>
                        <div className="mt-1 font-mono text-xs text-ink-3">{s.id}</div>
                      </div>
                      <SeverityBadge severity={s.severity} />
                    </button>
                    {open === s.id && <ScenarioBody id={s.id} />}
                  </Card>
                ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
