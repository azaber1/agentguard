"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Run, ScenarioSummary } from "@/lib/types";
import { Button, ErrorBanner, SeverityBadge } from "./ui";

interface ScenarioCatalog {
  categories: { id: string; label: string }[];
  scenarios: ScenarioSummary[];
}

export function RunLauncher({ agentId, disabled }: { agentId: string; disabled?: boolean }) {
  const router = useRouter();
  const catalog = useApi<ScenarioCatalog>("/scenarios");
  const [picking, setPicking] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const total = catalog.data?.scenarios.length ?? 0;

  async function start(ids: string[] | null) {
    setBusy(true);
    setError(null);
    try {
      const run = await api<Run>("/runs", { method: "POST", body: { agent_id: agentId, scenario_ids: ids } });
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the run.");
      setBusy(false);
    }
  }

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  return (
    <div>
      <ErrorBanner message={error} />
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => start(null)} disabled={busy || disabled}>
          {busy ? "Starting…" : `Run all ${total || ""} scenarios`}
        </Button>
        <Button variant="secondary" onClick={() => setPicking(!picking)} disabled={busy || disabled}>
          {picking ? "Hide scenario picker" : "Choose scenarios"}
        </Button>
      </div>
      {picking && catalog.data && (
        <div className="mt-4 space-y-4">
          {catalog.data.categories.map((c) => (
            <fieldset key={c.id}>
              <legend className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-3">{c.label}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {catalog.data!.scenarios
                  .filter((s) => s.category === c.id)
                  .map((s) => (
                    <label key={s.id} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
                      <span className="flex items-center gap-2">
                        <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                        <span className="text-ink">{s.name}</span>
                      </span>
                      <SeverityBadge severity={s.severity} />
                    </label>
                  ))}
              </div>
            </fieldset>
          ))}
          <Button onClick={() => start([...selected])} disabled={busy || selected.size === 0}>
            Run {selected.size} selected
          </Button>
        </div>
      )}
    </div>
  );
}
