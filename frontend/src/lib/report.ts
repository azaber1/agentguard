import { SEVERITIES } from "./format";
import type { ResultSummary, Severity } from "./types";

export interface Recommendation {
  rule_id: string;
  title: string;
  severity: Severity;
  owasp_ref: string;
  recommendation: string;
  occurrences: number;
  scenarios: string[];
}

/** One entry per rule, most severe first, then most frequent. */
export function aggregateRecommendations(results: ResultSummary[]): Recommendation[] {
  const byRule = new Map<string, Recommendation>();
  for (const r of results) {
    for (const f of r.findings) {
      const entry =
        byRule.get(f.rule_id) ??
        ({
          rule_id: f.rule_id,
          title: f.title,
          severity: f.severity,
          owasp_ref: f.owasp_ref,
          recommendation: f.recommendation,
          occurrences: 0,
          scenarios: [],
        } satisfies Recommendation);
      entry.occurrences += 1;
      if (SEVERITIES.indexOf(f.severity) < SEVERITIES.indexOf(entry.severity)) entry.severity = f.severity;
      if (!entry.scenarios.includes(r.scenario_name)) entry.scenarios.push(r.scenario_name);
      byRule.set(f.rule_id, entry);
    }
  }
  return [...byRule.values()].sort(
    (a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity) || b.occurrences - a.occurrences,
  );
}

export function severityCounts(results: ResultSummary[]): Partial<Record<Severity, number>> {
  const counts: Partial<Record<Severity, number>> = {};
  for (const r of results) for (const f of r.findings) counts[f.severity] = (counts[f.severity] ?? 0) + 1;
  return counts;
}

export type ResultFilter = "all" | "failed" | "passed";

export function filterResults(results: ResultSummary[], filter: ResultFilter): ResultSummary[] {
  if (filter === "all") return results;
  if (filter === "passed") return results.filter((r) => r.status === "passed");
  return results.filter((r) => r.status !== "passed");
}
