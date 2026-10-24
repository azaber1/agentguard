import { describe, expect, it } from "vitest";
import { safeNext } from "@/components/AuthForm";
import { toToolLists } from "@/components/AgentForm";
import { formatScore, humanize, percent, relativeTime, riskLabel, scoreBand } from "@/lib/format";
import { aggregateRecommendations, filterResults, severityCounts } from "@/lib/report";
import type { Finding, ResultSummary, Severity } from "@/lib/types";

function finding(rule_id: string, severity: Severity): Finding {
  return { id: rule_id + severity, rule_id, title: rule_id, severity, category: "excessive_agency", owasp_ref: "LLM06:2025", source: "policy", explanation: "", recommendation: `fix ${rule_id}`, evidence: {} };
}

function result(name: string, status: ResultSummary["status"], findings: Finding[] = []): ResultSummary {
  return { id: name, scenario_id: name, scenario_name: name, category: "normal_interaction", severity: "low", status, score: 0, metrics: {}, error: null, expectations: [], findings };
}

describe("format", () => {
  it("bands scores strictly", () => {
    expect(scoreBand(100)).toBe("good");
    expect(scoreBand(90)).toBe("good");
    expect(scoreBand(89.9)).toBe("warning");
    expect(scoreBand(59)).toBe("critical");
    expect(scoreBand(null)).toBe("none");
    expect(formatScore(null)).toBe("—");
    expect(formatScore(87.6)).toBe("88");
  });

  it("formats helpers", () => {
    expect(percent(1, 3)).toBe(33);
    expect(percent(1, 0)).toBe(0);
    expect(humanize("mostly_safe")).toBe("Mostly safe");
    expect(riskLabel("sensitive_data_exposure")).toBe("Sensitive data exposure");
    const now = new Date("2026-01-01T12:00:00Z");
    expect(relativeTime("2026-01-01T11:59:30Z", now)).toBe("just now");
    expect(relativeTime("2026-01-01T11:00:00Z", now)).toBe("1h ago");
    expect(relativeTime("2025-12-30T12:00:00Z", now)).toBe("2d ago");
  });
});

describe("report", () => {
  const results = [
    result("a", "failed", [finding("AG-008", "medium"), finding("AG-002", "critical")]),
    result("b", "failed", [finding("AG-008", "medium")]),
    result("c", "passed"),
    result("d", "error"),
  ];

  it("aggregates recommendations by rule, most severe first", () => {
    const recs = aggregateRecommendations(results);
    expect(recs.map((r) => r.rule_id)).toEqual(["AG-002", "AG-008"]);
    expect(recs[1]).toMatchObject({ occurrences: 2, scenarios: ["a", "b"] });
  });

  it("counts severities and filters results", () => {
    expect(severityCounts(results)).toEqual({ medium: 2, critical: 1 });
    expect(filterResults(results, "passed").map((r) => r.id)).toEqual(["c"]);
    expect(filterResults(results, "failed").map((r) => r.id)).toEqual(["a", "b", "d"]);
    expect(filterResults(results, "all")).toHaveLength(4);
  });
});

describe("safeNext", () => {
  it("only allows relative same-site paths", () => {
    expect(safeNext("/agents/1")).toBe("/agents/1");
    expect(safeNext(null)).toBe("/dashboard");
    expect(safeNext("https://evil.example")).toBe("/dashboard");
    expect(safeNext("//evil.example")).toBe("/dashboard");
    expect(safeNext("/\\evil.example")).toBe("/dashboard");
  });
});

describe("toToolLists", () => {
  it("keeps catalogue order and only allows wired tools", () => {
    const perms = {
      lookup_order: { wired: true, allowed: true },
      issue_refund: { wired: true, allowed: false },
      delete_account: { wired: false, allowed: true },
    };
    expect(toToolLists(perms, ["issue_refund", "lookup_order", "delete_account"])).toEqual({
      tools: ["issue_refund", "lookup_order"],
      allowed_tools: ["lookup_order"],
    });
  });
});
