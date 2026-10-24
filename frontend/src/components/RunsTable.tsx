import Link from "next/link";
import { relativeTime } from "@/lib/format";
import type { Run } from "@/lib/types";
import { ScoreBadge, StatusBadge } from "./ui";

export function RunsTable({ runs, showAgent = true }: { runs: Pick<Run, "id" | "agent_id" | "agent_name" | "status" | "passed" | "failed" | "errored" | "total" | "reliability_score" | "created_at">[]; showAgent?: boolean }) {
  if (runs.length === 0) return <p className="text-sm text-ink-2">No runs yet.</p>;
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full min-w-[620px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-ink-3">
          <tr>
            <th className="px-5 pb-2 font-medium">Run</th>
            {showAgent && <th className="px-3 pb-2 font-medium">Agent</th>}
            <th className="px-3 pb-2 font-medium">Status</th>
            <th className="px-3 pb-2 font-medium">Result</th>
            <th className="px-5 pb-2 font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-t border-border">
              <td className="px-5 py-2.5">
                <Link href={`/runs/${r.id}`} className="font-medium text-ink hover:text-accent">
                  {relativeTime(r.created_at)}
                </Link>
                <div className="font-mono text-xs text-ink-3">{r.id.slice(0, 8)}</div>
              </td>
              {showAgent && (
                <td className="px-3 py-2.5">
                  <Link href={`/agents/${r.agent_id}`} className="text-ink hover:text-accent">
                    {r.agent_name}
                  </Link>
                </td>
              )}
              <td className="px-3 py-2.5">
                <StatusBadge status={r.status} />
              </td>
              <td className="tabular px-3 py-2.5 text-ink-2">
                {r.passed}/{r.total} passed{r.failed ? ` · ${r.failed} failed` : ""}
                {r.errored ? ` · ${r.errored} errored` : ""}
              </td>
              <td className="px-5 py-2.5">
                <ScoreBadge score={r.reliability_score} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
